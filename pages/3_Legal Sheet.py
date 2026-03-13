"""
Page 7 — Agent 5A : Legal Sheet Updater
Upload PDF fiche légale → analyse → workflow approbation/édition/rejet → export.
"""

import streamlit as st
import json
import re
from datetime import datetime
from pathlib import Path
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent5a.updater import (
    analyze_legal_sheet, ALL_SECTIONS, STATUS_LABELS, SECTION_IDS,
    SECTION_PROFILES, get_sections_for_profile,
)
from agent4.impact import CAT_DEFINITIONS

st.set_page_config(page_title="Agent 5A — Legal Sheet", page_icon="📋", layout="wide")

CAT_LABELS = {k: v["label"] for k, v in CAT_DEFINITIONS.items()}
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Status")
    st.success("Anthropic ✓") if anthropic_key else st.error("ANTHROPIC_API_KEY manquante")
    st.divider()
    veille = st.session_state.get("veille_results", [])
    st.header("📡 Alertes disponibles")
    if veille:
        st.success(f"{len(veille)} alert(s) in memory")
    else:
        st.warning("No alerts.\nLancez l'Agent 1 d'abord.")
    st.divider()
    st.caption("Workflow: upload sheet → analyse → approve / edit / reject → export")
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

# ── Page principale ───────────────────────────────────────────────────────────
st.title("📋 Agent 5A — Legal Sheet Updater")
st.caption("Analyse et mise à jour des fiches légales · My Conformity Box")

# ── Étape 1 — Parameters ─────────────────────────────────────────────────────
st.subheader("① Parameters")

col1, col2, col3 = st.columns(3)
with col1:
    category = st.selectbox(
        "Catégorie",
        options=list(CAT_DEFINITIONS.keys()),
        format_func=lambda c: f"{c} — {CAT_LABELS[c]}",
        key="5a_category"
    )
with col2:
    market = st.selectbox(
        "Marché",
        ["Europe", "France", "Spain", "Italy", "Germany", "UK", "USA"],
        key="5a_market"
    )
with col3:
    urgency_filter = st.multiselect(
        "Alertes à inclure",
        ["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM"],
        key="5a_urgency"
    )

# Alertes filtrées par catégorie + urgence
veille = st.session_state.get("veille_results", [])
filtered_alerts = [
    e for e in veille
    if e.get("urgency") in urgency_filter
    and (category in e.get("categories_concerned", []) or not e.get("categories_concerned"))
]
st.caption(f"→ **{len(filtered_alerts)} alert(s)** applicables pour {category} / {market}")

st.divider()

# ── Étape 2 — Upload ou saisie de la fiche ───────────────────────────────────
st.subheader("② Legal sheet actuelle")

input_mode = st.radio(
    "Source de la fiche",
    ["📄 Upload PDF", "📝 Paste text"],
    horizontal=True,
    key="5a_input_mode"
)

fiche_text = ""
fiche_title = ""

if input_mode == "📄 Upload PDF":
    uploaded_pdf = st.file_uploader(
        "Choisir la fiche légale (PDF)",
        type=["pdf"],
        key="5a_pdf_upload"
    )
    if uploaded_pdf:
        # Extraction texte du PDF via PyPDF2 (disponible dans requirements)
        try:
            import io
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(uploaded_pdf.read()))
            fiche_text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
            fiche_title = uploaded_pdf.name.replace(".pdf", "").replace("_", " ")
            st.success(f"✓ PDF read — {len(reader.pages)} page(s) · {len(fiche_text):,} characters")
            with st.expander("Preview of extracted text"):
                st.text(fiche_text[:2000] + ("..." if len(fiche_text) > 2000 else ""))
        except Exception as e:
            st.error(f"Error lecture PDF : {e}")
            st.info("Essayez le mode 'Paste text' comme alternative.")

else:
    fiche_title = st.text_input(
        "Sheet title",
        placeholder="ex: Electronic equipment using bluetooth — EUROPE",
        key="5a_title"
    )
    fiche_text = st.text_area(
        "Contenu de la fiche (copier-coller depuis le PDF)",
        height=300,
        placeholder="Collez ici le contenu de votre fiche légale...",
        key="5a_text"
    )
    if fiche_text:
        st.caption(f"{len(fiche_text):,} characters")

st.divider()

# ── Étape 3 — Analysis profile ────────────────────────────────────────────────
st.subheader("③ Analysis profile")

profile_names = list(SECTION_PROFILES.keys())
profile = st.radio(
    "Analysis scope",
    profile_names,
    horizontal=True,
    key="5a_profile"
)

profile_info = SECTION_PROFILES[profile]
st.caption(f"*{profile_info['desc']}*")

# Sélection manuelle si profil Personnalisé
custom_ids = None
if profile == "✏️ Personnalisé":
    all_opts = {s["id"]: f"{s['label']} ({s['relevance']})" for s in ALL_SECTIONS}
    custom_ids = st.multiselect(
        "Sections to analyze",
        options=list(all_opts.keys()),
        default=[s["id"] for s in ALL_SECTIONS if s["relevance"] == "high"],
        format_func=lambda x: all_opts[x],
        key="5a_custom_sections"
    )
    sections_preview = [s for s in ALL_SECTIONS if s["id"] in (custom_ids or [])]
else:
    sections_preview = get_sections_for_profile(profile)

n_passes = max(1, -(-len(sections_preview) // 8))  # ceil division
cost_est = n_passes * 0.025  # ~$0.025 par passe Sonnet
st.info(
    f"**{len(sections_preview)} section(s)** · "
    f"**{n_passes} appel(s)** Claude · "
    f"Estimated cost : **~${cost_est:.2f}**"
)

st.divider()

# ── Étape 4 — Lancement analyse ───────────────────────────────────────────────
st.subheader("④ Analyse")

if not fiche_text.strip():
    st.info("Uploadez ou collez le contenu de la fiche légale pour continuer.")

col_launch, col_info = st.columns([2, 3])
with col_info:
    if not filtered_alerts:
        st.warning(f"No alerts {category} in memory — audit qualité uniquement.")
    else:
        st.info(f"{len(filtered_alerts)} alert(s) crossed with the sheet.")

with col_launch:
    launch = st.button(
        "🔍 Analyze sheet",
        disabled=not (anthropic_key and fiche_text.strip()),
        type="primary",
        use_container_width=True
    )

if launch:
    with st.status("🔍 Analysis in progress...", expanded=True) as status:
        try:
            chars = len(fiche_text)
            st.write(f"📄 Extracted text : {chars:,} characters")
            if chars > 12000:
                st.write(f"⚠️ Truncated text à 12 000 characters for analysis (optimal size)")
            st.write(f"🔀 Crossed with {len(filtered_alerts)} alert(s) · {category} / {market}...")

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
            st.session_state["5a_result"] = result
            st.session_state["5a_decisions"] = {}  # reset décisions
            sections = result.get("sections", [])
            n_update = sum(1 for s in sections if s.get("status") in ["MISSING","ENRICH","OBSOLETE"])
            n_ok     = sum(1 for s in sections if s.get("status") in ["OK","NA_OK"])
            # Mettre à jour les compteurs dans le résultat
            result["sections_to_update"] = n_update
            result["sections_ok"] = n_ok
            status.update(
                label=f"✅ Analyse terminée · {n_update} section(s) à mettre à jour · "
                      f"{n_ok} à jour · "
                      f"{token_usage['input_tokens']+token_usage['output_tokens']:,} tokens · "
                      ("N/A" if token_usage['cost_usd'] == 0 else f"${token_usage['cost_usd']:.4f}"),
                state="complete"
            )
        except ValueError as e:
            # Error JSON ou réponse vide — afficher le détail
            status.update(label=f"❌ Error d'analyse : {e}", state="error")
            st.error(str(e))
            st.info("💡 Conseil : essayez avec un texte plus court (mode 'Paste text' avec les sections les plus importantes) ou relancez l'analyse.")
            st.stop()
        except Exception as e:
            status.update(label=f"❌ Error: {e}", state="error")
            st.error(str(e))
            st.stop()

# ── Étape 4 — Workflow validation ────────────────────────────────────────────
if "5a_result" in st.session_state:
    result   = st.session_state["5a_result"]
    sections = result.get("sections", [])
    decisions = st.session_state.setdefault("5a_decisions", {})

    st.divider()
    st.subheader("⑤ Review and validation")

    # Récapitulatif
    overall = result.get("overall_status", "")
    overall_icons = {"MAJOR_UPDATE": "🔴", "MINOR_UPDATE": "🟡", "UP_TO_DATE": "✅"}
    overall_labels = {
        "MAJOR_UPDATE": "Mise à jour majeure requise",
        "MINOR_UPDATE": "Enrichissement mineur recommandé",
        "UP_TO_DATE": "Fiche à jour"
    }

    sections_by_status = {}
    for s in sections:
        sections_by_status.setdefault(s.get("status",""), []).append(s)

    n_ok      = len(sections_by_status.get("OK",[])) + len(sections_by_status.get("NA_OK",[]))
    n_action  = (len(sections_by_status.get("MISSING",[])) +
                 len(sections_by_status.get("ENRICH",[])) +
                 len(sections_by_status.get("OBSOLETE",[])))
    n_valid   = sum(1 for d in decisions.values() if d["action"] in ["approved","edited"])

    # Bandeau statut global coloré
    band_color = {"MAJOR_UPDATE": "#c0392b", "MINOR_UPDATE": "#e67e22", "UP_TO_DATE": "#27ae60"}.get(overall, "#7f8c8d")
    overall_icon  = overall_icons.get(overall, "?")
    overall_label = overall_labels.get(overall, overall)
    st.markdown(
        f"<div style='background:{band_color}22;border-left:4px solid {band_color};"
        f"padding:10px 16px;border-radius:4px;margin-bottom:8px'>"
        f"<b>{overall_icon} {overall_label}</b>"
        f"&nbsp;&nbsp;·&nbsp;&nbsp;✅ {n_ok} à jour"
        f"&nbsp;&nbsp;·&nbsp;&nbsp;⚠️ {n_action} à mettre à jour"
        f"&nbsp;&nbsp;·&nbsp;&nbsp;✔️ {n_valid} validée(s)"
        f"</div>",
        unsafe_allow_html=True
    )

    if result.get("summary"):
        st.info(result["summary"])

    # Spécificités nationales manquantes
    natl = result.get("national_specificities_missing", [])
    if natl:
        with st.expander(f"🌍 {len(natl)} spécificité(s) nationale(s) manquante(s)", expanded=True):
            for n in natl:
                st.warning(f"**{n.get('country','')}** — {n.get('missing_content','')} "
                           f"*(section : {n.get('section_id','')})*")

    st.divider()

    # Filtres d'affichage
    col_f1, col_f2 = st.columns([2, 2])
    with col_f1:
        show_status = st.multiselect(
            "Sections to display",
            ["MISSING", "ENRICH", "OBSOLETE", "OK", "NA_OK"],
            default=["MISSING", "ENRICH", "OBSOLETE"],
            format_func=lambda x: {
                "MISSING":  "➕ Contenu manquant",
                "ENRICH":   "⚠️ À enrichir",
                "OBSOLETE": "🔴 Obsolète",
                "OK":       "✅ À jour",
                "NA_OK":    "🔵 NA justifié",
            }.get(x, x),
            key="5a_filter_status"
        )
    with col_f2:
        show_priority = st.multiselect(
            "Priority",
            ["HIGH", "MEDIUM", "LOW", "NONE"],
            default=["HIGH", "MEDIUM", "LOW"],
            format_func=lambda x: {
                "HIGH": "🔴 Haute", "MEDIUM": "🟡 Moyenne",
                "LOW": "🟢 Basse", "NONE": "⚪ Aucune"
            }.get(x, x),
            key="5a_filter_priority"
        )

    # Boutons globaux
    col_all1, col_all2, _ = st.columns([1, 1, 2])
    sections_to_act = [
        s for s in sections
        if s.get("status") in show_status
        and s.get("priority") in show_priority
        and s.get("proposed_update")
    ]
    if col_all1.button("✅ Tout approuver", key="approve_all"):
        for s in sections_to_act:
            sid = s["section_id"]
            decisions[sid] = {
                "action": "approved",
                "final_text": s.get("proposed_update", ""),
                "section_label": s.get("section_label", "")
            }
        st.rerun()
    if col_all2.button("❌ Tout rejeter", key="reject_all"):
        for s in sections_to_act:
            sid = s["section_id"]
            decisions[sid] = {
                "action": "rejected",
                "final_text": "",
                "section_label": s.get("section_label", "")
            }
        st.rerun()

    # Sections
    for sec in sections:
        status_code = sec.get("status", "OK")
        priority    = sec.get("priority", "NONE")

        if status_code not in show_status:
            continue
        if priority not in show_priority:
            continue

        sid         = sec.get("section_id", "")
        s_icon, s_label = STATUS_LABELS.get(status_code, ("?", ""))
        p_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "⚪"}.get(priority, "")
        decision    = decisions.get(sid, {})
        action      = decision.get("action", "pending")

        # Couleur du header selon décision
        action_badge = {
            "approved": "✅ Approuvée",
            "edited":   "✏️ Éditée",
            "rejected": "❌ Rejetée",
            "pending":  "⏳ Pending"
        }.get(action, "")

        with st.expander(
            f"{s_icon} {sec.get('section_label','?')}  {p_icon}  —  {action_badge}",
            expanded=(action == "pending" and status_code in ["MISSING","OBSOLETE","ENRICH"])
        ):
            # Current content
            if sec.get("current_content_summary"):
                st.markdown("**Current content**")
                st.caption(sec["current_content_summary"])

            # Raison de la mise à jour
            if sec.get("update_reason"):
                st.markdown(f"**Why update** : {sec['update_reason']}")
                if sec.get("alert_reference"):
                    st.caption(f"Alerte source : *{sec['alert_reference']}*")

            # AI proposal — éditable
            if sec.get("proposed_update"):
                st.markdown("**AI proposal** *(éditable)*")
                edited_text = st.text_area(
                    "Texte proposé",
                    value=decision.get("final_text", sec["proposed_update"]),
                    height=180,
                    key=f"edit_{sid}",
                    label_visibility="collapsed"
                )

                col_a, col_e, col_r = st.columns(3)
                if col_a.button("✅ Approve", key=f"approve_{sid}"):
                    decisions[sid] = {
                        "action": "approved",
                        "final_text": sec.get("proposed_update", ""),
                        "section_label": sec.get("section_label","")
                    }
                    st.rerun()
                if col_e.button("✏️ Edit", key=f"edit_approve_{sid}"):
                    decisions[sid] = {
                        "action": "edited",
                        "final_text": edited_text,
                        "section_label": sec.get("section_label","")
                    }
                    st.rerun()
                if col_r.button("❌ Reject", key=f"reject_{sid}"):
                    decisions[sid] = {
                        "action": "rejected",
                        "final_text": "",
                        "section_label": sec.get("section_label","")
                    }
                    st.rerun()
            else:
                st.success("Section couverte — aucune modification nécessaire.")

    # ── Étape 5 — Export ─────────────────────────────────────────────────────
    approved = {k: v for k, v in decisions.items() if v["action"] in ["approved", "edited"]}
    rejected = {k: v for k, v in decisions.items() if v["action"] == "rejected"}
    pending  = [s for s in sections
                if s.get("status") in ["MISSING","ENRICH","OBSOLETE"]
                and s.get("section_id") not in decisions]

    st.divider()
    st.subheader("⑥ Export")

    n_approved_pure = sum(1 for d in approved.values() if d["action"] == "approved")
    n_edited        = sum(1 for d in approved.values() if d["action"] == "edited")
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("✅ Approved",   n_approved_pure)
    col_s2.metric("✏️ Edited",      n_edited)
    col_s3.metric("❌ Rejected",     len(rejected))
    col_s4.metric("⏳ Pending",   len(pending))

    if pending:
        st.warning(f"{len(pending)} section(s) non encore traitée(s).")

    if approved:
        # Export rapport de mise à jour
        rapport_lines = [
            f"# Rapport de mise à jour — {fiche_title or category}",
            f"**Marché** : {market}  |  **Catégorie** : {category}",
            f"**Date** : {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            f"**Sections approuvées** : {len(approved)}  |  "
            f"**Rejected** : {len(rejected)}  |  **Pending** : {len(pending)}",
            "",
            "---",
            ""
        ]
        for sid, dec in approved.items():
            action_label = "✏️ Éditée par le responsable" if dec["action"] == "edited" else "✅ Approuvée telle quelle"
            rapport_lines += [
                f"## {dec.get('section_label', sid)}",
                f"*{action_label}*",
                "",
                dec["final_text"],
                "",
                "---",
                ""
            ]

        rapport_md = "\n".join(rapport_lines)

        col_dl1, col_dl2 = st.columns(2)
        col_dl1.download_button(
            "⬇️ Exporter rapport Markdown",
            rapport_md.encode("utf-8"),
            f"regwatch_fiche_{category}_{market}_{datetime.now().strftime('%Y%m%d')}.md",
            "text/markdown"
        )

        # Export JSON complet
        # Enrichir avec les métadonnées de traçabilité pour saisie dans My Conformity Box
        sections_lookup = {s.get("section_id"): s for s in sections}
        export_json = {
            "category": category,
            "market": market,
            "fiche_title": fiche_title,
            "analysis_date": result.get("analysis_date", ""),
            "export_date": datetime.now().isoformat(),
            "profile": result.get("profile", ""),
            "approved_updates": [
                {
                    "section_id": sid,
                    "section_label": dec["section_label"],
                    "action": dec["action"],
                    "final_text": dec["final_text"],
                    "source_alert": sections_lookup.get(sid, {}).get("alert_reference"),
                    "update_reason": sections_lookup.get(sid, {}).get("update_reason"),
                    "priority": sections_lookup.get(sid, {}).get("priority"),
                    "approved_date": datetime.now().strftime("%Y-%m-%d"),
                }
                for sid, dec in approved.items()
            ],
            "rejected": list(rejected.keys()),
            "pending": [s["section_id"] for s in pending],
            "summary": result.get("summary", ""),
        }
        col_dl2.download_button(
            "⬇️ Exporter JSON (intégration)",
            json.dumps(export_json, indent=2, ensure_ascii=False).encode("utf-8"),
            f"regwatch_fiche_{category}_{market}_{datetime.now().strftime('%Y%m%d')}.json",
            "application/json"
        )

        st.info("💾 Le rapport validé peut être transmis à votre système de gestion documentaire.")
    else:
        st.info("Approuvez au moins une section pour activer l'export.")
