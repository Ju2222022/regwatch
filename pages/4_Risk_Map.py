"""
Page 8 — Agent 5B : Risk Mapper
Génère le risk mapping produit à partir de Agent 4 Mode Produit,
avec comparaison avant/après les mises à jour Agent 5A.
"""

import streamlit as st
import json
import pandas as pd
from datetime import datetime
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent5b.risk_mapper import generate_risk_mapping
try:
    from utils.legal_sheet_library import load_index, fetch_sheet_text, list_available_sheets
    LIBRARY_AVAILABLE = True
except Exception:
    LIBRARY_AVAILABLE = False

st.set_page_config(page_title="Agent 5B — Risk Map", page_icon="🗺️", layout="wide")

anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Status")
    st.success("Anthropic ✓") if anthropic_key else st.error("ANTHROPIC_API_KEY missing")
    st.divider()

    impact = st.session_state.get("impact_product_result", {})
    agent5a = st.session_state.get("5a_export_approved", [])

    st.header("📥 Available data")
    if impact:
        impacted = impact.get("impacted_products", [])
        non_impacted = impact.get("non_impacted_products", [])
        all_products = impacted + non_impacted
        st.success(f"Agent 4 ✓ — {len(impacted)} impacted · {len(non_impacted)} non impacted")
        if impacted:
            st.markdown("**Impacted products:**")
            _risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
            for _p in impacted:
                _name = _p.get("product_name", _p.get("name", _p.get("code", "?")))
                _risk = _p.get("risk_score", _p.get("risk_level", ""))
                st.caption(f"{_risk_icon.get(_risk,'⚪')} {_name}")
    else:
        st.warning("No Agent 4 results.\nRun Agent 4 in Product Mode first.")

    if agent5a:
        st.success(f"Agent 5A ✓ — {len(agent5a)} section(s) approuvée(s)")
    else:
        st.info("Agent 5A: no updates\n(before/after comparison disabled)")

    st.divider()
    st.caption("Workflow: Agent 1 → Agent 4 (Product Mode) → Agent 5B")
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
st.title("🗺️ Agent 5B — Risk Mapper")
st.caption("Regulatory risk mapping by product · 3 reading levels")

# ── Étape 1 — Vérification des données ───────────────────────────────────────
st.subheader("① Data sources")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Agent 4 — Product impact**")
    if impact:
        impacted_    = impact.get("impacted_products", [])
        non_imp_     = impact.get("non_impacted_products", [])
        all_products = impacted_ + non_imp_
        st.success(f"✓ {len(impacted_)} product(s) impacted · {len(non_imp_)} non impacted")
        with st.expander("Preview"):
            for p in impacted_[:3]:
                name = p.get("product_name", p.get("name", ""))
                risk = p.get("risk_level", p.get("overall_risk", ""))
                st.caption(f"• 🔴 {name} — {risk}")
            if len(impacted_) > 3:
                st.caption(f"... et {len(impacted_)-3} autre(s) impacted")
    else:
        all_products = []
        st.error("Missing — run Agent 4 in Product Mode")

with col2:
    st.markdown("**Agent 5A — Approved updates**")
    if agent5a:
        st.success(f"✓ {len(agent5a)} section(s) — before/after comparison enabled")
        with st.expander("Preview"):
            for upd in agent5a[:3]:
                st.caption(f"• {upd.get('section_label','?')} ({upd.get('action','')})")
    else:
        st.info("Not available — analysis will run without before/after comparison")

    # Import manuel des données 5A si pas en session
    if not agent5a:
        uploaded = st.file_uploader(
            "Import Agent 5A JSON (optional)",
            type=["json"],
            key="5b_import_5a"
        )
        if uploaded:
            try:
                data_5a = json.loads(uploaded.read())
                agent5a = data_5a.get("approved_updates", [])
                st.session_state["5a_export_approved"] = agent5a
                st.success(f"✓ {len(agent5a)} section(s) imported")
                st.rerun()
            except Exception as e:
                st.error(f"Import error: {e}")

st.divider()

# ── Étape 2 — Mode d'analyse + lancement ─────────────────────────────────────
st.subheader("② Analysis mode")

# Sélecteur de mode
analysis_mode = st.radio(
    "Base the risk analysis on:",
    [
        "📡 Regulatory alerts (Agent 4 output)",
        "📚 Updated legal sheet (Agent 5A — from library)",
    ],
    horizontal=True,
    key="5b_analysis_mode",
    help=(
        "**Alerts mode**: risk is assessed against raw regulatory alerts from Agent 4.\n\n"
        "**Legal sheet mode**: risk is assessed against the legal sheet AFTER Agent 5A approved updates — "
        "shows the real before/after compliance gap."
    )
)

# Si mode fiche légale — charger depuis bibliothèque
sheet_context = None
if "Legal sheet" in analysis_mode and LIBRARY_AVAILABLE:
    st.markdown("**Legal sheet source**")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        try:
            from data.referential import get_cat_labels as _gcl
            _labels = _gcl()
            all_cats_5b = list(_labels.keys())
            cat_fmt_5b  = lambda c: f"{c} — {_labels.get(c,'').split('(')[0].strip()[:40]}"
        except Exception:
            all_cats_5b = ["CAT1","CAT2","CAT3","CAT4","CAT5","CAT6","CAT7","CAT8","CAT9"]
            cat_fmt_5b  = lambda c: c
        sheet_cat = st.selectbox("Category", all_cats_5b, format_func=cat_fmt_5b, key="5b_sheet_cat")
    with col_s2:
        _gh_token_5b = st.secrets.get("GH_TOKEN", "")
        _index_5b = load_index(_gh_token_5b)
        _sheets_5b = list_available_sheets(_index_5b)
        _markets_5b = sorted(list({s["market"] for s in _sheets_5b})) or ["EU", "France"]
        sheet_market = st.selectbox("Market", _markets_5b, key="5b_sheet_market")

    # Vérifier si la fiche existe
    _entry_5b = next(
        (s for s in _sheets_5b if s["category"] == sheet_cat and s["market"] == sheet_market),
        None
    )
    if _entry_5b:
        st.success(f"📚 Sheet available: **{sheet_cat} — {sheet_market}** (uploaded {_entry_5b.get('uploaded','')})")
        sheet_context = {"category": sheet_cat, "market": sheet_market}
    else:
        st.warning(f"No sheet found for **{sheet_cat} — {sheet_market}** in library. Upload it via Configuration → Legal Sheet Library.")
        sheet_context = None

elif "Legal sheet" in analysis_mode and not LIBRARY_AVAILABLE:
    st.error("Library module not available.")

st.divider()
st.subheader("③ Risk mapping generation")

col_l, col_i = st.columns([2, 3])
with col_i:
    if not impact:
        st.warning("Run Agent 4 in Product Mode first.")
    else:
        imp_ = impact.get("impacted_products", [])
        mode_label = "Updated legal sheet" if "Legal sheet" in analysis_mode else "Regulatory alerts"
        ba_status = "enabled" if (agent5a or sheet_context) else "disabled (no 5A data)"
        st.info(
            f"{len(imp_)} impacted product(s) to analyze  \n"
            f"Analysis basis: **{mode_label}**  \n"
            f"Before/after comparison: **{ba_status}**  \n"
            f"Estimated cost: ~$0.05"
        )

with col_l:
    launch = st.button(
        "🗺️ Generate risk mapping",
        disabled=not (anthropic_key and bool(impact)),
        type="primary",
        use_container_width=True
    )

if launch:
    with st.status("🗺️ Generating...", expanded=True) as status:
        try:
            # Charger la fiche légale si mode bibliothèque
            _agent5a_final = agent5a or []
            if "Legal sheet" in analysis_mode and sheet_context:
                gh_token_5b = st.secrets.get("GH_TOKEN", "")
                st.write(f"Loading legal sheet {sheet_context['category']} — {sheet_context['market']} from library...")
                _sheet_text, _sheet_title = fetch_sheet_text(
                    sheet_context["category"], sheet_context["market"], gh_token_5b
                )
                if _sheet_text:
                    # Construire un contexte 5A synthétique depuis la fiche
                    _agent5a_final = [{
                        "section_label": "Legal sheet reference",
                        "action": "approved",
                        "final_text": _sheet_text[:3000],
                        "update_reason": f"Reference sheet {sheet_context['category']} — {sheet_context['market']}",
                        "priority": "HIGH",
                    }]
                    st.write(f"✅ Sheet loaded — {len(_sheet_text):,} chars")
                else:
                    st.warning("Could not load sheet — falling back to alerts mode.")

            imp__ = impact.get("impacted_products", [])
            n_batches__ = max(1, -(-len(imp__) // 4))
            st.write(f"Analysing {len(imp__)} impacted product(s) in {n_batches__} batch(es)...")
            if _agent5a_final:
                st.write(f"Integrating {len(_agent5a_final)} context element(s) for before/after comparison...")
            result, token_usage = generate_risk_mapping(
                anthropic_key=anthropic_key,
                impact_product_result=impact,
                agent5a_approved=_agent5a_final or [],
            )
            st.session_state["5b_result"] = result
            n_prod = len(result.get("products", []))
            n_high = result.get("executive_summary", {}).get("total_high", 0)
            total_tok = token_usage['input_tokens'] + token_usage['output_tokens']
            _cost_5b = "N/A" if token_usage['cost_usd'] == 0 else f"${token_usage['cost_usd']:.4f}"
            status.update(
                label=f"✅ Risk mapping complete · {n_prod} product(s) · {n_high} HIGH risk(s) · {total_tok:,} tokens · {_cost_5b}",
                state="complete"
            )
            if "session_tokens" not in st.session_state:
                st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
            st.session_state["session_tokens"]["input"]    += token_usage.get("input_tokens", 0)
            st.session_state["session_tokens"]["output"]   += token_usage.get("output_tokens", 0)
            st.session_state["session_tokens"]["cost_usd"] += token_usage.get("cost_usd", 0.0)
            st.session_state["session_tokens"]["calls"]    += 1
        except Exception as e:
            status.update(label=f"❌ Error: {e}", state="error")
            st.error(str(e))
            st.stop()

# ── Results ─────────────────────────────────────────────────────────────────
if "5b_result" in st.session_state:
    result   = st.session_state["5b_result"]
    products = result.get("products", [])
    exec_sum = result.get("executive_summary", {})
    reg_view = result.get("regulatory_view", [])

    st.divider()
    st.subheader("④ Results")

    # Bandeau exécutif
    n_h = exec_sum.get("total_high", 0)
    n_m = exec_sum.get("total_medium", 0)
    n_l = exec_sum.get("total_low", 0)

    st.markdown(
        f"**{exec_sum.get('key_message', '')}**  \n"
        f"🔴 {n_h} HIGH &nbsp;|&nbsp; 🟡 {n_m} MEDIUM &nbsp;|&nbsp; 🟢 {n_l} LOW"
    )

    st.divider()

    # 3 onglets
    tab_exec, tab_prod, tab_reg = st.tabs([
        "📊 Executive View",
        "📦 Product View",
        "📋 Regulatory View"
    ])

    # ── Onglet 1 : Executive View ─────────────────────────────────────────────
    with tab_exec:
        st.markdown("*Summary for management — global risk level per product*")

        risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
        delta_icon = {"IMPROVED": "⬇️ Improved", "UNCHANGED": "➡️ Unchanged", "WORSENED": "⬆️ Worsened"}

        has_5a = any(p.get("risk_delta") and p.get("risk_delta") != "UNCHANGED" for p in products)

        rows = []
        for p in products:
            row = {
                "Product": p.get("product_name", p.get("product_code", "")),
                "Categories": ", ".join(p.get("categories", [])),
                "Current risk": f"{risk_icon.get(p.get('risk_before',''),'?')} {p.get('risk_before','')}",
            }
            if has_5a or agent5a:
                row["Risk after 5A"] = f"{risk_icon.get(p.get('risk_after',''),'?')} {p.get('risk_after','')}"
                row["Change"] = delta_icon.get(p.get("risk_delta", ""), "—")
            row["Summary"] = p.get("executive_note", "")
            rows.append(row)

        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if agent5a:
            st.caption("⚠️ *After 5A values are simulated — actual compliance depends on implementation in My Conformity Box.*")

    # ── Onglet 2 : Product View ───────────────────────────────────────────────
    with tab_prod:
        st.markdown("*Product detail — corrective actions for product managers*")

        for p in products:
            risk_b = p.get("risk_before", "")
            risk_a = p.get("risk_after", "")
            icon_b = risk_icon.get(risk_b, "?")
            icon_a = risk_icon.get(risk_a, "?")
            delta  = delta_icon.get(p.get("risk_delta", ""), "")

            header = f"{icon_b} **{p.get('product_name', p.get('product_code', ''))}**"
            if agent5a and risk_b != risk_a:
                header += f" → {icon_a} {delta}"

            with st.expander(header, expanded=(risk_b == "HIGH")):

                # Non-conformities
                non_conf = p.get("non_conformities", [])
                if non_conf:
                    st.markdown("**Non-conformities**")
                    nc_rows = []
                    for nc in non_conf:
                        row_nc = {
                            "Regulation": nc.get("regulation", ""),
                            "Before": nc.get("status_before", ""),
                        }
                        if agent5a:
                            row_nc["After 5A"] = nc.get("status_after", "")
                            row_nc["Resolved by"] = nc.get("resolved_by") or "—"
                        nc_rows.append(row_nc)
                    st.dataframe(pd.DataFrame(nc_rows), use_container_width=True, hide_index=True)

                # Corrective actions
                actions = p.get("corrective_actions", [])
                if actions:
                    st.markdown("**Corrective actions**")
                    prio_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
                    for a in actions:
                        col_p, col_a, col_d, col_o = st.columns([1, 4, 2, 2])
                        col_p.markdown(f"{prio_icon.get(a.get('priority',''),'⚪')} {a.get('priority','')}")
                        col_a.markdown(a.get("action", ""))
                        col_d.caption(a.get("deadline", ""))
                        col_o.caption(a.get("owner", ""))

    # ── Onglet 3 : Regulatory View ─────────────────────────────────────────
    with tab_reg:
        st.markdown("*By regulation — for the regulatory affairs manager*")

        for reg in reg_view:
            urg = reg.get("urgency", "")
            icon_u = risk_icon.get(urg, "⚪")
            n_affected = len(reg.get("products_affected", []))

            with st.expander(
                f"{icon_u} **{reg.get('regulation', '')}** — {n_affected} product(s) concerné(s)",
                expanded=(urg == "HIGH")
            ):
                col_b, col_a = st.columns(2)
                def _fr_compliance(rate_str):
                    """Translates compliance rate to display string."""
                    if not rate_str or rate_str == "—":
                        return "—"
                    return (rate_str
                        .replace("products compliant", "product(s) conforme(s)")
                        
                        
                        .replace("All products compliant", "Tous conformes"))

                col_b.metric("Current compliance", _fr_compliance(reg.get("compliance_rate_before", "—")))
                if agent5a:
                    col_a.metric("Compliance after 5A *(simulation)*",
                                 _fr_compliance(reg.get("compliance_rate_after", "—")))

                if reg.get("products_affected"):
                    st.markdown("**Affected products:**")
                    # Trouver les noms depuis la liste produits
                    name_map = {p.get("product_code",""): p.get("product_name","") for p in products}
                    for code in reg["products_affected"]:
                        name = name_map.get(code, code)
                        prod_risk = next(
                            (p.get("risk_before","") for p in products
                             if p.get("product_code","") == code), ""
                        )
                        st.caption(f"• {name} — {risk_icon.get(prod_risk,'?')} {prod_risk}")

    # ── Export ───────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("④ Export")

    export_data = {
        "generated_at": datetime.now().isoformat(),
        "agent4_source": "session_state[impact_product_result]",
        "agent5a_updates_used": len(agent5a),
        "simulation_note": (
            "AFTER values are simulated — actual compliance depends on "
            "implementation in My Conformity Box"
        ) if agent5a else None,
        **result
    }

    col_dl1, col_dl2 = st.columns(2)
    col_dl1.download_button(
        "⬇️ Export full JSON",
        json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8"),
        f"regwatch_riskmap_{datetime.now().strftime('%Y%m%d')}.json",
        "application/json"
    )

    # CSV synthétique pour vue exécutive
    if products:
        csv_rows = []
        for p in products:
            csv_rows.append({
                "product_code": p.get("product_code", ""),
                "product_name": p.get("product_name", ""),
                "categories": ", ".join(p.get("categories", [])),
                "risk_before": p.get("risk_before", ""),
                "risk_after": p.get("risk_after", ""),
                "risk_delta": p.get("risk_delta", ""),
                "non_conformities_count": len(p.get("non_conformities", [])),
                "actions_count": len(p.get("corrective_actions", [])),
                "executive_note": p.get("executive_note", ""),
            })
        df_export = pd.DataFrame(csv_rows)
        col_dl2.download_button(
            "⬇️ Export CSV (executive view)",
            df_export.to_csv(index=False).encode("utf-8"),
            f"regwatch_riskmap_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
