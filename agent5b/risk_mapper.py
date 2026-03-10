"""
Agent 5B — Risk Mapper
Génère un risk mapping produit à partir des résultats Agent 4 (Mode Produit)
et compare l'état de conformité avant/après les mises à jour Agent 5A.
"""

import json
import re
import urllib.request
from datetime import datetime

SONNET_INPUT_COST  = 3.00
SONNET_OUTPUT_COST = 15.00

SYSTEM_5B = """You are Agent 5B — Risk Mapper for Decathlon Electronics.

Your mission: generate a regulatory risk mapping for each impacted product,
based on regulatory alerts (Agent 4 output) and approved legal sheet updates (Agent 5A output).

You must produce THREE levels of analysis:
1. EXECUTIVE — global risk level per product, suitable for management
2. PRODUCT — corrective actions with priority and suggested owner, for product managers  
3. REGULATORY — per-regulation view showing which products are affected and their compliance status

BEFORE/AFTER COMPARISON:
- BEFORE = current state based on Agent 4 analysis (alerts × product catalog)
- AFTER = simulated state assuming Agent 5A approved updates are implemented
- Clearly flag this as a simulation — actual compliance depends on real implementation

RISK LEVELS:
- HIGH: Active regulation, product likely non-compliant, immediate action required
- MEDIUM: Upcoming requirement (6-18 months) or partial compliance gap
- LOW: Monitoring required, no immediate action

OUTPUT — respond ONLY with valid JSON, no markdown:
{
  "analysis_date": "YYYY-MM-DD",
  "products_analyzed": 0,
  "alerts_used": 0,
  "executive_summary": {
    "total_high": 0,
    "total_medium": 0,
    "total_low": 0,
    "key_message": "One sentence for management"
  },
  "products": [
    {
      "product_code": "...",
      "product_name": "...",
      "categories": ["CAT3", "CAT9"],
      "risk_before": "HIGH|MEDIUM|LOW",
      "risk_after": "HIGH|MEDIUM|LOW",
      "risk_delta": "IMPROVED|UNCHANGED|WORSENED",
      "non_conformities": [
        {
          "regulation": "Directive or standard name",
          "status_before": "NON_COMPLIANT|PARTIAL|UNKNOWN",
          "status_after": "COMPLIANT|PARTIAL|NON_COMPLIANT",
          "resolved_by": "Section updated in Agent 5A (or null)"
        }
      ],
      "corrective_actions": [
        {
          "action": "Specific action to take",
          "priority": "HIGH|MEDIUM|LOW",
          "deadline": "ASAP|6 months|12 months|Monitoring",
          "owner": "Legal manager|Product manager|Supplier|Lab"
        }
      ],
      "executive_note": "One sentence summary for this product"
    }
  ],
  "regulatory_view": [
    {
      "regulation": "...",
      "urgency": "HIGH|MEDIUM|LOW",
      "products_affected": ["product_code1", "product_code2"],
      "compliance_rate_before": "X/Y products compliant",
      "compliance_rate_after": "X/Y products compliant"
    }
  ]
}
"""


def _parse_json(raw: str) -> dict:
    """Parse JSON robuste — cherche premier { dernier }."""
    if not raw:
        raise ValueError("Réponse vide")
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON invalide : {e}. Début : {raw[:150]}")
    raise ValueError(f"Aucun JSON trouvé. Début : {raw[:150]}")


def generate_risk_mapping(
    anthropic_key: str,
    impact_product_result: dict,
    agent5a_approved: list = None,
    category: str = "",
) -> tuple:
    """
    Génère le risk mapping produit avec comparaison avant/après 5A.

    Args:
        impact_product_result : sortie Agent 4 Mode Produit
        agent5a_approved      : sections approuvées par Agent 5A (peut être None)
        category              : catégorie principale analysée

    Returns:
        (result_dict, token_usage)
    """
    # Résumer les updates 5A pour le prompt
    updates_5a_summary = []
    if agent5a_approved:
        for upd in agent5a_approved:
            updates_5a_summary.append({
                "section": upd.get("section_label", ""),
                "action": upd.get("action", ""),
                "update_reason": upd.get("update_reason", ""),
                "priority": upd.get("priority", ""),
            })

    user_message = (
        f"Generate a risk mapping for the following products based on regulatory alerts.\n\n"
        f"AGENT 4 RESULTS (product impact analysis):\n"
        f"{json.dumps(impact_product_result, indent=2, ensure_ascii=False)[:4000]}\n\n"
        f"AGENT 5A APPROVED UPDATES ({len(updates_5a_summary)} sections updated):\n"
        f"{json.dumps(updates_5a_summary, indent=2, ensure_ascii=False)}\n\n"
        f"Today: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"Instructions:\n"
        f"- Analyze each product individually\n"
        f"- For BEFORE state: use Agent 4 alerts as-is\n"
        f"- For AFTER state: simulate impact of Agent 5A approved updates\n"
        f"- If no Agent 5A updates provided, BEFORE = AFTER\n"
        f"- Keep corrective actions concrete and actionable\n"
        f"- Flag the AFTER state clearly as a simulation\n"
        f"- Return valid JSON only, no markdown"
    )

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 6000,
        "system": SYSTEM_5B,
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
    cost = (inp * SONNET_INPUT_COST + out * SONNET_OUTPUT_COST) / 1_000_000
    token_usage = {"input_tokens": inp, "output_tokens": out, "cost_usd": round(cost, 5)}

    raw = data["content"][0]["text"].strip()
    return _parse_json(raw), token_usage
