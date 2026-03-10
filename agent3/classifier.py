"""
Agent 3 — Regulatory Classifier v3
Moteur de classification réglementaire Decathlon
Modèle : Llama 3 via Groq API (gratuit, sans carte bancaire)

Améliorations v3 :
- Groq API (llama-3.3-70b-versatile) — gratuit, rapide, sans quota EU bloqué
- Classe DecathlonClassifier : initialisation unique
- Rate limiting : pause entre requêtes batch
- Retry avec backoff exponentiel sur erreur 429
"""

import json
import time
import urllib.request
import urllib.error

# ── Référentiel Decathlon ─────────────────────────────────────────────────────

REFERENTIEL = """
CAT1 — Battery and accumulators (including component)
Batteries sold as finished goods to end consumer OR identified components.
Chemistry: Li, NiMh, Alkaline. Primary (non-rechargeable) vs secondary (rechargeable).
Does NOT apply to batteries anonymously embedded as components inside a product.

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
Despite the title, covers ANT+ protocol specifically.
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
4. When technology is implied but not confirmed, add to "categories_if_confirmed" flag only.

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

## OUTPUT RULES
Respond ONLY with a valid JSON object. No markdown, no explanation, no text outside the JSON.

Required structure:
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
  "confidence_global": "HIGH",
  "flags": {{
    "protocol_to_confirm": [],
    "categories_if_confirmed": [],
    "regulatory_edge_cases": []
  }}
}}
"""

# ── Classe principale ─────────────────────────────────────────────────────────

class DecathlonClassifier:
    """
    Classifier réglementaire Decathlon.
    Initialisation unique — évite de reconfigurer à chaque appel.
    """

    def __init__(self, api_key: str, delay_between_requests: float = 2.0, max_retries: int = 3):
        """
        Args:
            api_key           : Clé API Groq (gsk_...)
            delay_between_requests : Pause en secondes entre requêtes batch
            max_retries       : Tentatives max en cas d'erreur 429 ou réseau
        """
        self.api_key = api_key
        self.delay = delay_between_requests
        self.max_retries = max_retries
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "google/gemma-3-27b-it:free"

    def _call_api(self, user_message: str) -> dict:
        """Appel API Groq avec retry et backoff exponentiel."""
        payload = json.dumps({
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        }).encode("utf-8")

        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(
                    self.api_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://regwatch.streamlit.app",
                        "X-Title": "RegWatch Decathlon"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = 5 * (2 ** attempt)  # 5s, 10s, 20s
                    time.sleep(wait)
                    if attempt == self.max_retries - 1:
                        raise Exception(f"Quota dépassé après {self.max_retries} tentatives.")
                else:
                    body = e.read().decode("utf-8", errors="ignore")
                    raise Exception(f"Erreur API {e.code}: {body}")

            except urllib.error.URLError as e:
                wait = 3 * (2 ** attempt)
                time.sleep(wait)
                if attempt == self.max_retries - 1:
                    raise Exception(f"Erreur réseau: {e.reason}")

        raise Exception("Échec après plusieurs tentatives.")

    def _parse_response(self, data: dict) -> dict:
        """Extrait et parse le JSON de la réponse Groq."""
        raw = data["choices"][0]["message"]["content"].strip()
        # Retire les backticks si le modèle en ajoute malgré les instructions
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

    def classify_product(self, model_code: str, name: str, product_type: str, extra_info: str = "") -> dict:
        """Classifie un produit unique."""
        user_message = f"""Classify this product:

Model code: {model_code}
Name: {name}
Type: {product_type}
Additional info: {extra_info if extra_info else "none"}

Apply classification rules strictly. Return JSON only, no other text."""

        data = self._call_api(user_message)
        return self._parse_response(data)

    def classify_batch(self, products: list) -> list:
        """Classifie une liste de produits avec pause entre chaque requête."""
        results = []
        for i, p in enumerate(products):
            try:
                r = self.classify_product(
                    model_code=str(p.get("code", "")),
                    name=str(p.get("name", "")),
                    product_type=str(p.get("type", "")),
                    extra_info=str(p.get("extra_info", ""))
                )
                results.append({"status": "ok", "data": r})
            except Exception as e:
                results.append({
                    "status": "error",
                    "data": {"code": p.get("code"), "name": p.get("name"), "error": str(e)}
                })

            # Pause entre requêtes (sauf après le dernier)
            if i < len(products) - 1:
                time.sleep(self.delay)

        return results


# ── Wrappers fonctionnels (rétrocompatibilité avec les pages Streamlit) ───────

def classify_product(api_key: str, model_code: str, name: str, product_type: str, extra_info: str = "") -> dict:
    """Wrapper pour usage simple — produit unique."""
    return DecathlonClassifier(api_key).classify_product(model_code, name, product_type, extra_info)


def classify_batch(api_key: str, products: list) -> list:
    """Wrapper pour usage batch."""
    return DecathlonClassifier(api_key).classify_batch(products)
