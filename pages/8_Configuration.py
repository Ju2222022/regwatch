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
from data.referential import (
    load_referential, save_referential,
    get_legal_categories, get_cat_labels,
    update_subcategory, update_legal_category,
    add_legal_category, add_subcategory,
)

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")
st.title("⚙️ Configuration")
st.caption("Manage watch sources and legal referential")

SOURCES_FILE = "data/sources.json"

tab_sources, tab_ref = st.tabs(["🌍 Watch Sources", "📚 Legal Referential"])

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
