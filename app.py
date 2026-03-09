import streamlit as st

st.set_page_config(
    page_title="RegWatch — Decathlon",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 RegWatch — Veille Réglementaire Decathlon")
st.caption("PoC Phase 1 — Agent 3 : Classificateur Réglementaire")

st.info("👈 Utilisez le menu à gauche pour naviguer entre les modules.")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Agent 3", "✅ Actif", "Classificateur")
with col2:
    st.metric("Agent 1", "🔜 Phase 2", "Veille réglementaire")
with col3:
    st.metric("Agent 4", "🔜 Phase 3", "Impact analyzer")
