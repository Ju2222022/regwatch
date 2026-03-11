"""
Page 5 — Configuration
Watch source management (markets + domains + languages).
"""

import streamlit as st
import json
from pathlib import Path
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent1.watcher import load_sources, save_sources, LANGUAGE_LABELS

st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")
st.title("⚙️ Configuration — Watch Sources")
st.caption("Manage markets, domains and search languages for Agent 1")

SOURCES_FILE = "data/sources.json"

try:
    sources = load_sources(SOURCES_FILE)
except Exception:
    sources = {"EU": ["eur-lex.europa.eu"], "France": ["legifrance.gouv.fr"]}

# Clé interne — ne pas afficher comme marché
LANG_KEY = "_market_languages"
lang_map  = sources.get(LANG_KEY, {})
markets   = [k for k in sources if not k.startswith("_")]

# ── Vue d'ensemble ─────────────────────────────────────────────────────────────
st.subheader("📋 Active markets")

LANG_FLAGS = {"en": "🇬🇧", "fr": "🇫🇷", "zh": "🇨🇳", "es": "🇪🇸", "de": "🇩🇪",
              "ja": "🇯🇵", "ko": "🇰🇷", "pt": "🇧🇷", "it": "🇮🇹", "nl": "🇳🇱"}

if markets:
    cols = st.columns(min(len(markets), 6))
    for col, market in zip(cols, markets):
        lang = lang_map.get(market, "en")
        flag = LANG_FLAGS.get(lang, "🌐")
        col.metric(market, f"{len(sources.get(market, []))} domain(s)", f"{flag} {LANGUAGE_LABELS.get(lang, lang)}")
else:
    st.info("No markets configured.")

st.divider()

# ── Édition par marché ─────────────────────────────────────────────────────────
st.subheader("✏️ Edit a market")

tab_labels = markets + ["➕ New market"]
tabs = st.tabs(tab_labels)

LANG_OPTIONS = {
    "en": "🇬🇧 English",
    "fr": "🇫🇷 French",
    "zh": "🇨🇳 Mandarin Chinese",
    "es": "🇪🇸 Spanish",
    "de": "🇩🇪 German",
    "ja": "🇯🇵 Japanese",
    "ko": "🇰🇷 Korean",
    "pt": "🇧🇷 Portuguese",
    "it": "🇮🇹 Italian",
    "nl": "🇳🇱 Dutch",
}

# Onglets marchés existants
for tab, market in zip(tabs[:-1], markets):
    with tab:
        col_edit, col_lang, col_delete = st.columns([3, 1.5, 1])

        with col_edit:
            st.markdown(f"**Monitored domains for {market}**")
            edited_domains = st.text_area(
                "One domain per line",
                value="\n".join(sources.get(market, [])),
                height=200,
                key=f"edit_{market}"
            )

        with col_lang:
            st.markdown("**Search language**")
            st.caption("Agent 1 will translate watch topics into this language before searching.")
            current_lang = lang_map.get(market, "en")
            lang_keys = list(LANG_OPTIONS.keys())
            lang_idx  = lang_keys.index(current_lang) if current_lang in lang_keys else 0
            new_lang  = st.selectbox(
                "Language",
                options=lang_keys,
                index=lang_idx,
                format_func=lambda l: LANG_OPTIONS[l],
                key=f"lang_{market}",
                label_visibility="collapsed"
            )
            if new_lang != current_lang:
                st.info(f"Will search in **{LANG_OPTIONS[new_lang]}** for this market.")

        with col_delete:
            st.markdown("**Delete**")
            st.warning(f"This will delete **{market}** and its {len(sources.get(market,[]))} domain(s).")
            confirm = st.checkbox("Confirm deletion", key=f"confirm_del_{market}")
            if st.button(f"🗑️ Delete {market}", key=f"del_{market}",
                         disabled=not confirm, type="secondary"):
                del sources[market]
                if market in lang_map:
                    del lang_map[market]
                sources[LANG_KEY] = lang_map
                save_sources(sources, SOURCES_FILE)
                st.success(f"Market **{market}** deleted.")
                st.rerun()

        if st.button(f"💾 Save {market}", key=f"save_{market}", type="primary"):
            sources[market] = [d.strip() for d in edited_domains.split("\n") if d.strip()]
            lang_map[market] = new_lang
            sources[LANG_KEY] = lang_map
            save_sources(sources, SOURCES_FILE)
            st.success(
                f"✓ {len(sources[market])} domain(s) saved for **{market}** "
                f"· Language: {LANG_OPTIONS[new_lang]}"
            )
            st.rerun()

        st.divider()
        st.markdown("**Preview**")
        for d in sources.get(market, []):
            st.markdown(f"- `{d}`")

# ── Nouveau marché ─────────────────────────────────────────────────────────────
with tabs[-1]:
    st.markdown("**Create a new market**")

    col_a, col_b = st.columns(2)
    with col_a:
        new_name = st.text_input("Market name *", placeholder="e.g. Japan, Nordic, APAC")
    with col_b:
        new_lang_key = st.selectbox(
            "Search language *",
            options=list(LANG_OPTIONS.keys()),
            format_func=lambda l: LANG_OPTIONS[l],
            help="Agent 1 will translate watch topics into this language before searching official sources."
        )

    new_domains_text = st.text_area(
        "Initial domains (one per line)",
        placeholder="e.g.:\nmeti.go.jp\njsa.or.jp\nbiken.or.jp",
        height=150
    )

    # Suggestions par région
    with st.expander("💡 Domain suggestions by region"):
        suggestions = {
            "Germany 🇩🇪":  ["bsi.bund.de", "bundesanzeiger.de", "din.de", "vde.com"],
            "Nordic 🇸🇪":   ["dsb.dk", "elsaekerhetsverket.se", "nkom.no", "traficom.fi"],
            "USA 🇺🇸":      ["fcc.gov", "cpsc.gov", "ftc.gov", "federalregister.gov"],
            "UK 🇬🇧":       ["gov.uk", "legislation.gov.uk", "ofcom.org.uk"],
            "Japan 🇯🇵":    ["meti.go.jp", "soumu.go.jp", "jsa.or.jp"],
            "South Korea 🇰🇷": ["msit.go.kr", "rra.go.kr", "kats.go.kr"],
            "Brazil 🇧🇷":   ["anatel.gov.br", "inmetro.gov.br"],
        }
        for region, domains in suggestions.items():
            st.markdown(f"**{region}** : {' · '.join(f'`{d}`' for d in domains)}")

    if st.button("✅ Create market", type="primary", disabled=not new_name.strip()):
        name = new_name.strip()
        if name in sources:
            st.error(f"Market **{name}** already exists.")
        else:
            sources[name] = [d.strip() for d in new_domains_text.split("\n") if d.strip()]
            lang_map[name] = new_lang_key
            sources[LANG_KEY] = lang_map
            save_sources(sources, SOURCES_FILE)
            st.success(
                f"✓ Market **{name}** created with {len(sources[name])} domain(s) "
                f"· Language: {LANG_OPTIONS[new_lang_key]}"
            )
            st.rerun()

st.divider()

# ── Export / Import ────────────────────────────────────────────────────────────
st.subheader("📤 Export / Import configuration")

col_exp, col_imp = st.columns(2)
with col_exp:
    st.markdown("**Export configuration**")
    st.caption("Download your sources configuration to save or share it.")
    st.download_button(
        "⬇️ Download sources.json",
        data=json.dumps(sources, indent=2, ensure_ascii=False),
        file_name="sources.json",
        mime="application/json"
    )

with col_imp:
    st.markdown("**Import configuration**")
    st.caption("Replace the current configuration with a sources.json file.")
    uploaded = st.file_uploader("Choose a sources.json file", type="json")
    if uploaded:
        try:
            imported = json.load(uploaded)
            if isinstance(imported, dict):
                imported_markets = [k for k in imported if not k.startswith("_")]
                st.write(f"Valid file — {len(imported_markets)} market(s) detected: {', '.join(imported_markets)}")
                if st.button("✅ Confirm import", type="primary"):
                    save_sources(imported, SOURCES_FILE)
                    st.success("Configuration imported ✓")
                    st.rerun()
            else:
                st.error("Invalid format — file must contain a JSON object.")
        except Exception as e:
            st.error(f"Read error: {e}")
