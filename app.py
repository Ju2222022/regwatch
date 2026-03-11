import streamlit as st

st.set_page_config(
    page_title="RegWatch — Decathlon",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 RegWatch — Regulatory Intelligence Platform")
st.caption("Decathlon Electronics · AI-powered regulatory watch & compliance")

st.info("👈 Use the left menu to navigate between modules.")

# ── Architecture diagram ───────────────────────────────────────────────────────
st.markdown("### Architecture")

DIAGRAM = """
<style>
  .rw-wrap {
    font-family: 'Segoe UI', sans-serif;
    background: #f8f9ff;
    border-radius: 12px;
    padding: 28px 24px 20px 24px;
    display: flex;
    gap: 32px;
    align-items: flex-start;
  }

  /* ── Left: flow diagram ── */
  .rw-flow { flex: 0 0 420px; }

  /* Data sources banner */
  .rw-sources {
    background: #dde3f7;
    border-radius: 10px;
    padding: 14px 16px 10px 16px;
    margin-bottom: 0;
    display: flex;
    gap: 12px;
    align-items: stretch;
  }
  .rw-src-pill {
    background: #1a3a8f;
    color: #fff;
    border-radius: 20px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 600;
    text-align: center;
    flex: 1;
    line-height: 1.4;
  }
  .rw-src-label {
    color: #6b7bb8;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: .04em;
    align-self: center;
    flex: 0 0 90px;
    text-align: right;
  }

  /* Connector lines */
  .rw-connectors {
    display: flex;
    justify-content: space-around;
    padding: 0 80px;
    height: 28px;
    position: relative;
  }
  .rw-connectors::before {
    content: '';
    position: absolute;
    left: 50%; top: 0;
    width: 1px; height: 100%;
    background: #9aa8d4;
  }
  .rw-conn-line {
    width: 1px;
    background: #9aa8d4;
    height: 100%;
  }

  /* Agent nodes */
  .rw-row {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin: 4px 0;
  }
  .rw-agent {
    background: #2554d4;
    color: #fff;
    border-radius: 24px;
    padding: 10px 20px;
    font-size: 12px;
    font-weight: 700;
    text-align: center;
    min-width: 130px;
    line-height: 1.4;
  }
  .rw-agent span { font-weight: 400; opacity: .85; font-size: 11px; display: block; }
  .rw-agent.light { background: #7b9ef0; }

  /* Vertical connectors between rows */
  .rw-vline {
    display: flex;
    justify-content: center;
    height: 22px;
  }
  .rw-vline::after {
    content: '';
    width: 1px;
    height: 100%;
    background: #9aa8d4;
    display: block;
  }

  /* Fork line for 5A/5B */
  .rw-fork {
    display: flex;
    justify-content: center;
    height: 22px;
    position: relative;
    width: 280px;
    margin: 0 auto;
  }
  .rw-fork::before {
    content: '';
    position: absolute;
    left: 25%; right: 25%;
    top: 100%;
    height: 1px;
    background: #9aa8d4;
  }
  .rw-fork::after {
    content: '';
    position: absolute;
    left: 50%; top: 0;
    width: 1px; height: 100%;
    background: #9aa8d4;
  }
  .rw-fork-legs {
    display: flex;
    justify-content: center;
    width: 280px;
    margin: 0 auto;
    position: relative;
    height: 22px;
  }
  .rw-fork-legs::before {
    content: '';
    position: absolute;
    left: 25%; top: 0;
    width: 1px; height: 100%;
    background: #9aa8d4;
  }
  .rw-fork-legs::after {
    content: '';
    position: absolute;
    right: 25%; top: 0;
    width: 1px; height: 100%;
    background: #9aa8d4;
  }
  .rw-dashed {
    border-top: 2px dashed #7b9ef0;
    width: 60px;
    align-self: center;
    margin: 0 4px;
  }
  .rw-5ab-row {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 0;
    width: 280px;
    margin: 0 auto;
  }

  /* ── Right: legend table ── */
  .rw-legend {
    flex: 1;
    border: 1.5px solid #c8d0ec;
    border-radius: 8px;
    overflow: hidden;
    font-size: 13px;
  }
  .rw-legend-row {
    display: flex;
    border-bottom: 1px solid #e0e5f5;
  }
  .rw-legend-row:last-child { border-bottom: none; }
  .rw-legend-agent {
    background: #f0f3fc;
    padding: 10px 14px;
    font-weight: 700;
    color: #1a3a8f;
    min-width: 72px;
    border-right: 1px solid #e0e5f5;
    display: flex;
    align-items: center;
  }
  .rw-legend-desc {
    padding: 10px 14px;
    color: #333;
    line-height: 1.5;
  }
</style>

<div class="rw-wrap">

  <!-- LEFT: flow -->
  <div class="rw-flow">

    <!-- Data sources -->
    <div class="rw-sources">
      <div class="rw-src-pill">Regulations / Countries<br>from database</div>
      <div class="rw-src-pill">Internal referentials<br>Legal &amp; sub-legal categories</div>
      <div class="rw-src-pill">Product specs<br>(decathlon.fr, PIM…)</div>
      <div class="rw-src-label">Data<br>sources</div>
    </div>

    <!-- Lines from sources down -->
    <div style="display:flex;justify-content:space-around;padding:0 60px;height:26px;">
      <div style="width:1px;background:#9aa8d4;height:100%;"></div>
      <div style="width:1px;background:#9aa8d4;height:100%;"></div>
      <div style="width:1px;background:#9aa8d4;height:100%;"></div>
    </div>

    <!-- Agent 1 + Agent 2/3 row -->
    <div class="rw-row">
      <div class="rw-agent">Agent 1<span>Regulatory Watcher</span></div>
      <div style="display:flex;flex-direction:column;gap:8px;">
        <div class="rw-agent">Agent 2<span>Product Profiler</span></div>
        <div class="rw-agent">Agent 3<span>Regulatory Classifier</span></div>
      </div>
    </div>

    <!-- Line down to Agent 4 -->
    <div class="rw-vline" style="margin-left:-60px;"></div>

    <!-- Agent 4 -->
    <div class="rw-row" style="margin-left:-60px;">
      <div class="rw-agent">Agent 4<span>Impact Analyzer</span></div>
    </div>

    <!-- Fork to 5A / 5B -->
    <div class="rw-fork" style="margin-left:-60px;"></div>
    <div class="rw-fork-legs" style="margin-left:-60px;"></div>

    <!-- 5A — dashed — 5B -->
    <div class="rw-5ab-row" style="margin-left:-60px;">
      <div class="rw-agent light" style="min-width:110px;">Agent 5A<span>Legal Files</span></div>
      <div class="rw-dashed"></div>
      <div class="rw-agent light" style="min-width:110px;">Agent 5B<span>Risk Mapping</span></div>
    </div>

  </div>

  <!-- RIGHT: legend -->
  <div class="rw-legend">
    <div class="rw-legend-row">
      <div class="rw-legend-agent">Agent 1</div>
      <div class="rw-legend-desc">Monitors official sources (Tavily + Jina.ai), multi-topic, auto pre-fill by category, persistent history</div>
    </div>
    <div class="rw-legend-row">
      <div class="rw-legend-agent">Agent 2</div>
      <div class="rw-legend-desc">Extracts product specs from the web by model code</div>
    </div>
    <div class="rw-legend-row">
      <div class="rw-legend-agent">Agent 3</div>
      <div class="rw-legend-desc">Classifies products against Decathlon's internal referentials (legal &amp; sub-legal categories)</div>
    </div>
    <div class="rw-legend-row">
      <div class="rw-legend-agent">Agent 4</div>
      <div class="rw-legend-desc">Crosses alerts × internal referentials or product catalog</div>
    </div>
    <div class="rw-legend-row">
      <div class="rw-legend-agent">Agent 5A</div>
      <div class="rw-legend-desc">Audits and proposes updates to "My Conformity Box" legal sheets by category</div>
    </div>
    <div class="rw-legend-row">
      <div class="rw-legend-agent">Agent 5B</div>
      <div class="rw-legend-desc">Generates product risk mapping with before/after comparison post Agent 5A updates</div>
    </div>
  </div>

</div>
"""

st.html(DIAGRAM)
