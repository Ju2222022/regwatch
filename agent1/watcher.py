"""
Agent 1 — Regulatory Watcher v2
- Tavily pour la recherche sur domaines officiels
- Jina.ai pour lecture profonde des PDFs et pages dynamiques (EUR-Lex, etc.)
- Domaines configurables (chargés depuis data/sources.json)
- Compteur de tokens par appel
"""

import json
import urllib.request
import urllib.error
from datetime import datetime

# ── Domaines par défaut (si sources.json absent) ──────────────────────────────

DEFAULT_SOURCES = {
    "EU": [
        "eur-lex.europa.eu",
        "europa.eu",
        "echa.europa.eu",
        "single-market-economy.ec.europa.eu",
        "commission.europa.eu",
        "cenelec.eu",
        "iec.ch",
    ],
    "France": [
        "legifrance.gouv.fr",
        "anssi.fr",
        "economie.gouv.fr",
    ],
    "UK": [
        "gov.uk",
        "legislation.gov.uk",
    ],
    "USA": [
        "fcc.gov",
        "cpsc.gov",
        "ftc.gov",
    ],
}

TIMEFRAMES = {
    "⚡ 30 derniers jours": "month",
    "📅 12 derniers mois": "year",
    "🏛️ 3 derniers ans": "year",
}

# Tarifs Claude Haiku ($/1M tokens) — mis à jour si nécessaire
HAIKU_INPUT_COST  = 0.80  # $ per 1M input tokens
HAIKU_OUTPUT_COST = 4.00  # $ per 1M output tokens

CAT_DESCRIPTIONS = {
    "CAT1": "batteries, accumulators, lithium, alkaline, primary, secondary battery",
    "CAT2": "lamps, lighting, LED, torch, headlight, bike light",
    "CAT3": "electronic equipment, RoHS, WEEE, EMC, LVD, general electronics",
    "CAT4": "chargers, USB charger, power supply, adapter, rechargeable, photovoltaic",
    "CAT5": "ANT+, camera, video, remote control, wireless sensor",
    "CAT6": "MP3, audio player, music player",
    "CAT7": "GPS, radio, walkie talkie, telemeter, meteorological, ITE, SAR, frequency",
    "CAT8": "wifi, mobile phone, GSM, 4G, 5G, cellular, cybersecurity",
    "CAT9": "bluetooth, wireless earphone, connected watch, BLE",
}

SYSTEM_PROMPT = f"""You are Agent 1, a regulatory intelligence extractor for Decathlon Electronics.

You receive search results from regulatory sources and must extract structured regulatory entries.

REGWATCH CATEGORIES:
{json.dumps(CAT_DESCRIPTIONS, indent=2, ensure_ascii=False)}

OUTPUT — respond ONLY with valid JSON array, no markdown:
[
  {{
    "title": "Regulation/standard title",
    "source": "source domain",
    "date": "YYYY-MM-DD or estimated",
    "summary_fr": "Résumé en français (2-3 phrases max)",
    "categories_concerned": ["CAT3", "CAT9"],
    "markets": ["EU"],
    "urgency": "HIGH|MEDIUM|LOW",
    "action_required": "Description de l'action ou 'Surveillance uniquement'",
    "url": "source URL if available"
  }}
]

Rules:
- Only include genuine regulatory content (directives, standards, laws, enforcement actions)
- Skip generic news unless they announce a specific regulatory change
- urgency HIGH = deadline < 6 months or already in force
- urgency MEDIUM = deadline 6-18 months  
- urgency LOW = consultation or > 18 months
- If nothing relevant found, return []
"""

# ── Gestion sources configurables ─────────────────────────────────────────────

def load_sources(sources_json_path: str = "data/sources.json") -> dict:
    """Charge les sources depuis le fichier de config, fallback sur DEFAULT_SOURCES."""
    try:
        with open(sources_json_path) as f:
            return json.load(f)
    except Exception:
        return DEFAULT_SOURCES


def save_sources(sources: dict, sources_json_path: str = "data/sources.json"):
    """Sauvegarde les sources dans le fichier de config."""
    import os
    os.makedirs(os.path.dirname(sources_json_path), exist_ok=True)
    with open(sources_json_path, "w") as f:
        json.dump(sources, f, indent=2, ensure_ascii=False)


# ── Tavily search ─────────────────────────────────────────────────────────────

def search_tavily(tavily_key: str, query: str, domains: list, timeframe: str = "month") -> list:
    """Recherche Tavily sur les domaines réglementaires."""
    payload = json.dumps({
        "query": query,
        "search_depth": "advanced",
        "max_results": 10,
        "include_domains": domains,
        "time_range": timeframe,
        "include_raw_content": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {tavily_key}"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    results = []
    for r in data.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:800],
        })
    return results


# ── Jina.ai deep reader ───────────────────────────────────────────────────────

def fetch_with_jina(url: str) -> str:
    """
    Lit une page ou PDF via Jina.ai reader.
    Utile pour les sites à tiroirs (EUR-Lex) et les PDFs officiels.
    """
    jina_url = f"https://r.jina.ai/{url}"
    req = urllib.request.Request(
        jina_url,
        headers={"Accept": "text/plain", "X-Return-Format": "text"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="ignore")[:2000]
    except Exception as e:
        return f"[Jina fetch failed: {e}]"


def enrich_with_jina(results: list, max_enrich: int = 3) -> list:
    """
    Enrichit les N premiers résultats avec le contenu Jina.ai.
    Priorise les URLs EUR-Lex et les PDFs.
    """
    priority_domains = ["eur-lex.europa.eu", "cenelec.eu", "legifrance.gouv.fr"]
    enriched = []
    jina_count = 0

    for r in results:
        url = r.get("url", "")
        should_enrich = (
            jina_count < max_enrich and
            (any(d in url for d in priority_domains) or url.endswith(".pdf"))
        )
        if should_enrich:
            deep_content = fetch_with_jina(url)
            if "[Jina fetch failed" not in deep_content:
                r["content"] = deep_content
                r["enriched_by_jina"] = True
            jina_count += 1
        enriched.append(r)

    return enriched


# ── Claude extraction ─────────────────────────────────────────────────────────

def extract_regulatory_entries(anthropic_key: str, query: str, search_results: list, markets: list) -> tuple:
    """
    Extrait les entrées réglementaires structurées via Claude.
    Retourne (entries, token_usage) où token_usage = {input, output, cost_usd}
    """
    if not search_results:
        return [], {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    results_text = "\n\n".join([
        f"Title: {r['title']}\nURL: {r['url']}\n"
        f"{'[Enrichi Jina] ' if r.get('enriched_by_jina') else ''}"
        f"Content: {r['content']}"
        for r in search_results
    ])

    user_message = f"""Extract regulatory entries from these search results.

Search topic: {query}
Target markets: {', '.join(markets)}
Search date: {datetime.now().strftime('%Y-%m-%d')}

Search results:
{results_text}

Return JSON array only."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
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

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    # Tokens & coût
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
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part), token_usage
            except json.JSONDecodeError:
                continue
    return json.loads(raw), token_usage


# ── Pipeline principal ────────────────────────────────────────────────────────

def run_watch(
    anthropic_key: str,
    tavily_key: str,
    topic: str,
    markets: list,
    timeframe_label: str = "⚡ 30 derniers jours",
    sources_override: dict = None,
    use_jina: bool = True,
) -> tuple:
    """
    Lance une session de veille complète.

    Returns:
        (entries, stats) où stats contient les métriques de la session
    """
    sources = sources_override or load_sources()

    domains = []
    for market in markets:
        domains.extend(sources.get(market, []))
    domains = list(set(domains))

    timeframe = TIMEFRAMES.get(timeframe_label, "month")

    # Étape 1 — Tavily
    search_results = search_tavily(tavily_key, topic, domains, timeframe)
    tavily_count = len(search_results)

    # Étape 2 — Enrichissement Jina.ai
    jina_count = 0
    if use_jina and search_results:
        enriched = enrich_with_jina(search_results, max_enrich=3)
        jina_count = sum(1 for r in enriched if r.get("enriched_by_jina"))
        search_results = enriched

    if not search_results:
        return [], {"tavily_results": 0, "jina_enriched": 0, "entries_found": 0,
                    "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                    "warning": "Tavily n'a retourné aucun résultat. Essayez une période plus longue ou un sujet différent."}

    # Étape 3 — Claude extraction
    entries, token_usage = extract_regulatory_entries(
        anthropic_key, topic, search_results, markets
    )

    # Enrichir les entrées avec metadata session
    for entry in entries:
        entry["watch_topic"] = topic
        entry["watch_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry["timeframe"] = timeframe_label

    stats = {
        "tavily_results": tavily_count,
        "jina_enriched": jina_count,
        "entries_found": len(entries),
        **token_usage
    }

    return entries, stats
