"""
Page 7 — Agent 5A : Legal Sheet Updater
Analyze a legal sheet against regulatory alerts and propose section-level updates.
Sources: archived library (GitHub) · PDF upload · paste text
"""

import streamlit as st
import json
from datetime import datetime
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.legal_sheet_library import load_index, fetch_sheet_text, list_available_sheets, upload_sheet
    LIBRARY_AVAILABLE = True
except Exception as _lib_err:
    LIBRARY_AVAILABLE = False
    _LIBRARY_ERROR = str(_lib_err)
else:
    _LIBRARY_ERROR = ""

from agent5a.updater import (
    analyze_legal_sheet, ALL_SECTIONS, STATUS_LABELS, SECTION_IDS,
    SECTION_PROFILES, get_sections_for_profile,
)
from agent4.impact import CAT_DEFINITIONS

st.set_page_config(page_title="Legal Sheet Update · RegWatch", page_icon="📋", layout="wide")

CAT_LABELS    = {k: v["label"] for k, v in CAT_DEFINITIONS.items()}
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")
gh_token_5a   = st.secrets.get("GH_TOKEN", "")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Status")
    st.success("Anthropic ✓") if anthropic_key else st.error("ANTHROPIC_API_KEY missing")
    if LIBRARY_AVAILABLE:
        st.success("Library ✓") if gh_token_5a else st.warning("GH_TOKEN missing — library disabled")
    else:
        st.warning(f"Library module error: {_LIBRARY_ERROR}")
    st.divider()
    veille = st.session_state.get("veille_results", [])
    st.header("📡 Available alerts")
    if veille:
        st.success(f"{len(veille)} alert(s) in memory")
    else:
        st.warning("No alerts.\nRun Agent 1 first.")
    st.divider()
    st.caption("Workflow: select sheet → analyze → approve / edit / reject → export")
    st.divider()
    st.header("📊 Session tokens")
    if "session_tokens" not in st.session_state:
        st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
    t = st.session_state["session_tokens"]
    ca, cb = st.columns(2)
    ca.metric("Input",  f"{t['input']:,}")
    cb.metric("Output", f"{t['output']:,}")
    st.metric("Estimated cost", ("N/A" if t['cost_usd'] == 0 else f"${t['cost_usd']:.4f}"))
    st.caption(f"{t['calls']} Claude call(s)")
    if st.button("🔄 Reset", key="reset_tokens_sidebar"):
        st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
        st.rerun()

# ── Page ──────────────────────────────────────────────────────────────────────
st.title("📋 Legal Sheet Update")
st.caption("Legal sheet audit and update · My Conformity Box")

# ── ① Parameters ──────────────────────────────────────────────────────────────
st.subheader("① Parameters")

col1, col2, col3 = st.columns(3)
with col1:
    category = st.selectbox(
        "Category",
        options=list(CAT_DEFINITIONS.keys()),
        format_func=lambda c: f"{c} — {CAT_LABELS[c]}",
        key="5a_category",
    )
with col2:
    market = st.selectbox(
        "Market",
        ["EU", "France", "Spain", "Italy", "Germany", "UK", "USA"],
        key="5a_market",
    )
with col3:
    urgency_filter = st.multiselect(
        "Alerts to include",
        ["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM"],
        key="5a_urgency",
    )

veille = st.session_state.get("veille_results", [])
filtered_alerts = [
    e for e in veille
    if e.get("urgency") in urgency_filter
    and (category in e.get("categories_concerned", []) or not e.get("categories_concerned"))
]
st.caption(f"→ **{len(filtered_alerts)} alert(s)** applicable for {category} / {market}")

st.divider()

# ── ② Sheet source ────────────────────────────────────────────────────────────
st.subheader("② Legal sheet source")

_library_option = "📚 From library"
_upload_option  = "📄 Upload PDF"
_paste_option   = "📝 Paste text"

# Only show library option when it is actually usable
_source_options = []
if LIBRARY_AVAILABLE and gh_token_5a:
    _source_options.append(_library_option)
_source_options += [_upload_option, _paste_option]

input_mode = st.radio(
    "Sheet source",
    _source_options,
    horizontal=True,
    key="5a_input_mode",
)

fiche_text  = ""
fiche_title = ""

# ── Branch A : From library ───────────────────────────────────────────────────
if input_mode == _library_option:

    # Load index once and cache in session_state (avoids repeated GitHub API calls on reruns)
    if "5a_library_index" not in st.session_state:
        with st.spinner("Loading library index…"):
            st.session_state["5a_library_index"] = load_index(gh_token_5a)

    _index  = st.session_state["5a_library_index"]
    _sheets = list_available_sheets(_index)

    if not _sheets:
        st.warning(
            "No sheets found in the library. "
            "Upload PDFs first via **Configuration → Legal Sheet Library**."
        )
    else:
        _available_cats    = sorted({s["category"] for s in _sheets})
        _available_markets = sorted({s["market"]   for s in _sheets})

        col_lc, col_lm = st.columns(2)
        with col_lc:
            _default_cat_idx = _available_cats.index(category) if category in _available_cats else 0
            lib_category = st.selectbox(
                "Category",
                _available_cats,
                index=_default_cat_idx,
                format_func=lambda c: f"{c} — {CAT_LABELS.get(c, c)}",
                key="5a_lib_category",
            )
        with col_lm:
            # Only show markets that have a sheet for the chosen category
            _markets_for_cat = sorted({s["market"] for s in _sheets if s["category"] == lib_category})
            lib_market = st.selectbox(
                "Market",
                _markets_for_cat if _markets_for_cat else _available_markets,
                key="5a_lib_market",
            )

        _entry = next(
            (s for s in _sheets if s["category"] == lib_category and s["market"] == lib_market),
            None,
        )

        if _entry:
            st.success(
                f"📚 **{lib_category} — {lib_market}** · "
                f"uploaded {_entry.get('uploaded', '?')} · "
                f"{_entry.get('size_kb', '?')} KB"
            )

            _cache_key = f"5a_lib_text_{lib_category}_{lib_market}"

            if _cache_key not in st.session_state:
                if st.button("📥 Load sheet from library", key="5a_load_lib_btn"):
                    with st.spinner(f"Downloading {lib_category} — {lib_market} from GitHub…"):
                        _text, _title = fetch_sheet_text(lib_category, lib_market, gh_token_5a)
                    if _text:
                        st.session_state[_cache_key] = {"text": _text, "title": _title}
                        st.rerun()
                    else:
                        st.error(f"Could not load sheet: {_title}")
            else:
                _cached     = st.session_state[_cache_key]
                fiche_text  = _cached["text"]
                fiche_title = _cached["title"]

                col_loaded, col_reload = st.columns([4, 1])
                col_loaded.success(f"✓ Sheet loaded — {len(fiche_text):,} characters")
                if col_reload.button("🔄 Reload", key="5a_lib_reload"):
                    del st.session_state[_cache_key]
                    st.rerun()

                with st.expander("Preview extracted text"):
                    st.text(fiche_text[:2000] + ("…" if len(fiche_text) > 2000 else ""))

            # Sync Parameters section to the library selection
            if lib_category != category or lib_market != market:
                st.info(
                    f"ℹ️ Analysis will use **{lib_category} / {lib_market}** "
                    f"to match the loaded sheet."
                )
            category = lib_category
            market   = lib_market

        else:
            st.warning(
                f"No sheet found for **{lib_category} — {lib_market}** in the library.  \n"
                f"Upload it first via **Configuration → Legal Sheet Library**, "
                f"or switch to **Upload PDF** / **Paste text** mode."
            )

# ── Branch B : Upload PDF ─────────────────────────────────────────────────────
elif input_mode == _upload_option:
    uploaded_pdf = st.file_uploader(
        "Upload legal sheet (PDF)",
        type=["pdf"],
        key="5a_pdf_upload",
    )
    if uploaded_pdf:
        try:
            import io
            import PyPDF2
            reader      = PyPDF2.PdfReader(io.BytesIO(uploaded_pdf.read()))
            fiche_text  = "\n".join(page.extract_text() or "" for page in reader.pages)
            fiche_title = uploaded_pdf.name.replace(".pdf", "").replace("_", " ")
            st.success(
                f"✓ PDF read — {len(reader.pages)} page(s) · {len(fiche_text):,} characters"
            )
            with st.expander("Preview extracted text"):
                st.text(fiche_text[:2000] + ("…" if len(fiche_text) > 2000 else ""))
        except Exception as e:
            st.error(f"Error reading PDF: {e}")
            st.info("Try the 'Paste text' mode as an alternative.")

# ── Branch C : Paste text ─────────────────────────────────────────────────────
else:
    fiche_title = st.text_input(
        "Sheet title",
        placeholder="e.g. Electronic equipment using Bluetooth — EUROPE",
        key="5a_title",
    )
    fiche_text = st.text_area(
        "Sheet content (copy-paste from PDF)",
        height=300,
        placeholder="Paste your legal sheet content here…",
        key="5a_text",
    )
    if fiche_text:
        st.caption(f"{len(fiche_text):,} characters")

st.divider()

# ── ③ Analysis profile ────────────────────────────────────────────────────────
st.subheader("③ Analysis profile")

profile_names = list(SECTION_PROFILES.keys())
profile = st.radio(
    "Analysis scope",
    profile_names,
    horizontal=True,
    key="5a_profile",
)

profile_info = SECTION_PROFILES[profile]
st.caption(f"*{profile_info['desc']}*")

custom_ids = None
if profile == "✏️ Personnalisé":
    all_opts   = {s["id"]: f"{s['label']} ({s['relevance']})" for s in ALL_SECTIONS}
    custom_ids = st.multiselect(
        "Sections to analyze",
        options=list(all_opts.keys()),
        default=[s["id"] for s in ALL_SECTIONS if s["relevance"] == "high"],
        format_func=lambda x: all_opts[x],
        key="5a_custom_sections",
    )
    sections_preview = [s for s in ALL_SECTIONS if s["id"] in (custom_ids or [])]
else:
    sections_preview = get_sections_for_profile(profile)

n_passes = max(1, -(-len(sections_preview) // 8))
cost_est = n_passes * 0.025
st.info(
    f"**{len(sections_preview)} section(s)** · "
    f"**{n_passes} Claude call(s)** · "
    f"Estimated cost: **~${cost_est:.2f}**"
)

st.divider()

# ── ④ Analysis ────────────────────────────────────────────────────────────────
st.subheader("④ Analysis")

if not fiche_text.strip():
    st.info("Load or paste the legal sheet content to continue.")

col_launch, col_info_launch = st.columns([2, 3])
with col_info_launch:
    if not filtered_alerts:
        st.warning(f"No alerts for {category} in memory — quality audit only.")
    else:
        st.info(f"{len(filtered_alerts)} alert(s) will be crossed with the sheet.")

with col_launch:
    launch = st.button(
        "🔍 Analyze sheet",
        disabled=not (anthropic_key and fiche_text.strip()),
        type="primary",
        use_container_width=True,
    )

if launch:
    with st.status("🔍 Analysis in progress…", expanded=True) as status:
        try:
            chars = len(fiche_text)
            source_label = {
                _library_option: f"library ({category} — {market})",
                _upload_option:  "uploaded PDF",
                _paste_option:   "pasted text",
            }.get(input_mode, "unknown source")
            st.write(f"📄 Source: {source_label} · {chars:,} characters")
            if chars > 12000:
                st.write("⚠️ Text truncated to 12,000 characters for analysis")
            st.write(f"🔀 Crossing with {len(filtered_alerts)} alert(s) · {category} / {market}…")

            result, token_usage = analyze_legal_sheet(
                anthropic_key=anthropic_key,
                fiche_text=fiche_text,
                alerts=filtered_alerts,
                category=category,
                fiche_title=fiche_title,
                market=market,
                profile=profile,
                custom_section_ids=custom_ids,
            )
            st.session_state["5a_result"]    = result
            st.session_state["5a_decisions"] = {}

            sections = result.get("sections", [])
            n_update = sum(1 for s in sections if s.get("status") in ["MISSING", "ENRICH", "OBSOLETE"])
            n_ok     = sum(1 for s in sections if s.get("status") in ["OK", "NA_OK"])
            result["sections_to_update"] = n_update
            result["sections_ok"]        = n_ok

            _cost_5a = "N/A" if token_usage["cost_usd"] == 0 else f"${token_usage['cost_usd']:.4f}"
            status.update(
                label=(
                    f"✅ Analysis complete · {n_update} section(s) to update · "
                    f"{n_ok} up to date · "
                    f"{token_usage['input_tokens'] + token_usage['output_tokens']:,} tokens · "
                    f"{_cost_5a}"
                ),
                state="complete",
            )
            st.session_state["session_tokens"]["input"]    += token_usage.get("input_tokens", 0)
            st.session_state["session_tokens"]["output"]   += token_usage.get("output_tokens", 0)
            st.session_state["session_tokens"]["cost_usd"] += token_usage.get("cost_usd", 0.0)
            st.session_state["session_tokens"]["calls"]    += 1

        except ValueError as e:
            status.update(label=f"❌ Analysis error: {e}", state="error")
            st.error(str(e))
            st.info("💡 Tip: try with shorter text or re-run the analysis.")
            st.stop()
        except Exception as e:
            status.update(label=f"❌ Error: {e}", state="error")
            st.error(str(e))
            st.stop()

# ── ⑤ Review and validation ───────────────────────────────────────────────────
if "5a_result" in st.session_state:
    result    = st.session_state["5a_result"]
    sections  = result.get("sections", [])
    decisions = st.session_state.setdefault("5a_decisions", {})

    st.divider()
    st.subheader("⑤ Review and validation")

    overall = result.get("overall_status", "")
    overall_icons  = {"MAJOR_UPDATE": "🔴", "MINOR_UPDATE": "🟡", "UP_TO_DATE": "✅"}
    overall_labels = {
        "MAJOR_UPDATE": "Major update required",
        "MINOR_UPDATE": "Minor enrichment recommended",
        "UP_TO_DATE":   "Sheet up to date",
    }

    sections_by_status = {}
    for s in sections:
        sections_by_status.setdefault(s.get("status", ""), []).append(s)

    n_ok     = len(sections_by_status.get("OK", [])) + len(sections_by_status.get("NA_OK", []))
    n_action = (
        len(sections_by_status.get("MISSING",  [])) +
        len(sections_by_status.get("ENRICH",   [])) +
        len(sections_by_status.get("OBSOLETE", []))
    )
    n_valid = sum(1 for d in decisions.values() if d["action"] in ["approved", "edited"])

    band_color    = {"MAJOR_UPDATE": "#c0392b", "MINOR_UPDATE": "#e67e22", "UP_TO_DATE": "#27ae60"}.get(overall, "#7f8c8d")
    overall_icon  = overall_icons.get(overall, "?")
    overall_label = overall_labels.get(overall, overall)
    st.markdown(
        f"<div style='background:{band_color}22;border-left:4px solid {band_color};"
        f"padding:10px 16px;border-radius:4px;margin-bottom:8px'>"
        f"<b>{overall_icon} {overall_label}</b>"
        f"&nbsp;&nbsp;·&nbsp;&nbsp;✅ {n_ok} up to date"
        f"&nbsp;&nbsp;·&nbsp;&nbsp;⚠️ {n_action} to update"
        f"&nbsp;&nbsp;·&nbsp;&nbsp;✔️ {n_valid} validated"
        f"</div>",
        unsafe_allow_html=True,
    )

    if result.get("summary"):
        st.info(result["summary"])

    natl = result.get("national_specificities_missing", [])
    if natl:
        with st.expander(f"🌍 {len(natl)} missing national specificity(ies)", expanded=True):
            for n in natl:
                st.warning(
                    f"**{n.get('country', '')}** — {n.get('missing_content', '')} "
                    f"*(section: {n.get('section_id', '')})*"
                )

    st.divider()

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        show_status = st.multiselect(
            "Sections to display",
            ["MISSING", "ENRICH", "OBSOLETE", "OK", "NA_OK"],
            default=["MISSING", "ENRICH", "OBSOLETE"],
            format_func=lambda x: {
                "MISSING":  "➕ Missing content",
                "ENRICH":   "⚠️ To enrich",
                "OBSOLETE": "🔴 Obsolete",
                "OK":       "✅ Up to date",
                "NA_OK":    "🔵 NA justified",
            }.get(x, x),
            key="5a_filter_status",
        )
    with col_f2:
        show_priority = st.multiselect(
            "Priority",
            ["HIGH", "MEDIUM", "LOW", "NONE"],
            default=["HIGH", "MEDIUM", "LOW"],
            format_func=lambda x: {
                "HIGH": "🔴 High", "MEDIUM": "🟡 Medium",
                "LOW":  "🟢 Low",  "NONE":   "⚪ None",
            }.get(x, x),
            key="5a_filter_priority",
        )

    col_all1, col_all2, _ = st.columns([1, 1, 2])
    sections_to_act = [
        s for s in sections
        if s.get("status") in show_status
        and s.get("priority") in show_priority
        and s.get("proposed_update")
    ]
    if col_all1.button("✅ Approve all", key="approve_all"):
        for s in sections_to_act:
            sid = s["section_id"]
            decisions[sid] = {
                "action":        "approved",
                "final_text":    s.get("proposed_update", ""),
                "section_label": s.get("section_label", ""),
            }
        st.rerun()
    if col_all2.button("❌ Reject all", key="reject_all"):
        for s in sections_to_act:
            sid = s["section_id"]
            decisions[sid] = {
                "action":        "rejected",
                "final_text":    "",
                "section_label": s.get("section_label", ""),
            }
        st.rerun()

    for sec in sections:
        status_code = sec.get("status", "OK")
        priority    = sec.get("priority", "NONE")

        if status_code not in show_status:
            continue
        if priority not in show_priority:
            continue

        sid          = sec.get("section_id", "")
        s_icon, _    = STATUS_LABELS.get(status_code, ("?", ""))
        p_icon       = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "⚪"}.get(priority, "")
        decision     = decisions.get(sid, {})
        action       = decision.get("action", "pending")
        action_badge = {
            "approved": "✅ Approved",
            "edited":   "✏️ Edited",
            "rejected": "❌ Rejected",
            "pending":  "⏳ Pending",
        }.get(action, "")

        with st.expander(
            f"{s_icon} {sec.get('section_label', '?')}  {p_icon}  —  {action_badge}",
            expanded=(action == "pending" and status_code in ["MISSING", "OBSOLETE", "ENRICH"]),
        ):
            if sec.get("current_content_summary"):
                st.markdown("**Current content**")
                st.caption(sec["current_content_summary"])

            if sec.get("update_reason"):
                st.markdown(f"**Why update**: {sec['update_reason']}")
                if sec.get("alert_reference"):
                    st.caption(f"Source alert: *{sec['alert_reference']}*")

            if sec.get("proposed_update"):
                st.markdown("**AI proposal** *(editable)*")
                edited_text = st.text_area(
                    "Proposed text",
                    value=decision.get("final_text", sec["proposed_update"]),
                    height=180,
                    key=f"edit_{sid}",
                    label_visibility="collapsed",
                )
                col_a, col_e, col_r = st.columns(3)
                if col_a.button("✅ Approve", key=f"approve_{sid}"):
                    decisions[sid] = {
                        "action":        "approved",
                        "final_text":    sec.get("proposed_update", ""),
                        "section_label": sec.get("section_label", ""),
                    }
                    st.rerun()
                if col_e.button("✏️ Edit", key=f"edit_approve_{sid}"):
                    decisions[sid] = {
                        "action":        "edited",
                        "final_text":    edited_text,
                        "section_label": sec.get("section_label", ""),
                    }
                    st.rerun()
                if col_r.button("❌ Reject", key=f"reject_{sid}"):
                    decisions[sid] = {
                        "action":        "rejected",
                        "final_text":    "",
                        "section_label": sec.get("section_label", ""),
                    }
                    st.rerun()
            else:
                st.success("Section covered — no changes required.")

    # ── ⑥ Export ──────────────────────────────────────────────────────────────
    approved = {k: v for k, v in decisions.items() if v["action"] in ["approved", "edited"]}
    rejected = {k: v for k, v in decisions.items() if v["action"] == "rejected"}
    pending  = [
        s for s in sections
        if s.get("status") in ["MISSING", "ENRICH", "OBSOLETE"]
        and s.get("section_id") not in decisions
    ]

    st.divider()
    st.subheader("⑥ Export")

    n_approved_pure = sum(1 for d in approved.values() if d["action"] == "approved")
    n_edited        = sum(1 for d in approved.values() if d["action"] == "edited")
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("✅ Approved", n_approved_pure)
    col_s2.metric("✏️ Edited",   n_edited)
    col_s3.metric("❌ Rejected", len(rejected))
    col_s4.metric("⏳ Pending",  len(pending))

    if pending:
        st.warning(f"{len(pending)} section(s) not yet reviewed.")

    if approved:
        rapport_lines = [
            f"# Update report — {fiche_title or category}",
            f"**Market**: {market}  |  **Category**: {category}",
            f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Approved sections**: {len(approved)}  |  "
            f"**Rejected**: {len(rejected)}  |  **Pending**: {len(pending)}",
            "",
            "---",
            "",
        ]
        for sid, dec in approved.items():
            action_label = "✏️ Edited by manager" if dec["action"] == "edited" else "✅ Approved as-is"
            rapport_lines += [
                f"## {dec.get('section_label', sid)}",
                f"*{action_label}*",
                "",
                dec["final_text"],
                "",
                "---",
                "",
            ]
        rapport_md = "\n".join(rapport_lines)

        col_dl1, col_dl2 = st.columns(2)
        col_dl1.download_button(
            "⬇️ Export Markdown report",
            rapport_md.encode("utf-8"),
            f"regwatch_legal_sheet_{category}_{market}_{datetime.now().strftime('%Y%m%d')}.md",
            "text/markdown",
        )

        sections_lookup = {s.get("section_id"): s for s in sections}
        export_json = {
            "category":      category,
            "market":        market,
            "sheet_title":   fiche_title,
            "sheet_source":  input_mode,
            "analysis_date": result.get("analysis_date", ""),
            "export_date":   datetime.now().isoformat(),
            "profile":       result.get("profile", ""),
            "approved_updates": [
                {
                    "section_id":    sid,
                    "section_label": dec["section_label"],
                    "action":        dec["action"],
                    "final_text":    dec["final_text"],
                    "source_alert":  sections_lookup.get(sid, {}).get("alert_reference"),
                    "update_reason": sections_lookup.get(sid, {}).get("update_reason"),
                    "priority":      sections_lookup.get(sid, {}).get("priority"),
                    "approved_date": datetime.now().strftime("%Y-%m-%d"),
                }
                for sid, dec in approved.items()
            ],
            "rejected": list(rejected.keys()),
            "pending":  [s["section_id"] for s in pending],
            "summary":  result.get("summary", ""),
        }
        col_dl2.download_button(
            "⬇️ Export JSON (integration)",
            json.dumps(export_json, indent=2, ensure_ascii=False).encode("utf-8"),
            f"regwatch_legal_sheet_{category}_{market}_{datetime.now().strftime('%Y%m%d')}.json",
            "application/json",
        )

        st.info("💾 The validated report can be sent to your document management system.")

        # ── Library update prompt ──────────────────────────────────────────────
        if LIBRARY_AVAILABLE and gh_token_5a and len(approved) > 0:
            st.divider()
            with st.container(border=True):
                st.warning(
                    f"📚 **Library update recommended** — {len(approved)} section(s) approved. "
                    f"Apply the changes to the source document, export as PDF, and re-upload below "
                    f"to keep the **{category} — {market}** archived sheet in sync."
                )
                col_lib1, col_lib2 = st.columns(2)
                with col_lib1:
                    st.markdown("**Steps to update:**")
                    st.caption("1. Download the Markdown report above")
                    st.caption("2. Apply changes to your source document")
                    st.caption("3. Export as PDF and upload below")
                with col_lib2:
                    update_pdf = st.file_uploader(
                        "Upload updated sheet PDF",
                        type=["pdf"],
                        key="5a_update_library_pdf",
                    )
                    if update_pdf:
                        if st.button("📚 Update library", type="primary", key="5a_update_lib_btn"):
                            ok, msg = upload_sheet(
                                pdf_bytes=update_pdf.read(),
                                filename=update_pdf.name,
                                category=category,
                                market=market,
                                gh_token=gh_token_5a,
                            )
                            if ok:
                                st.success(msg)
                                # Invalidate cache so the library reflects the new version
                                _ck = f"5a_lib_text_{category}_{market}"
                                if _ck in st.session_state:
                                    del st.session_state[_ck]
                                if "5a_library_index" in st.session_state:
                                    del st.session_state["5a_library_index"]
                            else:
                                st.error(msg)
    else:
        st.info("Approve at least one section to enable export.")

# ── Send to Agent 5B ──────────────────────────────────────────────────────────
if "5a_result" in st.session_state and st.session_state.get("5a_decisions"):
    _approved_5b = [
        k for k, v in st.session_state["5a_decisions"].items()
        if v.get("action") in ["approved", "edited"]
    ]
    if _approved_5b:
        # Populate 5a_export_approved so Agent 5B can consume it
        _sections_lookup = {
            s.get("section_id"): s
            for s in st.session_state["5a_result"].get("sections", [])
        }
        st.session_state["5a_export_approved"] = [
            {
                "section_id":    sid,
                "section_label": v["section_label"],
                "action":        v["action"],
                "final_text":    v["final_text"],
                "update_reason": _sections_lookup.get(sid, {}).get("update_reason"),
                "priority":      _sections_lookup.get(sid, {}).get("priority"),
            }
            for sid, v in st.session_state["5a_decisions"].items()
            if v.get("action") in ["approved", "edited"]
        ]

        st.divider()
        with st.container(border=True):
            col_send, col_info_5b = st.columns([2, 3])
            with col_send:
                st.markdown("**➡️ Ready for Risk Mapper**")
                if st.button("🗺️ Send to Agent 5B — Risk Map", type="primary", key="send_to_5b_from_5a"):
                    st.switch_page("pages/4_Risk_Map.py")
            with col_info_5b:
                st.caption(
                    f"{len(_approved_5b)} section(s) approved — "
                    f"Agent 5B will generate a before/after risk comparison."
                )
