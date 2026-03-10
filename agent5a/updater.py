"""
Agent 5A — Legal Sheet Updater
Analyse une fiche légale existante section par section,
croise avec les alertes réglementaires Agent 1/4,
propose des mises à jour avec workflow approbation/édition/rejet.
"""

import json
import urllib.request
from datetime import datetime

HAIKU_INPUT_COST  = 0.80
HAIKU_OUTPUT_COST = 4.00

# ── Structure officielle des fiches "My Conformity Box" ──────────────────────

FICHE_SECTIONS = [
    {"id": "definition_category",       "label": "Product's definition — Category"},
    {"id": "definition_definition",     "label": "Product's definition — Definition"},
    {"id": "definition_comments",       "label": "Product's definition — Comments"},
    {"id": "labelling_language",        "label": "Labelling — Language"},
    {"id": "labelling_product",         "label": "Labelling — Mandatory on product"},
    {"id": "labelling_packaging",       "label": "Labelling — Mandatory on packaging"},
    {"id": "labelling_manual",          "label": "Labelling — Mandatory on instructions manual"},
    {"id": "labelling_warnings_gen",    "label": "Labelling — Warnings (general)"},
    {"id": "labelling_warnings_spec",   "label": "Labelling — Warnings (specific)"},
    {"id": "labelling_age",             "label": "Labelling — Target Age"},
    {"id": "labelling_sanctions",       "label": "Labelling — Sanctions / Fines"},
    {"id": "labelling_comments",        "label": "Labelling — Comments"},
    {"id": "env_recycling",             "label": "Environment — Recycling & Eco taxes"},
    {"id": "env_labelling",             "label": "Environment — Labelling"},
    {"id": "tech_safety",               "label": "Technical — General safety requirements"},
    {"id": "tech_standards",            "label": "Technical — Mandatory / voluntary standards"},
    {"id": "tech_physical",             "label": "Technical — Physical & mechanical properties"},
    {"id": "tech_electrical",           "label": "Technical — Electrical aspects"},
    {"id": "tech_inflammability",       "label": "Technical — Inflammability"},
    {"id": "tech_hygiene",              "label": "Technical — Hygiene"},
    {"id": "tech_radioactivity",        "label": "Technical — Radioactivity"},
    {"id": "tech_radiofrequency",       "label": "Technical — Radiofrequency"},
    {"id": "tech_noise",                "label": "Technical — Products making noise"},
    {"id": "tech_chemicals",            "label": "Technical — Chemical substances"},
    {"id": "tech_packaging_req",        "label": "Technical — Packaging requirements"},
    {"id": "tech_laboratory",           "label": "Technical — Laboratory"},
    {"id": "tech_sanctions",            "label": "Technical — Sanctions / Fines"},
    {"id": "tech_comments",             "label": "Technical — Comments"},
    {"id": "cert_registrations",        "label": "Certifications / Registrations"},
    {"id": "cert_laboratory",           "label": "Certifications — Laboratory"},
    {"id": "cert_comments",             "label": "Certifications — Comments"},
    {"id": "conformity_documents",      "label": "Conformity documents — Documents"},
    {"id": "conformity_format",         "label": "Conformity documents — Format"},
    {"id": "conformity_comments",       "label": "Conformity documents — Comments"},
    {"id": "import_general",            "label": "Importation rules — General rules"},
    {"id": "import_documents",          "label": "Importation rules — Documents"},
    {"id": "import_admin",              "label": "Importation rules — Administration"},
    {"id": "import_comments",           "label": "Importation rules — Comments"},
    {"id": "commercial_notification",   "label": "Commercialization — Notification / Declaration"},
    {"id": "commercial_store",          "label": "Commercialization — Display in store"},
    {"id": "commercial_internet",       "label": "Commercialization — Display on internet"},
    {"id": "commercial_consumers",      "label": "Commercialization — Information to consumers"},
    {"id": "commercial_comments",       "label": "Commercialization — Comments"},
]

SECTION_IDS = [s["id"] for s in FICHE_SECTIONS]

# ── Statuts possibles ─────────────────────────────────────────────────────────

STATUS_LABELS = {
    "OK":       ("✅", "Couverte et à jour"),
    "ENRICH":   ("⚠️", "À enrichir — contenu incomplet ou générique"),
    "OBSOLETE": ("🔴", "Obsolète — réglementation remplacée ou modifiée"),
    "MISSING":  ("➕", "Contenu manquant — nouvelle exigence ou spécificité nationale"),
    "NA_OK":    ("🔵", "NA justifié — cette section ne s'applique pas"),
}

# ── Prompt système ────────────────────────────────────────────────────────────

SYSTEM_5A = """You are Agent 5A — Legal Sheet Updater for Decathlon Electronics.

Your mission: analyze an existing legal compliance sheet ("My Conformity Box") section by section,
cross-reference it with recent regulatory alerts, and propose precise updates.

CONTEXT:
- These sheets cover the European Economic Area (all EU Member States)
- National specificities (France AGEC, Spain recycling decree, etc.) are included IN the same sheet
- A national mention is only needed if: (1) a Member State has an additional requirement not covered
  by the EU directive, OR (2) a national transposition creates a specific obligation
- Do NOT duplicate content already covered by EU directives
- The sheets are currently low quality — many sections are empty, generic, or "NA" without justification

YOUR ANALYSIS RULES:
- Be specific: quote regulation numbers, article numbers, deadlines
- If a section says "NA" but alerts suggest it should have content → flag as MISSING
- If content is outdated (old directive replaced) → flag as OBSOLETE  
- If content is generic boilerplate → flag as ENRICH
- If content correctly covers the regulatory requirement → flag as OK
- If "NA" is genuinely correct for this product category → flag as NA_OK
- Prioritize HIGH urgency alerts in your analysis

OUTPUT — respond ONLY with valid JSON, no markdown:
{
  "analysis_date": "YYYY-MM-DD",
  "category": "CAT9",
  "market": "Europe",
  "fiche_title": "...",
  "overall_status": "MAJOR_UPDATE|MINOR_UPDATE|UP_TO_DATE",
  "sections": [
    {
      "section_id": "tech_radiofrequency",
      "section_label": "Technical — Radiofrequency",
      "current_content_summary": "Brief description of what's currently in the section (or 'Empty/NA')",
      "status": "MISSING|ENRICH|OBSOLETE|OK|NA_OK",
      "alert_reference": "Title of the alert that triggered this flag (or null)",
      "proposed_update": "Complete text to insert or replace in this section. Write in English, professional regulatory tone. Be precise and actionable. Null if status is OK or NA_OK.",
      "update_reason": "Why this update is needed — cite specific regulation/article",
      "priority": "HIGH|MEDIUM|LOW|NONE"
    }
  ],
  "national_specificities_missing": [
    {
      "country": "France",
      "section_id": "commercial_internet",
      "missing_content": "AGEC Article 13 — digital environmental information obligation"
    }
  ],
  "summary": "Executive summary of the analysis",
  "sections_ok": 0,
  "sections_to_update": 0
}
"""


def analyze_legal_sheet(
    anthropic_key: str,
    fiche_text: str,
    alerts: list,
    category: str,
    fiche_title: str = "",
    market: str = "Europe",
) -> tuple:
    """
    Analyse une fiche légale et propose des mises à jour.

    Args:
        fiche_text  : contenu extrait du PDF de la fiche
        alerts      : alertes Agent 1 applicables (filtrées par catégorie)
        category    : ex "CAT9"
        fiche_title : titre de la fiche
        market      : "Europe" ou pays spécifique

    Returns:
        (result_dict, token_usage)
    """
    sections_ref = json.dumps(
        [{"id": s["id"], "label": s["label"]} for s in FICHE_SECTIONS],
        indent=2
    )

    user_message = f"""Analyze this legal compliance sheet and propose updates based on recent regulatory alerts.

LEGAL SHEET — {fiche_title or category} ({market})
{'='*60}
{fiche_text}
{'='*60}

APPLICABLE REGULATORY ALERTS ({len(alerts)} alerts):
{json.dumps(alerts, indent=2, ensure_ascii=False)}

PRODUCT CATEGORY: {category}
MARKET: {market}

SECTION STRUCTURE TO ANALYZE:
{sections_ref}

Today's date: {datetime.now().strftime('%Y-%m-%d')}

Instructions:
- Analyze EVERY section listed above
- For sections not visible in the fiche text, consider them as empty/NA
- Focus especially on sections that are empty or contain only "NA"
- Cross-reference with the regulatory alerts provided
- Propose concrete, actionable update text for each section that needs updating
- Maintain professional regulatory language consistent with the existing sheet style

Return complete JSON analysis."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 4096,
        "system": SYSTEM_5A,
        "messages": [{"role": "user", "content": user_message}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    usage = data.get("usage", {})
    input_tokens  = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost_usd = (input_tokens * HAIKU_INPUT_COST + output_tokens * HAIKU_OUTPUT_COST) / 1_000_000
    token_usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 5)
    }

    raw = data["content"][0]["text"].strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part), token_usage
            except json.JSONDecodeError:
                continue
    return json.loads(raw), token_usage


def extract_pdf_text_jina(pdf_url: str) -> str:
    """Extrait le texte d'un PDF via Jina.ai reader."""
    jina_url = f"https://r.jina.ai/{pdf_url}"
    req = urllib.request.Request(jina_url, headers={"User-Agent": "RegWatch/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")[:15000]
