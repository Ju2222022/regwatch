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


def _call_risk_batch(
    anthropic_key: str,
    products_batch: list,
    alerts_summary: list,
    updates_5a_summary: list,
    batch_label: str,
) -> tuple:
    """Analyse un batch de produits pour le risk mapping."""
    products_json = json.dumps(products_batch, indent=2, ensure_ascii=False)
    alerts_json   = json.dumps(alerts_summary, indent=2, ensure_ascii=False)
    updates_json  = json.dumps(updates_5a_summary, indent=2, ensure_ascii=False)
    today = datetime.now().strftime("%Y-%m-%d")

    user_message = (
        f"Generate a risk mapping for this product batch ({batch_label}).\n\n"
        f"PRODUCTS TO ANALYZE ({len(products_batch)} products):\n{products_json}\n\n"
        f"REGULATORY ALERTS CONTEXT:\n{alerts_json}\n\n"
        f"AGENT 5A APPROVED UPDATES ({len(updates_5a_summary)} sections):\n{updates_json}\n\n"
        f"Today: {today}\n"
        f"- Analyze each product individually\n"
        f"- BEFORE state: current compliance based on alerts\n"
        f"- AFTER state: simulate impact of Agent 5A updates (flag as simulation)\n"
        f"- If no 5A updates, BEFORE = AFTER\n"
        f"- Keep descriptions concise (max 100 chars each)\n"
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
    return _parse_json(data["content"][0]["text"].strip()),            {"input_tokens": inp, "output_tokens": out, "cost_usd": round(cost, 5)}


def generate_risk_mapping(
    anthropic_key: str,
    impact_product_result: dict,
    agent5a_approved: list = None,
    category: str = "",
    batch_size: int = 4,
) -> tuple:
    """
    Generates product risk mapping with before/after 5A comparison.
    Processes products in batches to avoid token limits.

    Args:
        impact_product_result : Agent 4 Product Mode output
        agent5a_approved      : Agent 5A approved sections (optional)
        batch_size            : products per API call (default 4)

    Returns:
        (result_dict, token_usage)
    """
    impacted     = impact_product_result.get("impacted_products", [])
    non_impacted = impact_product_result.get("non_impacted_products", [])

    # Résumer les alertes depuis les produits impactés
    alerts_summary = []
    seen = set()
    for p in impacted:
        for alert in p.get("applicable_alerts", p.get("alerts", [])):
            title = alert.get("alert_title", alert.get("title", ""))
            if title and title not in seen:
                seen.add(title)
                alerts_summary.append({
                    "title": title,
                    "urgency": alert.get("alert_urgency", alert.get("urgency", "")),
                    "change_type": alert.get("change_type", ""),
                })

    # Résumer les updates 5A
    updates_5a_summary = []
    if agent5a_approved:
        for upd in agent5a_approved:
            updates_5a_summary.append({
                "section": upd.get("section_label", ""),
                "action": upd.get("action", ""),
                "update_reason": upd.get("update_reason", ""),
                "priority": upd.get("priority", ""),
            })

    # Préparer produits allégés
    products_light = [
        {
            "code": p.get("code", p.get("product_code", "")),
            "name": p.get("name", p.get("product_name", "")),
            "categories": p.get("categories", []),
            "risk_score": p.get("risk_score", p.get("overall_risk", "")),
            "alerts": [a.get("alert_title", a.get("title", ""))
                       for a in p.get("applicable_alerts", p.get("alerts", []))[:3]],
        }
        for p in impacted
    ]

    # Découper en batches
    batches = [products_light[i:i+batch_size]
               for i in range(0, len(products_light), batch_size)]

    all_products_result = []
    all_reg_view        = []
    total_tokens        = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    exec_summary        = {"total_high": 0, "total_medium": 0, "total_low": 0, "key_message": ""}

    for idx, batch in enumerate(batches):
        batch_label = f"batch {idx+1}/{len(batches)}"
        result_batch, tu = _call_risk_batch(
            anthropic_key, batch, alerts_summary, updates_5a_summary, batch_label
        )
        all_products_result += result_batch.get("products", [])
        all_reg_view        += result_batch.get("regulatory_view", [])
        bs = result_batch.get("executive_summary", {})
        exec_summary["total_high"]   += bs.get("total_high", 0)
        exec_summary["total_medium"] += bs.get("total_medium", 0)
        exec_summary["total_low"]    += bs.get("total_low", 0)
        if not exec_summary["key_message"] and bs.get("key_message"):
            exec_summary["key_message"] = bs["key_message"]
        total_tokens["input_tokens"]  += tu["input_tokens"]
        total_tokens["output_tokens"] += tu["output_tokens"]
        total_tokens["cost_usd"]       = round(total_tokens["cost_usd"] + tu["cost_usd"], 5)

    return {
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "products_analyzed": len(all_products_result),
        "alerts_used": len(alerts_summary),
        "executive_summary": exec_summary,
        "products": all_products_result,
        "regulatory_view": all_reg_view,
        "token_usage": total_tokens,
    }, total_tokens
