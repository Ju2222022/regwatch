"""
Page 4 — Agent 1 : Regulatory Watcher
Veille réglementaire multi-sources avec Tavily + Jina.ai
Domaines configurables, compteur de tokens en temps réel.
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent1.watcher import run_watch, load_sources, save_sources, TIMEFRAMES

st.set_page_config(page_title="Agent 1 — Veille", page_icon="📡", layout="wide")
st.title("📡 Agent 1 — Regulatory Watcher")
st.caption("Surveillance des sources réglementaires officielles · Tavily + Jina.ai")

# ── Clés API ──────────────────────────────────────────────────────────────────
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")
tavily_key    = st.secrets.get("TAVILY_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Configuration")
    st.success("Clé Anthropic ✓") if anthropic_key else st.error("ANTHROPIC_API_KEY manquante")
    st.success("Clé Tavily ✓")    if tavily_key    else st.error("TAVILY_API_KEY manquante")

    st.divider()

    # ── Compteur tokens session ───────────────────────────────────────────
    st.header("📊 Tokens session")
    if "session_tokens" not in st.session_state:
        st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
    t = st.session_state["session_tokens"]
    col_a, col_b = st.columns(2)
    col_a.metric("Input", f"{t['input']:,}")
    col_b.metric("Output", f"{t['output']:,}")
    st.metric("Coût estimé session", f"${t['cost_usd']:.4f}")
    st.caption(f"{t['calls']} appel(s) Claude")
    if st.button("Réinitialiser compteur"):
        st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
        st.rerun()

    st.divider()

    # ── Gestion des sources ───────────────────────────────────────────────
    st.header("🗂️ Sources surveillées")
    sources = load_sources("data/sources.json")

    with st.expander("Configurer les domaines"):
        market_to_edit = st.selectbox("Marché à éditer", list(sources.keys()))
        current_domains = "\n".join(sources.get(market_to_edit, []))
        new_domains_text = st.text_area(
            f"Domaines pour {market_to_edit} (un par ligne)",
            value=current_domains,
            height=150
        )
        col1, col2 = st.columns(2)
        if col1.button("💾 Sauvegarder"):
            sources[market_to_edit] = [d.strip() for d in new_domains_text.split("\n") if d.strip()]
            save_sources(sources, "data/sources.json")
            st.success("Sauvegardé ✓")
            st.rerun()

        new_market = st.text_input("Ajouter un nouveau marché")
        if col2.button("➕ Ajouter") and new_market:
            sources[new_market] = []
            save_sources(sources, "data/sources.json")
            st.rerun()

    # Affichage résumé sources
    for market, domains in sources.items():
        st.caption(f"**{market}** — {len(domains)} domaine(s)")

# ── Formulaire veille ─────────────────────────────────────────────────────────
st.subheader("🔍 Lancer une session de veille")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    topic = st.text_input(
        "Sujet de veille *",
        placeholder="ex: Bluetooth electronics regulation EU",
        help="Décrivez le sujet en anglais pour de meilleurs résultats Tavily"
    )
with col2:
    selected_markets = st.multiselect(
        "Marchés",
        options=list(sources.keys()),
        default=["EU", "France"] if "EU" in sources else list(sources.keys())[:1]
    )
with col3:
    timeframe = st.selectbox("Période", options=list(TIMEFRAMES.keys()), index=0)

use_jina = st.toggle(
    "🔬 Enrichissement Jina.ai (lecture PDF + sites dynamiques EUR-Lex)",
    value=True,
    help="Lit en profondeur les 3 premiers résultats prioritaires (EUR-Lex, Legifrance, PDFs)"
)

st.caption("💡 Suggestions : *Bluetooth electronics regulation EU* · *lithium battery directive* · *cybersecurity EN 18031 connected devices* · *RoHS WEEE 2024* · *GPS radio frequency SAR Europe*")

ready = anthropic_key and tavily_key and topic and selected_markets
if not ready:
    st.warning("Renseignez un sujet et sélectionnez au moins un marché.")

if st.button("📡 Lancer la veille", disabled=not ready, type="primary"):
    domains_count = len(set(d for m in selected_markets for d in sources.get(m, [])))

    with st.status(f"🔍 Veille en cours : {topic}...", expanded=True) as status:
        try:
            st.write(f"**Étape 1** — Recherche Tavily sur {domains_count} domaines ({', '.join(selected_markets)})")
            st.write(f"**Étape 2** — {'Enrichissement Jina.ai activé (EUR-Lex, PDFs)' if use_jina else 'Jina.ai désactivé'}")
            st.write(f"**Étape 3** — Extraction Claude des entrées réglementaires")

            entries, stats = run_watch(
                anthropic_key=anthropic_key,
                tavily_key=tavily_key,
                topic=topic,
                markets=selected_markets,
                timeframe_label=timeframe,
                sources_override=sources,
                use_jina=use_jina,
            )

            # Mise à jour compteur session
            st.session_state["session_tokens"]["input"]    += stats.get("input_tokens", 0)
            st.session_state["session_tokens"]["output"]   += stats.get("output_tokens", 0)
            st.session_state["session_tokens"]["cost_usd"] += stats.get("cost_usd", 0.0)
            st.session_state["session_tokens"]["calls"]    += 1

            status.update(
                label=f"✅ {stats['entries_found']} entrée(s) · "
                      f"{stats['tavily_results']} résultats Tavily · "
                      f"{stats['jina_enriched']} enrichi(s) Jina · "
                      f"{stats['input_tokens']+stats['output_tokens']:,} tokens · "
                      f"${stats['cost_usd']:.4f}",
                state="complete"
            )
        except Exception as e:
            status.update(label=f"❌ Erreur : {e}", state="error")
            st.error(f"Détail : {e}")
            entries = []
            stats = {"tavily_results": 0, "jina_enriched": 0, "entries_found": 0,
                     "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    # ── Métriques de la session ───────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Résultats Tavily", stats.get("tavily_results", 0))
    m2.metric("Enrichis Jina", stats.get("jina_enriched", 0))
    m3.metric("Entrées extraites", stats.get("entries_found", 0))
    m4.metric("Tokens (in+out)", f"{stats.get('input_tokens',0)+stats.get('output_tokens',0):,}")
    m5.metric("Coût appel", f"${stats.get('cost_usd', 0):.4f}")

    # ── Résultats ─────────────────────────────────────────────────────────
    if stats.get("warning"):
        st.warning(f"⚠️ {stats['warning']}")
    elif not entries:
        st.warning("Aucune entrée réglementaire trouvée. Essayez un sujet plus spécifique ou une période plus longue.")
    else:
        st.success(f"**{len(entries)} texte(s) réglementaire(s) identifié(s)**")

        for i, entry in enumerate(entries):
            urgency = entry.get("urgency", "LOW")
            color   = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(urgency, "⚪")
            cats    = ", ".join(entry.get("categories_concerned", []))

            with st.expander(f"{color} {entry.get('title','Sans titre')} — {cats}", expanded=(i == 0)):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown("**Résumé**")
                    st.write(entry.get("summary_fr", ""))
                    if entry.get("action_required"):
                        st.info(f"**Action requise :** {entry['action_required']}")
                    if entry.get("url"):
                        st.markdown(f"[🔗 Voir la source]({entry['url']})")
                with col_b:
                    st.metric("Urgence", f"{color} {urgency}")
                    st.markdown("**Catégories concernées**")
                    for cat in entry.get("categories_concerned", []):
                        st.markdown(f"- `{cat}`")
                    st.caption(f"📅 {entry.get('date','?')}")
                    st.caption(f"🌍 {', '.join(entry.get('markets',[]))}")

        # ── Export + stockage session ─────────────────────────────────────
        st.divider()
        df = pd.DataFrame([{
            "Date": e.get("date", ""),
            "Titre": e.get("title", ""),
            "Résumé": e.get("summary_fr", ""),
            "Catégories": ", ".join(e.get("categories_concerned", [])),
            "Marchés": ", ".join(e.get("markets", [])),
            "Urgence": e.get("urgency", ""),
            "Action": e.get("action_required", ""),
            "Source URL": e.get("url", ""),
            "Sujet veille": e.get("watch_topic", ""),
            "Date veille": e.get("watch_date", ""),
        } for e in entries])

        st.dataframe(df[["Date","Titre","Catégories","Urgence","Action"]], use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Exporter CSV",
            csv,
            f"regwatch_veille_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )

        # Stockage pour Agent 4
        if "veille_results" not in st.session_state:
            st.session_state["veille_results"] = []
        st.session_state["veille_results"].extend(entries)
        st.info(f"💾 {len(st.session_state['veille_results'])} entrée(s) stockée(s) en session · disponibles pour l'Agent 4.")
