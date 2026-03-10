"""
Agent 4 — Impact Analyzer
Deux modes :
- Mode Produit  : croise alertes réglementaires × catalogue produits → score de risque
- Mode Catégorie: croise alertes réglementaires × définition CAT → delta fiches légales
"""

import json
import urllib.request
from datetime import datetime

# ── Référentiel catégories ────────────────────────────────────────────────────

CAT_DEFINITIONS = {
    "CAT1": {
        "label": "Batteries & accumulateurs",
        "scope": "Produits qui SONT une batterie ou un accumulateur (lithium, alcaline, NiMH...)",
        "key_regulations": ["Battery Regulation EU 2023/1542", "UN 38.3", "IEC 62133"],
        "keywords": ["battery", "accumulator", "lithium", "alkaline", "cell", "energy storage"]
    },
    "CAT2": {
        "label": "Lampes & éclairage",
        "scope": "Produits dont la fonction primaire est l'éclairage (lampes, torches, frontales...)",
        "key_regulations": ["ErP Directive 2009/125/EC", "Energy Labelling 2017/1369"],
        "keywords": ["lamp", "light", "torch", "headlamp", "LED", "lumen", "lighting"]
    },
    "CAT3": {
        "label": "Équipements électroniques (base)",
        "scope": "Tout produit électronique — catégorie parachute universelle",
        "key_regulations": ["RoHS 2011/65/EU", "WEEE 2012/19/EU", "CE Marking", "LVD 2014/35/EU", "EMC 2014/30/EU"],
        "keywords": ["electronic", "electrical", "RoHS", "WEEE", "CE", "EMC", "LVD", "hazardous substances"]
    },
    "CAT4": {
        "label": "Chargeurs & produits rechargeables",
        "scope": "Chargeurs, adaptateurs, produits avec batterie rechargeable intégrée",
        "key_regulations": ["Common Charger Directive 2022/2380", "Ecodesign 2019/1782", "IEC 62684"],
        "keywords": ["charger", "USB-C", "rechargeable", "power supply", "adapter", "charging"]
    },
    "CAT5": {
        "label": "Caméra / ANT+",
        "scope": "Produits utilisant le protocole ANT+ ou caméras sportives",
        "key_regulations": ["RED 2014/53/EU", "FCC Part 15"],
        "keywords": ["ANT+", "camera", "video", "action cam", "wireless sensor", "2.4GHz"]
    },
    "CAT6": {
        "label": "Lecteur MP3 / Audio",
        "scope": "Appareils dont la fonction principale est la lecture audio",
        "key_regulations": ["Audio Equipment Directive", "RED 2014/53/EU"],
        "keywords": ["MP3", "audio", "music player", "headphones", "earphones"]
    },
    "CAT7": {
        "label": "GPS / Radio / Talkie / Télémètre",
        "scope": "Produits utilisant GPS, radio FM/AM, talkie-walkie, télémètre laser",
        "key_regulations": ["RED 2014/53/EU", "ITU Radio Regulations", "SAR limits"],
        "keywords": ["GPS", "GNSS", "radio", "walkie-talkie", "rangefinder", "laser", "frequency", "SAR"]
    },
    "CAT8": {
        "label": "Téléphone / Wifi / GSM",
        "scope": "Produits avec connectivité Wifi, GSM/4G/5G ou NFC",
        "key_regulations": ["RED 2014/53/EU", "EN 18031 cybersecurity", "GDPR"],
        "keywords": ["wifi", "GSM", "4G", "5G", "cellular", "NFC", "cybersecurity", "EN 18031"]
    },
    "CAT9": {
        "label": "Équipement Bluetooth",
        "scope": "Produits avec connectivité Bluetooth (BLE ou Classic)",
        "key_regulations": ["RED 2014/53/EU", "EN 18031 cybersecurity", "BLE spec"],
        "keywords": ["bluetooth", "BLE", "wireless", "connected", "pairing", "2.4GHz"]
    },
}

# Requêtes de veille générées dynamiquement depuis les définitions de catégories
# Chaque catégorie génère plusieurs requêtes couvrant son périmètre complet
CAT_WATCH_QUERIES = {
    "CAT1": [
        "lithium battery regulation EU safety accumulators 2024",
        "battery due diligence traceability regulation EU",
        "UN 38.3 IEC 62133 battery testing standard update",
    ],
    "CAT2": [
        "LED lighting lamp ecodesign energy labelling regulation EU",
        "torch headlamp photobiological safety standard update",
        "ErP ecodesign lighting directive update EU",
    ],
    "CAT3": [
        "RoHS hazardous substances electronics restriction update EU",
        "WEEE waste electrical equipment directive 2024",
        "EMC electromagnetic compatibility directive electronics EU",
        "LVD low voltage directive CE marking electronics update",
        "ecodesign electronics energy efficiency EU regulation",
    ],
    "CAT4": [
        "USB-C common charger ecodesign power supply regulation EU",
        "rechargeable battery charger efficiency directive update",
        "photovoltaic solar charger regulation EU standard",
    ],
    "CAT5": [
        "ANT+ radio equipment directive RED 2.4GHz regulation",
        "action camera video equipment radio frequency EU",
        "wireless sensor sport device RED directive update",
    ],
    "CAT6": [
        "audio equipment MP3 player regulation directive EU",
        "headphones earphones noise exposure standard EN 50332",
        "portable audio device regulation update EU",
    ],
    "CAT7": [
        "GPS GNSS radio frequency regulation SAR EU",
        "walkie talkie radio equipment directive RED update",
        "laser rangefinder telemeter regulation EU safety",
        "meteorological device radio frequency ITU regulation",
    ],
    "CAT8": [
        "wifi cybersecurity EN 18031 radio equipment connected devices",
        "GSM 4G 5G radio equipment directive RED update EU",
        "cybersecurity connected products regulation EU CRA",
        "NFC contactless device regulation EU standard",
    ],
    "CAT9": [
        "bluetooth BLE connected devices cybersecurity EN 18031",
        "bluetooth radio equipment directive RED 2.4GHz EU",
        "connected wearable device regulation cybersecurity EU",
    ],
}

HAIKU_INPUT_COST  = 0.80
HAIKU_OUTPUT_COST = 4.00

# ── Mode Produit ──────────────────────────────────────────────────────────────

SYSTEM_PRODUCT = """You are Agent 4 — Impact Analyzer (Product Mode) for Decathlon Electronics.

You receive:
1. A list of regulatory alerts (from Agent 1 watchlist)
2. A product catalog with their regulatory categories (CAT1-CAT9)

Your task: for each product, identify which regulatory alerts apply based on category overlap,
and compute an impact score.

OUTPUT — respond ONLY with valid JSON, no markdown:
{
  "analysis_date": "YYYY-MM-DD",
  "mode": "product",
  "impacted_products": [
    {
      "code": "product_code",
      "name": "product_name",
      "categories": ["CAT3", "CAT9"],
      "applicable_alerts": [
        {
          "alert_title": "...",
          "alert_urgency": "HIGH|MEDIUM|LOW",
          "reason": "why this alert applies to this product",
          "action": "specific action for this product"
        }
      ],
      "risk_score": "HIGH|MEDIUM|LOW",
      "risk_summary": "Brief summary of overall risk for this product"
    }
  ],
  "non_impacted_products": ["code1", "code2"],
  "summary": "Overall analysis summary",
  "token_usage": {}
}
"""

SYSTEM_CATEGORY = """You are Agent 4 — Impact Analyzer (Category Mode) for Decathlon Electronics.

You receive:
1. A list of regulatory alerts (from Agent 1 watchlist)
2. The current regulatory category definitions with their associated regulations

Your task: for each category, identify which alerts require updating the legal sheet,
and describe what needs to change.

OUTPUT — respond ONLY with valid JSON, no markdown:
{
  "analysis_date": "YYYY-MM-DD",
  "mode": "category",
  "category_impacts": [
    {
      "category": "CAT9",
      "label": "Équipement Bluetooth",
      "applicable_alerts": [
        {
          "alert_title": "...",
          "alert_urgency": "HIGH|MEDIUM|LOW",
          "change_type": "NEW_REGULATION|UPDATE|DEADLINE|WITHDRAWAL",
          "fiche_update_required": true,
          "update_description": "What needs to change in the legal sheet"
        }
      ],
      "update_priority": "HIGH|MEDIUM|LOW|NONE",
      "update_summary": "Summary of required legal sheet updates"
    }
  ],
  "categories_no_update": ["CAT2", "CAT6"],
  "summary": "Overall analysis summary",
  "total_updates_required": 0
}
"""


def _parse_json(raw: str) -> dict:
    """Parse JSON robuste — cherche premier { dernier }."""
    if not raw:
        raise ValueError("Réponse vide de l'API Claude")
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON invalide : {e}. Début : {raw[:150]}")
    raise ValueError(f"Aucun JSON trouvé. Début : {raw[:150]}")


def _call_claude(anthropic_key: str, system: str, user_message: str) -> tuple:
    """Appel Claude Sonnet avec retour (result_dict, token_usage)."""
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "system": system,
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
    input_tokens  = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost_usd = (input_tokens * HAIKU_INPUT_COST + output_tokens * HAIKU_OUTPUT_COST) / 1_000_000
    token_usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 5)
    }

    raw = data["content"][0]["text"].strip()
    return _parse_json(raw), token_usage


def analyze_product_impact(
    anthropic_key: str,
    alerts: list,
    product_catalog: list,
) -> tuple:
    """
    Mode Produit : croise alertes × catalogue.

    Args:
        alerts         : liste d'entrées Agent 1 [{title, categories_concerned, urgency...}]
        product_catalog: liste de produits [{code, name, categories: [CAT3, CAT9]}]

    Returns:
        (result, token_usage)
    """
    user_message = f"""Analyze regulatory impact on this product catalog.

REGULATORY ALERTS ({len(alerts)} alerts):
{json.dumps(alerts, indent=2, ensure_ascii=False)}

PRODUCT CATALOG ({len(product_catalog)} products):
{json.dumps(product_catalog, indent=2, ensure_ascii=False)}

CATEGORY DEFINITIONS:
{json.dumps({k: {"label": v["label"], "scope": v["scope"]} for k, v in CAT_DEFINITIONS.items()}, indent=2)}

Today's date: {datetime.now().strftime('%Y-%m-%d')}

Return JSON only."""

    result, token_usage = _call_claude(anthropic_key, SYSTEM_PRODUCT, user_message)
    result["token_usage"] = token_usage
    return result, token_usage


def analyze_category_impact(
    anthropic_key: str,
    alerts: list,
    active_categories: list = None,
) -> tuple:
    """
    Mode Catégorie : croise alertes × définitions CAT → delta fiches légales.

    Args:
        alerts           : liste d'entrées Agent 1
        active_categories: liste de codes CAT actifs (ex: ["CAT3","CAT9"]) — None = toutes

    Returns:
        (result, token_usage)
    """
    cats = {k: v for k, v in CAT_DEFINITIONS.items()
            if active_categories is None or k in active_categories}

    user_message = f"""Analyze which regulatory categories need legal sheet updates.

REGULATORY ALERTS ({len(alerts)} alerts):
{json.dumps(alerts, indent=2, ensure_ascii=False)}

ACTIVE CATEGORY DEFINITIONS:
{json.dumps(cats, indent=2, ensure_ascii=False)}

Today's date: {datetime.now().strftime('%Y-%m-%d')}

Return JSON only."""

    result, token_usage = _call_claude(anthropic_key, SYSTEM_CATEGORY, user_message)
    result["token_usage"] = token_usage
    return result, token_usage


def get_watch_queries_for_categories(categories: list) -> list:
    """
    Génère les requêtes de veille depuis les définitions de catégories.
    Chaque catégorie produit plusieurs requêtes couvrant son périmètre complet.
    Utilisé par l'Agent 1 pour la veille automatique par périmètre.
    """
    queries = []
    for cat in categories:
        if cat not in CAT_WATCH_QUERIES:
            continue
        cat_queries = CAT_WATCH_QUERIES[cat]
        for topic in cat_queries:
            queries.append({
                "topic": topic,
                "categories": [cat],
                "markets": ["EU", "France"],
                "timeframe": "📅 12 derniers mois"
            })
    return queries


def get_watch_queries_deduplicated(categories: list) -> list:
    """
    Même chose mais déduplique les requêtes similaires entre catégories.
    Retourne aussi un résumé : N catégories → M requêtes.
    """
    all_queries = get_watch_queries_for_categories(categories)
    seen = set()
    deduped = []
    for q in all_queries:
        if q["topic"] not in seen:
            seen.add(q["topic"])
            deduped.append(q)
    return deduped
