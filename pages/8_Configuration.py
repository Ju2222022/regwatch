"""
Page 8 — Configuration
Two tabs:
  - Watch Sources : market domains + languages
  - Legal Referential : legal categories + subcategories editor
"""

import streamlit as st
import json
from pathlib import Path
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent1.watcher import load_sources, save_sources, LANGUAGE_LABELS
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from utils.legal_sheet_library import (
        load_index, upload_sheet, delete_sheet,
        list_available_sheets, fetch_sheet_text
    )
    LIBRARY_AVAILABLE = True
except Exception:
    LIBRARY_AVAILABLE = False

from data.referential import (
    load_referential, save_referential,
    get_legal_categories, get_cat_labels,
    update_subcategory, update_legal_category,
    add_legal_category, add_subcategory,
)

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")
st.title("⚙️ Configuration")
st.caption("Manage watch sources and legal referential")

SOURCES_FILE  = "data/sources.json"
REVIEW_CONFIG = Path(__file__).parent.parent / "data" / "review_config.json"

def _load_review_cfg() -> dict:
    if REVIEW_CONFIG.exists():
        with open(REVIEW_CONFIG) as f:
            return json.load(f)
    return {"active_categories":["CAT1","CAT3","CAT4","CAT7","CAT8","CAT9"],
            "markets":["EU","France"],"email_recipients":[],"frequency":"weekly","enabled":True}

def _save_review_cfg(cfg: dict):
    with open(REVIEW_CONFIG, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

tab_sources, tab_ref, tab_review, tab_library = st.tabs(["🌍 Watch Sources", "📚 Legal Referential", "📅 Periodic Review", "📁 Legal Sheet Library"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — WATCH SOURCES
# ══════════════════════════════════════════════════════════════════════════════
with tab_sources:
    st.subheader("Watch Sources — Markets & Domains")
    st.caption("Manage markets, domains and search languages for Agent 1")

    try:
        sources = load_sources(SOURCES_FILE)
    except Exception:
        sources = {"EU": ["eur-lex.europa.eu"], "France": ["legifrance.gouv.fr"]}

    LANG_KEY = "_market_languages"
    lang_map  = sources.get(LANG_KEY, {})
    markets   = sorted([k for k in sources if not k.startswith("_")])

    LANG_FLAGS = {"en": "🇬🇧", "fr": "🇫🇷", "zh": "🇨🇳", "es": "🇪🇸", "de": "🇩🇪",
                  "ja": "🇯🇵", "ko": "🇰🇷", "pt": "🇧🇷", "it": "🇮🇹", "nl": "🇳🇱"}
    LANG_OPTIONS = {
        "en": "🇬🇧 English", "fr": "🇫🇷 French", "zh": "🇨🇳 Mandarin Chinese",
        "es": "🇪🇸 Spanish", "de": "🇩🇪 German", "ja": "🇯🇵 Japanese",
        "ko": "🇰🇷 Korean", "pt": "🇧🇷 Portuguese", "it": "🇮🇹 Italian", "nl": "🇳🇱 Dutch",
    }

    # Summary: scrollable grid of market badges
    if markets:
        st.markdown("**Active markets**")
        badge_html = "<div style='display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px;'>"
        for m in markets:
            lang = lang_map.get(m, "en")
            flag = LANG_FLAGS.get(lang, "🌐")
            n = len(sources.get(m, []))
            badge_html += (
                f"<div style='background:#1e2130;border-radius:8px;padding:10px 16px;"
                f"min-width:120px;text-align:center;border:1px solid #333;'>"
                f"<div style='font-weight:600;font-size:15px;'>{m}</div>"
                f"<div style='color:#888;font-size:13px;'>{n} domain(s)</div>"
                f"<div style='font-size:12px;margin-top:2px;'>{flag} {LANGUAGE_LABELS.get(lang, lang)}</div>"
                f"</div>"
            )
        badge_html += "</div>"
        st.markdown(badge_html, unsafe_allow_html=True)

    st.divider()

    # Market selector (scalable — works with 2 or 200 markets)
    col_sel, col_add = st.columns([3, 1])
    with col_sel:
        selected_market = st.selectbox(
            "Select a market to configure",
            options=markets + ["➕ New market"],
            key="market_selector"
        )
    st.markdown("")

    market = selected_market
    if market != "➕ New market":
        with st.container(border=True):
            col_edit, col_lang, col_delete = st.columns([3, 1.5, 1])
            with col_edit:
                st.markdown(f"**Monitored domains for {market}**")
                edited_domains = st.text_area(
                    "One domain per line",
                    value="\n".join(sources.get(market, [])),
                    height=200, key=f"edit_{market}"
                )
            with col_lang:
                st.markdown("**Search language**")
                current_lang = lang_map.get(market, "en")
                lang_keys = list(LANG_OPTIONS.keys())
                lang_idx  = lang_keys.index(current_lang) if current_lang in lang_keys else 0
                new_lang  = st.selectbox(
                    "Language", options=lang_keys, index=lang_idx,
                    format_func=lambda l: LANG_OPTIONS[l],
                    key=f"lang_{market}", label_visibility="collapsed"
                )
            with col_delete:
                st.markdown("**Delete**")
                confirm = st.checkbox("Confirm deletion", key=f"confirm_del_{market}")
                if st.button(f"🗑️ Delete {market}", key=f"del_{market}",
                             disabled=not confirm, type="secondary"):
                    del sources[market]
                    if market in lang_map: del lang_map[market]
                    sources[LANG_KEY] = lang_map
                    save_sources(sources, SOURCES_FILE)
                    st.success(f"Market **{market}** deleted.")
                    st.rerun()

            if st.button(f"💾 Save {market}", key=f"save_{market}", type="primary"):
                sources[market] = [d.strip() for d in edited_domains.split("\n") if d.strip()]
                lang_map[market] = new_lang
                sources[LANG_KEY] = lang_map
                save_sources(sources, SOURCES_FILE)
                st.success(f"✓ {len(sources[market])} domain(s) saved for **{market}**")
                st.rerun()

    else:
        with st.container(border=True):
            st.markdown("**Create a new market**")
        col_a, col_b = st.columns(2)
        with col_a:
            new_name = st.text_input("Market name *", placeholder="e.g. Japan, Nordic, APAC")
        with col_b:
            new_lang_key = st.selectbox(
                "Search language *", options=list(LANG_OPTIONS.keys()),
                format_func=lambda l: LANG_OPTIONS[l]
            )
        new_domains_text = st.text_area("Initial domains (one per line)", height=150)
        if st.button("✅ Create market", type="primary", disabled=not new_name.strip()):
            name = new_name.strip()
            if name in sources:
                st.error(f"Market **{name}** already exists.")
            else:
                sources[name] = [d.strip() for d in new_domains_text.split("\n") if d.strip()]
                lang_map[name] = new_lang_key
                sources[LANG_KEY] = lang_map
                save_sources(sources, SOURCES_FILE)
                st.success(f"✓ Market **{name}** created")
                st.rerun()

    st.divider()
    col_exp, col_imp = st.columns(2)
    with col_exp:
        st.download_button("⬇️ Download sources.json",
            data=json.dumps(sources, indent=2, ensure_ascii=False),
            file_name="sources.json", mime="application/json")
    with col_imp:
        uploaded = st.file_uploader("Import sources.json", type="json", key="import_sources")
        if uploaded:
            try:
                imported = json.load(uploaded)
                imported_markets = [k for k in imported if not k.startswith("_")]
                st.write(f"{len(imported_markets)} market(s) detected")
                if st.button("✅ Confirm import", type="primary"):
                    save_sources(imported, SOURCES_FILE)
                    st.success("Configuration imported ✓")
                    st.rerun()
            except Exception as e:
                st.error(f"Read error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LEGAL REFERENTIAL
# ══════════════════════════════════════════════════════════════════════════════
with tab_ref:
    st.subheader("Legal Referential — Categories & Sub-categories")
    st.caption("Single source of truth for all agents. Changes apply immediately across the platform.")

    legal_cats = get_legal_categories()

    if not legal_cats:
        st.warning("No legal categories found in referential.")
        st.stop()

    # ── Sélection catégorie légale ────────────────────────────────────────────
    legal_cat_options = {c["id"]: c["label"] for c in legal_cats}
    selected_legal_cat_id = st.selectbox(
        "Legal category",
        options=list(legal_cat_options.keys()),
        format_func=lambda x: legal_cat_options[x],
        key="ref_legal_cat_select"
    )
    selected_legal_cat = next((c for c in legal_cats if c["id"] == selected_legal_cat_id), {})
    subcategories = selected_legal_cat.get("subcategories", [])

    # ── Résumé + édition catégorie légale ────────────────────────────────────
    with st.container(border=True):
        col_info, col_edit_btn = st.columns([4, 1])
        with col_info:
            st.markdown(f"**{selected_legal_cat.get('label', '')}**")
            st.caption(selected_legal_cat.get("description", "—"))
            rules = selected_legal_cat.get("classification_rules", {})
            fallback = rules.get("mandatory_fallback")
            if fallback:
                st.info(f"🪂 Mandatory fallback: **{fallback}** — {rules.get('fallback_rule', '')[:80]}...")
            st.caption(f"{len(subcategories)} sub-categorie(s)")
        with col_edit_btn:
            edit_legal_cat = st.toggle("✏️ Edit domain", key="toggle_edit_legal_cat")

    if edit_legal_cat:
        with st.form("form_edit_legal_cat"):
            st.markdown("**Edit legal category**")
            new_label = st.text_input("Label", value=selected_legal_cat.get("label", ""))
            new_desc  = st.text_area("Description", value=selected_legal_cat.get("description", ""), height=80)
            st.markdown("**Classification rules**")
            new_fallback = st.text_input(
                "Mandatory fallback sub-category ID (leave empty if none)",
                value=rules.get("mandatory_fallback") or ""
            )
            new_fallback_rule = st.text_area("Fallback rule", value=rules.get("fallback_rule", ""), height=80)
            new_spec_rule     = st.text_area("Specificity rule", value=rules.get("specificity_rule", ""), height=80)
            new_multi = st.checkbox("Allow multi-label", value=rules.get("multi_label", True))
            if st.form_submit_button("💾 Save", type="primary"):
                updated = {
                    "label": new_label, "description": new_desc,
                    "classification_rules": {
                        "mandatory_fallback": new_fallback or None,
                        "fallback_rule": new_fallback_rule,
                        "specificity_rule": new_spec_rule,
                        "multi_label": new_multi,
                        "multi_label_rule": rules.get("multi_label_rule", ""),
                    }
                }
                if update_legal_category(selected_legal_cat_id, updated):
                    st.success("✓ Legal category updated"); st.rerun()
                else:
                    st.error("Update failed")

    st.divider()

    # ── Liste sous-catégories ─────────────────────────────────────────────────
    st.markdown(f"### Sub-categories")

    if not subcategories:
        st.info("No sub-categories defined yet.")
    else:
        sub_options = {s["id"]: f"{s['id']} — {s['label'][:70]}" for s in subcategories}
        selected_sub_id = st.selectbox(
            "Select a sub-category",
            options=list(sub_options.keys()),
            format_func=lambda x: sub_options[x],
            key="ref_sub_select"
        )
        selected_sub = next((s for s in subcategories if s["id"] == selected_sub_id), {})

        view_tab, edit_tab = st.tabs(["👁️ View", "✏️ Edit"])

        with view_tab:
            col_v1, col_v2 = st.columns([3, 2])
            with col_v1:
                st.markdown("**Definition**")
                st.write(selected_sub.get("definition", "—"))
                st.markdown("**Scope**")
                st.info(selected_sub.get("scope", "—"))
                st.markdown("**Classification rule**")
                st.warning(selected_sub.get("classification_rule", "—"))
            with col_v2:
                st.markdown("**Key regulations**")
                for reg in selected_sub.get("key_regulations", []):
                    st.markdown(f"- {reg}")
                st.markdown("**Keywords**")
                st.caption(" · ".join(selected_sub.get("keywords", [])))
                st.markdown("**Watch queries (Agent 1)**")
                for q in selected_sub.get("watch_queries", []):
                    st.markdown(f"- `{q}`")

        with edit_tab:
            with st.form(f"form_edit_sub_{selected_sub_id}"):
                new_sub_label = st.text_input("Label (official name)", value=selected_sub.get("label", ""))
                new_sub_def   = st.text_area("Definition", value=selected_sub.get("definition", ""), height=200)
                new_sub_scope = st.text_area("Scope", value=selected_sub.get("scope", ""), height=100)
                new_sub_rule  = st.text_area("Classification rule", value=selected_sub.get("classification_rule", ""), height=80)
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    new_sub_regs = st.text_area("Key regulations (one per line)",
                        value="\n".join(selected_sub.get("key_regulations", [])), height=120)
                with col_f2:
                    new_sub_keywords = st.text_area("Keywords (one per line)",
                        value="\n".join(selected_sub.get("keywords", [])), height=120)
                new_sub_queries = st.text_area("Watch queries — Agent 1 (one per line)",
                    value="\n".join(selected_sub.get("watch_queries", [])), height=120,
                    help="These queries are used by Agent 1 when pre-filling watch topics for this sub-category.")

                if st.form_submit_button("💾 Save sub-category", type="primary"):
                    updated_sub = {
                        "label":               new_sub_label,
                        "definition":          new_sub_def,
                        "scope":               new_sub_scope,
                        "classification_rule": new_sub_rule,
                        "key_regulations": [r.strip() for r in new_sub_regs.split("\n") if r.strip()],
                        "keywords":        [k.strip() for k in new_sub_keywords.split("\n") if k.strip()],
                        "watch_queries":   [q.strip() for q in new_sub_queries.split("\n") if q.strip()],
                    }
                    if update_subcategory(selected_legal_cat_id, selected_sub_id, updated_sub):
                        st.success(f"✓ {selected_sub_id} updated — changes applied across all agents immediately.")
                        st.rerun()
                    else:
                        st.error("Update failed")

    st.divider()

    # ── Ajouter sous-catégorie ────────────────────────────────────────────────
    with st.expander("➕ Add a new sub-category", expanded=False):
        with st.form("form_add_sub"):
            st.markdown(f"**New sub-category in *{selected_legal_cat.get('label', '')}***")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                new_id  = st.text_input("ID (e.g. CAT10)", placeholder="CAT10")
            with col_a2:
                new_lbl = st.text_input("Label (official name)")
            new_def   = st.text_area("Definition", height=120)
            new_scope = st.text_area("Scope", height=80)
            new_rule  = st.text_area("Classification rule", height=68)
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                new_regs = st.text_area("Key regulations (one per line)", height=100)
            with col_b2:
                new_kws  = st.text_area("Keywords (one per line)", height=100)
            new_qs = st.text_area("Watch queries (one per line)", height=100)
            if st.form_submit_button("➕ Add sub-category", type="primary"):
                if not new_id or not new_lbl:
                    st.error("ID and Label are required.")
                else:
                    new_sub = {
                        "id": new_id.strip(), "label": new_lbl.strip(),
                        "definition": new_def.strip(), "scope": new_scope.strip(),
                        "classification_rule": new_rule.strip(),
                        "key_regulations": [r.strip() for r in new_regs.split("\n") if r.strip()],
                        "keywords":        [k.strip() for k in new_kws.split("\n") if k.strip()],
                        "watch_queries":   [q.strip() for q in new_qs.split("\n") if q.strip()],
                    }
                    if add_subcategory(selected_legal_cat_id, new_sub):
                        st.success(f"✓ {new_id} added"); st.rerun()
                    else:
                        st.error(f"ID {new_id} already exists.")

    # ── Ajouter catégorie légale ──────────────────────────────────────────────
    with st.expander("➕ Add a new legal category (new domain)", expanded=False):
        with st.form("form_add_legal_cat"):
            st.caption("Use this to onboard a new product domain (e.g. Textiles, Toys, Food supplements...)")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                nc_id    = st.text_input("ID (lowercase, no spaces)", placeholder="textiles")
            with col_c2:
                nc_label = st.text_input("Label", placeholder="Textiles")
            nc_desc  = st.text_area("Description", height=80)
            st.markdown("**Classification rules** (optional)")
            nc_fallback      = st.text_input("Mandatory fallback sub-category ID (leave empty if none)")
            nc_fallback_rule = st.text_area("Fallback rule", height=68)
            nc_spec_rule     = st.text_area("Specificity rule", height=68)
            nc_multi         = st.checkbox("Allow multi-label", value=True)
            if st.form_submit_button("➕ Create legal category", type="primary"):
                if not nc_id or not nc_label:
                    st.error("ID and Label are required.")
                else:
                    new_cat = {
                        "id": nc_id.strip().lower().replace(" ", "_"),
                        "label": nc_label.strip(), "description": nc_desc.strip(),
                        "classification_rules": {
                            "mandatory_fallback": nc_fallback.strip() or None,
                            "fallback_rule": nc_fallback_rule.strip(),
                            "specificity_rule": nc_spec_rule.strip(),
                            "multi_label": nc_multi,
                        },
                        "subcategories": []
                    }
                    if add_legal_category(new_cat):
                        st.success(f"✓ '{nc_label}' created. Now add sub-categories."); st.rerun()
                    else:
                        st.error(f"ID '{nc_id}' already exists.")

    st.divider()

    # ── Export / Import ───────────────────────────────────────────────────────
    st.subheader("📤 Export / Import referential")
    col_ex, col_im = st.columns(2)
    with col_ex:
        ref_data = load_referential()
        st.download_button("⬇️ Download legal_categories.json",
            data=json.dumps(ref_data, indent=2, ensure_ascii=False),
            file_name="legal_categories.json", mime="application/json")
        st.caption("Full referential — all legal categories, sub-categories, definitions, rules, and watch queries.")
    with col_im:
        uploaded_ref = st.file_uploader("Import legal_categories.json", type="json", key="import_ref")
        if uploaded_ref:
            try:
                imported_ref = json.load(uploaded_ref)
                n_cats = len(imported_ref.get("legal_categories", []))
                n_subs = sum(len(c.get("subcategories", [])) for c in imported_ref.get("legal_categories", []))
                st.write(f"{n_cats} legal categorie(s) · {n_subs} sub-categorie(s) detected")
                if st.button("✅ Confirm import", type="primary", key="confirm_import_ref"):
                    save_referential(imported_ref)
                    st.success("Referential imported ✓ — all agents updated immediately."); st.rerun()
            except Exception as e:
                st.error(f"Read error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PERIODIC REVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_review:
    st.subheader("Periodic Review — Configuration")
    st.caption("Automated regulatory watch — configure categories, markets, frequency and recipients")

    cfg = _load_review_cfg()

    # ── Run now ───────────────────────────────────────────────────────────────
    gh_token = st.secrets.get("GH_TOKEN", "")

    with st.container(border=True):
        col_run, col_last = st.columns([2, 3])
        with col_run:
            st.markdown("**▶️ Run a review now**")
            if st.button("🚀 Launch review", type="primary", disabled=not gh_token):
                try:
                    import urllib.request, urllib.error
                    payload = json.dumps({"ref": "main"}).encode()
                    req = urllib.request.Request(
                        "https://api.github.com/repos/Ju2222022/regwatch/actions/workflows/periodic_review.yml/dispatches",
                        data=payload,
                        headers={
                            "Authorization": f"Bearer {gh_token}",
                            "Accept": "application/vnd.github+json",
                            "Content-Type": "application/json",
                            "X-GitHub-Api-Version": "2022-11-28",
                        },
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        if resp.status == 204:
                            st.success("✅ Review launched! Results will appear in the Review page in a few minutes.")
                        else:
                            st.warning(f"Unexpected response: {resp.status}")
                except urllib.error.HTTPError as e:
                    body = e.read().decode("utf-8", errors="ignore")
                    st.error(f"Error launching review: {e.code} — {body[:200]}")
                except Exception as e:
                    st.error(f"Error: {e}")
            if not gh_token:
                st.caption("⚠️ GH_TOKEN not configured in Streamlit secrets.")

        with col_last:
            REVIEW_HISTORY_PATH = Path(__file__).parent.parent / "data" / "review_history.json"
            if REVIEW_HISTORY_PATH.exists():
                with open(REVIEW_HISTORY_PATH) as f:
                    history = json.load(f)
                reviews = history.get("reviews", [])
                if reviews:
                    latest = reviews[-1]
                    st.markdown("**Last review**")
                    st.caption(f"📅 {latest.get('date', '')} · {latest.get('total_new', 0)} new alert(s)")
                    cats_done = ", ".join(latest.get("categories", []))
                    st.caption(f"Categories: {cats_done}")
                else:
                    st.info("No review run yet.")
            else:
                st.info("No review run yet.")

    st.divider()

    # ── Frequency ─────────────────────────────────────────────────────────────
    st.markdown("**Automatic frequency**")
    st.caption("The review will run automatically at the selected frequency. You can always trigger it manually above.")

    freq_options = {
        "manual":   "Manual only — no automatic schedule",
        "weekly":   "Every week",
        "biweekly": "Twice a month",
        "monthly":  "Once a month",
    }
    current_freq = cfg.get("frequency", "weekly")
    selected_freq = st.selectbox(
        "Frequency",
        options=list(freq_options.keys()),
        index=list(freq_options.keys()).index(current_freq) if current_freq in freq_options else 1,
        format_func=lambda f: freq_options[f],
        label_visibility="collapsed"
    )

    st.divider()

    # ── Categories ────────────────────────────────────────────────────────────
    st.markdown("**Categories to monitor**")
    st.caption("Agent 1 will search for regulatory updates for each selected category")
    try:
        from data.referential import get_cat_labels as _gcl
        _labels = _gcl()
        all_cats = list(_labels.keys())
        cat_format = lambda c: f"{c} — {_labels.get(c,'').split('(')[0].strip()[:50]}"
    except Exception:
        all_cats = ["CAT1","CAT2","CAT3","CAT4","CAT5","CAT6","CAT7","CAT8","CAT9"]
        cat_format = lambda c: c

    current_cats = cfg.get("active_categories", [])
    selected_cats = st.multiselect(
        "Categories",
        options=all_cats,
        default=[c for c in current_cats if c in all_cats],
        format_func=cat_format,
        label_visibility="collapsed"
    )

    st.divider()

    # ── Markets ───────────────────────────────────────────────────────────────
    st.markdown("**Markets to monitor**")
    try:
        available_markets = sorted([k for k in load_sources(SOURCES_FILE) if not k.startswith("_")])
    except Exception:
        available_markets = ["EU", "France", "UK", "USA", "China", "Germany", "Spain"]

    current_markets = cfg.get("markets", ["EU", "France"])
    selected_markets = st.multiselect(
        "Markets",
        options=available_markets,
        default=[m for m in current_markets if m in available_markets],
        label_visibility="collapsed"
    )

    st.divider()

    # ── Email recipients ──────────────────────────────────────────────────────
    st.markdown("**Email recipients**")
    st.caption("Recipients are managed via the **REVIEW_EMAIL_TO** GitHub secret — separate multiple addresses with commas.")
    st.info(
        "To add or change recipients:\n"
        "1. Go to your GitHub repo → Settings → Environments → regwatch\n"
        "2. Edit **REVIEW_EMAIL_TO** with comma-separated addresses\n"
        "   Example: `email1@example.com,email2@example.com`"
    )

    st.divider()

    # ── Save ──────────────────────────────────────────────────────────────────
    if st.button("💾 Save configuration", type="primary"):
        new_cfg = {
            **cfg,
            "active_categories": selected_cats,
            "markets":           selected_markets,
            "email_recipients":  cfg.get("email_recipients", []),  # Managed via GitHub secret REVIEW_EMAIL_TO
            "frequency":         selected_freq,
            "enabled":           selected_freq != "manual",
        }
        _save_review_cfg(new_cfg)
        st.success("✅ Configuration saved — will apply at next review.")
        st.rerun()

    st.divider()

    # ── History summary ───────────────────────────────────────────────────────
    if REVIEW_HISTORY_PATH.exists():
        with open(REVIEW_HISTORY_PATH) as f:
            history = json.load(f)
        reviews = history.get("reviews", [])
        if len(reviews) > 1:
            st.markdown(f"**History — {len(reviews)} review(s) run**")
            import pandas as pd
            rows = [{"Date": r.get("date",""), "New alerts": r.get("total_new",0),
                     "Categories": ", ".join(r.get("categories",[]))}
                    for r in reversed(reviews[-5:])]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — LEGAL SHEET LIBRARY
# ══════════════════════════════════════════════════════════════════════════════
with tab_library:
    st.subheader("📁 Legal Sheet Library")
    st.caption("Store and manage legal sheets by category and market — used automatically by Agent 5A and Run All.")

    if not LIBRARY_AVAILABLE:
        st.error("Library module not available — check `utils/legal_sheet_library.py`.")
        st.stop()

    gh_token = st.secrets.get("GH_TOKEN", "")
    if not gh_token:
        st.warning("⚠️ GH_TOKEN not configured in Streamlit secrets — uploads will not be persisted.")

    gh_token = st.secrets.get("GH_TOKEN", "")
    index = load_index(gh_token)
    sheets = list_available_sheets(index)

    # ── Current library ───────────────────────────────────────────────────────
    st.markdown(f"**Available sheets — {len(sheets)} file(s)**")
    if sheets:
        import pandas as pd
        df = pd.DataFrame(sheets)[["category", "market", "filename", "uploaded", "size_kb"]]
        df.columns = ["Category", "Market", "Original filename", "Uploaded", "Size (KB)"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No sheets uploaded yet. Use the form below to add your first sheet.")

    st.divider()

    # ── Upload new sheet ──────────────────────────────────────────────────────
    st.markdown("**📤 Upload a new sheet**")

    try:
        from data.referential import get_cat_labels as _gcl
        _labels = _gcl()
        all_cats = list(_labels.keys())
        cat_fmt = lambda c: f"{c} — {_labels.get(c,'').split('(')[0].strip()[:50]}"
    except Exception:
        all_cats = ["CAT1","CAT2","CAT3","CAT4","CAT5","CAT6","CAT7","CAT8","CAT9"]
        cat_fmt = lambda c: c

    try:
        from agent1.watcher import load_sources as _ls
        _src = _ls("data/sources.json")
        available_markets_lib = sorted([k for k in _src if not k.startswith("_")])
    except Exception:
        available_markets_lib = ["EU", "France", "Germany", "Spain", "Italy", "UK"]

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        upload_cat = st.selectbox(
            "Category *",
            options=all_cats,
            format_func=cat_fmt,
            key="lib_upload_cat"
        )
    with col_u2:
        upload_market = st.selectbox(
            "Market *",
            options=available_markets_lib,
            key="lib_upload_market"
        )

    # Avertir si une fiche existe déjà
    existing = next(
        (s for s in sheets if s["category"] == upload_cat and s["market"] == upload_market),
        None
    )
    if existing:
        st.warning(
            f"⚠️ A sheet already exists for **{upload_cat} — {upload_market}** "
            f"(uploaded {existing['uploaded']}). Uploading will replace it."
        )

    uploaded_pdf = st.file_uploader(
        "Legal sheet PDF *",
        type=["pdf"],
        key="lib_pdf_upload",
        help="Upload the legal sheet PDF for this category and market."
    )

    if uploaded_pdf:
        st.caption(f"📄 {uploaded_pdf.name} · {round(uploaded_pdf.size / 1024, 1)} KB")
        if st.button("💾 Save to library", type="primary", key="lib_save"):
            with st.spinner("Uploading to GitHub..."):
                pdf_bytes = uploaded_pdf.read()
                ok, msg = upload_sheet(
                    pdf_bytes=pdf_bytes,
                    filename=uploaded_pdf.name,
                    category=upload_cat,
                    market=upload_market,
                    gh_token=gh_token,
                )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()

    # ── Delete a sheet ────────────────────────────────────────────────────────
    if sheets:
        st.markdown("**🗑️ Delete a sheet**")
        sheet_options = {f"{s['category']} — {s['market']}": (s["category"], s["market"])
                         for s in sheets}
        to_delete = st.selectbox(
            "Select sheet to delete",
            options=list(sheet_options.keys()),
            key="lib_delete_select"
        )
        confirm_del = st.checkbox("Confirm deletion", key="lib_confirm_del")
        if st.button("🗑️ Delete sheet", disabled=not confirm_del, type="secondary", key="lib_delete_btn"):
            cat_del, mkt_del = sheet_options[to_delete]
            with st.spinner("Deleting..."):
                ok, msg = delete_sheet(cat_del, mkt_del, gh_token)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()

    # ── Bulk upload ───────────────────────────────────────────────────────────
    st.markdown("**📦 Bulk upload — multiple sheets at once**")
    st.caption("Upload all your PDFs at once — assign category and market for each file before saving.")

    bulk_files = st.file_uploader(
        "Select multiple PDF files",
        type=["pdf"],
        accept_multiple_files=True,
        key="lib_bulk_upload"
    )

    if bulk_files:
        st.markdown(f"**{len(bulk_files)} file(s) selected — assign category and market for each:**")

        try:
            from data.referential import get_cat_labels as _gcl2
            _labels2 = _gcl2()
            all_cats2 = list(_labels2.keys())
            cat_fmt2  = lambda c: f"{c} — {_labels2.get(c,'').split('(')[0].strip()[:40]}"
        except Exception:
            all_cats2 = ["CAT1","CAT2","CAT3","CAT4","CAT5","CAT6","CAT7","CAT8","CAT9"]
            cat_fmt2  = lambda c: c

        try:
            from agent1.watcher import load_sources as _ls2
            _src2 = _ls2("data/sources.json")
            avail_mkts2 = sorted([k for k in _src2 if not k.startswith("_")])
        except Exception:
            avail_mkts2 = ["EU", "France", "Germany", "Spain", "Italy", "UK", "USA", "China", "India", "Canada"]

        bulk_assignments = []
        for i, f in enumerate(bulk_files):
            col_f, col_c, col_m = st.columns([3, 2, 2])
            with col_f:
                st.caption(f"📄 {f.name} · {round(f.size/1024,1)} KB")
            with col_c:
                cat_i = st.selectbox(
                    "Category",
                    options=all_cats2,
                    format_func=cat_fmt2,
                    key=f"bulk_cat_{i}",
                    label_visibility="collapsed"
                )
            with col_m:
                mkt_i = st.selectbox(
                    "Market",
                    options=avail_mkts2,
                    key=f"bulk_mkt_{i}",
                    label_visibility="collapsed"
                )
            bulk_assignments.append((f, cat_i, mkt_i))

        # Détecter les doublons dans la sélection
        combos = [(cat, mkt) for _, cat, mkt in bulk_assignments]
        duplicates = [c for c in set(combos) if combos.count(c) > 1]
        if duplicates:
            st.warning(
                f"⚠️ Duplicate assignments detected: "
                + ", ".join(f"{c} — {m}" for c, m in duplicates)
                + ". Each CAT × Market combination must be unique."
            )
            can_bulk = False
        else:
            can_bulk = True

        if st.button(
            f"💾 Upload all {len(bulk_files)} sheet(s)",
            type="primary",
            key="lib_bulk_save",
            disabled=not can_bulk or not gh_token
        ):
            if not gh_token:
                st.error("GH_TOKEN not configured — cannot upload.")
            else:
                progress = st.progress(0, text="Starting upload...")
                success_count = 0
                errors = []
                for idx, (f, cat_i, mkt_i) in enumerate(bulk_assignments):
                    progress.progress(
                        (idx) / len(bulk_assignments),
                        text=f"Uploading {cat_i} — {mkt_i} ({idx+1}/{len(bulk_assignments)})..."
                    )
                    ok, msg = upload_sheet(
                        pdf_bytes=f.read(),
                        filename=f.name,
                        category=cat_i,
                        market=mkt_i,
                        gh_token=gh_token,
                    )
                    if ok:
                        success_count += 1
                    else:
                        errors.append(f"{cat_i} — {mkt_i}: {msg}")
                    import time as _time
                    _time.sleep(0.5)  # Éviter de saturer l'API GitHub

                progress.progress(1.0, text="Done!")
                if success_count:
                    st.success(f"✅ {success_count}/{len(bulk_assignments)} sheet(s) uploaded successfully.")
                if errors:
                    for err in errors:
                        st.error(err)
                if success_count:
                    st.rerun()

        if not gh_token:
            st.caption("⚠️ GH_TOKEN not configured in Streamlit secrets — bulk upload unavailable.")
