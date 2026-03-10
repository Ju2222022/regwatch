"""
Agent 1 — Regulatory Watcher v6
- Sidebar allégée (tokens uniquement)
- Configuration sources → page dédiée
- Légende criticité déplacée avant les résultats
- Résultats persistés en session_state
"""

import streamlit as st
import pandas as pd
import json, time
from datetime import datetime
from pathlib import Path
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent1.watcher import run_watch, load_sources, TIMEFRAMES

st.set_page_config(page_title="Agent 1 — Veille", page_icon="📡", layout="wide")

# ── Référentiels ──────────────────────────────────────────────────────────────
CAT_LABELS = {
    "CAT1": "Batteries & accumulateurs",
    "CAT2": "Lampes & éclairage",
    "CAT3": "Équipements électroniques (base)",
    "CAT4": "Chargeurs & produits rechargeables",
    "CAT5": "Caméra / ANT+",
    "CAT6": "Lecteur MP3",
    "CAT7": "GPS / Radio / Talkie / Télémètre",
    "CAT8": "Téléphone / Wifi / GSM",
    "CAT9": "Équipement Bluetooth",
}

URGENCY_DEF = {
    "HIGH":   ("🔴", "En vigueur ou échéance < 6 mois — action immédiate"),
    "MEDIUM": ("🟡", "Échéance 6-18 mois — planifier la conformité"),
    "LOW":    ("🟢", "Consultation ou échéance > 18 mois — surveillance"),
}

HISTORY_FILE = "data/watch_history.json"

# ── Persistance ───────────────────────────────────────────────────────────────
def load_history():
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_to_history(entries):
    h = load_history()
    h.extend(entries)
    Path(HISTORY_FILE).parent.mkdir(exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

# ── Chargement sources ────────────────────────────────────────────────────────
try:
    sources = load_sources("data/sources.json")
except Exception:
    sources = {"EU": ["eur-lex.europa.eu", "europa.eu"], "France": ["legifrance.gouv.fr"]}

# ── Clés API ──────────────────────────────────────────────────────────────────
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")
tavily_key    = st.secrets.get("TAVILY_API_KEY", "")

# ── Session state ─────────────────────────────────────────────────────────────
if "session_tokens" not in st.session_state:
    st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
if "watch_topics" not in st.session_state:
    st.session_state["watch_topics"] = [
        {"topic": "", "markets": ["EU", "France"], "timeframe": "📅 12 derniers mois"}
    ]
if "last_results" not in st.session_state:
    st.session_state["last_results"] = []
if "last_stats" not in st.session_state:
    st.session_state["last_stats"] = {}

# ── Sidebar — tokens uniquement ───────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Statut")
    st.success("Anthropic ✓") if anthropic_key else st.error("ANTHROPIC_API_KEY manquante")
    st.success("Tavily ✓")    if tavily_key    else st.error("TAVILY_API_KEY manquante")
    st.divider()
    st.header("📊 Tokens session")
    t = st.session_state["session_tokens"]
    ca, cb = st.columns(2)
    ca.metric("Input",  f"{t['input']:,}")
    cb.metric("Output", f"{t['output']:,}")
    st.metric("Coût estimé", f"${t['cost_usd']:.4f}")
    st.caption(f"{t['calls']} appel(s) Claude")
    if st.button("🔄 Réinitialiser"):
        st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
        st.rerun()
    st.divider()
    st.caption("⚙️ Pour gérer les sources, rendez-vous dans **Configuration**.")

# ── Page principale ───────────────────────────────────────────────────────────
st.title("📡 Agent 1 — Regulatory Watcher")
st.caption("Surveillance des sources réglementaires officielles · Tavily + Jina.ai")

# ── Pré-remplissage par catégorie ─────────────────────────────────────────────
with st.expander("🏷️ Pré-remplir les sujets depuis les catégories Decathlon", expanded=False):
    st.caption("Sélectionnez les catégories de votre périmètre — les sujets de veille correspondants seront générés automatiquement.")
    from agent4.impact import CAT_DEFINITIONS, get_watch_queries_for_categories
    cat_options = {k: f"{k} — {v['label']}" for k, v in CAT_DEFINITIONS.items()}
    selected_cats = st.multiselect(
        "Catégories actives",
        options=list(cat_options.keys()),
        default=["CAT3","CAT4","CAT9"],
        format_func=lambda c: cat_options[c],
        key="cat_prefill_select"
    )
    if st.button("🔄 Générer les sujets de veille", key="btn_prefill"):
        queries = get_watch_queries_for_categories(selected_cats)
        st.session_state["watch_topics"] = [
            {"topic": q["topic"], "markets": q["markets"], "timeframe": q["timeframe"]}
            for q in queries
        ]
        st.success(f"{len(queries)} sujet(s) générés pour : {', '.join(selected_cats)}")
        st.rerun()

# ── Formulaire ────────────────────────────────────────────────────────────────
st.subheader("🔍 Sujets de veille")

col_left, col_right = st.columns([3, 1])
with col_right:
    use_jina = st.toggle("🔬 Jina.ai (PDF + EUR-Lex)", value=True)
with col_left:
    st.caption("💡 *EN 18031 cybersecurity radio equipment EU* · *lithium battery directive* · *RoHS WEEE 2024*")

topics_to_delete = []
for i, item in enumerate(st.session_state["watch_topics"]):
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 0.3])
        with c1:
            st.session_state["watch_topics"][i]["topic"] = st.text_input(
                f"Sujet {i+1}", value=item["topic"],
                placeholder="ex: EN 18031 cybersecurity radio equipment EU",
                key=f"topic_{i}", label_visibility="collapsed"
            )
        with c2:
            avail = list(sources.keys())
            def_m = [m for m in item["markets"] if m in avail] or avail[:2]
            st.session_state["watch_topics"][i]["markets"] = st.multiselect(
                "Marchés", avail, default=def_m,
                key=f"markets_{i}", label_visibility="collapsed"
            )
        with c3:
            tf_keys = list(TIMEFRAMES.keys())
            def_tf = tf_keys.index(item["timeframe"]) if item["timeframe"] in tf_keys else 1
            st.session_state["watch_topics"][i]["timeframe"] = st.selectbox(
                "Période", tf_keys, index=def_tf,
                key=f"timeframe_{i}", label_visibility="collapsed"
            )
        with c4:
            if st.button("🗑️", key=f"del_{i}") and len(st.session_state["watch_topics"]) > 1:
                topics_to_delete.append(i)

for i in reversed(topics_to_delete):
    st.session_state["watch_topics"].pop(i)
    st.rerun()

col_add, col_run = st.columns([1, 3])
with col_add:
    if st.button("➕ Ajouter un sujet"):
        st.session_state["watch_topics"].append(
            {"topic": "", "markets": ["EU", "France"], "timeframe": "📅 12 derniers mois"}
        )
        st.rerun()

valid_topics = [t for t in st.session_state["watch_topics"] if t["topic"].strip() and t["markets"]]
ready = anthropic_key and tavily_key and bool(valid_topics)

with col_run:
    launch = st.button(
        f"📡 Lancer la veille ({len(valid_topics)} sujet{'s' if len(valid_topics)>1 else ''})",
        disabled=not ready, type="primary", use_container_width=True
    )

# ── Exécution ─────────────────────────────────────────────────────────────────
if launch:
    all_entries = []
    total_stats = {"tavily_results":0,"jina_enriched":0,"entries_found":0,
                   "input_tokens":0,"output_tokens":0,"cost_usd":0.0}
    progress = st.progress(0, text="Démarrage...")

    for idx, item in enumerate(valid_topics):
        topic, markets, timeframe = item["topic"].strip(), item["markets"], item["timeframe"]
        progress.progress(int(idx/len(valid_topics)*100),
                          text=f"Sujet {idx+1}/{len(valid_topics)} : {topic[:50]}...")

        with st.status(f"📡 [{idx+1}/{len(valid_topics)}] {topic}", expanded=False) as status:
            try:
                entries, stats = run_watch(
                    anthropic_key=anthropic_key, tavily_key=tavily_key,
                    topic=topic, markets=markets, timeframe_label=timeframe,
                    sources_override=sources, use_jina=use_jina,
                )
                for k in ["tavily_results","jina_enriched","entries_found","input_tokens","output_tokens"]:
                    total_stats[k] += stats.get(k, 0)
                total_stats["cost_usd"] += stats.get("cost_usd", 0.0)
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

        if idx < len(valid_topics)-1:
            time.sleep(1)

    progress.progress(100, text="Terminé ✓")
    st.session_state["last_results"] = all_entries
    st.session_state["last_stats"]   = total_stats

    if all_entries:
        save_to_history(all_entries)
        if "veille_results" not in st.session_state:
            st.session_state["veille_results"] = []
        st.session_state["veille_results"].extend(all_entries)

# ── Affichage résultats ───────────────────────────────────────────────────────
def render_entry(entry, key):
    urgency = entry.get("urgency","LOW")
    u_icon, u_desc = URGENCY_DEF.get(urgency, ("⚪",""))
    cats_raw = entry.get("categories_concerned",[])
    cats_inline = "  ·  ".join(f"**{c}** ({CAT_LABELS.get(c,c)})" for c in cats_raw)
    with st.expander(f"{u_icon} {entry.get('title','Sans titre')}", key=key):
        col_a, col_b = st.columns([3,1])
        with col_a:
            st.markdown("**Résumé**")
            st.write(entry.get("summary_fr","—"))
            if entry.get("action_required"):
                st.info(f"⚙️ **Action suggérée** *(à valider)* : {entry['action_required']}")
            url = entry.get("url","")
            if url and url.startswith("http"):
                st.markdown(f"[🔗 Accéder au document source]({url})")
            else:
                st.caption("⚠️ URL source non disponible")
            st.caption(f"Sujet : *{entry.get('watch_topic','')}* · Extrait le {entry.get('watch_date','—')}")
        with col_b:
            st.metric("Urgence", f"{u_icon} {urgency}", help=u_desc)
            st.markdown("**Catégories**")
            st.markdown(cats_inline or "—")
            st.caption(f"📅 {entry.get('date','?')}")
            st.caption(f"🌍 {', '.join(entry.get('markets',[]))}")

if st.session_state["last_results"]:
    all_entries = st.session_state["last_results"]
    total_stats = st.session_state["last_stats"]

    st.divider()
    st.subheader("📊 Récapitulatif")
    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Sujets traités",   len(valid_topics) or "—")
    m2.metric("Résultats Tavily", total_stats.get("tavily_results",0))
    m3.metric("Entrées extraites",len(all_entries))
    m4.metric("Tokens totaux",    f"{total_stats.get('input_tokens',0)+total_stats.get('output_tokens',0):,}")
    m5.metric("Coût total",       f"${total_stats.get('cost_usd',0):.4f}")

    st.success(f"**{len(all_entries)} entrée(s) réglementaire(s) identifiée(s)**")

    # Toggle vue
    view_mode = st.radio(
        "Regrouper par", ["🔴 Criticité","📂 Thématique"],
        horizontal=True, key="view_mode_main"
    )

    # Légende juste avant les résultats
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        for col, (level, (icon, desc)) in zip([c1,c2,c3], URGENCY_DEF.items()):
            col.markdown(f"{icon} **{level}**")
            col.caption(desc)

    if view_mode == "🔴 Criticité":
        for level in ["HIGH","MEDIUM","LOW"]:
            lvl_entries = [e for e in all_entries if e.get("urgency")==level]
            if not lvl_entries: continue
            icon, desc = URGENCY_DEF[level]
            st.markdown(f"### {icon} {level} — {len(lvl_entries)} entrée(s)")
            for i, e in enumerate(lvl_entries):
                render_entry(e, f"crit_{level}_{i}")
    else:
        topics_seen = list(dict.fromkeys(e.get("watch_topic","Sans thématique") for e in all_entries))
        for topic in topics_seen:
            t_entries = [e for e in all_entries if e.get("watch_topic")==topic]
            st.markdown(f"### 📂 {topic} — {len(t_entries)} entrée(s)")
            for i, e in enumerate(t_entries):
                render_entry(e, f"theme_{topic[:15]}_{i}")

    # Export CSV
    st.divider()
    df = pd.DataFrame([{
        "Date":        e.get("date",""),
        "Titre":       e.get("title",""),
        "Résumé":      e.get("summary_fr",""),
        "Catégories":  ", ".join(f"{c} ({CAT_LABELS.get(c,c)})" for c in e.get("categories_concerned",[])),
        "Marchés":     ", ".join(e.get("markets",[])),
        "Urgence":     e.get("urgency",""),
        "Action":      e.get("action_required",""),
        "URL Source":  e.get("url",""),
        "Sujet":       e.get("watch_topic",""),
        "Date veille": e.get("watch_date",""),
    } for e in all_entries])
    st.dataframe(df[["Date","Titre","Catégories","Urgence","Action","URL Source"]], use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exporter CSV", csv,
        f"regwatch_veille_{datetime.now().strftime('%Y%m%d_%H%M')}.csv","text/csv")
    st.info(f"💾 {len(st.session_state.get('veille_results',[]))} entrée(s) disponibles pour l'Agent 4.")

# ── Historique ────────────────────────────────────────────────────────────────
st.divider()
with st.expander("🗃️ Historique des veilles précédentes", expanded=False):
    history = load_history()
    if not history:
        st.caption("Aucun historique enregistré.")
    else:
        col_h1, col_h2 = st.columns([3,1])
        col_h1.caption(f"{len(history)} entrée(s) enregistrée(s) au total")
        if col_h2.button("🗑️ Effacer l'historique"):
            Path(HISTORY_FILE).write_text("[]")
            st.session_state["last_results"] = []
            st.rerun()
        view_h = st.radio("Vue", ["🔴 Criticité","📂 Thématique"], horizontal=True, key="view_history")
        if view_h == "🔴 Criticité":
            for level in ["HIGH","MEDIUM","LOW"]:
                lvl = [e for e in history if e.get("urgency")==level]
                if not lvl: continue
                icon, _ = URGENCY_DEF[level]
                st.markdown(f"### {icon} {level} — {len(lvl)} entrée(s)")
                for i, e in enumerate(lvl):
                    render_entry(e, f"hist_crit_{level}_{i}")
        else:
            topics_h = list(dict.fromkeys(e.get("watch_topic","?") for e in history))
            for topic in topics_h:
                t_entries = [e for e in history if e.get("watch_topic")==topic]
                st.markdown(f"### 📂 {topic} — {len(t_entries)} entrée(s)")
                for i, e in enumerate(t_entries):
                    render_entry(e, f"hist_theme_{topic[:10]}_{i}")
