"""
Page 3 — Agent 2 : Product Profiler
Recherche les specs d'un produit Decathlon par code modèle
puis lance automatiquement la classification Agent 3.
"""

import streamlit as st
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent2.profiler import search_and_profile, profile_to_classifier_input
from agent3.classifier import classify_product

st.set_page_config(page_title="Agent 2 — Profiler", page_icon="🔎", layout="wide")
st.title("🔎 Agent 2 — Product Profiler")
st.caption("Recherche automatique des specs produit → Classification réglementaire")

# Clé API depuis les Secrets
api_key = st.secrets.get("ANTHROPIC_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Settings")
    if api_key:
        st.success("API key loaded ✓")
    else:
        st.warning("ANTHROPIC_API_KEY non trouvée")
        api_key = st.text_input("Clé API Anthropic (secours)", type="password")

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

st.info("💡 Entrez un code modèle Decathlon — l'Agent 2 recherche les specs sur le web, puis l'Agent 3 classifie automatiquement.")

col1, col2 = st.columns(2)
with col1:
    model_code = st.text_input("Model code *", placeholder="ex: 8941337")
    product_name = st.text_input("Product name *", placeholder="ex: FIT100M")
with col2:
    extra_info = st.text_input("Additional info (optional)",
                                placeholder="ex: GPS Bluetooth rechargeable")
    st.caption("Si vous avez déjà des infos, ajoutez-les ici pour améliorer la précision.")

if st.button("🚀 Profiler + Classifier", disabled=not api_key, type="primary"):
    if not model_code or not product_name:
        st.error("Model code et nom commercial requis.")
    else:
        # ── Étape 1 : Agent 2 — Profiling ─────────────────────────────────
        with st.status("🔎 Agent 2 — Recherche des specs produit...", expanded=True) as status:
            try:
                st.write(f"Recherche en cours pour **{product_name}** (code {model_code})...")
                profile = search_and_profile(api_key, model_code, product_name, extra_info)
                status.update(label="✅ Agent 2 — Profil extrait", state="complete")
            except Exception as e:
                status.update(label=f"⚠️ Agent 2 — Error: {e}", state="error")
                st.warning("Passage en mode dégradé : classification sans profil web.")
                profile = {
                    "code": model_code, "name": product_name,
                    "technologies": {
                        "wireless": [], "power": [], "primary_function": "",
                        "sensors": [], "connectivity": []
                    },
                    "data_confidence": "LOW",
                    "missing_info": ["web search failed"]
                }

        # Afficher le profil
        st.subheader("📋 Profil technologique extrait")
        techs = profile.get("technologies", {})
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("**Sans-fil**")
            for t in techs.get("wireless", []) or ["—"]:
                st.markdown(f"- {t}")
        with col_b:
            st.markdown("**Alimentation**")
            for t in techs.get("power", []) or ["—"]:
                st.markdown(f"- {t}")
        with col_c:
            st.markdown("**Capteurs**")
            for t in techs.get("sensors", []) or ["—"]:
                st.markdown(f"- {t}")

        if profile.get("product_description_summary"):
            st.caption(f"📝 {profile['product_description_summary']}")

        confidence_color = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}
        conf = profile.get("data_confidence", "?")
        st.caption(f"Confiance données : {confidence_color.get(conf, '⚪')} {conf}")

        # ── Étape 2 : Agent 3 — Classification ────────────────────────────
        classifier_input = profile_to_classifier_input(profile)

        with st.status("🏷️ Agent 3 — Classification réglementaire...", expanded=True) as status:
            try:
                st.write("Classifying...")
                result = classify_product(
                    api_key,
                    classifier_input["code"],
                    classifier_input["name"],
                    classifier_input["type"],
                    classifier_input["extra_info"]
                )
                status.update(label="✅ Agent 3 — Classification complete", state="complete")
            except Exception as e:
                status.update(label=f"❌ Agent 3 — Error: {e}", state="error")
                st.stop()

        # Afficher la classification
        st.subheader("📂 Résultat de classification")
        col_res, col_conf = st.columns([2, 1])

        with col_res:
            for cat in result.get("assigned_categories", []):
                label = CAT_LABELS.get(cat, cat)
                justif = result.get("category_justification", {}).get(cat, "")
                st.markdown(f"**{cat}** — {label}")
                if justif:
                    st.caption(f"↳ {justif}")

        with col_conf:
            confidence = result.get("confidence_global", "?")
            color = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(confidence, "⚪")
            st.metric("Confiance", f"{color} {confidence}")

        # Flags
        flags = result.get("flags", {})
        to_confirm = flags.get("protocol_to_confirm", [])
        if_confirmed = flags.get("categories_if_confirmed", [])
        edge_cases = flags.get("regulatory_edge_cases", [])

        if to_confirm or if_confirmed or edge_cases:
            st.subheader("⚠️ Points of attention")
            for f in to_confirm:
                st.info(f"📌 Protocol to confirm: {f}")
            for f in if_confirmed:
                st.info(f"💡 Potential category: {f}")
            for f in edge_cases:
                st.warning(f"⚖️ Edge case: {f}")

        with st.expander("Voir les données complètes (profil + classification)"):
            st.json({"profil_agent2": profile, "classification_agent3": result})
