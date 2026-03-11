# RegWatch — Regulatory Intelligence Platform · Julien DLUBALA

AI-powered regulatory watch and compliance platform.
Deployed at [regwatch.streamlit.app](https://regwatch.streamlit.app)

---

## Agent Architecture

| Agent | Status | Role |
|---|---|---|
| Agent 1 — Regulatory Watch | ✅ Active | Monitors official sources (Tavily + Jina.ai), multi-topic, auto pre-fill by category, persistent history |
| Agent 2 — Product Profiler | ✅ Active | Extracts product specs from the web by model code |
| Agent 3 — Regulatory Classifier | ✅ Active | Classifies products against Decathlon's regulatory framework (CAT1-CAT9) |
| Agent 4 — Impact Analyzer | ✅ Active | Crosses alerts × product catalog (Product Mode → Agent 5B) or × categories (Category Mode → Agent 5A) |
| Agent 5A — Legal Sheet Updater | ✅ Active | Audits and proposes updates to "My Conformity Box" legal sheets by category |
| Agent 5B — Risk Mapper | ✅ Active | Generates product risk mapping with before/after comparison post Agent 5A updates |

---

## Tech Stack

| Component | Tool |
|---|---|
| Interface | Python + Streamlit (Streamlit Cloud) |
| AI Engine | Claude Haiku (Agents 1–4) · Claude Sonnet (Agents 5A, 5B) |
| Regulatory search | Tavily API |
| PDF / dynamic site reading | Jina.ai reader (r.jina.ai) · PyPDF2 |
| Version control | GitHub (Ju2222022/regwatch) |

---

## Project Structure

```
regwatch/
├── app.py                          ← Home page
├── agent1/
│   └── watcher.py                  ← Regulatory watch — Tavily + Jina.ai, token counter
├── agent2/
│   └── profiler.py                 ← Product profiler by model code
├── agent3/
│   └── classifier.py               ← Regulatory classifier CAT1-CAT9
├── agent4/
│   └── impact.py                   ← Impact Analyzer — Product Mode + Category Mode (batch processing)
├── agent5a/
│   └── updater.py                  ← Legal Sheet Updater — analysis + validation workflow
├── agent5b/
│   └── risk_mapper.py              ← Risk Mapper — 3-level analysis, before/after comparison
├── data/
│   ├── sources.json                ← Watch domains by market (configurable via UI)
│   └── watch_history.json          ← Watch history (PoC persistence)
├── pages/
│   ├── 1_Agent3_Classificateur.py  ← Regulatory Classifier UI
│   ├── 2_Concordance.py            ← AI vs manual classification concordance
│   ├── 3_Agent2_Profiler.py        ← Product Profiler UI
│   ├── 4_Agent1_Veille.py          ← Regulatory Watch UI
│   ├── 5_Configuration.py          ← Watch sources management by market
│   ├── 6_Agent4_Impact.py          ← Impact Analyzer UI
│   ├── 7_Agent5A_Fiche.py          ← Legal Sheet Updater UI
│   └── 8_Agent5B_RiskMap.py        ← Risk Mapper UI (3 tabs: Executive / Product / Regulatory)
└── .streamlit/
    └── config.toml                 ← Decathlon theme
```

---

## Required Streamlit Secrets

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
TAVILY_API_KEY    = "tvly-..."
```

---

## Decathlon Electronics Regulatory Framework (CAT1-CAT9)

| Code | Category | Logic |
|---|---|---|
| CAT1 | Batteries & accumulators | Only if the product IS a battery |
| CAT2 | Lamps & lighting | Primary function = lighting |
| CAT3 | Electronic equipment | Universal fallback — all electronic products |
| CAT4 | Chargers & rechargeable products | Includes USB-C, solar charger |
| CAT5 | Camera / ANT+ | ANT+ protocol explicitly confirmed |
| CAT6 | MP3 player | Primary audio function |
| CAT7 | GPS / Radio / Walkie-talkie / Rangefinder | Protocol confirmed |
| CAT8 | Phone / Wifi / GSM | Wifi or cellular confirmed |
| CAT9 | Bluetooth equipment | Bluetooth explicitly confirmed |

> **Fallback rule**: CAT3 is assigned to every electronic product. Sub-categories (CAT5–CAT9) are added only when the protocol is explicitly confirmed.

---

## Agent 1 — Regulatory Watch

1. User defines one or more **watch topics** (e.g. *EN 18031 cybersecurity radio equipment EU*)
2. **Tavily** searches official domains (EUR-Lex, Legifrance, CENELEC...)
3. **Jina.ai** enriches priority results (PDFs, dynamic EUR-Lex pages)
4. **Claude Haiku** extracts structured regulatory entries tagged CAT1-CAT9
5. Results are displayed by criticality or topic, exportable to CSV
6. History is persisted in `data/watch_history.json`

**Category pre-fill**: user selects active categories (e.g. CAT9), the agent automatically generates matching watch queries.

**Criticality:**
- 🔴 HIGH — regulation in force or deadline < 6 months
- 🟡 MEDIUM — deadline 6–18 months
- 🟢 LOW — consultation or deadline > 18 months

---

## Agent 2 — Product Profiler

Automatically extracts technical specifications from a product by its model code.

1. User enters a **model code** (e.g. *8941337 FIT100M*)
2. **Tavily** searches product sheets on the web (Decathlon site, retailers, technical databases)
3. **Claude Haiku** extracts and structures specs relevant to regulatory classification:
   - Product type and primary function
   - Communication protocols (Bluetooth, ANT+, GPS, WiFi...)
   - Integrated / rechargeable battery
   - Electrical characteristics
4. The product profile enriches Agent 3 classification and can be sent to Agent 4

> Without Agent 2, Agent 3 concordance is ~27% (name + type only). With Agent 2, it rises to ~70%+.

---

## Agent 3 — Regulatory Classifier

Classifies a product into the Decathlon Electronics framework (CAT1-CAT9) from its description or Agent 2 profile.

**Classification rules:**
- Every product receives **CAT3 by default** (universal fallback)
- Sub-categories are added only when the protocol is **explicitly confirmed**
- Multiple categories can apply simultaneously (e.g. CAT3 + CAT9 for a Bluetooth watch)

**Example:**
```
Product: GPS Bluetooth watch with heart rate sensor
→ CAT3 (electronic equipment)     ← always
→ CAT7 (GPS confirmed)             ← protocol detected
→ CAT9 (Bluetooth confirmed)       ← protocol detected
```

**Concordance page**: compares AI classification vs manual Decathlon classification on 11 PoC products. Validates model reliability before deployment.

---

## Agent 4 — Impact Analyzer

Crosses Agent 1 alerts with the product catalog or active categories.

**Product Mode** → identifies impacted catalog products → prepares risk mapping for Agent 5B.
Processes products in **batches of 4** to avoid token limits.

**Category Mode** → identifies impacted categories and change type (NEW / UPDATE / DEADLINE / WITHDRAWAL) → prepares legal sheet updates for Agent 5A.

**Session state flow:**
```
Agent 1 → session_state["veille_results"]
Agent 4 Product Mode  → session_state["impact_product_result"]  → Agent 5B
Agent 4 Category Mode → session_state["impact_category_result"] → Agent 5A
```

---

## Agent 5A — Legal Sheet Updater

Audits a "My Conformity Box" legal sheet (PDF upload) and proposes section-by-section updates, crossed with regulatory alerts.

### Analysis profiles

| Profile | Sections | API calls | Est. cost |
|---|---|---|---|
| ⚡ Quick watch | ~8 (high only) | 1 | ~$0.03 |
| 📋 Standard | ~16 (high + medium) | 2 | ~$0.05 |
| 🔍 Full | ~25 (all) | 3 | ~$0.08 |
| ✏️ Custom | user-selected | variable | variable |

### Validation workflow

```
AI analyses each section → status per section
        ↓
Status types:
  ✅ OK       — covered and up to date
  ⚠️ ENRICH  — incomplete or generic
  🔴 OBSOLETE — replaced regulation
  ➕ MISSING  — missing content
  🔵 NA_OK    — NA justified
        ↓
Regulatory manager:
  ✅ Approve  — accept AI text as-is
  ✏️ Edit     — modify text then validate
  ❌ Reject
        ↓
Export Markdown + JSON with traceability metadata
(section, final text, source alert, reason, priority, date)
```

### Europe specifics

Europe covers the entire EEA by default (EU directives). A national mention is added only if a Member State has an additional requirement not covered by the directive (e.g. French AGEC, Spanish recycling decree).

---

## Agent 5B — Risk Mapper

Generates a regulatory risk mapping per product from Agent 4 (Product Mode) results,
with a before/after compliance comparison against Agent 5A approved updates.

**Flow:**
```
Agent 4 Product Mode → session_state["impact_product_result"]
Agent 5A JSON export → imported optionally for before/after comparison
        ↓
Agent 5B — 3-level risk mapping
```

**3 reading levels (3 tabs):**
- 📊 **Executive View** — product × risk level table for management
- 📦 **Product View** — non-conformities + corrective actions with priority/deadline/owner, for product managers
- 📋 **Regulatory View** — by regulation, before/after compliance rate, for the regulatory affairs manager

**Before/after comparison:**
- BEFORE = current state from Agent 4 alert analysis
- AFTER = simulated state assuming Agent 5A approved updates are implemented
- Clearly flagged as simulation in the UI

**Export:** Full JSON + CSV summary (executive view)

---

## Configuration Page

Watch source management by market. Tab-based editing, import/export `sources.json`.

---

## PoC Results — Agent 3 (Phase 1)

- **11 products** tested against Decathlon Electronics framework
- **Concordance**: 3/11 (27%) with name + type only — 6/11 (55%) with enriched description
- **Zero total divergence** across all tests
- With Agent 2 (web specs): estimated concordance 70%+

---

## Roadmap

| Phase | Status | Content |
|---|---|---|
| Phase 1 | ✅ Complete | Agents 2 + 3 operational, concordance validated |
| Phase 2 | ✅ Complete | Agent 1 (watch) · Agent 4 (impact analyzer) · Configuration page |
| Phase 3 | ✅ Complete | Agent 5A (legal sheets) · Agent 5B (risk mapping) operational |
| Phase 4 | 🔜 Planned | Team presentation · Go/No-Go · Google Sheets persistence · Automated scheduling |

---

## PoC Notes

- **Persistence**: `watch_history.json` is local — reset on each GitHub redeploy. Google Sheets migration in Phase 4.
- **Estimated costs**: ~$0.001/classification · ~$0.006/watch session · ~$0.05/legal sheet analysis (Standard profile) · ~$0.03/risk mapping (3 products)
- **Scheduling**: manual watch in PoC · GitHub Actions automation in Phase 4
- **Sidebar**: internal Streamlit code display (known issue) — to be addressed in final design review (Phase 4)
- **Language**: interface fully in English for international use
