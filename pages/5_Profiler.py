"""
pages/5_Profiler.py — Agent 2: Product Profiler
Scrapes and displays raw product specs from the web by model code.
No classification here — that's Agent 3's job.
"""

import streamlit as st
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent2.profiler import profile_product, profile_batch

st.set_page_config(page_title="Product Profiler · RegWatch", page_icon="🔍", layout="wide")

# ── Session state ─────────────────────────────────────────────────────────────
if "session_tokens" not in st.session_state:
    st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost": 0.0}

# ── API keys ──────────────────────────────────────────────────────────────────
try:
    ANTHROPIC_KEY = st.secrets["ANTHROPIC_API_KEY"]
    TAVILY_KEY    = st.secrets["TAVILY_API_KEY"]
    JINA_KEY      = st.secrets["JINA_API_KEY"]
except Exception:
    ANTHROPIC_KEY = TAVILY_KEY = JINA_KEY = ""

HAIKU_COST_IN  = 0.80 / 1_000_000
HAIKU_COST_OUT = 4.00 / 1_000_000


def _display_profile(profile: dict):
    """Render a product profile as structured Streamlit blocks."""
    found = profile.get("found", False)
    code  = profile.get("code", "?")
    name  = profile.get("name") or "—"
    brand = profile.get("brand") or "—"
    url   = profile.get("url", "")
    desc  = profile.get("description") or "—"
    error = profile.get("error")

    if error:
        st.error(f"⚠️ Error fetching **{code}**: {error}")
        return

    if not found:
        st.warning(f"⚠️ Product **{code}** not found or page content not relevant.")
        if url:
            st.caption(f"URL attempted: [{url}]({url})")
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### {name}")
        st.caption(f"**Code:** {code} · **Brand:** {brand}")
    with col2:
        if url:
            st.link_button("🔗 View product page", url)

    st.markdown(f"**Description:** {desc}")
    st.divider()

    techs = profile.get("technologies", {})
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**🛜 Wireless protocols**")
        wireless = techs.get("wireless", [])
        for w in wireless:
            st.markdown(f"- {w}")
        if not wireless:
            st.caption("None detected")

        st.markdown("**⚡ Power / Charging**")
        power = techs.get("power", [])
        for p in power:
            st.markdown(f"- {p}")
        if not power:
            st.caption("None detected")

    with col_b:
        st.markdown("**📡 Sensors**")
        sensors = techs.get("sensors", [])
        for s in sensors:
            st.markdown(f"- {s}")
        if not sensors:
            st.caption("None detected")

        st.markdown("**🔗 Connectivity**")
        connectivity = techs.get("connectivity", [])
        for c in connectivity:
            st.markdown(f"- {c}")
        if not connectivity:
            st.caption("None detected")

    st.divider()
    key_specs = profile.get("key_specs", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Battery life", key_specs.get("battery_life") or "—")
    with col2:
        st.metric("Water resistance", key_specs.get("water_resistance") or "—")
    with col3:
        st.metric("Weight", key_specs.get("weight") or "—")
    other = key_specs.get("other", [])
    if other:
        st.caption("Other specs: " + " · ".join(other))

    with st.expander("🔧 Raw JSON output"):
        clean = {k: v for k, v in profile.items() if k != "_tokens"}
        st.json(clean)


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🔍 Agent 2 — Product Profiler")
st.caption("Fetches raw product specs from the web by model code. No classification — use Agent 3 for that.")
st.info("📋 **Output:** product name, description, detected technologies (wireless, power, sensors) and key specs. Results are ready to feed into Agent 3 (Classifier).")
st.divider()

if not ANTHROPIC_KEY or not TAVILY_KEY or not JINA_KEY:
    st.error("⚠️ Missing API keys — check Streamlit secrets (ANTHROPIC_API_KEY, TAVILY_API_KEY, JINA_API_KEY).")
    st.stop()

mode = st.radio("Mode", ["Single product", "Batch"], horizontal=True)

# ─────────────────────────────────────────────────────────────────────────────
if mode == "Single product":
    with st.form("profiler_single"):
        model_code = st.text_input(
            "Model code *",
            placeholder="e.g. 8788459",
            help="Decathlon model code — will be searched on decathlon.fr"
        )
        submitted = st.form_submit_button("🔍 Fetch product specs", type="primary")

    if submitted:
        if not model_code.strip():
            st.warning("Please enter a model code.")
        else:
            with st.spinner(f"Searching and scraping specs for **{model_code.strip()}**…"):
                profile = profile_product(model_code.strip(), TAVILY_KEY, JINA_KEY, ANTHROPIC_KEY)

            tok = profile.get("_tokens", {})
            tok_in  = tok.get("input", 0)
            tok_out = tok.get("output", 0)
            cost    = tok_in * HAIKU_COST_IN + tok_out * HAIKU_COST_OUT
            st.session_state["session_tokens"]["input"]  += tok_in
            st.session_state["session_tokens"]["output"] += tok_out
            st.session_state["session_tokens"]["cost"]   += cost

            _display_profile(profile)

else:
    with st.form("profiler_batch"):
        codes_raw = st.text_area(
            "Model codes (one per line) *",
            placeholder="8788459\n2679873\n1234567",
            height=120,
        )
        submitted = st.form_submit_button("🔍 Fetch all products", type="primary")

    if submitted:
        codes = [c.strip() for c in codes_raw.strip().splitlines() if c.strip()]
        if not codes:
            st.warning("Please enter at least one model code.")
        else:
            progress_bar = st.progress(0, text="Initialising…")
            results = []

            def _progress_cb(i, total, code):
                progress_bar.progress(i / total, text=f"[{i+1}/{total}] Fetching {code}…")

            with st.spinner("Fetching product specs…"):
                from agent2.profiler import profile_batch
                results = profile_batch(codes, TAVILY_KEY, JINA_KEY, ANTHROPIC_KEY, _progress_cb)

            progress_bar.progress(1.0, text="Done!")

            total_in  = sum(r.get("_tokens", {}).get("input", 0) for r in results)
            total_out = sum(r.get("_tokens", {}).get("output", 0) for r in results)
            cost = total_in * HAIKU_COST_IN + total_out * HAIKU_COST_OUT
            st.session_state["session_tokens"]["input"]  += total_in
            st.session_state["session_tokens"]["output"] += total_out
            st.session_state["session_tokens"]["cost"]   += cost

            st.success(f"✅ {len(results)} products fetched.")
            for r in results:
                label = f"{'✅' if r.get('found') else '❌'} {r.get('code','?')} — {r.get('name') or 'Not found'}"
                with st.expander(label):
                    _display_profile(r)

            clean = [{k: v for k, v in r.items() if k != "_tokens"} for r in results]
            st.download_button(
                "⬇️ Download batch results (JSON)",
                data=json.dumps(clean, indent=2, ensure_ascii=False),
                file_name="profiler_batch_results.json",
                mime="application/json",
            )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
sess = st.session_state["session_tokens"]
tot_in  = sess["input"]
tot_out = sess["output"]
tot_cost = sess["cost"]
cost_str = "N/A" if (tot_in == 0 and tot_out == 0) else ("N/A" if tot_cost == 0 else f"${tot_cost:.4f}")
st.caption(
    f"📊 Session tokens — Input: {tot_in:,} · Output: {tot_out:,} · "
    f"Estimated cost: {cost_str} (Haiku)"
)
