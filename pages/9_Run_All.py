"""
Page 9 — Run All
Orchestration des 3 flux RegWatch en mode guidé.

Flux 1 — Watch → Legal Sheet update  : A1 → A4 (Category) → A5A
Flux 2 — Product analysis             : A2 → A3 → A4 (Product) → A5B
Flux 3 — Full audit                   : A1 + A2 → A4 (both) → A5A + A5B
"""

import streamlit as st
import json
import time
import sys
import os
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent1.watcher import run_watch, load_sources, TIMEFRAMES
from agent2.profiler import profile_product, profile_to_classifier_input
from agent3.classifier import classify_product
from agent4.impact import analyze_product_impact, analyze_category_impact
from agent5a.updater import analyze_legal_sheet
try:
    from utils.legal_sheet_library import load_index, fetch_sheet_text
    LIBRARY_AVAILABLE = True
except Exception:
    LIBRARY_AVAILABLE = False
from agent5b.risk_mapper import generate_risk_mapping
from data.referential import get_cat_labels

st.set_page_config(page_title="Run All · RegWatch", page_icon="⚡", layout="wide")

# ── Session state ─────────────────────────────────────────────────────────────
if "session_tokens" not in st.session_state:
    st.session_state["session_tokens"] = {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
_st = st.session_state["session_tokens"]
for _k, _v in {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}.items():
    if _k not in _st:
        _st[_k] = _v

# ── API Keys ──────────────────────────────────────────────────────────────────
try:
    ANTHROPIC_KEY = st.secrets["ANTHROPIC_API_KEY"]
    TAVILY_KEY    = st.secrets.get("TAVILY_API_KEY", "")
    JINA_KEY      = st.secrets.get("JINA_API_KEY", "")
except Exception:
    ANTHROPIC_KEY = TAVILY_KEY = JINA_KEY = ""

HAIKU_IN   = 0.80  / 1_000_000
HAIKU_OUT  = 4.00  / 1_000_000
SONNET_IN  = 3.00  / 1_000_000
SONNET_OUT = 15.00 / 1_000_000

SOURCES_FILE = "data/sources.json"
CAT_LABELS   = get_cat_labels()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚡ Run All — Orchestrated Workflows")
st.caption("Chain multiple agents automatically — choose a workflow and let RegWatch do the rest.")

if not ANTHROPIC_KEY:
    st.error("⚠️ ANTHROPIC_API_KEY missing — check Streamlit secrets.")
    st.stop()

st.divider()

# ── Workflow selector ─────────────────────────────────────────────────────────
WORKFLOWS = {
    "📋 Flux 1 — Watch → Legal Sheet update": {
        "desc": "Run a regulatory watch, analyze category impact, then update legal sheets.",
        "steps": ["Agent 1 — Watch", "Agent 4 — Category impact", "Agent 5A — Legal Sheet"],
        "agents": "A1 → A4 (Category) → A5A",
        "needs_watch": True,
        "needs_product": False,
        "needs_product_impact": False,
    },
    "📦 Flux 2 — Product analysis": {
        "desc": "Profile a product, classify it, analyze regulatory impact, then generate risk mapping.",
        "steps": ["Agent 2 — Profiler", "Agent 3 — Classifier", "Agent 4 — Product impact", "Agent 5B — Risk Map"],
        "agents": "A2 → A3 → A4 (Product) → A5B",
        "needs_watch": False,
        "needs_product": True,
        "needs_product_impact": True,
    },
    "🔍 Flux 3 — Full audit": {
        "desc": "Combine regulatory watch AND product analysis for a complete regulatory audit.",
        "steps": ["Agent 1 — Watch", "Agent 2 — Profiler", "Agent 3 — Classifier",
                  "Agent 4 — Category + Product", "Agent 5A — Legal Sheet", "Agent 5B — Risk Map"],
        "agents": "A1 + A2 → A4 → A5A + A5B",
        "needs_watch": True,
        "needs_product": True,
        "needs_product_impact": True,
    },
}

selected_workflow = st.selectbox("Select a workflow", options=list(WORKFLOWS.keys()))
wf = WORKFLOWS[selected_workflow]

col_desc, col_steps = st.columns([2, 1])
with col_desc:
    st.info(f"**{wf['agents']}** — {wf['desc']}")
with col_steps:
    st.markdown("**Steps:**")
    for i, step in enumerate(wf["steps"], 1):
        st.caption(f"{i}. {step}")

st.divider()

# ── Parameters ────────────────────────────────────────────────────────────────
st.subheader("⚙️ Parameters")

params = {}

# ── Watch parameters (Flux 1 & 3) ────────────────────────────────────────────
if wf["needs_watch"]:
    st.markdown("**Regulatory Watch (Agent 1)**")
    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        params["watch_topic"] = st.text_input(
            "Watch topic *",
            placeholder="e.g. RoHS update EU 2025",
        )
    with col_w2:
        try:
            sources = load_sources(SOURCES_FILE)
            available_markets = [k for k in sources if not k.startswith("_")]
        except Exception:
            available_markets = ["EU", "France"]
        params["markets"] = st.multiselect("Markets", available_markets, default=["EU", "France"])
    with col_w3:
        params["timeframe"] = st.selectbox("Timeframe", options=list(TIMEFRAMES.keys()), index=1)

    params["watch_cats"] = st.multiselect(
        "Categories to analyze (Agent 4 — Category Mode)",
        options=list(CAT_LABELS.keys()),
        default=["CAT3", "CAT9"],
        format_func=lambda c: f"{c} — {CAT_LABELS.get(c,'').split('(')[0].strip()[:40]}"
    )
    st.divider()

# ── Product parameters (Flux 2 & 3) ──────────────────────────────────────────
if wf["needs_product"]:
    st.markdown("**Product Profiling (Agent 2 → 3 → 4 Product Mode → 5B)**")

    product_mode = st.radio("Product input mode", ["Single product", "Batch (CSV/Excel)"], horizontal=True)

    if product_mode == "Single product":
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            params["model_code"] = st.text_input("Model code *", placeholder="e.g. 8735154")
        with col_p2:
            params["domain"] = st.text_input("Domain", value="decathlon.fr")
        params["product_mode"] = "single"

    else:
        params["domain"] = st.text_input("Domain", value="decathlon.fr", key="domain_batch_run")
        uploaded = st.file_uploader("Upload product list (CSV/Excel with `code` column)", type=["csv", "xlsx", "xls"])
        if uploaded:
            try:
                if uploaded.name.endswith(".csv"):
                    df = pd.read_csv(uploaded)
                else:
                    df = pd.read_excel(uploaded)
                df.columns = df.columns.str.lower().str.strip()
                if "code" in df.columns:
                    df["code"] = df["code"].apply(
                        lambda x: str(int(float(str(x).replace(",", "").strip())))
                        if str(x).replace(",", "").replace(".", "").strip().isdigit()
                        else str(x).strip()
                    )
                    params["model_codes"] = [str(c).strip() for c in df["code"].dropna() if str(c).strip()]
                    st.success(f"✅ {len(params['model_codes'])} product codes loaded")
                    st.dataframe(df[["code"]].head(5), use_container_width=True)
                else:
                    st.error("Column 'code' not found.")
            except Exception as e:
                st.error(f"Error reading file: {e}")
        params["product_mode"] = "batch"

    st.divider()

# ── Launch ────────────────────────────────────────────────────────────────────
can_launch = True
if wf["needs_watch"] and not params.get("watch_topic", "").strip():
    can_launch = False
if wf["needs_product"]:
    if params.get("product_mode") == "single" and not params.get("model_code", "").strip():
        can_launch = False
    if params.get("product_mode") == "batch" and not params.get("model_codes"):
        can_launch = False

if not can_launch:
    st.info("Fill in the required parameters above to launch the workflow.")

if st.button("🚀 Launch workflow", type="primary", disabled=not can_launch):

    st.divider()
    st.subheader("📊 Execution")

    results   = {}
    total_cost = 0.0

    # ── Agent 1 — Watch ───────────────────────────────────────────────────────
    if wf["needs_watch"]:
        with st.status("📡 Agent 1 — Regulatory Watch...", expanded=True) as s1:
            try:
                st.write(f"Searching **{params['watch_topic']}** on {', '.join(params['markets'])}...")
                entries, stats = run_watch(
                    anthropic_key=ANTHROPIC_KEY,
                    tavily_key=TAVILY_KEY,
                    topic=params["watch_topic"],
                    markets=params["markets"],
                    timeframe_label=params["timeframe"],
                    sources_override=load_sources(SOURCES_FILE),
                )
                results["watch_entries"] = entries
                st.session_state["veille_results"] = entries
                cost_a1 = stats.get("cost_usd", 0)
                total_cost += cost_a1
                high = sum(1 for e in entries if e.get("urgency") == "HIGH")
                s1.update(label=f"✅ Agent 1 — {len(entries)} alert(s) · {high} HIGH · ${cost_a1:.4f}", state="complete")
            except Exception as e:
                s1.update(label=f"❌ Agent 1 error: {e}", state="error")
                st.stop()

    # ── Agent 4 — Category Mode ───────────────────────────────────────────────
    alerts = results.get("watch_entries", st.session_state.get("veille_results", []))

    if wf["needs_watch"] and alerts and params.get("watch_cats"):
        with st.status("📋 Agent 4 — Category Impact...", expanded=False) as s4c:
            try:
                impact_cat, tu4c = analyze_category_impact(
                    anthropic_key=ANTHROPIC_KEY,
                    alerts=alerts,
                    active_categories=params["watch_cats"],
                )
                results["impact_category"] = impact_cat
                st.session_state["impact_category_result"] = impact_cat
                cost_a4c = tu4c.get("cost_usd", 0)
                total_cost += cost_a4c
                n_cats = len(impact_cat.get("category_impacts", []))
                s4c.update(label=f"✅ Agent 4 Category — {n_cats} categorie(s) to update · ${cost_a4c:.4f}", state="complete")
            except Exception as e:
                s4c.update(label=f"❌ Agent 4 Category error: {e}", state="error")

    # ── Agent 5A — Legal Sheet ────────────────────────────────────────────────
    if wf["needs_watch"] and "impact_category" in results:
        with st.status("📋 Agent 5A — Legal Sheet Updater...", expanded=False) as s5a:
            try:
                cat_impacts = results["impact_category"].get("category_impacts", [])
                first_cat = cat_impacts[0].get("category", params["watch_cats"][0]) if cat_impacts else params["watch_cats"][0]
                result_5a, tu5a = analyze_legal_sheet(
                    anthropic_key=ANTHROPIC_KEY,
                    fiche_text="[No sheet uploaded — alert-based analysis only]",
                    alerts=alerts,
                    category=first_cat,
                    fiche_title=f"Auto — {first_cat}",
                    market="Europe",
                    profile="⚡ Veille rapide",
                )
                results["legal_sheet"] = result_5a
                st.session_state["5a_result"] = result_5a
                cost_a5a = tu5a.get("cost_usd", 0)
                total_cost += cost_a5a
                n_upd = result_5a.get("sections_to_update", 0)
                s5a.update(label=f"✅ Agent 5A — {n_upd} section(s) to update · ${cost_a5a:.4f}", state="complete")
            except Exception as e:
                s5a.update(label=f"❌ Agent 5A error: {e}", state="error")

    # ── Agent 2 + 3 — Profile & Classify ─────────────────────────────────────
    classified_products = []

    if wf["needs_product"]:
        codes = ([params["model_code"]] if params.get("product_mode") == "single"
                 else params.get("model_codes", []))

        for code in codes:
            with st.status(f"🔍 Agent 2 — Profiling {code}...", expanded=False) as s2:
                try:
                    profile = profile_product(
                        model_code=code,
                        domain=params.get("domain", "decathlon.fr"),
                        jina_key=JINA_KEY,
                        api_key=ANTHROPIC_KEY,
                        tavily_key=TAVILY_KEY,
                    )
                    tok2 = profile.get("_tokens", {})
                    cost_a2 = tok2.get("input", 0) * HAIKU_IN + tok2.get("output", 0) * HAIKU_OUT
                    total_cost += cost_a2
                    name = profile.get("name") or code
                    found = profile.get("found", False)
                    s2.update(label=f"{'✅' if found else '⚠️'} Agent 2 — {name} · ${cost_a2:.4f}", state="complete")

                    ci = profile_to_classifier_input(profile)
                    clf = classify_product(
                        api_key=ANTHROPIC_KEY,
                        model_code=ci["code"],
                        name=ci.get("name") or ci["code"],
                        product_type=ci.get("type", ""),
                        extra_info=(ci.get("description", "") + " " + ci.get("extra_info", "")).strip()[:500],
                    )
                    tok3 = clf.get("_tokens", {})
                    cost_a3 = tok3.get("input_tokens", 0) * HAIKU_IN + tok3.get("output_tokens", 0) * HAIKU_OUT
                    total_cost += cost_a3
                    cats = clf.get("assigned_categories", ["CAT3"])
                    classified_products.append({
                        "code": code,
                        "name": ci.get("name") or code,
                        "categories": cats,
                    })

                except Exception as e:
                    s2.update(label=f"❌ Error {code}: {e}", state="error")

        results["classified_products"] = classified_products

    # ── Agent 4 — Product Mode ────────────────────────────────────────────────
    if wf["needs_product_impact"] and classified_products:
        product_alerts = alerts if alerts else st.session_state.get("veille_results", [])
        if not product_alerts:
            st.warning("⚠️ No alerts for product impact analysis. Run a watch first or use session alerts.")
        else:
            with st.status("📊 Agent 4 — Product Impact...", expanded=False) as s4p:
                try:
                    impact_prod, tu4p = analyze_product_impact(
                        anthropic_key=ANTHROPIC_KEY,
                        alerts=product_alerts,
                        product_catalog=classified_products,
                    )
                    results["impact_product"] = impact_prod
                    st.session_state["impact_product_result"] = impact_prod
                    cost_a4p = tu4p.get("cost_usd", 0)
                    total_cost += cost_a4p
                    n_imp = len(impact_prod.get("impacted_products", []))
                    s4p.update(label=f"✅ Agent 4 Product — {n_imp} impacted product(s) · ${cost_a4p:.4f}", state="complete")
                except Exception as e:
                    s4p.update(label=f"❌ Agent 4 Product error: {e}", state="error")

            # ── Agent 5B — Risk Map ───────────────────────────────────────────
            if "impact_product" in results:
                with st.status("🗺️ Agent 5B — Risk Mapper...", expanded=False) as s5b:
                    try:
                        approved_5a = []
                        if "legal_sheet" in results:
                            approved_5a = [s for s in results["legal_sheet"].get("sections", [])
                                           if s.get("status") in ["MISSING", "ENRICH", "OBSOLETE"]]
                        result_5b, tu5b = generate_risk_mapping(
                            anthropic_key=ANTHROPIC_KEY,
                            impact_product_result=results["impact_product"],
                            agent5a_approved=approved_5a or None,
                        )
                        results["risk_map"] = result_5b
                        st.session_state["5b_result"] = result_5b
                        cost_a5b = tu5b.get("cost_usd", 0)
                        total_cost += cost_a5b
                        high = result_5b.get("executive_summary", {}).get("total_high", 0)
                        s5b.update(label=f"✅ Agent 5B — {high} HIGH risk(s) · ${cost_a5b:.4f}", state="complete")
                    except Exception as e:
                        s5b.update(label=f"❌ Agent 5B error: {e}", state="error")

    # ── Summary ───────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("✅ Workflow complete")
    st.metric("Total cost", f"${total_cost:.4f}")
    st.success("All agents completed. Results are available in each dedicated page.")

    nav_cols = st.columns(4)
    if "watch_entries" in results:
        nav_cols[0].page_link("pages/1_Watch.py", label="📡 Watch", icon="📡")
    if "impact_product" in results or "impact_category" in results:
        nav_cols[1].page_link("pages/2_Impact.py", label="📊 Impact", icon="📊")
    if "legal_sheet" in results:
        nav_cols[2].page_link("pages/3_Legal_Sheet.py", label="📋 Legal Sheet", icon="📋")
    if "risk_map" in results:
        nav_cols[3].page_link("pages/4_Risk_Map.py", label="🗺️ Risk Map", icon="🗺️")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
sess = st.session_state["session_tokens"]
tot_cost = sess["cost_usd"]
cost_str = "N/A" if tot_cost == 0 else f"${tot_cost:.4f}"
st.caption(f"📊 Session tokens — Input: {sess['input']:,} · Output: {sess['output']:,} · Estimated cost: {cost_str}")
