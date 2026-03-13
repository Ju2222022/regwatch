"""
agent2/profiler.py — RegWatch Product Profiler v2
Méthode : appel API Anthropic avec web_search tool (beta).
La recherche se fait en 1 seul appel — Claude cherche ET extrait.
"""

import json
import urllib.request
import urllib.error
import time

# ── Prompt système ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Agent 2, a universal product profiler for regulatory classification.

Your task: given web search results about a product, extract ALL technically relevant characteristics — whatever the product category (electronics, textiles, sports equipment, optics, tools, etc.).

EXTRACTION RULES:
- Extract ONLY what is explicitly stated in the search results. Never invent or assume.
- Be exhaustive: capture every technical characteristic that could be relevant for regulatory compliance.
- Group findings into the most appropriate categories for the product type found.
- Use the exact terminology from the source (e.g. "IPX7", "USB-C", "CE marked", "Class II").

For the "technologies" object, use these keys as a guide but add any others that are relevant:
  - "wireless": any radio/wireless protocols or frequencies (e.g. Bluetooth 5.0, ANT+, GPS, WiFi 2.4GHz, 868MHz)
  - "power": power source and charging (e.g. Li-Ion 300mAh, USB-C, 2xAAA, solar, mains 230V)
  - "primary_function": one short phrase describing what the product does
  - "sensors": any measurement or detection components (e.g. optical HR, barometer, CMOS 12MP)
  - "connectivity": data interfaces and ecosystem (e.g. Bluetooth app sync, ANT+ head unit)
  - "materials": if relevant for compliance (e.g. "ABS plastic", "stainless steel 316L")
  - "certifications": any regulatory marks found (e.g. CE, FCC, RoHS, EN ISO 4210)

For "key_specs", capture the most compliance-relevant measurements:
  - "battery_life": duration if stated
  - "water_resistance": IP code, ATM rating, or any water/dust protection
  - "weight": product weight
  - "dimensions": if stated
  - "other": list of any other notable specs (voltage, wattage, frequency range, laser class, etc.)

CRITICAL OUTPUT RULES:
- Respond ONLY with a valid JSON object. No markdown, no text outside JSON.
- Empty string "" for unknown text fields, empty list [] for unknown list fields.
- Set "found": true only if you found actual product specs.

{
  "code": "<model_code>",
  "name": "<full product name>",
  "brand": "<brand>",
  "description": "<2-3 sentence technical summary>",
  "technologies": {
    "wireless": [],
    "power": [],
    "primary_function": "",
    "sensors": [],
    "connectivity": []
  },
  "key_specs": {
    "battery_life": "",
    "water_resistance": "",
    "weight": "",
    "dimensions": "",
    "other": []
  },
  "found": true
}
"""

# ── Appel API ──────────────────────────────────────────────────────────────────

def _call_api(payload: dict, api_key: str, beta: str = "",
              max_retries: int = 3) -> dict:
    """Generic Anthropic API call with retry on 429."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    if beta:
        headers["anthropic-beta"] = beta

    for attempt in range(max_retries):
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                wait = 15 * (attempt + 1)  # 15s, 30s, 45s
                time.sleep(wait)
                continue
            raise


def _parse_json_from_text(raw: str) -> dict:
    """Robustly extract JSON from Claude response."""
    raw = raw.strip()
    # Strip markdown code fences
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Find JSON object boundaries
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
    return {}


def _extract_text_from_response(data: dict) -> str:
    """Extract all text content from an Anthropic response (handles web_search multi-turn)."""
    texts = []
    for block in data.get("content", []):
        btype = block.get("type", "")
        if btype == "text":
            texts.append(block.get("text", ""))
        elif btype == "tool_result":
            for item in block.get("content", []):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
    return "\n".join(texts)


# ── Pipeline principal ─────────────────────────────────────────────────────────

def profile_product(model_code: str, domain: str = "decathlon.fr",
                    jina_key: str = "", api_key: str = "",
                    tavily_key: str = "", name_hint: str = "") -> dict:
    """
    Profile a Decathlon product in 2 steps:
    1. Claude web_search fetches specs from the web
    2. Claude extracts structured JSON from the search results
    """
    search_name = name_hint if name_hint else model_code
    domain_clean = domain.strip().lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")

    # ── Step 1 : web search via Claude ────────────────────────────────────────
    search_query = (
        f"Find the complete technical specifications for Decathlon product code {model_code} "
        f"({search_name}) on {domain_clean}. "
        f"Return ALL technical characteristics: materials, components, protocols, certifications, "
        f"power, dimensions, compliance markings — whatever is relevant for this product type."
    )

    # ── Single call: search + extract in one shot ─────────────────────────────
    user_msg = (
        f"Decathlon {model_code} {search_name} {domain_clean} technical specifications. "
        f"Return ONLY the JSON object from your instructions. No text outside JSON."
    )

    try:
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 800,
            "system": SYSTEM_PROMPT,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{"role": "user", "content": user_msg}]
        }
        data = _call_api(payload, api_key, beta="web-search-2025-03-05")

        # Extract the final text block (last text block = Claude's final answer)
        raw = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                raw = block.get("text", "")

        usage = data.get("usage", {})
        tok_in  = usage.get("input_tokens", 0)
        tok_out = usage.get("output_tokens", 0)

        result = _parse_json_from_text(raw)
        if not result:
            result = {"code": model_code, "found": False, "error": "JSON parse failed"}
        result.setdefault("code", model_code)
        result["_tokens"] = {"input": tok_in, "output": tok_out}
        return result

    except Exception as e:
        return {
            "code": model_code, "name": "", "brand": "", "description": "",
            "technologies": {"wireless": [], "power": [], "sensors": [],
                             "connectivity": [], "primary_function": ""},
            "key_specs": {"battery_life": "", "water_resistance": "", "weight": "", "other": []},
            "found": False,
            "error": str(e),
            "_tokens": {"input": 0, "output": 0},
        }


def profile_batch(model_codes: list, domain: str = "decathlon.fr",
                  jina_key: str = "", api_key: str = "",
                  progress_cb=None, tavily_key: str = "",
                  name_hints: dict = None) -> list:
    """Profile multiple products. name_hints: {code: name} optional dict."""
    results = []
    for i, code in enumerate(model_codes):
        if progress_cb:
            progress_cb(i, len(model_codes), code)
        hint = (name_hints or {}).get(code.strip(), "")
        results.append(profile_product(code.strip(), domain, jina_key, api_key, tavily_key, hint))
    return results


def profile_to_classifier_input(profile: dict) -> dict:
    """Convert Agent 2 output into structured input for Agent 3."""
    techs = profile.get("technologies", {})
    all_info = (
        techs.get("wireless", []) +
        techs.get("power", []) +
        techs.get("sensors", []) +
        techs.get("connectivity", [])
    )
    return {
        "code":        profile.get("code", ""),
        "name":        profile.get("name", ""),
        "type":        techs.get("primary_function", ""),
        "description": profile.get("description", ""),
        "extra_info":  ", ".join(all_info) if all_info else "",
    }
