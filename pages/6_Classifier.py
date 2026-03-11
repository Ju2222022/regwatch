"""
Page 1 — Agent 3 : Regulatory Classifier
Interface Streamlit pour classer un produit manuellement ou en batch
"""

import streamlit as st
import pandas as pd
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent3.classifier import classify_product, classify_batch

st.set_page_config(page_title="Agent 3 — Classifier", page_icon="🏷️", layout="wide")
st.title("🏷️ Agent 3 — Regulatory Classifier")

# ── Clé API — chargée automatiquement depuis les Secrets Streamlit ───────────
api_key = st.secrets.get("ANTHROPIC_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Settings")
    if api_key:
        st.success("API key loaded ✓")
    else:
        # Fallback : saisie manuelle si le secret n'est pas configuré
        st.warning("ANTHROPIC_API_KEY secret not found in Streamlit Secrets")
        api_key = st.text_input("API Key (fallback)", type="password",
                                 help="Configure ANTHROPIC_API_KEY in Settings > Secrets")
    st.divider()
    st.header("📊 Session tokens")
    if "session_tokens" not in st.session_state:
        st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
    t = st.session_state["session_tokens"]
    ca, cb = st.columns(2)
    ca.metric("Input",  f"{t['input']:,}")
    cb.metric("Output", f"{t['output']:,}")
    st.metric("Estimated cost", f"${t['cost_usd']:.4f}")
    st.caption(f"{t['calls']} Claude call(s)")
    if st.button("🔄 Reset", key="reset_tokens_sidebar"):
        st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
        st.rerun()

# ── Mapping catégories ────────────────────────────────────────────────────────
CAT_LABELS = {
    "CAT1": "🔋 Batteries & accumulators",
    "CAT2": "💡 Lamps & lighting",
    "CAT3": "⚡ Electronic equipment (base)",
    "CAT4": "🔌 Chargers & rechargeable products",
    "CAT5": "📡 Camera / ANT+",
    "CAT6": "🎵 MP3 player",
    "CAT7": "🛰️ GPS / Radio / Walkie-talkie / Rangefinder",
    "CAT8": "📶 Phone / Wifi",
    "CAT9": "📲 Bluetooth equipment",
}

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🔍 Classify a product", "📋 Batch — multiple products"])

# ── TAB 1 : Produit unique ────────────────────────────────────────────────────
with tab1:
    st.subheader("Classify a product")
    
    col1, col2 = st.columns(2)
    with col1:
        model_code = st.text_input("Model code", placeholder="ex: 8941337")
        product_name = st.text_input("Product name", placeholder="ex: FIT100M")
    with col2:
        product_type = st.text_input("Type / Description", placeholder="ex: Smartwatch GPS Bluetooth")
        extra_info = st.text_input("Additional info (optional)", 
                                    placeholder="e.g. URL slug, partial specs...")

    if st.button("🚀 Classify", disabled=not api_key, type="primary"):
        if not product_name or not product_type:
            st.error("Name and type are required.")
        else:
            with st.spinner("Classifying..."):
                try:
                    result = classify_product(api_key, model_code, product_name, product_type, extra_info)
                    if "session_tokens" not in st.session_state:
                        st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
                    st.session_state["session_tokens"]["input"]    += 1500
                    st.session_state["session_tokens"]["output"]   += 400
                    st.session_state["session_tokens"]["cost_usd"] += round(((1500 * 0.80 + 400 * 4.00) / 1_000_000), 5)
                    st.session_state["session_tokens"]["calls"]    += 1
                    
                    # ── Résultat principal
                    st.success("Classification complete")
                    
                    col_a, col_b = st.columns([2, 1])
                    with col_a:
                        st.markdown("### 📂 Assigned categories")
                        for cat in result.get("assigned_categories", []):
                            label = CAT_LABELS.get(cat, cat)
                            justif = result.get("category_justification", {}).get(cat, "")
                            st.markdown(f"**{cat}** — {label}")
                            if justif:
                                st.caption(f"↳ {justif}")
                    
                    with col_b:
                        confidence = result.get("confidence_global", "?")
                        color = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(confidence, "⚪")
                        st.metric("Global confidence", f"{color} {confidence}")
                        
                        techs = result.get("detected_technologies", {})
                        confirmed = techs.get("confirmed", [])
                        if confirmed:
                            st.markdown("**Confirmed technologies**")
                            for t in confirmed:
                                st.markdown(f"- {t}")

                    # ── Flags
                    flags = result.get("flags", {})
                    to_confirm = flags.get("protocol_to_confirm", [])
                    if_confirmed = flags.get("categories_if_confirmed", [])
                    edge_cases = flags.get("regulatory_edge_cases", [])
                    
                    if to_confirm or if_confirmed or edge_cases:
                        st.markdown("### ⚠️ Points of attention")
                        for f in to_confirm:
                            st.info(f"📌 Protocol to confirm: {f}")
                        for f in if_confirmed:
                            st.info(f"💡 Potential category: {f}")
                        for f in edge_cases:
                            st.warning(f"⚖️ Edge case: {f}")

                    # ── JSON brut (expandable)
                    with st.expander("View raw JSON"):
                        st.json(result)

                except json.JSONDecodeError:
                    st.error("JSON parsing error — the model did not return valid JSON. Please try again.")
                except Exception as e:
                    st.error(f"Error: {e}")

# ── TAB 2 : Batch ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Classify multiple products")
    st.caption("Upload a CSV or Excel file with columns: code, name, type, extra_info (optional)")

    uploaded = st.file_uploader("Product file", type=["csv", "xlsx"])
    
    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded, sheet_name="Exemples produits")
            
            st.dataframe(df.head(5))
            required = {"name", "type"}
            if not required.issubset(set(df.columns.str.lower())):
                st.error("Required columns: 'name' and 'type' at minimum.")
            else:
                # Normaliser les noms de colonnes
                df.columns = df.columns.str.lower().str.strip()
                df = df.rename(columns={"model code": "code"})
                products = df.to_dict(orient="records")
                
                if st.button("🚀 Classify le batch", disabled=not api_key, type="primary"):
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
                    st.success(f"{len(results_list)} products classified")
                    st.dataframe(df_results[["code", "name", "categories", "confidence", "flags"]])
                    
                    csv = df_results.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Download results CSV", csv, 
                                       "regwatch_classifications.csv", "text/csv")
        except Exception as e:
            st.error(f"File read error: {e}")
