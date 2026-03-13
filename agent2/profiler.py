"""
agent2/profiler.py — RegWatch Product Profiler
Extrait les technologies et specs clés d'un produit Decathlon
à partir d'une recherche web par code modèle + nom produit.

Méthode : web_search tool Claude (anthropic-beta: web-search-2025-03-05)
Pas de Tavily, pas de Jina — recherche directement via Claude Haiku.
"""

import json
import urllib.request
import urllib.parse
import urllib.error

SYSTEM_PROMPT = """You are Agent 2, a product technology profiler for Decathlon Electronics.

Your task: given a product name, model code, and web search results about this product,
extract a structured technology profile to be used for regulatory classification.

Focus ONLY on extracting factual technical information. Do not invent or assume.

Extract the following when present:
- Wireless protocols: Bluetooth, ANT+, GPS, WiFi, GSM/4G/5G, NFC, radio
- Power: rechargeable battery, USB charging (USB-C, micro-USB), alkaline batteries, mains powered, solar
- Primary function: lighting, audio, tracking, measurement, fitness, communication
- Key sensors: heart rate, accelerometer, barometer, temperature, cadence, altimeter
- Connectivity: app connectivity, Zwift, Strava compatible
- Special features: waterproof rating, screen type, laser

OUTPUT — respond ONLY with valid JSON, no markdown:
{
  "code": "<model_code>",
  "name": "<product_name>",
  "brand": "<brand>",
  "description": "<1-2 sentence summary>",
  "technologies": {
    "wireless": ["Bluetooth", "GPS"],
    "power": ["rechargeable battery", "USB-C charging"],
    "primary_function": "fitness tracking",
    "sensors": ["heart rate", "GPS"],
    "connectivity": ["app sync", "Strava"]
  },
  "key_specs": {
    "battery_life": "",
    "water_resistance": "",
    "weight": "",
    "other": []
  },
  "found": true
}
"""


def _build_search_prompt(code: str, name: str, domain: str, extra_info: str = "") -> str:
    domain_hint = f" Focus on results from {domain}." if domain else ""
    extra = f"\nAdditional known info: {extra_info}" if extra_info else ""
    return (
        f"Search for: Decathlon {name} {code} specifications techniques caractéristiques"
        f"{domain_hint}"
        f"\n\nReturn the key technical specs found.{extra}"
    )


def _call_claude_with_search(query_prompt: str, api_key: str) -> str:
    """Call Claude Haiku with web_search tool. Returns concatenated text from all blocks."""
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": query_prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "web-search-2025-03-05",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read())

    # Collect all text content from response blocks
    full_text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            full_text += block.get("text", "")
        elif block.get("type") == "tool_result":
            for item in block.get("content", []):
                if item.get("type") == "text":
                    full_text += item.get("text", "")
    return full_text


def _call_claude_extract(user_message: str, api_key: str) -> tuple[dict, int, int]:
    """Call Claude Haiku to extract structured JSON from search results."""
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read())

    raw = data["content"][0]["text"].strip()
    usage = data.get("usage", {})
    tok_in  = usage.get("input_tokens", 0)
    tok_out = usage.get("output_tokens", 0)

    # Parse JSON robustly
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part), tok_in, tok_out
            except json.JSONDecodeError:
                continue
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(raw[start:end]), tok_in, tok_out
    return {}, tok_in, tok_out


def profile_product(model_code: str, domain: str = "decathlon.fr",
                    jina_key: str = "", api_key: str = "",
                    tavily_key: str = "") -> dict:
    """
    Profile a product by model code + domain.
    Step 1: Claude web_search finds specs on the web (filtered by domain hint).
    Step 2: Claude Haiku extracts structured JSON from search results.
    """
    name_hint = model_code  # we only have the code at this stage

    # Step 1: web search
    search_prompt = _build_search_prompt(model_code, name_hint, domain)
    try:
        search_text = _call_claude_with_search(search_prompt, api_key)
    except Exception as e:
        search_text = f"[Search failed: {e}]"

    # Step 2: structured extraction
    extract_prompt = (
        f"Extract technology profile for Decathlon product code: {model_code}\n"
        f"Domain hint: {domain}\n\n"
        f"Search results:\n{search_text[:3000]}\n\n"
        f"Return JSON only."
    )
    try:
        result, tok_in, tok_out = _call_claude_extract(extract_prompt, api_key)
        if not result:
            result = {"code": model_code, "found": False}
        result["_tokens"] = {"input": tok_in, "output": tok_out}
        return result
    except Exception as e:
        return {
            "code": model_code,
            "name": "",
            "brand": "",
            "description": "",
            "technologies": {"wireless": [], "power": [], "sensors": [],
                             "connectivity": [], "primary_function": ""},
            "key_specs": {"battery_life": "", "water_resistance": "", "weight": "", "other": []},
            "found": False,
            "error": str(e),
            "_tokens": {"input": 0, "output": 0},
        }


def profile_batch(model_codes: list, domain: str = "decathlon.fr",
                  jina_key: str = "", api_key: str = "",
                  progress_cb=None, tavily_key: str = "") -> list:
    """Profile multiple products."""
    results = []
    for i, code in enumerate(model_codes):
        if progress_cb:
            progress_cb(i, len(model_codes), code)
        results.append(profile_product(code.strip(), domain, jina_key, api_key, tavily_key))
    return results


def profile_to_classifier_input(profile: dict) -> dict:
    """Convert a raw profile (Agent 2 output) into structured input for Agent 3."""
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
