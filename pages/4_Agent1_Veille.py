"""
Page 4 — Agent 1 : Regulatory Watcher
Veille multi-sujets avec Tavily + Jina.ai
Domaines configurables, compteur de tokens en temps réel.
"""

import streamlit as st
import pandas as pd
import time
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
            value=current_domains, height=150
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

    for market, domains in sources.items():
        st.caption(f"**{market}** — {len(domains)} domaine(s)")

# ── Initialisation liste de sujets ────────────────────────────────────────────
if "watch_topics" not in st.session_state:
    st.session_state["watch_topics"] = [
        {"topic": "", "markets": ["EU", "France"], "timeframe": "📅 12 derniers mois"}
    ]

SUGGESTED_TOPICS = [
    "EN 18031 cybersecurity radio equipment EU",
    "lithium battery directive regulation EU",
    "Bluetooth electronics RoHS WEEE",
    "GPS radio frequency SAR Europe",
    "USB-C charger ecodesign regulation",
    "RoHS WEEE 2024 update",
]

# ── Formulaire multi-sujets ───────────────────────────────────────────────────
st.subheader("🔍 Sujets de veille")

col_left, col_right = st.columns([3, 1])
with col_right:
    use_jina = st.toggle(
        "🔬 Jina.ai (PDF + EUR-Lex)",
        value=True,
        help="Lecture profonde des 3 premiers résultats prioritaires par sujet"
    )

with col_left:
    st.caption("💡 Suggestions : " + " · ".join(f"*{s}*" for s in SUGGESTED_TOPICS[:4]))

# Afficher chaque sujet
topics_to_delete = []
for i, item in enumerate(st.session_state["watch_topics"]):
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 0.3])
        with c1:
            st.session_state["watch_topics"][i]["topic"] = st.text_input(
                f"Sujet {i+1}",
                value=item["topic"],
                placeholder="ex: EN 18031 cybersecurity radio equipment EU",
                key=f"topic_{i}",
                label_visibility="collapsed"
            )
        with c2:
            available_markets = list(sources.keys())
            default_markets = [m for m in item["markets"] if m in available_markets] or available_markets[:2]
            st.session_state["watch_topics"][i]["markets"] = st.multiselect(
                "Marchés",
                options=available_markets,
                default=default_markets,
                key=f"markets_{i}",
                label_visibility="collapsed"
            )
        with c3:
            st.session_state["watch_topics"][i]["timeframe"] = st.selectbox(
                "Période",
                options=list(TIMEFRAMES.keys()),
                index=list(TIMEFRAMES.keys()).index(item["timeframe"]) if item["timeframe"] in TIMEFRAMES else 1,
                key=f"timeframe_{i}",
                label_visibility="collapsed"
            )
        with c4:
            if st.button("🗑️", key=f"del_{i}", help="Supprimer ce sujet") and len(st.session_state["watch_topics"]) > 1:
                topics_to_delete.append(i)

for i in reversed(topics_to_delete):
    st.session_state["watch_topics"].pop(i)
    st.rerun()

# Bouton ajout sujet
col_add, col_run = st.columns([1, 3])
with col_add:
    if st.button("➕ Ajouter un sujet"):
        st.session_state["watch_topics"].append(
            {"topic": "", "markets": ["EU", "France"], "timeframe": "📅 12 derniers mois"}
        )
        st.rerun()

# ── Lancement ─────────────────────────────────────────────────────────────────
valid_topics = [t for t in st.session_state["watch_topics"] if t["topic"].strip() and t["markets"]]
ready = anthropic_key and tavily_key and len(valid_topics) > 0

if not ready:
    st.warning("Renseignez au moins un sujet avec un marché sélectionné.")

with col_run:
    launch = st.button(
        f"📡 Lancer la veille ({len(valid_topics)} sujet{'s' if len(valid_topics) > 1 else ''})",
        disabled=not ready,
        type="primary",
        use_container_width=True
    )

if launch:
    all_entries = []
    total_stats = {"tavily_results": 0, "jina_enriched": 0, "entries_found": 0,
                   "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    progress = st.progress(0, text="Démarrage...")

    for idx, item in enumerate(valid_topics):
        topic    = item["topic"].strip()
        markets  = item["markets"]
        timeframe = item["timeframe"]
        pct = int((idx / len(valid_topics)) * 100)
        progress.progress(pct, text=f"Sujet {idx+1}/{len(valid_topics)} : {topic[:50]}...")

        with st.status(f"📡 [{idx+1}/{len(valid_topics)}] {topic}", expanded=False) as status:
            try:
                entries, stats = run_watch(
                    anthropic_key=anthropic_key,
                    tavily_key=tavily_key,
                    topic=topic,
                    markets=markets,
                    timeframe_label=timeframe,
                    sources_override=sources,
                    use_jina=use_jina,
                )

                # Accumuler stats
                for key in ["tavily_results", "jina_enriched", "entries_found", "input_tokens", "output_tokens"]:
                    total_stats[key] += stats.get(key, 0)
                total_stats["cost_usd"] += stats.get("cost_usd", 0.0)

                # Mise à jour compteur session
                st.session_state["session_tokens"]["input"]    += stats.get("input_tokens", 0)
                st.session_state["session_tokens"]["output"]   += stats.get("output_tokens", 0)
                st.session_state["session_tokens"]["cost_usd"] += stats.get("cost_usd", 0.0)
                st.session_state["session_tokens"]["calls"]    += 1

                all_entries.extend(entries)

                if stats.get("warning"):
                    status.update(label=f"⚠️ {topic[:40]} — {stats['warning']}", state="error")
                else:
                    status.update(
                        label=f"✅ {topic[:40]} — {stats['entries_found']} entrée(s) · "
                              f"{stats['tavily_results']} résultats · "
                              f"{stats['input_tokens']+stats['output_tokens']:,} tokens · "
                              f"${stats['cost_usd']:.4f}",
                        state="complete"
                    )

            except Exception as e:
                status.update(label=f"❌ {topic[:40]} — Erreur : {e}", state="error")

        # Pause courte entre sujets pour éviter rate limiting
        if idx < len(valid_topics) - 1:
            time.sleep(1)

    progress.progress(100, text="Terminé ✓")

    # ── Récapitulatif ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("📊 Récapitulatif de session")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Sujets traités", len(valid_topics))
    m2.metric("Résultats Tavily", total_stats["tavily_results"])
    m3.metric("Entrées extraites", total_stats["entries_found"])
    m4.metric("Tokens totaux", f"{total_stats['input_tokens']+total_stats['output_tokens']:,}")
    m5.metric("Coût total", f"${total_stats['cost_usd']:.4f}")

    # ── Résultats groupés par urgence ─────────────────────────────────────
    if not all_entries:
        st.warning("Aucune entrée réglementaire trouvée sur l'ensemble des sujets.")
    else:
        st.success(f"**{len(all_entries)} entrée(s) réglementaire(s) identifiée(s)**")

        for urgency_level, icon in [("HIGH", "🔴"), ("MEDIUM", "🟡"), ("LOW", "🟢")]:
            level_entries = [e for e in all_entries if e.get("urgency") == urgency_level]
            if not level_entries:
                continue
            st.markdown(f"### {icon} Urgence {urgency_level} — {len(level_entries)} entrée(s)")
            for entry in level_entries:
                cats = ", ".join(entry.get("categories_concerned", []))
                with st.expander(f"{entry.get('title','Sans titre')} — {cats}"):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.markdown("**Résumé**")
                        st.write(entry.get("summary_fr", ""))
                        if entry.get("action_required"):
                            st.info(f"**Action requise :** {entry['action_required']}")
                        if entry.get("url"):
                            st.markdown(f"[🔗 Voir la source]({entry['url']})")
                        st.caption(f"Sujet veille : *{entry.get('watch_topic','')}*")
                    with col_b:
                        st.markdown("**Catégories**")
                        for cat in entry.get("categories_concerned", []):
                            st.markdown(f"- `{cat}`")
                        st.caption(f"📅 {entry.get('date','?')}")
                        st.caption(f"🌍 {', '.join(entry.get('markets',[]))}")

        # ── Export CSV ────────────────────────────────────────────────────
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
        } for e in all_entries])

        st.dataframe(df[["Date","Titre","Catégories","Urgence","Action"]], use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Exporter tous les résultats CSV",
            csv,
            f"regwatch_veille_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )

        # Stockage pour Agent 4
        if "veille_results" not in st.session_state:
            st.session_state["veille_results"] = []
        st.session_state["veille_results"].extend(all_entries)
        st.info(f"💾 {len(st.session_state['veille_results'])} entrée(s) en mémoire · disponibles pour l'Agent 4.")
