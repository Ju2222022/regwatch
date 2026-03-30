"""
Page 6 — Agent 4 : Impact Analyzer
Two modes: Product (risk mapping) and Category (legal sheet delta).
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent4.impact import (
    analyze_product_impact,
    analyze_category_impact,
    CAT_DEFINITIONS,
)

st.set_page_config(page_title="Agent 4 — Impact", page_icon="⚡", layout="wide")

CAT_LABELS = {k: v["label"] for k, v in CAT_DEFINITIONS.items()}

URGENCY_COLOR = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
RISK_COLOR    = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "⚪"}

anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Status")
    st.success("Anthropic ✓") if anthropic_key else st.error("ANTHROPIC_API_KEY manquante")

    st.divider()

    # Alertes en mémoire depuis Agent 1
    veille = st.session_state.get("veille_results", [])
    st.header("📡 Available alerts")
    if veille:
        st.success(f"{len(veille)} alert(s) in memory")
        cats_in_alerts = list(set(
            c for e in veille for c in e.get("categories_concerned", [])
        ))
        st.caption("Categories concerned:")
        for c in sorted(cats_in_alerts):
            st.caption(f"  • {c} — {CAT_LABELS.get(c,'')}")
    else:
        st.warning("No alerts in memory.\nRun a watch session from Agent 1 first.")
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

    st.divider()
    st.caption("Alerts are automatically passed from Agent 1 via session state.")

# ── Page principale ───────────────────────────────────────────────────────────
st.title("⚡ Agent 4 — Impact Analyzer")
st.caption("Cross-reference regulatory alerts × product catalog or × legal categories")

# Vérification alertes
veille = st.session_state.get("veille_results", [])
if not veille:
    st.warning("⚠️ No regulatory alerts in memory. Run a watch session from **Agent 1** first.")
    st.stop()

st.info(f"**{len(veille)} alert(s)** from Agent 1 ready for analysis.")

# ── Choix du mode ─────────────────────────────────────────────────────────────
st.subheader("🎯 Analysis mode")

mode = st.radio(
    "What do you want to analyse?",
    [
        "📦 Product Mode — Which products are impacted?",
        "📋 Category Mode — Which legal sheets need updating?",
    ],
    horizontal=False,
)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# MODE PRODUIT
# ══════════════════════════════════════════════════════════════════════════════
if "Product Mode" in mode:
    st.subheader("📦 Product Mode")
    st.caption("Identify which products in your catalog are impacted by regulatory alerts.")

    # Saisie du catalogue
    st.markdown("**Product catalog**")
    st.caption("Enter your products with their regulatory categories (from Agent 3).")

    # Catalogue par défaut — 11 produits PoC
    default_catalog = [
        {"code": "8941337", "name": "FIT100M", "categories": ["CAT3","CAT4","CAT7","CAT9"]},
        {"code": "8931927", "name": "BC500",   "categories": ["CAT3"]},
        {"code": "8918748", "name": "DS100",   "categories": ["CAT3","CAT9"]},
        {"code": "8935832", "name": "Home Trainer", "categories": ["CAT3","CAT4","CAT9"]},
        {"code": "8944010", "name": "DYNAMO100","categories": ["CAT2","CAT3","CAT4"]},
        {"code": "8937261", "name": "HL500",   "categories": ["CAT2","CAT3","CAT4"]},
        {"code": "8928473", "name": "HL50",    "categories": ["CAT2","CAT3"]},
        {"code": "8920154", "name": "Massage gun","categories": ["CAT3","CAT4"]},
        {"code": "8941112", "name": "Massage belt","categories": ["CAT3","CAT4"]},
        {"code": "8939201", "name": "BC100",   "categories": ["CAT3"]},
        {"code": "8916423", "name": "HR Monitor","categories": ["CAT3","CAT9"]},
    ]

    use_default = st.toggle("Use PoC catalog (11 products)", value=True)

    if use_default:
        catalog = default_catalog
        df_cat = pd.DataFrame([{
            "Code": p["code"], "Product": p["name"],
            "Categories": ", ".join(p["categories"])
        } for p in catalog])
        st.dataframe(df_cat, use_container_width=True, hide_index=True)
    else:
        st.caption("Collez votre catalogue en JSON : [{\"code\":\"...\", \"name\":\"...\", \"categories\":[\"CAT3\"]}]")
        catalog_json = st.text_area("Catalogue JSON", height=200,
                                     value=json.dumps(default_catalog[:3], indent=2))
        try:
            catalog = json.loads(catalog_json)
            st.success(f"{len(catalog)} product(s) loaded")
        except Exception as e:
            st.error(f"JSON invalide : {e}")
            catalog = []

    # Filtrer les alertes
    st.markdown("**Alerts to analyze**")
    urgency_filter = st.multiselect(
        "Filtrer par urgence", ["HIGH","MEDIUM","LOW"],
        default=["HIGH","MEDIUM"],
        help="Select urgency levels to include in the analysis"
    )
    filtered_alerts = [e for e in veille if e.get("urgency") in urgency_filter]
    st.caption(f"{len(filtered_alerts)} alert(s) selected out of {len(veille)}")

    launch_product = st.button(
        "⚡ Analyze product impact",
        disabled=not (anthropic_key and catalog and filtered_alerts),
        type="primary"
    )

    if launch_product:
        with st.status("⚡ Analysis in progress...", expanded=True) as status:
            try:
                st.write(f"Cross-referencing {len(filtered_alerts)} alert(s) × {len(catalog)} product(s)...")
                result, token_usage = analyze_product_impact(
                    anthropic_key, filtered_alerts, catalog
                )
                # Stocker pour Agent 5B
                st.session_state["impact_product_result"] = result
                status.update(
                    label=f"✅ Analysis complete · "
                          f"{token_usage['input_tokens']+token_usage['output_tokens']:,} tokens · "
                          ("N/A" if token_usage['cost_usd'] == 0 else f"${token_usage['cost_usd']:.4f}"),
                    state="complete"
                )
            except Exception as e:
                status.update(label=f"❌ Error: {e}", state="error")
                st.stop()

    # Affichage résultats Product Mode
    if "impact_product_result" in st.session_state:
        result = st.session_state["impact_product_result"]
        impacted = result.get("impacted_products", [])
        non_impacted = result.get("non_impacted_products", [])

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Impacted products",     len(impacted))
        c2.metric("Non-impacted products", len(non_impacted))
        c3.metric("Analyzed alerts",     len(filtered_alerts))

        if result.get("summary"):
            st.info(result["summary"])

        # Heat map simplifiée
        st.subheader("🗺️ Risk Map")
        for level in ["HIGH","MEDIUM","LOW"]:
            level_products = [p for p in impacted if p.get("risk_score")==level]
            if not level_products: continue
            icon = RISK_COLOR[level]
            st.markdown(f"#### {icon} Risk {level} — {len(level_products)} product(s)")
            for prod in level_products:
                with st.expander(
                    f"{icon} {prod.get('name','?')} ({prod.get('code','')}) — "
                    f"{', '.join(prod.get('categories',[]))}"
                ):
                    st.markdown(f"**Risk summary**: {prod.get('risk_summary','—')}")
                    st.markdown("**Applicable alerts**")
                    for alert in prod.get("applicable_alerts", []):
                        a_icon = URGENCY_COLOR.get(alert.get("alert_urgency","LOW"),"⚪")
                        st.markdown(f"{a_icon} **{alert.get('alert_title','?')}**")
                        st.caption(f"↳ Raison : {alert.get('reason','')}")
                        if alert.get("action"):
                            st.info(f"⚙️ Action : {alert['action']}")

        if non_impacted:
            st.markdown(f"#### ⚪ Non-impacted — {len(non_impacted)} product(s)")
            st.caption(", ".join(non_impacted))

        # Export CSV
        rows = []
        for p in impacted:
            for alert in p.get("applicable_alerts", []):
                rows.append({
                    "Code":         p.get("code",""),
                    "Product":      p.get("name",""),
                    "Categories":   ", ".join(p.get("categories",[])),
                    "Risk":       p.get("risk_score",""),
                    "Alert":       alert.get("alert_title",""),
                    "Urgency":      alert.get("alert_urgency",""),
                    "Raison":       alert.get("reason",""),
                    "Action":       alert.get("action",""),
                })
        if rows:
            df_export = pd.DataFrame(rows)
            st.download_button(
                "⬇️ Export Risk Map CSV",
                df_export.to_csv(index=False).encode("utf-8"),
                f"regwatch_risk_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                "text/csv"
            )
        st.info("💾 Results available for Agent 5B (Risk Mapper).")

# ══════════════════════════════════════════════════════════════════════════════
# MODE CATÉGORIE
# ══════════════════════════════════════════════════════════════════════════════
else:
    st.subheader("📋 Category Mode")
    st.caption("Identify which legal sheets need updating based on the new alerts.")

    # Sélection des catégories actives
    st.markdown("**Active categories scope**")
    st.caption("Select the categories used by Decathlon for its products.")

    all_cats = list(CAT_DEFINITIONS.keys())
    active_cats = st.multiselect(
        "Active categories",
        options=all_cats,
        default=["CAT1","CAT2","CAT3","CAT4","CAT7","CAT9"],
        format_func=lambda c: f"{c} — {CAT_LABELS.get(c,'')}"
    )

    # Filtrer les alertes
    st.markdown("**Alerts to analyze**")
    urgency_filter_cat = st.multiselect(
        "Filtrer par urgence", ["HIGH","MEDIUM","LOW"],
        default=["HIGH","MEDIUM"],
        key="urgency_cat"
    )
    filtered_alerts_cat = [e for e in veille if e.get("urgency") in urgency_filter_cat]
    st.caption(f"{len(filtered_alerts_cat)} alert(s) selected")

    launch_cat = st.button(
        "⚡ Analyze category impacts",
        disabled=not (anthropic_key and active_cats and filtered_alerts_cat),
        type="primary"
    )

    if launch_cat:
        with st.status("⚡ Analysis in progress...", expanded=True) as status:
            try:
                st.write(f"Cross-referencing {len(filtered_alerts_cat)} alert(s) × {len(active_cats)} categorie(s)...")
                result_cat, token_usage_cat = analyze_category_impact(
                    anthropic_key, filtered_alerts_cat, active_cats
                )
                st.session_state["impact_category_result"] = result_cat
                cost_str_cat = "N/A" if token_usage_cat['cost_usd'] == 0 else f"${token_usage_cat['cost_usd']:.4f}"
                status.update(
                    label=f"✅ Analysis complete · {token_usage_cat['input_tokens']+token_usage_cat['output_tokens']:,} tokens · {cost_str_cat}",
                    state="complete"
                )
            except Exception as e:
                status.update(label=f"❌ Error: {e}", state="error")
                st.stop()

    # Category Mode results
    if "impact_category_result" in st.session_state:
        result_cat = st.session_state["impact_category_result"]
        cat_impacts = result_cat.get("category_impacts", [])
        no_update   = result_cat.get("categories_no_update", [])
        total_upd   = result_cat.get("total_updates_required", 0)

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Categories to update", len(cat_impacts))
        c2.metric("Categories with no changes", len(no_update))
        c3.metric("Total updates required", total_upd)

        if result_cat.get("summary"):
            st.info(result_cat["summary"])

        st.subheader("📋 Legal sheets to update")
        for level in ["HIGH","MEDIUM","LOW"]:
            level_cats = [c for c in cat_impacts if c.get("update_priority")==level]
            if not level_cats: continue
            icon = RISK_COLOR[level]
            st.markdown(f"#### {icon} Priority {level} — {len(level_cats)} categorie(s)")
            for cat_item in level_cats:
                cat_code = cat_item.get("category","?")
                with st.expander(
                    f"{icon} {cat_code} — {cat_item.get('label','')} "
                    f"({len(cat_item.get('applicable_alerts',[]))} alert(s))"
                ):
                    st.markdown(f"**Summary**: {cat_item.get('update_summary','—')}")
                    for alert in cat_item.get("applicable_alerts", []):
                        a_icon = URGENCY_COLOR.get(alert.get("alert_urgency","LOW"),"⚪")
                        change = alert.get("change_type","")
                        st.markdown(f"{a_icon} **{alert.get('alert_title','?')}** `{change}`")
                        if alert.get("update_description"):
                            st.info(f"📝 Sheet update: {alert['update_description']}")

        if no_update:
            st.markdown(f"#### ⚪ No update required")
            st.caption(", ".join(f"{c} ({CAT_LABELS.get(c,'')})" for c in no_update))

        # Export
        rows_cat = []
        for cat_item in cat_impacts:
            for alert in cat_item.get("applicable_alerts",[]):
                rows_cat.append({
                    "Category":    cat_item.get("category",""),
                    "Label":        cat_item.get("label",""),
                    "Priority":     cat_item.get("update_priority",""),
                    "Alert":       alert.get("alert_title",""),
                    "Urgency":      alert.get("alert_urgency",""),
                    "Change type": alert.get("change_type",""),
                    "Update":  alert.get("update_description",""),
                })
        if rows_cat:
            df_cat_exp = pd.DataFrame(rows_cat)
            st.download_button(
                "⬇️ Export category analysis CSV",
                df_cat_exp.to_csv(index=False).encode("utf-8"),
                f"regwatch_cat_impact_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                "text/csv"
            )
        st.info("💾 Results available for Agent 5A (Legal Sheet Updater).")
# ── Send to buttons ───────────────────────────────────────────────────────────
_has_product = "impact_product_result" in st.session_state
_has_category = "impact_category_result" in st.session_state

if _has_product or _has_category:
    st.divider()
    cols = st.columns(2)
    if _has_product:
        with cols[0]:
            with st.container(border=True):
                st.markdown("**➡️ Product results ready**")
                if st.button("🗺️ Send to Agent 5B — Risk Map", type="primary", key="send_to_5b"):
                    st.switch_page("pages/4_Risk_Map.py")
                st.caption("Generate a risk mapping per product from the impact analysis.")
    if _has_category:
        with cols[1]:
            with st.container(border=True):
                st.markdown("**➡️ Category results ready**")
                if st.button("📋 Send to Agent 5A — Legal Sheet", type="primary", key="send_to_5a"):
                    st.switch_page("pages/3_Legal_Sheet.py")
                st.caption("Update legal sheets based on the category impact analysis.")


