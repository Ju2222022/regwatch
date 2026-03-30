"""
Agent 5A — Legal Sheet Updater
Analyse une fiche légale existante section par section,
croise avec les alertes réglementaires Agent 1/4,
propose des mises à jour avec workflow approbation/édition/rejet.
"""

import json
import re
import urllib.request
from datetime import datetime

HAIKU_INPUT_COST  = 0.80
HAIKU_OUTPUT_COST = 4.00

# ── Structure officielle des fiches "My Conformity Box" ──────────────────────

# ── Catalogue complet des sections ───────────────────────────────────────────
# Chaque section a un niveau de pertinence :
#   "high"   : change souvent, fort enjeu réglementaire → à analyser par défaut
#   "medium" : change parfois, pertinent selon contexte
#   "low"    : stable ou procédural, rarement modifié

ALL_SECTIONS = [
    {"id": "definition_category",     "label": "Product's definition — Category",              "relevance": "high"},
    {"id": "definition_definition",   "label": "Product's definition — Definition",            "relevance": "medium"},
    {"id": "labelling_product",       "label": "Labelling — Mandatory on product",             "relevance": "high"},
    {"id": "labelling_packaging",     "label": "Labelling — Mandatory on packaging",           "relevance": "high"},
    {"id": "labelling_manual",        "label": "Labelling — Mandatory on instructions manual", "relevance": "high"},
    {"id": "labelling_warnings_gen",  "label": "Labelling — Warnings (general)",               "relevance": "medium"},
    {"id": "labelling_warnings_spec", "label": "Labelling — Warnings (specific)",              "relevance": "medium"},
    {"id": "env_recycling",           "label": "Environment — Recycling & Eco taxes",          "relevance": "high"},
    {"id": "env_labelling",           "label": "Environment — Environmental labelling",        "relevance": "high"},
    {"id": "tech_safety",             "label": "Technical — General safety requirements",      "relevance": "high"},
    {"id": "tech_standards",          "label": "Technical — Mandatory / voluntary standards",  "relevance": "high"},
    {"id": "tech_radiofrequency",     "label": "Technical — Radiofrequency",                   "relevance": "high"},
    {"id": "tech_chemicals",          "label": "Technical — Chemical substances",              "relevance": "high"},
    {"id": "tech_laboratory",         "label": "Technical — Laboratory",                       "relevance": "medium"},
    {"id": "commercial_internet",     "label": "Commercialization — Display on internet",      "relevance": "high"},
    {"id": "commercial_consumers",    "label": "Commercialization — Information to consumers", "relevance": "high"},
    {"id": "commercial_store",        "label": "Commercialization — Display in store",         "relevance": "medium"},
    {"id": "conformity_documents",    "label": "Conformity documents — Documents",             "relevance": "medium"},
    {"id": "tech_physical",           "label": "Technical — Physical & mechanical properties", "relevance": "low"},
    {"id": "tech_electrical",         "label": "Technical — Electrical aspects",               "relevance": "low"},
    {"id": "tech_noise",              "label": "Technical — Products making noise",            "relevance": "low"},
    {"id": "tech_packaging_req",      "label": "Technical — Packaging requirements",           "relevance": "low"},
    {"id": "cert_registrations",      "label": "Certifications / Registrations",               "relevance": "low"},
    {"id": "import_general",          "label": "Importation rules — General rules",            "relevance": "low"},
    {"id": "commercial_notification", "label": "Commercialization — Notification / Declaration","relevance": "low"},
    # Sections exclues par défaut (quasi-statiques pour l'électronique)
    # tech_inflammability, tech_hygiene, tech_radioactivity, labelling_sanctions,
    # tech_sanctions, conformity_format, import_documents, import_admin,
    # cert_laboratory, definition_comments, labelling_language, labelling_age
]

# ── Profils de sélection ──────────────────────────────────────────────────────
SECTION_PROFILES = {
    "⚡ Veille rapide": {
        "desc": "Sections à fort impact réglementaire uniquement (~8 sections, 1 appel)",
        "relevance": ["high"],
        "max_per_pass": 8,
    },
    "📋 Standard": {
        "desc": "Sections high + medium (~16 sections, 2 appels)",
        "relevance": ["high", "medium"],
        "max_per_pass": 8,
    },
    "🔍 Complet": {
        "desc": "Toutes les sections actives (~25 sections, 3 appels)",
        "relevance": ["high", "medium", "low"],
        "max_per_pass": 8,
    },
    "✏️ Personnalisé": {
        "desc": "Sélection manuelle des sections",
        "relevance": [],
        "max_per_pass": 8,
    },
}

def get_sections_for_profile(profile_name: str, custom_ids: list = None) -> list:
    """Retourne les sections à analyser selon le profil choisi."""
    profile = SECTION_PROFILES.get(profile_name, SECTION_PROFILES["📋 Standard"])
    if profile_name == "✏️ Personnalisé" and custom_ids:
        return [s for s in ALL_SECTIONS if s["id"] in custom_ids]
    relevance_filter = profile["relevance"]
    return [s for s in ALL_SECTIONS if s["relevance"] in relevance_filter]

def split_into_passes(sections: list, max_per_pass: int = 8) -> list:
    """Découpe une liste de sections en passes de taille max_per_pass."""
    return [sections[i:i+max_per_pass] for i in range(0, len(sections), max_per_pass)]

# Rétrocompat : FICHE_SECTIONS = toutes les sections high+medium
FICHE_SECTIONS = [s for s in ALL_SECTIONS if s["relevance"] in ["high", "medium"]]
FICHE_SECTIONS_A = FICHE_SECTIONS[:8]
FICHE_SECTIONS_B = FICHE_SECTIONS[8:]
SECTION_IDS = [s["id"] for s in ALL_SECTIONS]

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
  "market": "EU",
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



def _parse_json_response(raw: str, pass_label: str) -> dict:
    """Parse JSON depuis la réponse Claude.
    Stratégie : trouver le premier { et le dernier } dans la réponse,
    quelle que soit l'enveloppe markdown.
    """
    if not raw:
        raise ValueError(f"Reponse vide ({pass_label})")

    # Toujours chercher premier { et dernier } — fonctionne avec ou sans ```json
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start >= 0 and end > start:
        candidate = raw[start:end]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"JSON invalide ({pass_label}) : {e}. "
                f"Debut reponse : {raw[:120]}"
            )

    raise ValueError(f"Aucun JSON trouve ({pass_label}). Debut : {raw[:120]}")



def _call_analysis(
    anthropic_key: str,
    fiche_text_truncated: str,
    alerts: list,
    category: str,
    fiche_title: str,
    market: str,
    sections_pass: list,
    pass_label: str,
) -> tuple:
    """Un seul appel Claude pour un sous-ensemble de sections."""
    sections_ref = json.dumps(
        [{"id": s["id"], "label": s["label"]} for s in sections_pass],
        indent=2
    )
    # Résumer les alertes pour économiser des tokens
    alerts_short = json.dumps(
        [{"title": a.get("title", ""), "urgency": a.get("urgency", ""),
          "summary_fr": a.get("summary_fr", "")[:250],
          "categories_concerned": a.get("categories_concerned", [])}
         for a in alerts],
        indent=2, ensure_ascii=False
    )

    user_message = (
        f"Analyze this legal compliance sheet ({pass_label}) and propose updates.\n\n"
        f"LEGAL SHEET — {fiche_title or category} ({market})\n"
        f"{'='*60}\n"
        f"{fiche_text_truncated}\n"
        f"{'='*60}\n\n"
        f"APPLICABLE REGULATORY ALERTS ({len(alerts)}):\n"
        f"{alerts_short}\n\n"
        f"PRODUCT CATEGORY: {category} | MARKET: {market}\n"
        f"Today: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"SECTIONS TO ANALYZE IN THIS PASS:\n"
        f"{sections_ref}\n\n"
"IMPORTANT: Keep proposed_update text under 300 chars per section. Analyze ONLY the sections listed. Return valid JSON (no markdown):\n"
        "{\"sections\": ["
        "{\"section_id\":\"...\",\"section_label\":\"...\","
        "\"current_content_summary\":\"...\","
        "\"status\":\"OK|ENRICH|MISSING|OBSOLETE|NA_OK\","
        "\"alert_reference\":null,"
        "\"proposed_update\":null,"
        "\"update_reason\":\"...\","
        "\"priority\":\"HIGH|MEDIUM|LOW|NONE\"}"
        "]}"
    )

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 6000,
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

    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())

    usage = data.get("usage", {})
    inp  = usage.get("input_tokens", 0)
    out  = usage.get("output_tokens", 0)
    cost = (inp * HAIKU_INPUT_COST + out * HAIKU_OUTPUT_COST) / 1_000_000
    token_usage = {"input_tokens": inp, "output_tokens": out, "cost_usd": round(cost, 5)}

    raw = data["content"][0]["text"].strip()
    return _parse_json_response(raw, pass_label), token_usage


def analyze_legal_sheet(
    anthropic_key: str,
    fiche_text: str,
    alerts: list,
    category: str,
    fiche_title: str = "",
    market: str = "EU",
    profile: str = "📋 Standard",
    custom_section_ids: list = None,
) -> tuple:
    """Analyse une fiche légale selon le profil choisi (passes de 8 sections max)."""
    fiche_text_truncated = fiche_text[:6000] + (
        f"\n[... tronqué — {len(fiche_text)-6000} caractères ...]"
        if len(fiche_text) > 6000 else ""
    )

    sections_to_analyze = get_sections_for_profile(profile, custom_section_ids)
    passes = split_into_passes(sections_to_analyze, max_per_pass=8)

    total_tokens = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    all_sections = []

    for pass_idx, pass_sections in enumerate(passes):
        pass_label = f"Pass {pass_idx+1}/{len(passes)}"
        result_pass, tu = _call_analysis(
            anthropic_key, fiche_text_truncated, alerts,
            category, fiche_title, market,
            pass_sections, pass_label
        )
        all_sections.extend(result_pass.get("sections", []))
        total_tokens["input_tokens"]  += tu["input_tokens"]
        total_tokens["output_tokens"] += tu["output_tokens"]
        total_tokens["cost_usd"]      = round(total_tokens["cost_usd"] + tu["cost_usd"], 5)

    n_update = sum(1 for s in all_sections if s.get("status") in ["MISSING", "ENRICH", "OBSOLETE"])
    n_ok     = sum(1 for s in all_sections if s.get("status") in ["OK", "NA_OK"])

    return {
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "category": category,
        "market": market,
        "fiche_title": fiche_title,
        "profile": profile,
        "sections_analyzed": len(sections_to_analyze),
        "overall_status": (
            "MAJOR_UPDATE" if n_update >= 5 else
            "MINOR_UPDATE" if n_update >= 1 else
            "UP_TO_DATE"
        ),
        "sections": all_sections,
        "sections_ok": n_ok,
        "sections_to_update": n_update,
        "national_specificities_missing": [],
        "summary": (
            f"Profil {profile} · {len(sections_to_analyze)} sections analysées — "
            f"{n_update} à mettre à jour, {n_ok} à jour."
        ),
        "token_usage": total_tokens,
    }, total_tokens
