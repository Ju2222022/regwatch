"""
Page 2 — Rapport de concordance IA vs Ground Truth
"""

import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Concordance", page_icon="📊", layout="wide")
st.title("📊 Rapport de Concordance — Agent 3 vs Classifications manuelles")
st.caption("Comparez les classifications IA avec vos classifications de référence")

uploaded = st.file_uploader(
    "Fichier avec classifications manuelles (colonnes: code, name, type, ground_truth)",
    type=["csv", "xlsx"]
)

CAT_LABELS = {
    "CAT1": "Batteries", "CAT2": "Lampes", "CAT3": "Électronique (base)",
    "CAT4": "Rechargeable", "CAT5": "ANT+", "CAT6": "MP3",
    "CAT7": "GPS/Radio", "CAT8": "Wifi", "CAT9": "Bluetooth",
}

# Résultats de la session PoC pré-chargés pour démo
POC_RESULTS = [
    {"name": "W100", "code": 8539879, "ai": ["CAT3"], "gt": ["CAT3"], "confidence": "HIGH"},
    {"name": "BC500", "code": 8931927, "ai": ["CAT3"], "gt": ["CAT3", "CAT9"], "confidence": "MEDIUM"},
    {"name": "HL50", "code": 8602576, "ai": ["CAT2", "CAT3"], "gt": ["CAT2"], "confidence": "HIGH"},
    {"name": "SL510", "code": 8739267, "ai": ["CAT2", "CAT3", "CAT4"], "gt": ["CAT2", "CAT3", "CAT4"], "confidence": "HIGH"},
    {"name": "Electrical pump", "code": 8882285, "ai": ["CAT3", "CAT4"], "gt": ["CAT3", "CAT4"], "confidence": "HIGH"},
    {"name": "Massage gun", "code": 8585304, "ai": ["CAT3", "CAT4"], "gt": ["CAT3", "CAT4"], "confidence": "MEDIUM"},
    {"name": "Massage belt", "code": 8647292, "ai": ["CAT3", "CAT4"], "gt": ["CAT3", "CAT4"], "confidence": "MEDIUM"},
    {"name": "DS100", "code": 8945229, "ai": ["CAT3", "CAT4", "CAT9"], "gt": ["CAT3", "CAT4"], "confidence": "HIGH"},
    {"name": "Home trainer", "code": 8861638, "ai": ["CAT3", "CAT9"], "gt": ["CAT3", "CAT9"], "confidence": "HIGH"},
    {"name": "FIT100M", "code": 8941337, "ai": ["CAT3", "CAT4", "CAT7", "CAT9"], "gt": ["CAT3", "CAT4", "CAT9"], "confidence": "HIGH"},
    {"name": "DYNAMO100", "code": 8665145, "ai": ["CAT2", "CAT3", "CAT4"], "gt": ["CAT2", "CAT3", "CAT4"], "confidence": "MEDIUM"},
]

st.subheader("Résultats PoC — 11 produits de référence")

rows = []
for r in POC_RESULTS:
    ai = set(r["ai"]); gt = set(r["gt"])
    extra = ai - gt; missing = gt - ai
    if ai == gt:
        status = "✅ Parfait"
    elif not missing:
        status = "🟡 Sur-classifié"
    elif not extra:
        status = "🟠 Sous-classifié"
    else:
        status = "❌ Divergence"
    rows.append({
        "Produit": r["name"],
        "Code": r["code"],
        "Status": status,
        "Catégories IA": ", ".join(sorted(r["ai"])),
        "Ground Truth": ", ".join(sorted(r["gt"])),
        "Extra (IA)": ", ".join(sorted(extra)) if extra else "—",
        "Manquant (IA)": ", ".join(sorted(missing)) if missing else "—",
        "Confiance": r["confidence"],
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

# Métriques globales
perfect = sum(1 for r in rows if r["Status"] == "✅ Parfait")
total = len(rows)
missing_total = sum(1 for r in rows if r["Manquant (IA)"] != "—")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Concordance parfaite", f"{perfect}/{total}", f"{perfect/total*100:.0f}%")
col2.metric("Aucune cat. manquante", f"{total - missing_total}/{total}")
col3.metric("Divergence totale", "0/11", "✅")
col4.metric("Version prompt", "v2 — Parachute")

st.info("💡 Les écarts restants (HL50 CAT3, DS100 CAT9, FIT100M CAT7) sont des questions métier ouvertes — à trancher avec l'équipe réglementaire.")
