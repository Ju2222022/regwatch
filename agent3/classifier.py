"""
Agent 3 — Regulatory Classifier
Moteur de classification réglementaire Decathlon
Modèle : Gemini 1.5 Pro via Google Generative AI API
"""

import json
import google.generativeai as genai

REFERENTIEL = """
CAT1 — Battery and accumulators (including component)
Batteries sold as finished goods to end consumer OR identified components.
Chemistry: Li, NiMh, Alkaline. Primary (non-rechargeable) vs secondary (rechargeable).
⚠ Does NOT apply to batteries anonymously embedded as components inside a product.

CAT2 — Lamp (cap lamp, LED, neon lantern, rainproof torch)
Products whose PRIMARY function is lighting: torch, headlight, bike light, dynamo light.
LED technology. CAT3 always applies as basis alongside this category.

CAT3 — Electronic equipments [MANDATORY PARACHUTE — applies to ALL electronic products]
Groups all basic electronic requirements. Safety net covering all connectivity regardless
of protocol (BT, ANT+, GPS, wifi, etc.). CAT3 alone is sufficient when specific protocol
is uncertain. Specific sub-categories (CAT5/7/8/9) add precision ON TOP of CAT3.

CAT4 — Sun charger, Electrical charger, USB charger, rechargeable products
Products with: photovoltaic, household adapter, OR rechargeable battery/charging function.
Applies when product has secondary (rechargeable) battery or USB/mains charging capability.

CAT5 — Camera video (with laser device) + remote control using ANT+
⚠ Despite the title, covers ANT+ protocol specifically.
Add ONLY when ANT+ is EXPLICITLY confirmed in product specs or description.

CAT6 — MP3 player
Products with specifically MP3 playback function.

CAT7 — Meteorological station, Mini radio, GPS, Talkie walkie, Telemeter
Add ONLY when EXPLICITLY confirmed: GPS module, radio reception, walkie talkie,
meteorological sensors, or laser telemeter.
SAR applies if >500mW. Cybersecurity rules may apply.

CAT8 — Mobile Phone / products with wifi
Add ONLY when wifi or GSM/4G/5G is EXPLICITLY confirmed.

CAT9 — Electronic equipment using bluetooth
Add ONLY when Bluetooth is EXPLICITLY stated in product name, type, or description.
SAR considerations. Cybersecurity rules may apply.
"""

SYSTEM_PROMPT = f"""You are Agent 3, a regulatory classifier for Decathlon Electronics products.
Your task: assign legal categories from Decathlon's internal referential.

{REFERENTIEL}

## CLASSIFICATION RULES

1. CAT3 is MANDATORY for every electronic product — no exception.
2. Apply the "parachute" principle: CAT3 covers all connectivity when protocol is uncertain.
   Only add specific sub-categories (CAT5/7/8/9) when that protocol is EXPLICITLY confirmed.
3. Multi-labeling: a product MUST have all applicable categories simultaneously.
4. When technology is implied but not confirmed → add to "categories_if_confirmed" flag only.

## DECISION STEPS
- CAT3: always
- CAT2: primary function is lighting
- CAT1: battery sold as finished good to consumer
- CAT4: rechargeable battery or USB/mains charging (explicit or strongly implied)
- CAT9: "Bluetooth" explicitly stated
- CAT7: "GPS" explicitly stated
- CAT5: "ANT+" explicitly stated
- CAT8: "wifi" or "4G/5G" explicitly stated
- CAT6: "MP3" explicitly stated

## OUTPUT — respond ONLY with valid JSON, no markdown fences:
{{
  "code": "<model_code>",
  "name": "<product_name>",
  "detected_technologies": {{
    "confirmed": ["explicitly stated technologies"],
    "implied": ["strongly implied but unconfirmed"],
    "uncertain": ["possible but unclear"]
  }},
  "assigned_categories": ["CAT3"],
  "category_justification": {{
    "CAT3": "mandatory parachute — electronic product"
  }},
  "confidence_global": "HIGH|MEDIUM|LOW",
  "flags": {{
    "protocol_to_confirm": ["wireless stated but protocol unknown — CAT3 parachute applied"],
    "categories_if_confirmed": ["CAT9 if Bluetooth confirmed"],
    "regulatory_edge_cases": ["e.g. medical device potential — legal team review"]
  }}
}}
"""

def classify_product(api_key: str, model_code: str, name: str, product_type: str, extra_info: str = "") -> dict:
    """
    Classifie un produit et retourne un dict structuré.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=SYSTEM_PROMPT
    )

    user_message = f"""Classify this product:

Model code: {model_code}
Name: {name}
Type: {product_type}
Additional info: {extra_info if extra_info else "none"}

Apply classification rules strictly. Return JSON only."""

    response = model.generate_content(user_message)
    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)


def classify_batch(api_key: str, products: list) -> list:
    """Classifie une liste de produits."""
    results = []
    for p in products:
        try:
            r = classify_product(
                api_key=api_key,
                model_code=p.get("code", ""),
                name=p.get("name", ""),
                product_type=p.get("type", ""),
                extra_info=p.get("extra_info", "")
            )
            results.append({"status": "ok", "data": r})
        except Exception as e:
            results.append({
                "status": "error",
                "data": {"code": p.get("code"), "name": p.get("name"), "error": str(e)}
            })
    return results
