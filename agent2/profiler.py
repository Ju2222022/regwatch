"""
agent2/profiler.py — RegWatch Product Profiler v3
2 appels séparés avec délai :
  1. web_search (max_tokens=300) → récupère snippets bruts, peu de tokens
  2. extract (max_tokens=800, sans web_search) → structure le JSON depuis les snippets
"""

import json
import time
import urllib.request
import urllib.error

# ── System prompt extraction ───────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Agent 2, a product technology profiler for Decathlon Electronics.

Given web search snippets about a product, extract a structured technology profile.
Focus ONLY on factual technical information. Do NOT invent or assume.

Extract when present:
- Wireless: Bluetooth (version), ANT+, GPS, WiFi, GSM/4G/5G, NFC
- Power: rechargeable battery (mAh), USB-C/micro-USB charging, alkaline, solar
- Primary function: cycling computer, GPS watch, heart rate monitor, fitness tracker, etc.
- Sensors: heart rate, GPS, accelerometer, barometer, altimeter, cadence, power meter, SpO2
- Connectivity: app name, Strava, Zwift, ANT+ devices
- Key specs: battery life (hours), water resistance (IPX/ATM), weight (g)

Respond ONLY with valid JSON, no markdown, no explanation:
{
  "code": "",
  "name": "",
  "brand": "",
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

# ── API helper ─────────────────────────────────────────────────────────────────

def _call_api(payload: dict, api_key: str, beta: str = "", max_retries: int = 2) -> dict:
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
                time.sleep(20)
                continue
            body = e.read().decode("utf-8", errors="ignore")
            raise Exception(f"HTTP {e.code}: {body[:200]}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
            raise
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


# ── Pipeline ───────────────────────────────────────────────────────────────────

def profile_product(model_code: str, domain: str = "decathlon.fr",
                    jina_key: str = "", api_key: str = "",
                    tavily_key: str = "", name_hint: str = "") -> dict:
    """
    Step 1 — web_search with max_tokens=300 to get short snippets only.
    Step 2 — extract JSON from snippets (no web_search, controlled input size).
    """
    search_name  = name_hint if name_hint else model_code
    domain_clean = domain.strip().lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")

    # ── Step 1 : web search — très court pour limiter tokens ──────────────────
    snippets = ""
    tok_s_in = tok_s_out = 0
    try:
        search_payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,   # volontairement bas — on veut juste les faits clés
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{
                "role": "user",
                "content": (
                    f"Find technical specs for Decathlon {model_code} {search_name} "
                    f"on {domain_clean}. List: wireless protocols, battery, sensors, "
                    f"water resistance, weight. Short bullet points only."
                )
            }]
        }
        search_data = _call_api(search_payload, api_key, beta="web-search-2025-03-05")

        # Collecter uniquement les blocs texte (pas les tool_use)
        for block in search_data.get("content", []):
            if block.get("type") == "text":
                snippets += block.get("text", "")

        usage = search_data.get("usage", {})
        tok_s_in  = usage.get("input_tokens", 0)
        tok_s_out = usage.get("output_tokens", 0)

    except Exception as e:
        snippets = f"Product: {search_name}, code: {model_code}"

    # Pause entre les deux appels pour éviter le rate limit
    time.sleep(3)

    # ── Step 2 : extraction JSON — sans web_search ────────────────────────────
    # Tronquer les snippets à 1500 chars max pour contrôler le coût
    snippets_trimmed = snippets[:1500] if snippets else f"{search_name} {model_code}"

    tok_e_in = tok_e_out = 0
    try:
        extract_payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 800,
            "system": SYSTEM_PROMPT,
            "messages": [{
                "role": "user",
                "content": (
                    f"Model code: {model_code}\n"
                    f"Product: {search_name}\n"
                    f"Domain: {domain_clean}\n\n"
                    f"Snippets:\n{snippets_trimmed}\n\n"
                    f"Return JSON only."
                )
            }]
        }
        extract_data = _call_api(extract_payload, api_key)
        raw = extract_data["content"][0]["text"]
        usage2   = extract_data.get("usage", {})
        tok_e_in  = usage2.get("input_tokens", 0)
        tok_e_out = usage2.get("output_tokens", 0)

        result = _parse_json(raw)
        if not result:
            result = {"code": model_code, "found": False, "error": "JSON parse failed"}
        result.setdefault("code", model_code)
        result["_tokens"] = {
            "input":  tok_s_in + tok_e_in,
            "output": tok_s_out + tok_e_out,
        }
        return result

    except Exception as e:
        return {
            "code": model_code, "name": "", "brand": "", "description": "",
            "technologies": {"wireless": [], "power": [], "sensors": [],
                             "connectivity": [], "primary_function": ""},
            "key_specs": {"battery_life": "", "water_resistance": "", "weight": "", "other": []},
            "found": False,
            "error": str(e),
            "_tokens": {"input": tok_s_in, "output": tok_s_out},
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
            time.sleep(5)  # pause entre produits en batch
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
