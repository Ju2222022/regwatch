"""
agent2/profiler.py — RegWatch Product Profiler
Scrapes product specs from the web (Jina.ai + Tavily) by model code.
Returns raw structured data only — no classification, no regulatory analysis.
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import streamlit as st


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _jina_fetch(url: str, jina_key: str = "") -> str:
    """Fetch a URL via Jina.ai reader. Key is optional (anonymous quota available)."""
    jina_url = f"https://r.jina.ai/{url}"
    headers = {"Accept": "application/json"}
    if jina_key:
        headers["Authorization"] = f"Bearer {jina_key}"
    req = urllib.request.Request(jina_url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data.get("data", {}).get("content", "")


def _claude_call(prompt: str, api_key: str, max_tokens: int = 1000) -> tuple[str, int, int]:
    """Call Claude Haiku. Returns (text, input_tokens, output_tokens)."""
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    text = data["content"][0]["text"]
    usage = data.get("usage", {})
    return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)


def _parse_json_safe(raw: str) -> dict:
    """Robustly extract JSON from a Claude response."""
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
    return {}


# ── Tavily search ─────────────────────────────────────────────────────────────

def _tavily_search(query: str, tavily_key: str, max_results: int = 3) -> list[dict]:
    payload = json.dumps({
        "api_key": tavily_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data.get("results", [])


# ── Main functions ────────────────────────────────────────────────────────────

def search_product_url(model_code: str, tavily_key: str) -> str | None:
    """Find the best Decathlon URL for a model code via Tavily."""
    query = f'site:decathlon.fr "{model_code}" fiche produit'
    results = _tavily_search(query, tavily_key, max_results=3)
    for r in results:
        url = r.get("url", "")
        if "decathlon.fr" in url and model_code.lower() in url.lower():
            return url
    if results:
        return results[0].get("url")
    return None


def scrape_product_specs(model_code: str, product_url: str | None,
                          jina_key: str, api_key: str) -> dict:
    """
    Scrape product specs from the URL (Jina.ai) and extract structured data via Claude.
    Returns raw specs dict only — no classification.
    """
    raw_content = ""
    source_url = product_url or f"https://www.decathlon.fr/search?Ntt={urllib.parse.quote(model_code)}"

    try:
        raw_content = _jina_fetch(source_url, jina_key)
    except Exception as e:
        raw_content = f"[Fetch failed: {e}]"

    prompt = f"""You are a product data extraction assistant.
Extract structured specifications from the following product page content for model code: {model_code}

Return ONLY a valid JSON object with this exact structure:
{{
  "code": "{model_code}",
  "name": "product name or empty string",
  "brand": "brand name or empty string",
  "url": "{source_url}",
  "description": "short product description (2-3 sentences max) or empty string",
  "technologies": {{
    "wireless": ["list of wireless protocols found: Bluetooth, BLE, GPS, ANT+, WiFi, etc."],
    "power": ["list of power/charging info: rechargeable, USB-C, solar, AA battery, etc."],
    "sensors": ["list of sensors: heart rate, barometer, accelerometer, etc."],
    "connectivity": ["list of connectivity features: app sync, phone pairing, etc."],
    "primary_function": "main product function in 1-5 words"
  }},
  "key_specs": {{
    "battery_life": "battery life info or empty string",
    "water_resistance": "water resistance rating or empty string",
    "weight": "weight or empty string",
    "other": ["any other notable specs"]
  }},
  "found": true
}}

If the product is not found or content is irrelevant, return the same structure with "found": false and empty strings/lists.

Page content:
{raw_content[:4000]}
"""

    try:
        raw, tok_in, tok_out = _claude_call(prompt, api_key, max_tokens=800)
        result = _parse_json_safe(raw)
        result["_tokens"] = {"input": tok_in, "output": tok_out}
        return result
    except Exception as e:
        return {
            "code": model_code,
            "name": "",
            "brand": "",
            "url": source_url,
            "description": "",
            "technologies": {"wireless": [], "power": [], "sensors": [], "connectivity": [], "primary_function": ""},
            "key_specs": {"battery_life": "", "water_resistance": "", "weight": "", "other": []},
            "found": False,
            "error": str(e),
            "_tokens": {"input": 0, "output": 0},
        }


def profile_product(model_code: str, tavily_key: str, jina_key: str, api_key: str) -> dict:
    """
    Full pipeline: find URL via Tavily → scrape via Jina → extract specs via Claude.
    Returns raw product profile dict.
    """
    product_url = search_product_url(model_code, tavily_key)
    return scrape_product_specs(model_code, product_url, jina_key, api_key)


def profile_batch(model_codes: list[str], tavily_key: str, jina_key: str,
                  api_key: str, progress_cb=None) -> list[dict]:
    """Profile multiple products. progress_cb(i, total, code) for UI updates."""
    results = []
    for i, code in enumerate(model_codes):
        if progress_cb:
            progress_cb(i, len(model_codes), code)
        results.append(profile_product(code.strip(), tavily_key, jina_key, api_key))
    return results


def profile_to_classifier_input(profile: dict) -> dict:
    """
    Convert a raw profile (Agent 2 output) into structured input for Agent 3 classifier.
    """
    techs = profile.get("technologies", {})
    wireless = techs.get("wireless", [])
    power = techs.get("power", [])
    sensors = techs.get("sensors", [])
    connectivity = techs.get("connectivity", [])
    all_info = wireless + power + sensors + connectivity
    extra_info = ", ".join(all_info) if all_info else ""

    return {
        "code": profile.get("code", ""),
        "name": profile.get("name", ""),
        "type": techs.get("primary_function", ""),
        "description": profile.get("description", ""),
        "extra_info": extra_info,
    }
