"""
Page 0 — Periodic Review
Affiche l'historique des revues périodiques et les dernières alertes.
"""

import json
import streamlit as st
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="Periodic Review — RegWatch", page_icon="📅", layout="wide")

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).parent.parent
REVIEW_HISTORY = ROOT / "data" / "review_history.json"
REVIEW_CONFIG  = ROOT / "data" / "review_config.json"

# ── Load data ─────────────────────────────────────────────────────────────────
def load_history() -> dict:
    if REVIEW_HISTORY.exists():
        with open(REVIEW_HISTORY) as f:
            return json.load(f)
    return {"reviews": []}

def load_config() -> dict:
    if REVIEW_CONFIG.exists():
        with open(REVIEW_CONFIG) as f:
            return json.load(f)
    return {}

# ── Urgency colors ────────────────────────────────────────────────────────────
URGENCY_COLORS = {"HIGH": "#d32f2f", "MEDIUM": "#f57c00", "LOW": "#388e3c"}

def urgency_badge(urgency: str) -> str:
    color = URGENCY_COLORS.get(urgency, "#666")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:0.78em;font-weight:700">{urgency}</span>'

# ── Page ──────────────────────────────────────────────────────────────────────
st.title("📅 Periodic Review")
st.caption("Automated regulatory watch — history and latest alerts")

history = load_history()
config  = load_config()
reviews = history.get("reviews", [])

# ── Config summary ────────────────────────────────────────────────────────────
with st.expander("⚙️ Current configuration", expanded=False):
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"**Categories:** {', '.join(config.get('active_categories', []))}")
    col2.markdown(f"**Markets:** {', '.join(config.get('markets', []))}")
    _freq_display = {
        "manual": "Manual only", "weekly": "Every week",
        "biweekly": "Twice a month", "monthly": "Once a month"
    }
    col3.markdown(f"**Frequency:** {_freq_display.get(config.get('frequency','manual'), config.get('frequency','manual').capitalize())}")
    recipients = config.get("email_recipients", [])
    if recipients:
        st.markdown(f"**Email recipients:** {', '.join(recipients)}")
    st.info("To modify the configuration, go to the **Configuration** page → Periodic Review tab.")

st.divider()

if not reviews:
    st.info("No reviews yet. Run the first review from **GitHub Actions → periodic_review → Run workflow**, or configure an automatic schedule.")
    st.stop()

# ── Latest review ─────────────────────────────────────────────────────────────
latest = reviews[-1]
st.subheader(f"🔔 Latest review — {latest['date']}")

total_new = latest.get("total_new", 0)
results   = latest.get("results", {})

# KPI row
cats_with_new = sum(1 for d in results.values() if d.get("new_count", 0) > 0)
high_count    = sum(
    1 for d in results.values()
    for e in d.get("new_entries", [])
    if e.get("urgency") == "HIGH"
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("New alerts", total_new)
k2.metric("Categories affected", cats_with_new)
k3.metric("HIGH urgency", high_count, delta=None)
k4.metric("Categories monitored", len(latest.get("categories", [])))

if total_new == 0:
    st.success("✅ No new regulatory alerts since last review.")
else:
    st.warning(f"⚠️ {total_new} new alert(s) identified — review below.")

# New entries by category
for cat, cat_data in results.items():
    new_entries = cat_data.get("new_entries", [])
    all_entries = cat_data.get("entries", [])
    if not new_entries:
        continue

    with st.expander(f"**{cat}** — {len(new_entries)} new / {len(all_entries)} total", expanded=True):
        for entry in new_entries:
            urgency = entry.get("urgency", "LOW")
            col_a, col_b = st.columns([5, 1])
            with col_a:
                url = entry.get("url", "")
                title = entry.get("title", "Untitled")
                if url:
                    st.markdown(f"**[{title}]({url})**")
                else:
                    st.markdown(f"**{title}**")
                st.caption(entry.get("summary", ""))
            with col_b:
                st.markdown(urgency_badge(urgency), unsafe_allow_html=True)
            st.divider()

st.divider()

# ── Review history ─────────────────────────────────────────────────────────────
st.subheader(f"📊 History ({len(reviews)} review(s))")

# Summary table
rows = []
for rev in reversed(reviews):
    rows.append({
        "Date":         rev.get("date", ""),
        "New alerts":   rev.get("total_new", 0),
        "Categories":   ", ".join(rev.get("categories", [])),
        "Markets":      ", ".join(rev.get("markets", [])),
    })

if rows:
    import pandas as pd
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Reviews are run via **GitHub Actions** · "
    "Results are automatically committed to `data/review_history.json` · "
    "[Open GitHub Actions](https://github.com/Ju2222022/regwatch/actions)"
)
