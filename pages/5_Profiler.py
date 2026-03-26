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
    st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
# Guard against stale session state from older versions
_st = st.session_state["session_tokens"]
for _k, _v in {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}.items():
    if _k not in _st:
        _st[_k] = _v

# ── API keys ──────────────────────────────────────────────────────────────────
try:
    ANTHROPIC_KEY = st.secrets["ANTHROPIC_API_KEY"]
    TAVILY_KEY    = st.secrets.get("TAVILY_API_KEY", "")
    JINA_KEY      = st.secrets.get("JINA_API_KEY", "")
except Exception:
    ANTHROPIC_KEY = ""
    TAVILY_KEY = ""
    JINA_KEY = ""

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
st.info("📋 **Output:** product name, description, detected technologies (wireless, power, sensors) and key specs. Results are ready to feed into Agent 3 (Classifier).\n\n🔍 **Method:** Claude web search — searches the web for the model code on the specified domain.")
st.divider()

if not ANTHROPIC_KEY:
    st.error("⚠️ Missing API key — check Streamlit secrets (ANTHROPIC_API_KEY). JINA_API_KEY is optional.")
    st.stop()

mode = st.radio("Mode", ["Single product", "Batch"], horizontal=True)

# ─────────────────────────────────────────────────────────────────────────────
if mode == "Single product":
    with st.form("profiler_single"):
        model_code = st.text_input(
            "Model code *",
            placeholder="e.g. 8788459",
        )
        domain = st.text_input(
            "Domain *",
            value="decathlon.fr",
            placeholder="e.g. decathlon.fr, decathlon.ca, decathlon.de",
            help="Tavily will find the product page on this domain"
        )
        submitted = st.form_submit_button("🔍 Fetch product specs", type="primary")

    if submitted:
        if not model_code.strip():
            st.warning("Please enter a model code.")
        else:
            with st.spinner(f"Scraping **{domain.strip()}** for **{model_code.strip()}**…"):
                profile = profile_product(model_code.strip(), domain.strip(), JINA_KEY, ANTHROPIC_KEY, TAVILY_KEY)

            tok = profile.get("_tokens", {})
            tok_in  = tok.get("input", 0)
            tok_out = tok.get("output", 0)
            cost    = tok_in * HAIKU_COST_IN + tok_out * HAIKU_COST_OUT
            st.session_state["session_tokens"]["input"]  += tok_in
            st.session_state["session_tokens"]["output"] += tok_out
            st.session_state["session_tokens"]["cost_usd"] += cost

            _display_profile(profile)

            # ── Send to Agent 3 ───────────────────────────────────────────────
            if profile.get("found"):
                st.session_state["last_profile"] = profile
                st.divider()
                with st.container(border=True):
                    col_send, col_info = st.columns([2, 3])
                    with col_send:
                        st.markdown("**➡️ Ready for Classifier**")
                        if st.button("🏷️ Send to Agent 3 — Classifier", type="primary", key="send_to_classifier"):
                            st.switch_page("pages/6_Classifier.py")
                    with col_info:
                        st.caption(f"Product **{profile.get('name', profile.get('code',''))}** profiled — send to Agent 3 to classify into CAT1-CAT9.")

else:
    st.markdown("**Upload a CSV or Excel file** with a `code` column (one model code per row).")
    st.caption("Accepted columns: `code` (required). Other columns are ignored.")

    # ── Download template ──────────────────────────────────────────────────
    import io
    template_csv = "code\n8788459\n2679873\n1234567\n"
    st.download_button(
        "⬇️ Download CSV template",
        data=template_csv,
        file_name="profiler_batch_template.csv",
        mime="text/csv",
    )

    domain_batch = st.text_input(
        "Domain *", value="decathlon.fr",
        placeholder="e.g. decathlon.fr, decathlon.ca, decathlon.de",
        key="domain_batch",
        help="Domain used to search all products in this batch"
    )

    uploaded = st.file_uploader("Upload product list", type=["csv", "xlsx", "xls"])

    if uploaded:
        try:
            import pandas as pd
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)

            # Normalise column names
            df.columns = df.columns.str.lower().str.strip()
            for alias in ["model code", "model_code", "modèle", "ref", "reference"]:
                if alias in df.columns:
                    df = df.rename(columns={alias: "code"})
                    break
            # Force code column as string — Excel converts codes to numbers (8788459 → 8,788,459)
            if "code" in df.columns:
                df["code"] = df["code"].apply(
                    lambda x: str(int(float(str(x).replace(",", "").strip())))
                    if str(x).replace(",", "").replace(".", "").strip().isdigit()
                    else str(x).strip()
                )

            if "code" not in df.columns:
                st.error("❌ Column 'code' not found. Please check your file headers.")
            else:
                codes = [str(c).strip() for c in df["code"].dropna() if str(c).strip()]
                st.success(f"✅ {len(codes)} model codes loaded.")
                st.dataframe(df[["code"]].head(10), use_container_width=True)

                if st.button("🔍 Fetch all products", type="primary"):
                    progress_bar = st.progress(0, text="Initialising…")
                    results = []

                    def _progress_cb(i, total, code):
                        progress_bar.progress(i / total, text=f"[{i+1}/{total}] Fetching {code}…")

                    results = profile_batch(codes, domain_batch.strip(), JINA_KEY, ANTHROPIC_KEY, _progress_cb, TAVILY_KEY)
                    progress_bar.progress(1.0, text="Done!")

                    total_in  = sum(r.get("_tokens", {}).get("input", 0) for r in results)
                    total_out = sum(r.get("_tokens", {}).get("output", 0) for r in results)
                    cost = total_in * HAIKU_COST_IN + total_out * HAIKU_COST_OUT
                    st.session_state["session_tokens"]["input"]  += total_in
                    st.session_state["session_tokens"]["output"] += total_out
                    st.session_state["session_tokens"]["cost_usd"] += cost

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
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
sess = st.session_state["session_tokens"]
tot_in  = sess["input"]
tot_out = sess["output"]
tot_cost = sess["cost_usd"]
cost_str = "N/A" if (tot_in == 0 and tot_out == 0) else ("N/A" if tot_cost == 0 else f"${tot_cost:.4f}")
st.caption(
    f"📊 Session tokens — Input: {tot_in:,} · Output: {tot_out:,} · "
    f"Estimated cost: {cost_str} (Haiku)"
)
