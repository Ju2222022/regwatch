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

st.set_page_config(page_title="Agent 5B — Risk Mapping", page_icon="🗺️", layout="wide")

anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Statut")
    st.success("Anthropic ✓") if anthropic_key else st.error("ANTHROPIC_API_KEY manquante")
    st.divider()

    impact = st.session_state.get("impact_product_result", {})
    agent5a = st.session_state.get("5a_export_approved", [])

    st.header("📥 Données disponibles")
    if impact:
        impacted = impact.get("impacted_products", [])
        non_impacted = impact.get("non_impacted_products", [])
        all_products = impacted + non_impacted
        st.success(f"Agent 4 ✓ — {len(impacted)} impacté(s) · {len(non_impacted)} non impacté(s)")
    else:
        st.warning("Aucun résultat Agent 4.\nLancez Agent 4 Mode Produit.")

    if agent5a:
        st.success(f"Agent 5A ✓ — {len(agent5a)} section(s) approuvée(s)")
    else:
        st.info("Agent 5A : aucune mise à jour\n(comparaison avant/après désactivée)")

    st.divider()
    st.caption("Flux : Agent 1 → Agent 4 (Mode Produit) → Agent 5B")

# ── Page principale ───────────────────────────────────────────────────────────
st.title("🗺️ Agent 5B — Risk Mapper")
st.caption("Risk mapping réglementaire par produit · 3 niveaux de lecture")

# ── Étape 1 — Vérification des données ───────────────────────────────────────
st.subheader("① Données source")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Agent 4 — Impact produit**")
    if impact:
        impacted_    = impact.get("impacted_products", [])
        non_imp_     = impact.get("non_impacted_products", [])
        all_products = impacted_ + non_imp_
        st.success(f"✓ {len(impacted_)} produit(s) impacté(s) · {len(non_imp_)} non impacté(s)")
        with st.expander("Aperçu"):
            for p in impacted_[:3]:
                name = p.get("product_name", p.get("name", ""))
                risk = p.get("risk_level", p.get("overall_risk", ""))
                st.caption(f"• 🔴 {name} — {risk}")
            if len(impacted_) > 3:
                st.caption(f"... et {len(impacted_)-3} autre(s) impacté(s)")
    else:
        all_products = []
        st.error("Manquant — lancez Agent 4 Mode Produit")

with col2:
    st.markdown("**Agent 5A — Mises à jour approuvées**")
    if agent5a:
        st.success(f"✓ {len(agent5a)} section(s) — comparaison avant/après activée")
        with st.expander("Aperçu"):
            for upd in agent5a[:3]:
                st.caption(f"• {upd.get('section_label','?')} ({upd.get('action','')})")
    else:
        st.info("Non disponible — l'analyse sera faite sans comparaison avant/après")

    # Import manuel des données 5A si pas en session
    if not agent5a:
        uploaded = st.file_uploader(
            "Importer le JSON Agent 5A (optionnel)",
            type=["json"],
            key="5b_import_5a"
        )
        if uploaded:
            try:
                data_5a = json.loads(uploaded.read())
                agent5a = data_5a.get("approved_updates", [])
                st.session_state["5a_export_approved"] = agent5a
                st.success(f"✓ {len(agent5a)} section(s) importée(s)")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur import : {e}")

st.divider()

# ── Étape 2 — Lancement ──────────────────────────────────────────────────────
st.subheader("② Génération du risk mapping")

col_l, col_i = st.columns([2, 3])
with col_i:
    if not impact:
        st.warning("Lancez d'abord Agent 4 en Mode Produit.")
        imp_ = impact.get("impacted_products", [])
        before_after = "activée" if agent5a else "désactivée (pas de données 5A)"
        st.info(
            f"{len(imp_)} produit(s) impacté(s) à analyser  \n"
            f"Comparaison avant/après : **{before_after}**  \n"
            f"Coût estimé : ~$0.05"
        )

with col_l:
    launch = st.button(
        "🗺️ Générer le risk mapping",
        disabled=not (anthropic_key and bool(impact)),
        type="primary",
        use_container_width=True
    )

if launch:
    with st.status("🗺️ Génération en cours...", expanded=True) as status:
        try:
            imp__ = impact.get("impacted_products", [])
            st.write(f"Analyse de {len(imp__)} produit(s) impacté(s)...")
            if agent5a:
                st.write(f"Intégration de {len(agent5a)} mise(s) à jour Agent 5A...")
            result, token_usage = generate_risk_mapping(
                anthropic_key=anthropic_key,
                impact_product_result=impact,
                agent5a_approved=agent5a or [],
            )
            st.session_state["5b_result"] = result
            n_prod = len(result.get("products", []))
            n_high = result.get("executive_summary", {}).get("total_high", 0)
            status.update(
                label=(
                    f"✅ Risk mapping terminé · {n_prod} produit(s) · "
                    f"{n_high} risque(s) HIGH · "
                    f"{token_usage['input_tokens']+token_usage['output_tokens']:,} tokens · "
                    f"${token_usage['cost_usd']:.4f}"
                ),
                state="complete"
            )
        except Exception as e:
            status.update(label=f"❌ Erreur : {e}", state="error")
            st.error(str(e))
            st.stop()

# ── Résultats ─────────────────────────────────────────────────────────────────
if "5b_result" in st.session_state:
    result   = st.session_state["5b_result"]
    products = result.get("products", [])
    exec_sum = result.get("executive_summary", {})
    reg_view = result.get("regulatory_view", [])

    st.divider()
    st.subheader("③ Résultats")

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
        "📊 Vue Exécutive",
        "📦 Vue Produit",
        "📋 Vue Réglementaire"
    ])

    # ── Onglet 1 : Vue Exécutive ─────────────────────────────────────────────
    with tab_exec:
        st.markdown("*Synthèse pour la direction — niveau de risque global par produit*")

        risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
        delta_icon = {"IMPROVED": "⬇️ Amélioré", "UNCHANGED": "➡️ Inchangé", "WORSENED": "⬆️ Dégradé"}

        has_5a = any(p.get("risk_delta") and p.get("risk_delta") != "UNCHANGED" for p in products)

        rows = []
        for p in products:
            row = {
                "Produit": p.get("product_name", p.get("product_code", "")),
                "Catégories": ", ".join(p.get("categories", [])),
                "Risque actuel": f"{risk_icon.get(p.get('risk_before',''),'?')} {p.get('risk_before','')}",
            }
            if has_5a or agent5a:
                row["Risque après 5A"] = f"{risk_icon.get(p.get('risk_after',''),'?')} {p.get('risk_after','')}"
                row["Évolution"] = delta_icon.get(p.get("risk_delta", ""), "—")
            row["Synthèse"] = p.get("executive_note", "")
            rows.append(row)

        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if agent5a:
            st.caption("⚠️ *Les valeurs 'après 5A' sont une simulation — la conformité réelle dépend de l'implémentation dans My Conformity Box.*")

    # ── Onglet 2 : Vue Produit ───────────────────────────────────────────────
    with tab_prod:
        st.markdown("*Détail par produit — actions correctives pour les chefs de produit*")

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

                # Non-conformités
                non_conf = p.get("non_conformities", [])
                if non_conf:
                    st.markdown("**Non-conformités**")
                    nc_rows = []
                    for nc in non_conf:
                        row_nc = {
                            "Réglementation": nc.get("regulation", ""),
                            "Avant": nc.get("status_before", ""),
                        }
                        if agent5a:
                            row_nc["Après 5A"] = nc.get("status_after", "")
                            row_nc["Résolu par"] = nc.get("resolved_by") or "—"
                        nc_rows.append(row_nc)
                    st.dataframe(pd.DataFrame(nc_rows), use_container_width=True, hide_index=True)

                # Actions correctives
                actions = p.get("corrective_actions", [])
                if actions:
                    st.markdown("**Actions correctives**")
                    prio_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
                    for a in actions:
                        col_p, col_a, col_d, col_o = st.columns([1, 4, 2, 2])
                        col_p.markdown(f"{prio_icon.get(a.get('priority',''),'⚪')} {a.get('priority','')}")
                        col_a.markdown(a.get("action", ""))
                        col_d.caption(a.get("deadline", ""))
                        col_o.caption(a.get("owner", ""))

    # ── Onglet 3 : Vue Réglementaire ─────────────────────────────────────────
    with tab_reg:
        st.markdown("*Par réglementation — pour le responsable affaires réglementaires*")

        for reg in reg_view:
            urg = reg.get("urgency", "")
            icon_u = risk_icon.get(urg, "⚪")
            n_affected = len(reg.get("products_affected", []))

            with st.expander(
                f"{icon_u} **{reg.get('regulation', '')}** — {n_affected} produit(s) concerné(s)",
                expanded=(urg == "HIGH")
            ):
                col_b, col_a = st.columns(2)
                col_b.metric("Conformité actuelle", reg.get("compliance_rate_before", "—"))
                if agent5a:
                    col_a.metric("Conformité après 5A *(simulation)*",
                                 reg.get("compliance_rate_after", "—"))

                if reg.get("products_affected"):
                    st.markdown("**Produits concernés :**")
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
        "⬇️ Exporter JSON complet",
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
            "⬇️ Exporter CSV (vue exécutive)",
            df_export.to_csv(index=False).encode("utf-8"),
            f"regwatch_riskmap_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
