"""
pages/6_Classifier.py — Agent 3: Regulatory Classifier
Fetches product specs via Agent 2 (by model code) then classifies CAT1-CAT9.
Both blocks are shown: specs (from A2) + classification (from A3).
"""

import streamlit as st
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.referential import get_cat_labels as _get_cat_labels
from agent2.profiler import profile_product, profile_to_classifier_input
from agent3.classifier import classify_product, classify_batch

st.set_page_config(page_title="Classifier · RegWatch", page_icon="🏷️", layout="wide")

CAT_LABELS = _get_cat_labels()

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

HAIKU_COST_IN   = 0.80  / 1_000_000
HAIKU_COST_OUT  = 4.00  / 1_000_000
SONNET_COST_IN  = 3.00  / 1_000_000
SONNET_COST_OUT = 15.00 / 1_000_000

CAT_COLORS = {
    "CAT1": "#1565C0", "CAT2": "#F57F17", "CAT3": "#1B5E20",
    "CAT4": "#6A1B9A", "CAT5": "#AD1457", "CAT6": "#00838F",
    "CAT7": "#E65100", "CAT8": "#37474F", "CAT9": "#2E7D32",
}


def _badge(cat_id: str) -> str:
    color = CAT_COLORS.get(cat_id, "#555")
    label = CAT_LABELS.get(cat_id, cat_id).split("(")[0].strip()[:35]
    return f'<span style="background:{color};color:white;padding:3px 10px;border-radius:12px;font-size:0.82em;margin:2px;display:inline-block">{cat_id} — {label}</span>'


def _display_specs_block(profile: dict):
    """Display compact product specs from Agent 2 output."""
    if not profile.get("found"):
        st.warning(f"⚠️ Product specs not found for **{profile.get('code','?')}** — classification based on provided info only.")
        return

    techs = profile.get("technologies", {})
    wireless = techs.get("wireless", [])
    power    = techs.get("power", [])
    sensors  = techs.get("sensors", [])

    st.markdown(f"**{profile.get('name','—')}** — {profile.get('description','')[:150]}")

    all_tech = wireless + power + sensors + techs.get("connectivity", [])
    if all_tech:
        st.caption("Detected: " + " · ".join(all_tech))
    else:
        st.caption("No specific technologies detected via scraping.")

    url = profile.get("url", "")
    if url:
        st.caption(f"Source: [{url}]({url})")


def _display_classification(result: dict):
    """Display Agent 3 classification output."""
    cats = result.get("categories", [])
    confidence = result.get("confidence", "")
    reasoning  = result.get("reasoning", "")
    flags      = result.get("flags", [])

    if not cats:
        st.error("No categories returned.")
        return

    st.markdown("**Assigned categories:**")
    badges_html = " ".join(_badge(c) for c in cats)
    st.markdown(badges_html, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Confidence", confidence or "—")
    with col2:
        if flags:
            st.markdown("**⚠️ Flags**")
            for f in flags:
                st.markdown(f"- {f}")

    if reasoning:
        with st.expander("📋 Reasoning"):
            st.markdown(reasoning)


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🏷️ Agent 3 — Regulatory Classifier")
st.caption("Fetches product specs via Agent 2, then classifies CAT1–CAT9 against Decathlon's regulatory framework.")
st.info("**Workflow:** 🔍 Agent 2 fetches specs by model code → 🏷️ Agent 3 classifies based on specs + your input")
st.divider()

if not ANTHROPIC_KEY or not TAVILY_KEY or not JINA_KEY:
    st.error("⚠️ Missing API keys — check Streamlit secrets.")
    st.stop()

mode = st.radio("Mode", ["Single product", "Batch"], horizontal=True)

# ─────────────────────────────────────────────────────────────────────────────
# SINGLE PRODUCT
# ─────────────────────────────────────────────────────────────────────────────
if mode == "Single product":
    with st.form("classifier_single"):
        st.markdown("#### Product information")
        col1, col2 = st.columns(2)
        with col1:
            model_code   = st.text_input("Model code *", placeholder="e.g. 8788459")
        with col2:
            product_name = st.text_input("Product name *", placeholder="e.g. Decathlon GPS Watch W500")

        col3, col4 = st.columns(2)
        with col3:
            product_type = st.text_input(
                "Type / Description (optional)",
                placeholder="e.g. GPS sports watch with heart rate monitor"
            )
        with col4:
            extra_info = st.text_input(
                "Additional info (optional)",
                placeholder="e.g. Bluetooth, rechargeable via USB-C, barometric altimeter"
            )

        submitted = st.form_submit_button("🏷️ Fetch specs & classify", type="primary")

    if submitted:
        if not model_code.strip() or not product_name.strip():
            st.warning("Model code and product name are required.")
        else:
            # Step 1: Fetch specs via Agent 2
            with st.spinner(f"🔍 Agent 2 — Fetching specs for **{model_code.strip()}**…"):
                profile = profile_product(model_code.strip(), TAVILY_KEY, JINA_KEY, ANTHROPIC_KEY)

            # Display specs block
            st.markdown("### 📦 Product specs (Agent 2)")
            _display_specs_block(profile)
            st.divider()

            # Track A2 tokens (Haiku)
            tok2 = profile.get("_tokens", {})
            t2_in  = tok2.get("input", 0)
            t2_out = tok2.get("output", 0)
            cost2  = t2_in * HAIKU_COST_IN + t2_out * HAIKU_COST_OUT
            st.session_state["session_tokens"]["input"]  += t2_in
            st.session_state["session_tokens"]["output"] += t2_out
            st.session_state["session_tokens"]["cost"]   += cost2

            # Build classifier input: merge profile with user inputs
            classifier_input = profile_to_classifier_input(profile)
            classifier_input["name"]        = product_name.strip() or classifier_input.get("name", "")
            classifier_input["type"]        = product_type.strip() or classifier_input.get("type", "")
            if extra_info.strip():
                existing = classifier_input.get("extra_info", "")
                classifier_input["extra_info"] = (existing + ", " + extra_info.strip()).strip(", ")

            # Step 2: Classify via Agent 3
            with st.spinner("🏷️ Agent 3 — Classifying…"):
                result = classify_product(
                    code=classifier_input["code"],
                    name=classifier_input["name"],
                    product_type=classifier_input.get("type", ""),
                    description=classifier_input.get("description", ""),
                    extra_info=classifier_input.get("extra_info", ""),
                    api_key=ANTHROPIC_KEY,
                )

            # Display classification block
            st.markdown("### 🏷️ Classification (Agent 3)")
            _display_classification(result)

            # Track A3 tokens (Haiku)
            tok3 = result.get("_tokens", {})
            t3_in  = tok3.get("input", 0)
            t3_out = tok3.get("output", 0)
            cost3  = t3_in * HAIKU_COST_IN + t3_out * HAIKU_COST_OUT
            st.session_state["session_tokens"]["input"]  += t3_in
            st.session_state["session_tokens"]["output"] += t3_out
            st.session_state["session_tokens"]["cost"]   += cost3

# ─────────────────────────────────────────────────────────────────────────────
# BATCH MODE
# ─────────────────────────────────────────────────────────────────────────────
else:
    st.markdown("**Format:** one product per line — `model_code | product_name | type (optional) | extra_info (optional)`")
    with st.form("classifier_batch"):
        batch_raw = st.text_area(
            "Products (one per line) *",
            placeholder="8788459 | GPS Watch W500 | GPS sports watch | Bluetooth, USB-C rechargeable\n2679873 | Heart Rate Sensor | chest strap | ANT+, Bluetooth",
            height=150,
        )
        submitted = st.form_submit_button("🏷️ Fetch specs & classify all", type="primary")

    if submitted:
        lines = [l.strip() for l in batch_raw.strip().splitlines() if l.strip()]
        if not lines:
            st.warning("Please enter at least one product.")
        else:
            products = []
            for line in lines:
                parts = [p.strip() for p in line.split("|")]
                products.append({
                    "code":        parts[0] if len(parts) > 0 else "",
                    "name":        parts[1] if len(parts) > 1 else "",
                    "type":        parts[2] if len(parts) > 2 else "",
                    "extra_info":  parts[3] if len(parts) > 3 else "",
                })

            progress_bar = st.progress(0, text="Initialising…")
            all_results = []

            for i, prod in enumerate(products):
                code = prod["code"]
                progress_bar.progress(i / len(products), text=f"[{i+1}/{len(products)}] {code} — fetching specs…")

                # A2
                profile = profile_product(code, TAVILY_KEY, JINA_KEY, ANTHROPIC_KEY)
                tok2 = profile.get("_tokens", {})
                t2_in, t2_out = tok2.get("input", 0), tok2.get("output", 0)
                st.session_state["session_tokens"]["input"]  += t2_in
                st.session_state["session_tokens"]["output"] += t2_out
                st.session_state["session_tokens"]["cost"]   += t2_in * HAIKU_COST_IN + t2_out * HAIKU_COST_OUT

                # Merge inputs
                ci = profile_to_classifier_input(profile)
                ci["name"] = prod["name"] or ci.get("name", "")
                ci["type"] = prod["type"] or ci.get("type", "")
                if prod["extra_info"]:
                    ci["extra_info"] = (ci.get("extra_info", "") + ", " + prod["extra_info"]).strip(", ")

                progress_bar.progress((i + 0.5) / len(products), text=f"[{i+1}/{len(products)}] {code} — classifying…")

                # A3
                result = classify_product(
                    code=ci["code"], name=ci["name"],
                    product_type=ci.get("type", ""),
                    description=ci.get("description", ""),
                    extra_info=ci.get("extra_info", ""),
                    api_key=ANTHROPIC_KEY,
                )
                tok3 = result.get("_tokens", {})
                t3_in, t3_out = tok3.get("input", 0), tok3.get("output", 0)
                st.session_state["session_tokens"]["input"]  += t3_in
                st.session_state["session_tokens"]["output"] += t3_out
                st.session_state["session_tokens"]["cost"]   += t3_in * HAIKU_COST_IN + t3_out * HAIKU_COST_OUT

                all_results.append({"product": prod, "profile": profile, "classification": result})

            progress_bar.progress(1.0, text="Done!")
            st.success(f"✅ {len(all_results)} products classified.")

            for item in all_results:
                prod   = item["product"]
                prof   = item["profile"]
                result = item["classification"]
                cats   = result.get("categories", [])
                label  = f"{'✅' if prof.get('found') else '⚠️'} {prod['code']} — {prod['name'] or prof.get('name','?')} → {', '.join(cats) if cats else '?'}"

                with st.expander(label):
                    st.markdown("**📦 Specs (Agent 2)**")
                    _display_specs_block(prof)
                    st.markdown("**🏷️ Classification (Agent 3)**")
                    _display_classification(result)

            # Export
            export = [
                {
                    "code": item["product"]["code"],
                    "name": item["product"]["name"],
                    "found": item["profile"].get("found"),
                    "categories": item["classification"].get("categories", []),
                    "confidence": item["classification"].get("confidence", ""),
                }
                for item in all_results
            ]
            st.download_button(
                "⬇️ Download results (JSON)",
                data=json.dumps(export, indent=2, ensure_ascii=False),
                file_name="classifier_batch_results.json",
                mime="application/json",
            )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
sess = st.session_state["session_tokens"]
tot_in  = sess["input"]
tot_out = sess["output"]
tot_cost = sess["cost"]
cost_str = "N/A" if (tot_in == 0 and tot_out == 0) else f"${tot_cost:.4f}"
st.caption(
    f"📊 Session tokens — Input: {tot_in:,} · Output: {tot_out:,} · "
    f"Estimated cost: {cost_str} (Haiku)"
)
