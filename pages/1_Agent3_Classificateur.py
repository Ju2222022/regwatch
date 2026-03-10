"""
Page 1 — Agent 3 : Classificateur Réglementaire
Interface Streamlit pour classer un produit manuellement ou en batch
"""

import streamlit as st
import pandas as pd
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent3.classifier import classify_product, classify_batch

st.set_page_config(page_title="Agent 3 — Classificateur", page_icon="🏷️", layout="wide")
st.title("🏷️ Agent 3 — Classificateur Réglementaire")

# ── Clé API — chargée automatiquement depuis les Secrets Streamlit ───────────
api_key = st.secrets.get("OPENROUTER_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Configuration")
    if api_key:
        st.success("Clé API chargée ✓")
    else:
        # Fallback : saisie manuelle si le secret n'est pas configuré
        st.warning("Secret OPENROUTER_API_KEY non trouvé dans les Secrets Streamlit")
        api_key = st.text_input("Clé API Groq (secours)", type="password",
                                 help="Configurez OPENROUTER_API_KEY dans Settings > Secrets")

# ── Mapping catégories ────────────────────────────────────────────────────────
CAT_LABELS = {
    "CAT1": "🔋 Batteries & accumulateurs",
    "CAT2": "💡 Lampes & éclairage",
    "CAT3": "⚡ Équipements électroniques (base)",
    "CAT4": "🔌 Chargeurs & produits rechargeables",
    "CAT5": "📡 Caméra / ANT+",
    "CAT6": "🎵 Lecteur MP3",
    "CAT7": "🛰️ GPS / Radio / Talkie / Télémètre",
    "CAT8": "📶 Téléphone / Wifi",
    "CAT9": "📲 Équipement Bluetooth",
}

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🔍 Classifier un produit", "📋 Batch — plusieurs produits"])

# ── TAB 1 : Produit unique ────────────────────────────────────────────────────
with tab1:
    st.subheader("Classifier un produit")
    
    col1, col2 = st.columns(2)
    with col1:
        model_code = st.text_input("Code modèle", placeholder="ex: 8941337")
        product_name = st.text_input("Nom commercial", placeholder="ex: FIT100M")
    with col2:
        product_type = st.text_input("Type / Description", placeholder="ex: Smartwatch GPS Bluetooth")
        extra_info = st.text_input("Infos complémentaires (optionnel)", 
                                    placeholder="ex: slug URL, specs partielles...")

    if st.button("🚀 Classifier", disabled=not api_key, type="primary"):
        if not product_name or not product_type:
            st.error("Nom et type requis.")
        else:
            with st.spinner("Classification en cours..."):
                try:
                    result = classify_product(api_key, model_code, product_name, product_type, extra_info)
                    
                    # ── Résultat principal
                    st.success("Classification terminée")
                    
                    col_a, col_b = st.columns([2, 1])
                    with col_a:
                        st.markdown("### 📂 Catégories assignées")
                        for cat in result.get("assigned_categories", []):
                            label = CAT_LABELS.get(cat, cat)
                            justif = result.get("category_justification", {}).get(cat, "")
                            st.markdown(f"**{cat}** — {label}")
                            if justif:
                                st.caption(f"↳ {justif}")
                    
                    with col_b:
                        confidence = result.get("confidence_global", "?")
                        color = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(confidence, "⚪")
                        st.metric("Confiance globale", f"{color} {confidence}")
                        
                        techs = result.get("detected_technologies", {})
                        confirmed = techs.get("confirmed", [])
                        if confirmed:
                            st.markdown("**Technologies confirmées**")
                            for t in confirmed:
                                st.markdown(f"- {t}")

                    # ── Flags
                    flags = result.get("flags", {})
                    to_confirm = flags.get("protocol_to_confirm", [])
                    if_confirmed = flags.get("categories_if_confirmed", [])
                    edge_cases = flags.get("regulatory_edge_cases", [])
                    
                    if to_confirm or if_confirmed or edge_cases:
                        st.markdown("### ⚠️ Points d'attention")
                        for f in to_confirm:
                            st.info(f"📌 Protocole à confirmer : {f}")
                        for f in if_confirmed:
                            st.info(f"💡 Catégorie potentielle : {f}")
                        for f in edge_cases:
                            st.warning(f"⚖️ Cas limite : {f}")

                    # ── JSON brut (expandable)
                    with st.expander("Voir le JSON brut"):
                        st.json(result)

                except json.JSONDecodeError:
                    st.error("Erreur de parsing JSON — le modèle n'a pas renvoyé un JSON valide. Réessayez.")
                except Exception as e:
                    st.error(f"Erreur : {e}")

# ── TAB 2 : Batch ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Classifier plusieurs produits")
    st.caption("Uploadez un fichier CSV ou Excel avec les colonnes : code, name, type, extra_info (optionnel)")

    uploaded = st.file_uploader("Fichier produits", type=["csv", "xlsx"])
    
    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
            
            st.dataframe(df.head(5))
            required = {"name", "type"}
            if not required.issubset(set(df.columns.str.lower())):
                st.error("Colonnes requises : 'name' et 'type' au minimum.")
            else:
                df.columns = df.columns.str.lower()
                products = df.to_dict(orient="records")
                
                if st.button("🚀 Classifier le batch", disabled=not api_key, type="primary"):
                    progress = st.progress(0)
                    results_list = []
                    
                    for i, p in enumerate(products):
                        try:
                            r = classify_product(
                                api_key,
                                str(p.get("code", "")),
                                str(p.get("name", "")),
                                str(p.get("type", "")),
                                str(p.get("extra_info", ""))
                            )
                            results_list.append({
                                "code": p.get("code", ""),
                                "name": p.get("name", ""),
                                "categories": ", ".join(r.get("assigned_categories", [])),
                                "confidence": r.get("confidence_global", ""),
                                "flags": "; ".join(r.get("flags", {}).get("protocol_to_confirm", []) + 
                                                   r.get("flags", {}).get("regulatory_edge_cases", [])),
                                "raw": json.dumps(r, ensure_ascii=False)
                            })
                        except Exception as e:
                            results_list.append({
                                "code": p.get("code", ""), "name": p.get("name", ""),
                                "categories": "ERREUR", "confidence": "", 
                                "flags": str(e), "raw": ""
                            })
                        progress.progress((i + 1) / len(products))
                    
                    df_results = pd.DataFrame(results_list)
                    st.success(f"{len(results_list)} produits classifiés")
                    st.dataframe(df_results[["code", "name", "categories", "confidence", "flags"]])
                    
                    csv = df_results.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Télécharger les résultats CSV", csv, 
                                       "regwatch_classifications.csv", "text/csv")
        except Exception as e:
            st.error(f"Erreur lecture fichier : {e}")
