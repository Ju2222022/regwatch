"""
Agent 3 — Regulatory Classifier v2
Moteur de classification réglementaire Decathlon
Modèle : Claude (Anthropic API)

Améliorations v2 :
- Classe DecathlonClassifier : initialisation unique de la config API
- Rate limiting : pause entre chaque requête batch (évite les 429)
- Retry avec backoff exponentiel : réessaie automatiquement si quota dépassé
- JSON forcé via le prompt : pas de parsing fragile
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

## OUTPUT RULES
- Respond ONLY with valid JSON
- No markdown fences, no explanation outside the JSON
- Required format:
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

# ── Classe principale ─────────────────────────────────────────────────────────

class DecathlonClassifier:
    """
    Classifier réglementaire Decathlon.
    Initialisation unique de la config API — évite de reconfigurer à chaque appel.
    """

    def __init__(self, api_key: str, delay_between_requests: float = 2.0, max_retries: int = 3):
        """
        Args:
            api_key: Clé API Anthropic (sk-ant-...)
            delay_between_requests: Pause en secondes entre chaque requête batch (défaut 2s)
            max_retries: Nombre de tentatives en cas d'erreur 429 ou réseau
        """
        self.api_key = api_key
        self.delay = delay_between_requests
        self.max_retries = max_retries
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-haiku-4-5-20251001"

    def _call_api(self, user_message: str) -> dict:
        """
        Appel API avec retry et backoff exponentiel.
        Réessaie automatiquement si erreur 429 (quota) ou erreur réseau temporaire.
        """
        payload = json.dumps({
            "model": self.model,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}]
        }).encode("utf-8")

        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(
                    self.api_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    # Rate limit — backoff exponentiel : 5s, 10s, 20s
                    wait = 5 * (2 ** attempt)
                    time.sleep(wait)
                    if attempt == self.max_retries - 1:
                        raise Exception(f"Quota dépassé après {self.max_retries} tentatives. Réessayez dans quelques minutes.")
                else:
                    raise Exception(f"Erreur API {e.code}: {e.reason}")

            except urllib.error.URLError as e:
                wait = 3 * (2 ** attempt)
                time.sleep(wait)
                if attempt == self.max_retries - 1:
                    raise Exception(f"Erreur réseau: {e.reason}")

        raise Exception("Échec après plusieurs tentatives.")

    def _parse_response(self, data: dict) -> dict:
        """Extrait et parse le JSON de la réponse Claude."""
        raw = data["content"][0]["text"].strip()
        # Sécurité : retire les backticks si le modèle en ajoute malgré les instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)

    def classify_product(self, model_code: str, name: str, product_type: str, extra_info: str = "") -> dict:
        """
        Classifie un produit unique.

        Args:
            model_code: Code modèle Decathlon
            name: Nom commercial du produit
            product_type: Type/description du produit
            extra_info: Informations complémentaires (URL slug, specs...)

        Returns:
            dict structuré avec assigned_categories, justifications, flags
        """
        user_message = f"""Classify this product:

Model code: {model_code}
Name: {name}
Type: {product_type}
Additional info: {extra_info if extra_info else "none"}

Apply classification rules strictly. Return JSON only."""

        data = self._call_api(user_message)
        return self._parse_response(data)

    def classify_batch(self, products: list) -> list:
        """
        Classifie une liste de produits avec pause entre chaque requête.

        Args:
            products: liste de dicts avec keys: code, name, type, extra_info (optionnel)

        Returns:
            liste de dicts avec status ("ok" ou "error") et data
        """
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

            # Pause entre requêtes pour respecter le rate limit
            # Sauf après le dernier produit
            if i < len(products) - 1:
                time.sleep(self.delay)

        return results


# ── Fonctions utilitaires (rétrocompatibilité) ────────────────────────────────

def classify_product(api_key: str, model_code: str, name: str, product_type: str, extra_info: str = "") -> dict:
    """Wrapper fonctionnel pour usage simple (page Streamlit produit unique)."""
    classifier = DecathlonClassifier(api_key)
    return classifier.classify_product(model_code, name, product_type, extra_info)


def classify_batch(api_key: str, products: list) -> list:
    """Wrapper fonctionnel pour usage batch (page Streamlit batch)."""
    classifier = DecathlonClassifier(api_key)
    return classifier.classify_batch(products)
