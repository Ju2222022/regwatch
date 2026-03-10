import streamlit as st

st.set_page_config(
    page_title="RegWatch — Decathlon",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 RegWatch — Regulatory Intelligence Platform")
st.caption("Decathlon Electronics · AI-powered regulatory watch & compliance")

st.info("👈 Use the left menu to navigate between modules.")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Agent 1", "✅ Active", "Regulatory Watch")
col2.metric("Agent 2", "✅ Active", "Product Profiler")
col3.metric("Agent 3", "✅ Active", "Classifier")
col4.metric("Agent 4", "✅ Active", "Impact Analyzer")
col5.metric("Agent 5A/5B", "✅ Active", "Legal Sheet / Risk Map")
