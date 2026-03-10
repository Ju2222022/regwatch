"""
Agent 2 — Product Profiler
Extrait les technologies et specs clés d'un produit Decathlon
à partir d'une recherche web par code modèle via Claude web search.
"""

import json
import urllib.request
import urllib.error

SYSTEM_PROMPT = """You are Agent 2, a product technology profiler for Decathlon Electronics.

Your task: given a product name, model code, and web search snippets about this product,
extract a structured technology profile to be used for regulatory classification.

Focus ONLY on extracting factual technical information. Do not invent or assume.

Extract the following when present:
- Wireless protocols: Bluetooth, ANT+, GPS, WiFi, GSM/4G/5G, NFC, radio
- Power: rechargeable battery, USB charging (USB-C, micro-USB), alkaline batteries, mains powered, dynamo
- Primary function: lighting, audio, tracking, measurement, fitness, communication
- Key sensors: heart rate, accelerometer, barometer, temperature, cadence
- Connectivity: app connectivity, Zwift, Strava compatible
- Special features: waterproof rating, screen type, laser

OUTPUT — respond ONLY with valid JSON, no markdown:
{
  "code": "<model_code>",
  "name": "<product_name>",
  "technologies": {
    "wireless": ["Bluetooth", "GPS"],
    "power": ["rechargeable battery", "USB-C charging"],
    "primary_function": "fitness tracking",
    "sensors": ["heart rate", "GPS"],
    "connectivity": ["app sync", "Strava"]
  },
  "product_description_summary": "Brief 1-2 sentence summary",
  "data_confidence": "HIGH|MEDIUM|LOW",
  "missing_info": ["info that could not be found"]
}
"""


def search_and_profile(api_key: str, code: str, name: str, extra_info: str = "") -> dict:
    """
    Profil complet d'un produit via Claude web search + extraction.
    Utilise le tool web_search natif de l'API Anthropic.
    """
    query = f"Decathlon {code} {name} spécifications techniques caractéristiques"
    if extra_info:
        query += f" {extra_info}"

    messages = [
        {
            "role": "user",
            "content": f"""Search for technical specifications of this Decathlon product.
IMPORTANT: Use the model code {code} as the primary search identifier — it is unique and unambiguous.
The name '{name}' is an internal name and may differ from the commercial name or match other products.

Search query to use: {query}

After searching, extract and return ONLY a JSON technology profile with this structure:
{{
  "code": "{code}",
  "name": "{name}",
  "technologies": {{
    "wireless": [],
    "power": [],
    "primary_function": "",
    "sensors": [],
    "connectivity": []
  }},
  "product_description_summary": "",
  "data_confidence": "HIGH|MEDIUM|LOW",
  "missing_info": []
}}

Return JSON only, no other text."""
        }
    ]

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": messages
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "web-search-2025-03-05"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read())

    # Extraire le texte JSON de la réponse
    raw = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            raw += block.get("text", "")

    raw = raw.strip()
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    return json.loads(raw)


def profile_to_classifier_input(profile: dict) -> dict:
    """
    Convertit un profil Agent 2 en input enrichi pour Agent 3.
    Assemble toutes les technologies en extra_info lisible.
    """
    techs = profile.get("technologies", {})
    all_info = (
        techs.get("wireless", []) +
        techs.get("power", []) +
        techs.get("sensors", []) +
        techs.get("connectivity", [])
    )
    extra_info = ", ".join(all_info) if all_info else ""

    return {
        "code": str(profile.get("code", "")),
        "name": str(profile.get("name", "")),
        "type": str(techs.get("primary_function", "")),
        "extra_info": extra_info
    }
