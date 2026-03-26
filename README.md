# RegWatch — Regulatory Intelligence Platform · Julien Dlubala

AI-powered regulatory watch and compliance platform for Decathlon Electronics.
Deployed at [regwatch.streamlit.app](https://regwatch.streamlit.app)

---

## Agent Architecture

| Agent | Page | Role |
|---|---|---|
| Agent 1 — Regulatory Watcher | Watch | Monitors official sources (Tavily), multi-topic, auto pre-fill by category, persistent history |
| Agent 2 — Product Profiler | Profiler | Extracts product specs from the web by model code |
| Agent 3 — Regulatory Classifier | Classifier | Classifies products against Decathlon's regulatory framework (CAT1-CAT9) |
| Agent 4 — Impact Analyzer | Impact | Crosses alerts × product catalog (Product Mode) or × categories (Category Mode) |
| Agent 5A — Legal Sheet Updater | Legal Sheet | Audits and proposes updates to legal sheets by category |
| Agent 5B — Risk Mapper | Risk Map | Generates product risk mapping with before/after comparison |

---

## Tech Stack

| Component | Tool |
|---|---|
| Interface | Python + Streamlit (Streamlit Cloud) |
| AI Engine | Claude Haiku (Agents 1–3) · Claude Sonnet (Agents 4, 5A, 5B) |
| Regulatory search | Tavily API |
| Email notifications | Resend API |
| Automated scheduling | GitHub Actions |
| Version control | GitHub (Ju2222022/regwatch) |

---

## Project Structure

```
regwatch/
├── app.py                          ← Home page + architecture diagram
├── agent1/
│   └── watcher.py                  ← Regulatory watch — Tavily, multilingual, token counter
├── agent2/
│   └── profiler.py                 ← Product profiler by model code
├── agent3/
│   └── classifier.py               ← Regulatory classifier CAT1-CAT9
├── agent4/
│   └── impact.py                   ← Impact Analyzer — Product Mode + Category Mode
├── agent5a/
│   └── updater.py                  ← Legal Sheet Updater — analysis + validation workflow
├── agent5b/
│   └── risk_mapper.py              ← Risk Mapper — 3-level analysis, before/after comparison
├── data/
│   ├── legal_categories.json       ← Single source of truth — CAT1-CAT9 definitions
│   ├── sources.json                ← Watch domains by market (configurable via UI)
│   ├── watch_history.json          ← Watch session history
│   ├── review_history.json         ← Periodic review history
│   └── review_config.json          ← Periodic review configuration
├── scripts/
│   └── periodic_review.py          ← Automated review script (GitHub Actions)
├── pages/
│   ├── 0_Review.py                 ← Periodic Review history page
│   ├── 1_Watch.py                  ← Regulatory Watch UI
│   ├── 2_Impact.py                 ← Impact Analyzer UI
│   ├── 3_Legal Sheet.py            ← Legal Sheet Updater UI
│   ├── 4_Risk Map.py               ← Risk Mapper UI
│   ├── 5_Profiler.py               ← Product Profiler UI
│   ├── 6_Classifier.py             ← Regulatory Classifier UI
│   ├── 7_Concordance.py            ← AI vs manual classification concordance
│   └── 8_Configuration.py          ← Watch sources + Legal referential + Periodic review config
└── .github/
    └── workflows/
        └── periodic_review.yml     ← GitHub Actions workflow (manual + scheduled)
```

---

## Required Secrets

### Streamlit Cloud (Settings → Secrets)

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
TAVILY_API_KEY    = "tvly-..."
RESEND_API_KEY    = "re_..."
GH_TOKEN          = "ghp_..."
```

### GitHub Actions (Settings → Environments → regwatch)

```
ANTHROPIC_API_KEY
TAVILY_API_KEY
RESEND_API_KEY
REVIEW_EMAIL_TO     # comma-separated recipients
REVIEW_EMAIL_FROM   # verified sender (e.g. onboarding@resend.dev)
GH_TOKEN
```

---

## Decathlon Electronics Regulatory Framework (CAT1-CAT9)

| Code | Category | Logic |
|---|---|---|
| CAT1 | Batteries & accumulators | Only if the product IS a battery |
| CAT2 | Lamps & lighting | Primary function = lighting |
| CAT3 | Electronic equipment | Universal fallback — all electronic products |
| CAT4 | Chargers & rechargeable products | USB-C, solar charger |
| CAT5 | Camera / ANT+ | ANT+ protocol explicitly confirmed |
| CAT6 | MP3 player | Primary audio function |
| CAT7 | GPS / Radio / Walkie-talkie / Rangefinder | Protocol confirmed |
| CAT8 | Phone / Wifi / GSM | Wifi or cellular confirmed |
| CAT9 | Bluetooth equipment | Bluetooth explicitly confirmed |

> **Fallback rule**: CAT3 is assigned to every electronic product. Sub-categories (CAT5–CAT9) are added only when the protocol is explicitly confirmed.

---

## Periodic Review

Automated regulatory watch that runs on a schedule via GitHub Actions.

**Flow:**
1. GitHub Actions triggers the review (manually or on schedule)
2. Agent 1 runs on all configured categories
3. New alerts are identified by comparison with previous reviews
4. Results saved to `data/review_history.json` and committed to GitHub
5. Email report sent via Resend to configured recipients

**Configuration:** managed from the app → Configuration page → Periodic Review tab.

**Schedule options** (edit `.github/workflows/periodic_review.yml`):
- Weekly — every Monday at 7:00 UTC
- Twice a month — 1st and 15th at 7:00 UTC
- Monthly — 1st of month at 7:00 UTC

---

## Agent 1 — Regulatory Watch

1. User defines watch topics (e.g. *EN 18031 cybersecurity radio equipment EU*)
2. **Tavily** searches official domains (EUR-Lex, Legifrance, CENELEC...)
3. **Claude Haiku** extracts structured regulatory entries tagged CAT1-CAT9
4. Results displayed by criticality or topic, exportable to CSV
5. History persisted in `data/watch_history.json`

**Criticality:**
- 🔴 HIGH — regulation in force or deadline < 6 months
- 🟡 MEDIUM — deadline 6–18 months
- 🟢 LOW — consultation or deadline > 18 months

---

## Agent 2 — Product Profiler

Extracts technical specifications from a product by model code.

1. User enters a **model code** (e.g. *8735154*)
2. **Tavily** searches product pages on the web
3. **Claude Haiku** extracts specs relevant to regulatory classification:
   - Product type and primary function
   - Communication protocols (Bluetooth, ANT+, GPS, WiFi...)
   - Battery type, charging method
4. Profile feeds directly into Agent 3 classification

---

## Agent 3 — Regulatory Classifier

Classifies a product into the Decathlon Electronics framework (CAT1-CAT9).

**Classification rules:**
- Every product receives **CAT3 by default** (universal fallback)
- Sub-categories added only when protocol is **explicitly confirmed**
- Multiple categories can apply simultaneously

**Example:**
```
GPS Bluetooth watch (rechargeable)
→ CAT3 (electronic equipment)   ← always
→ CAT4 (rechargeable)            ← confirmed
→ CAT7 (GPS confirmed)           ← confirmed
→ CAT9 (Bluetooth confirmed)     ← confirmed
```

---

## Agent 4 — Impact Analyzer

Crosses Agent 1 alerts with the product catalog or active categories.

**Product Mode** → identifies impacted catalog products → feeds Agent 5B.
**Category Mode** → identifies impacted categories → feeds Agent 5A.

**Session state flow:**
```
Agent 1 → veille_results
Agent 4 Product Mode  → impact_product_result  → Agent 5B
Agent 4 Category Mode → impact_category_result → Agent 5A
```

---

## Agent 5A — Legal Sheet Updater

Audits a legal sheet (PDF) and proposes section-by-section updates.

| Profile | Sections | Est. cost |
|---|---|---|
| ⚡ Quick | ~8 (HIGH only) | ~$0.03 |
| 📋 Standard | ~16 (HIGH + MEDIUM) | ~$0.05 |
| 🔍 Full | ~25 (all) | ~$0.08 |

**Validation workflow:** AI proposes → manager approves / edits / rejects → export JSON + Markdown

---

## Agent 5B — Risk Mapper

Generates regulatory risk mapping per product with before/after comparison.

**3 reading levels:**
- 📊 **Executive View** — product × risk level for management
- 📦 **Product View** — non-conformities + corrective actions for product managers
- 📋 **Regulatory View** — by regulation, before/after compliance rate

---

## PoC Results

- **11 products** tested against Decathlon Electronics framework
- **Zero total divergence** across all tests
- Concordance: 55% (name + type) → 70%+ (with Agent 2 web specs)

---

## Roadmap

| Phase | Status | Content |
|---|---|---|
| Phase 1 | ✅ Complete | Agents 2 + 3 operational, concordance validated |
| Phase 2 | ✅ Complete | Agent 1 · Agent 4 · Configuration page |
| Phase 3 | ✅ Complete | Agent 5A · Agent 5B operational |
| Phase 4 | ✅ Complete | Periodic review · Email notifications · Full test plan validated |
| Phase 5 | 🔜 Planned | Team presentation · PIM integration · Multi-market deployment |

---

## Cost Estimates

| Operation | Estimated cost |
|---|---|
| Product classification (Agent 3) | ~$0.003 |
| Product profiling (Agent 2) | ~$0.002 |
| Watch session (Agent 1, 1 topic) | ~$0.004 |
| Legal sheet analysis — Standard (Agent 5A) | ~$0.05 |
| Risk mapping — 3 products (Agent 5B) | ~$0.03 |
| Periodic review — all 6 CAT | ~$0.05 |
