"""
Page 5 — Configuration
Gestion des sources de veille (marchés + domaines).
Page dédiée pour éviter la surcharge de la sidebar.
"""

import streamlit as st
import json
from pathlib import Path
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent1.watcher import load_sources, save_sources

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings — Sources de veille")
st.caption("Gérez les marchés et domaines surveillés par l'Agent 1")

SOURCES_FILE = "data/sources.json"

try:
    sources = load_sources(SOURCES_FILE)
except Exception:
    sources = {"EU": ["eur-lex.europa.eu"], "France": ["legifrance.gouv.fr"]}

# ── Vue d'ensemble ────────────────────────────────────────────────────────────
st.subheader("📋 Active markets")

cols = st.columns(len(sources) if sources else 1)
for col, (market, domains) in zip(cols, sources.items()):
    col.metric(market, f"{len(domains)} domaine(s)")

st.divider()

# ── Édition par marché ────────────────────────────────────────────────────────
st.subheader("✏️ Modifier un marché")

tab_list = list(sources.keys()) + ["➕ Nouveau marché"]
tabs = st.tabs(tab_list)

# Onglets marchés existants
for tab, market in zip(tabs[:-1], sources.keys()):
    with tab:
        col_edit, col_delete = st.columns([4, 1])
        with col_edit:
            st.markdown(f"**Domaines surveillés pour {market}**")
            edited_domains = st.text_area(
                "Un domaine par ligne",
                value="\n".join(sources[market]),
                height=200,
                key=f"edit_{market}"
            )
            if st.button(f"💾 Save {market}", key=f"save_{market}", type="primary"):
                sources[market] = [d.strip() for d in edited_domains.split("\n") if d.strip()]
                save_sources(sources, SOURCES_FILE)
                st.success(f"✓ {len(sources[market])} domaine(s) sauvegardé(s) pour **{market}**")
                st.rerun()

        with col_delete:
            st.markdown("**Delete this market**")
            st.warning(f"Cette action supprimera **{market}** et ses {len(sources[market])} domaine(s).")
            confirm = st.checkbox(f"Confirmer la suppression", key=f"confirm_del_{market}")
            if st.button(f"🗑️ Delete {market}", key=f"del_{market}",
                         disabled=not confirm, type="secondary"):
                del sources[market]
                save_sources(sources, SOURCES_FILE)
                st.success(f"Marché **{market}** supprimé.")
                st.rerun()

        # Active domains preview
        st.divider()
        st.markdown("**Preview**")
        for d in sources.get(market, []):
            st.markdown(f"- `{d}`")

# Onglet nouveau marché
with tabs[-1]:
    st.markdown("**Créer un nouveau marché**")
    col_a, col_b = st.columns(2)
    with col_a:
        new_name = st.text_input("Market name *", placeholder="ex: Germany, Nordic, APAC")
    with col_b:
        st.markdown("")  # spacer

    new_domains_text = st.text_area(
        "Domaines initiaux (un par ligne)",
        placeholder="ex:\nbsi.bund.de\nbundesanzeiger.de\ndin.de",
        height=150
    )

    # Suggestions par région
    with st.expander("💡 Suggestions de domaines par région"):
        suggestions = {
            "Germany": ["bsi.bund.de", "bundesanzeiger.de", "din.de", "vde.com"],
            "Nordic": ["dsb.dk", "elsaekerhetsverket.se", "nkom.no", "traficom.fi"],
            "USA": ["fcc.gov", "cpsc.gov", "ftc.gov", "federalregister.gov"],
            "UK": ["gov.uk", "legislation.gov.uk", "ofcom.org.uk"],
        }
        for region, domains in suggestions.items():
            st.markdown(f"**{region}** : {' · '.join(f'`{d}`' for d in domains)}")

    if st.button("✅ Créer le marché", type="primary", disabled=not new_name.strip()):
        if new_name.strip() in sources:
            st.error(f"Le marché **{new_name}** existe déjà.")
        else:
            sources[new_name.strip()] = [
                d.strip() for d in new_domains_text.split("\n") if d.strip()
            ]
            save_sources(sources, SOURCES_FILE)
            st.success(f"✓ Marché **{new_name}** créé avec {len(sources[new_name.strip()])} domaine(s)")
            st.rerun()

st.divider()

# ── Export / Import ───────────────────────────────────────────────────────────
st.subheader("📤 Export / Import de la configuration")

col_exp, col_imp = st.columns(2)
with col_exp:
    st.markdown("**Export la configuration**")
    st.caption("Téléchargez votre configuration sources pour la sauvegarder ou la partager.")
    st.download_button(
        "⬇️ Télécharger sources.json",
        data=json.dumps(sources, indent=2, ensure_ascii=False),
        file_name="sources.json",
        mime="application/json"
    )

with col_imp:
    st.markdown("**Import une configuration**")
    st.caption("Remplacez la configuration actuelle par un fichier sources.json.")
    uploaded = st.file_uploader("Choisir un fichier sources.json", type="json")
    if uploaded:
        try:
            imported = json.load(uploaded)
            if isinstance(imported, dict):
                st.write(f"Fichier valide — {len(imported)} marché(s) détecté(s) : {', '.join(imported.keys())}")
                if st.button("✅ Confirmer l'import", type="primary"):
                    save_sources(imported, SOURCES_FILE)
                    st.success("Configuration importée ✓")
                    st.rerun()
            else:
                st.error("Format invalide — le fichier doit contenir un objet JSON.")
        except Exception as e:
            st.error(f"Error de lecture : {e}")
