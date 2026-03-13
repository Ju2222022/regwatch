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
    TAVILY_KEY    = st.secrets.get("TAVILY_API_KEY", "")
    JINA_KEY      = st.secrets.get("JINA_API_KEY", "")
except Exception:
    ANTHROPIC_KEY = ""
    TAVILY_KEY = ""
    JINA_KEY = ""

HAIKU_COST_IN   = 0.80  / 1_000_000
HAIKU_COST_OUT  = 4.00  / 1_000_000
SONNET_COST_IN  = 3.00  / 1_000_000
SONNET_COST_OUT = 15.00 / 1_000_000

CONFIDENCE_COLORS = {
    "HIGH":   "#1B5E20",   # green
    "MEDIUM": "#E65100",   # orange
    "LOW":    "#B71C1C",   # red
    "":       "#37474F",   # grey fallback
}


def _badge(cat_id: str, confidence: str = "") -> str:
    color = CONFIDENCE_COLORS.get(str(confidence).upper(), CONFIDENCE_COLORS[""])
    label = CAT_LABELS.get(cat_id, cat_id).split("(")[0].strip()[:35]
    return f'<span style="background:{color};color:white;padding:3px 10px;border-radius:12px;font-size:0.82em;margin:2px;display:inline-block">{cat_id} — {label}</span>'


def _display_specs_block(profile: dict):
    """Display compact product specs from Agent 2 output."""
    if not profile.get("found"):
        st.warning(f"⚠️ Product specs not found for **{profile.get('code','?')}** — classification based on provided info only.")
        return

    techs = profile.get("technologies", {})
    wireless     = techs.get("wireless", [])
    power        = techs.get("power", [])
    sensors      = techs.get("sensors", [])
    connectivity = techs.get("connectivity", [])
    primary      = techs.get("primary_function", "")
    key_specs    = profile.get("key_specs", {})

    name = profile.get("name", "—")
    desc = profile.get("description", "")
    st.markdown(f"**{name}**" + (f" — {desc[:180]}" if desc else ""))
    if primary:
        st.caption(f"Primary function: {primary}")

    col_a, col_b = st.columns(2)
    with col_a:
        if wireless:
            st.markdown("🛜 **Wireless:** " + " · ".join(wireless))
        if power:
            st.markdown("⚡ **Power:** " + " · ".join(power))
    with col_b:
        if sensors:
            st.markdown("📡 **Sensors:** " + " · ".join(sensors))
        if connectivity:
            st.markdown("🔗 **Connectivity:** " + " · ".join(connectivity))

    # Key specs row
    specs_parts = []
    if key_specs.get("battery_life"):
        specs_parts.append(f"🔋 {key_specs['battery_life']}")
    if key_specs.get("water_resistance"):
        specs_parts.append(f"💧 {key_specs['water_resistance']}")
    if key_specs.get("weight"):
        specs_parts.append(f"⚖️ {key_specs['weight']}")
    for o in key_specs.get("other", []):
        specs_parts.append(o)
    if specs_parts:
        st.caption(" · ".join(specs_parts))

    url = profile.get("url", "")
    if url:
        st.caption(f"Source: [{url}]({url})")


def _display_classification(result: dict):
    """Display Agent 3 classification output."""
    cats        = result.get("assigned_categories", result.get("categories", []))
    confidence  = result.get("confidence_global", result.get("confidence", ""))
    justif      = result.get("category_justification", {})
    flags_raw   = result.get("flags", {})
    det         = result.get("detected_technologies", {})

    if not cats:
        st.error("No categories returned.")
        return

    # ── Badges + confidence ───────────────────────────────────────────────────
    col_cat, col_conf = st.columns([3, 1])
    with col_cat:
        st.markdown("**Assigned categories:**")
        badges_html = " ".join(_badge(cat, confidence) for cat in cats)
        st.markdown(badges_html, unsafe_allow_html=True)
    with col_conf:
        conf_icon = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(
            str(confidence).upper(), "⚪")
        st.metric("Confidence", f"{conf_icon} {confidence}" if confidence else "—")

    # ── Detected technologies ─────────────────────────────────────────────────
    confirmed = det.get("confirmed", [])
    implied   = det.get("implied", [])
    uncertain = det.get("uncertain", [])
    if confirmed or implied or uncertain:
        with st.expander("🔬 Detected technologies"):
            if confirmed:
                tags = "".join(
                    f'<span style="background:#1B5E20;color:white;padding:2px 8px;'
                    f'border-radius:10px;font-size:0.8em;margin:2px;display:inline-block">✅ {t}</span>'
                    for t in confirmed
                )
                st.markdown(tags, unsafe_allow_html=True)
            if implied:
                tags = "".join(
                    f'<span style="background:#E65100;color:white;padding:2px 8px;'
                    f'border-radius:10px;font-size:0.8em;margin:2px;display:inline-block">🟡 {t}</span>'
                    for t in implied
                )
                st.markdown(tags, unsafe_allow_html=True)
            if uncertain:
                tags = "".join(
                    f'<span style="background:#37474F;color:white;padding:2px 8px;'
                    f'border-radius:10px;font-size:0.8em;margin:2px;display:inline-block">❓ {t}</span>'
                    for t in uncertain
                )
                st.markdown(tags, unsafe_allow_html=True)

    # ── Justification par catégorie ───────────────────────────────────────────
    if justif and isinstance(justif, dict):
        with st.expander("📋 Category justification"):
            for cat_id, reason in justif.items():
                cat_label = CAT_LABELS.get(cat_id, cat_id).split("(")[0].strip()
                conf_color = {"HIGH": "#1B5E20", "MEDIUM": "#E65100",
                              "LOW":  "#B71C1C"}.get(str(confidence).upper(), "#37474F")
                st.markdown(
                    f'<div style="border-left:3px solid {conf_color};'
                    f'padding:6px 12px;margin:4px 0;border-radius:0 6px 6px 0;'
                    f'background:rgba(255,255,255,0.04)">' 
                    f'<span style="font-weight:600">{cat_id}</span> — {cat_label}<br/>'
                    f'<span style="color:#aaa;font-size:0.88em">{reason}</span></div>',
                    unsafe_allow_html=True
                )

    # ── Flags ─────────────────────────────────────────────────────────────────
    FLAG_CONFIG = {
        "protocol_to_confirm":    ("🔍 Protocols to confirm",    "#1565C0"),
        "categories_if_confirmed":("➕ Categories if confirmed",  "#6A1B9A"),
        "regulatory_edge_cases":  ("⚖️ Regulatory edge cases",   "#B71C1C"),
    }
    has_flags = False
    if isinstance(flags_raw, dict):
        has_flags = any(v for v in flags_raw.values())
    elif isinstance(flags_raw, list):
        has_flags = bool(flags_raw)

    if has_flags:
        with st.expander("⚠️ Flags"):
            if isinstance(flags_raw, dict):
                for key, (label, color) in FLAG_CONFIG.items():
                    items = flags_raw.get(key, [])
                    if not items:
                        continue
                    st.markdown(
                        f'<div style="font-weight:600;color:{color};'
                        f'margin-top:8px;margin-bottom:4px">{label}</div>',
                        unsafe_allow_html=True
                    )
                    for item in (items if isinstance(items, list) else [items]):
                        st.markdown(
                            f'<div style="padding:4px 10px;margin:2px 0;'
                            f'background:rgba(255,255,255,0.04);border-radius:4px;'
                            f'font-size:0.9em">• {item}</div>',
                            unsafe_allow_html=True
                        )
            else:
                for item in flags_raw:
                    st.markdown(f"- {item}")


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🏷️ Agent 3 — Regulatory Classifier")
st.caption("Fetches product specs via Agent 2, then classifies CAT1–CAT9 against Decathlon's regulatory framework.")
st.info("**Workflow:** 🔍 Agent 2 fetches specs by model code → 🏷️ Agent 3 classifies based on specs + your input")
st.divider()

if not ANTHROPIC_KEY:
    st.error("⚠️ Missing API key — check Streamlit secrets (ANTHROPIC_API_KEY).")
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
            domain = st.text_input("Domain *", value="decathlon.fr",
                                   placeholder="e.g. decathlon.fr, decathlon.ca",
                                   help="Domain to scrape — https://www.{domain}/search?Ntt={model_code}")

        col3, col4 = st.columns(2)
        with col3:
            product_name = st.text_input("Product name (fallback if not found)",
                                         placeholder="e.g. GPS Watch W500")
        with col4:
            product_type = st.text_input("Type / Description (optional)",
                                         placeholder="e.g. GPS sports watch")

        extra_info = st.text_input("Additional info (optional)",
                                   placeholder="e.g. Bluetooth, rechargeable via USB-C")

        submitted = st.form_submit_button("🏷️ Fetch specs & classify", type="primary")

    if submitted:
        if not model_code.strip():
            st.warning("Model code is required.")
        else:
            # Step 1: Fetch specs via Agent 2
            with st.spinner(f"🔍 Agent 2 — Scraping **{domain.strip()}** for **{model_code.strip()}**…"):
                profile = profile_product(model_code.strip(), domain.strip(), JINA_KEY, ANTHROPIC_KEY, TAVILY_KEY, name_hint=product_name.strip())

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

            # Build classifier input: A2 scrape is priority, user inputs fill gaps
            classifier_input = profile_to_classifier_input(profile)
            if not classifier_input.get("name"):
                classifier_input["name"] = product_name.strip()
            if not classifier_input.get("type"):
                classifier_input["type"] = product_type.strip()
            if extra_info.strip():
                existing = classifier_input.get("extra_info", "")
                classifier_input["extra_info"] = (existing + ", " + extra_info.strip()).strip(", ")

            # Step 2: Classify via Agent 3
            with st.spinner("🏷️ Agent 3 — Classifying…"):
                extra = classifier_input.get("extra_info", "")
                if classifier_input.get("description"):
                    extra = (classifier_input["description"] + " " + extra).strip()
                name_for_a3 = classifier_input.get("name") or classifier_input["code"]
                result = classify_product(
                    ANTHROPIC_KEY,
                    classifier_input["code"],
                    name_for_a3,
                    classifier_input.get("type", ""),
                    extra,
                )

            # Display classification block
            st.markdown("### 🏷️ Classification (Agent 3)")
            _display_classification(result)

            # Track A3 tokens (Haiku)
            tok3 = result.get("_tokens", {})
            t3_in  = tok3.get("input", 0)
            t3_out = tok3.get("output", 0)
            # classify_product doesn't expose tokens — estimate from typical usage
            cost3  = t3_in * HAIKU_COST_IN + t3_out * HAIKU_COST_OUT
            st.session_state["session_tokens"]["input"]  += t3_in
            st.session_state["session_tokens"]["output"] += t3_out
            st.session_state["session_tokens"]["cost"]   += cost3

# ─────────────────────────────────────────────────────────────────────────────
# BATCH MODE
# ─────────────────────────────────────────────────────────────────────────────
else:
    st.markdown("**Upload a CSV or Excel file** with your product list.")
    st.caption("Required column: `code` (model code). Optional: `name`, `type`, `extra_info`.")

    # ── Download template ──────────────────────────────────────────────────
    template_csv = "code,name,type,extra_info\n8788459,GPS Watch W500,GPS sports watch,Bluetooth rechargeable USB-C\n2679873,Heart Rate Sensor,chest strap,ANT+ Bluetooth\n"
    st.download_button(
        "⬇️ Download CSV template",
        data=template_csv,
        file_name="classifier_batch_template.csv",
        mime="text/csv",
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

            if "code" not in df.columns:
                st.error("❌ Column 'code' not found. Please check your file headers.")
            else:
                df = df.fillna("")
                products = []
                for _, row in df.iterrows():
                    code = str(row.get("code", "")).strip()
                    if code:
                        products.append({
                            "code":       code,
                            "name":       str(row.get("name", "")).strip(),
                            "type":       str(row.get("type", "")).strip(),
                            "extra_info": str(row.get("extra_info", "")).strip(),
                        })

                preview_cols = [col for col in ["code", "name", "type", "extra_info"] if col in df.columns]
                st.success(f"✅ {len(products)} products loaded.")
                st.dataframe(df[preview_cols].head(10), use_container_width=True)

                domain_batch = st.text_input(
                    "Domain *", value="decathlon.fr",
                    placeholder="e.g. decathlon.fr, decathlon.ca",
                    key="domain_batch_cls",
                    help="Domain to scrape for all products in this batch"
                )
                if st.button("🏷️ Fetch specs & classify all", type="primary"):
                    progress_bar = st.progress(0, text="Initialising…")
                    all_results = []

                    for i, prod in enumerate(products):
                        code = prod["code"]
                        progress_bar.progress(i / len(products), text=f"[{i+1}/{len(products)}] {code} — fetching specs…")

                        # A2
                        profile = profile_product(code, domain_batch, JINA_KEY, ANTHROPIC_KEY, TAVILY_KEY, name_hint=prod.get("name",""))
                        tok2 = profile.get("_tokens", {})
                        t2_in, t2_out = tok2.get("input", 0), tok2.get("output", 0)
                        st.session_state["session_tokens"]["input"]  += t2_in
                        st.session_state["session_tokens"]["output"] += t2_out
                        st.session_state["session_tokens"]["cost"]   += t2_in * HAIKU_COST_IN + t2_out * HAIKU_COST_OUT

                        # Merge inputs — A2 scrape is priority, CSV fields fill gaps only
                        ci = profile_to_classifier_input(profile)
                        # A2 scraped name takes priority — CSV value is fallback only
                        if not ci.get("name"):
                            ci["name"] = prod["name"]
                        # A2 scraped type takes priority — CSV value is fallback only
                        if not ci.get("type"):
                            ci["type"] = prod["type"]
                        # extra_info is always additive (CSV can enrich)
                        if prod["extra_info"]:
                            ci["extra_info"] = (ci.get("extra_info", "") + ", " + prod["extra_info"]).strip(", ")

                        progress_bar.progress((i + 0.5) / len(products), text=f"[{i+1}/{len(products)}] {code} — classifying…")

                        # A3
                        extra = ci.get("extra_info", "")
                        if ci.get("description"):
                            extra = (ci["description"] + " " + extra).strip()
                        result = classify_product(
                            ANTHROPIC_KEY,
                            ci["code"],
                            ci.get("name") or ci["code"],
                            ci.get("type", ""),
                            extra,
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
                        cats   = result.get("assigned_categories", result.get("categories", []))
                        label  = f"{'✅' if prof.get('found') else '⚠️'} {prod['code']} — {prod['name'] or prof.get('name','?')} → {', '.join(cats) if cats else '?'}"
                        with st.expander(label):
                            st.markdown("**📦 Specs (Agent 2)**")
                            _display_specs_block(prof)
                            st.markdown("**🏷️ Classification (Agent 3)**")
                            _display_classification(result)

                    # Export
                    export = [
                        {
                            "code":       item["product"]["code"],
                            "name":       item["profile"].get("name") or item["product"]["name"],
                            "found":      item["profile"].get("found"),
                            "categories": item["classification"].get("assigned_categories", item["classification"].get("categories", [])),
                            "confidence": item["classification"].get("confidence_global", item["classification"].get("confidence", "")),
                        }
                        for item in all_results
                    ]
                    st.download_button(
                        "⬇️ Download results (JSON)",
                        data=json.dumps(export, indent=2, ensure_ascii=False),
                        file_name="classifier_batch_results.json",
                        mime="application/json",
                    )
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")

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
