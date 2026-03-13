"""
agent2/profiler.py — RegWatch Product Profiler v4
Recherche : Tavily (snippets courts, ~500 tokens)
Extraction : Claude Haiku (JSON structuré, ~800 tokens)
Total par produit : ~1300 tokens input = ~$0.001
"""

import json
import time
import urllib.request
import urllib.error

SYSTEM_PROMPT = """You are Agent 2, a product technology profiler for Decathlon Electronics.

Given web search snippets about a product, extract a structured technology profile.
Focus ONLY on factual technical information. Do NOT invent or assume.

Extract when present:
- Wireless: Bluetooth (version if known), ANT+, GPS, WiFi, GSM/4G/5G, NFC
- Power: rechargeable battery (mAh if known), USB-C/micro-USB, alkaline, solar
- Primary function: cycling computer, GPS watch, heart rate monitor, fitness tracker, etc.
- Sensors: heart rate, GPS, accelerometer, barometer, altimeter, cadence, power meter, SpO2
- Connectivity: app name, Strava, Zwift, ANT+ devices
- Key specs: battery life (hours), water resistance (IPX/ATM), weight (g)

Respond ONLY with valid JSON, no markdown:
{
  "code": "",
  "name": "",
  "brand": "Decathlon",
  "description": "",
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
    "other": []
  },
  "found": true
}
"""


def _tavily_search(query: str, tavily_key: str, max_results: int = 5) -> list:
    """Search via Tavily. Returns list of {url, title, content} snippets."""
    payload = json.dumps({
        "api_key": tavily_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
    }).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return data.get("results", [])
    except Exception:
        return []


def _call_claude(payload: dict, api_key: str, max_retries: int = 3) -> dict:
    """Claude Haiku API call with retry on 429."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    for attempt in range(max_retries):
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(15 * (attempt + 1))
                continue
            body = e.read().decode("utf-8", errors="ignore")
            raise Exception(f"HTTP {e.code}: {body[:300]}")
    raise Exception("Failed after retries")


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except Exception:
                continue
    try:
        return json.loads(raw)
    except Exception:
        pass
    s, e = raw.find("{"), raw.rfind("}") + 1
    if s >= 0 and e > s:
        try:
            return json.loads(raw[s:e])
        except Exception:
            pass
    return {}


def profile_product(model_code: str, domain: str = "decathlon.fr",
                    jina_key: str = "", api_key: str = "",
                    tavily_key: str = "", name_hint: str = "") -> dict:
    """
    Step 1 — Tavily searches the web → short snippets (~500 tokens)
    Step 2 — Claude Haiku extracts JSON from snippets (~800 tokens)
    Total : ~1300 tokens = ~$0.001 per product
    """
    search_name  = name_hint if name_hint else model_code
    domain_clean = (domain.strip().lower()
                    .replace("https://", "").replace("http://", "")
                    .replace("www.", "").rstrip("/"))

    # ── Step 1 : Tavily search ────────────────────────────────────────────────
    snippets_text = ""
    if tavily_key:
        # Search by model code ONLY — no name to avoid cross-product contamination
        # (e.g. "W500" would match unrelated products with similar names)
        query = f"Decathlon {model_code} {domain_clean}"
        results = _tavily_search(query, tavily_key)
        # Priority: results containing the exact model code
        code_results   = [r for r in results if model_code in r.get("url", "") or model_code in r.get("content", "")]
        domain_results = [r for r in results if domain_clean in r.get("url", "") and r not in code_results]
        other_results  = [r for r in results if r not in code_results and r not in domain_results]
        ordered = code_results + domain_results + other_results

        parts = []
        for r in ordered[:4]:
            title   = r.get("title", "")
            content = r.get("content", "")[:400]  # 400 chars max par snippet
            url     = r.get("url", "")
            parts.append(f"[{title}] ({url})\n{content}")
        snippets_text = "\n\n".join(parts)

    if not snippets_text:
        snippets_text = f"Product: {search_name}, code: {model_code}, brand: Decathlon"

    # ── Step 2 : Claude Haiku extraction ─────────────────────────────────────
    try:
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 800,
            "system": SYSTEM_PROMPT,
            "messages": [{
                "role": "user",
                "content": (
                    f"Model code: {model_code}\n"
                    f"Domain: {domain_clean}\n\n"
                    f"Search snippets (extract info ONLY for product with code {model_code}):\n"
                    f"{snippets_text[:2000]}\n\n"
                    f"Return JSON only. If snippets describe a different product, set found: false."
                )
            }]
        }
        data   = _call_claude(payload, api_key)
        raw    = data["content"][0]["text"]
        usage  = data.get("usage", {})
        tok_in  = usage.get("input_tokens", 0)
        tok_out = usage.get("output_tokens", 0)

        result = _parse_json(raw)
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
    results = []
    for i, code in enumerate(model_codes):
        if progress_cb:
            progress_cb(i, len(model_codes), code)
        hint = (name_hints or {}).get(code.strip(), "")
        results.append(profile_product(code.strip(), domain, jina_key, api_key, tavily_key, hint))
        if i < len(model_codes) - 1:
            time.sleep(2)
    return results


def profile_to_classifier_input(profile: dict) -> dict:
    techs    = profile.get("technologies", {})
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
        "description": profile.get("description", "")[:300],
        "extra_info":  ", ".join(all_info)[:500] if all_info else "",
    }
