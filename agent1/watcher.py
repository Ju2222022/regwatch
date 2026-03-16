"""
Agent 1 — Regulatory Watcher v3
- Multilingual search: topic translated per market language group
- EU + anglophone markets: 1 call in English
- Local language markets (FR, CN, ES, DE...): separate calls
- All results normalized to English before consolidation
- Deduplication across market groups
"""

import json
import urllib.request
import urllib.error
from datetime import datetime
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from data.referential import get_cat_descriptions_short

# ── Language groups ────────────────────────────────────────────────────────────
# Each market belongs to a language group.
# Groups share a single Tavily call. Local-language groups get a separate call.

MARKET_LANGUAGE_GROUP = {
    "EU":          "en",
    "UK":          "en",
    "USA":         "en",
    "Australia":   "en",
    "France":      "fr",
    "Belgium":     "fr",
    "Switzerland": "fr",
    "China":       "zh",
    "Spain":       "es",
    "Germany":     "de",
    "Austria":     "de",
}

LANGUAGE_LABELS = {
    "en": "English",
    "fr": "French",
    "zh": "Mandarin Chinese",
    "es": "Spanish",
    "de": "German",
}

# ── Default sources per market ─────────────────────────────────────────────────
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
    "China": [
        "samr.gov.cn",
        "miit.gov.cn",
        "cnca.org.cn",
        "gb688.cn",
    ],
    "Germany": [
        "bnetza.de",
        "bsi.bund.de",
        "gesetze-im-internet.de",
    ],
    "Spain": [
        "mincotur.gob.es",
        "boe.es",
        "cnmc.es",
    ],
}

TIMEFRAMES = {
    "⚡ Last 7 days":    "w",
    "⚡ Last 30 days":   "m",
    "📅 Last 12 months": "y",
    # Tavily time_range values: d / w / m / y (short form required since 2025)
}

# Tarifs Claude Haiku
HAIKU_INPUT_COST  = 0.80
HAIKU_OUTPUT_COST = 4.00

# CAT_DESCRIPTIONS loaded dynamically from data/legal_categories.json
CAT_DESCRIPTIONS = get_cat_descriptions_short()

SYSTEM_EXTRACT = f"""You are Agent 1, a regulatory intelligence extractor for Decathlon Electronics.

You receive search results (possibly in multiple languages) and must extract structured regulatory entries.
Always output in English, regardless of the source language.

REGWATCH CATEGORIES:
{json.dumps(CAT_DESCRIPTIONS, indent=2, ensure_ascii=False)}

OUTPUT — respond ONLY with a valid JSON array, no markdown:
[
  {{
    "title": "Regulation/standard title (in English)",
    "source": "source domain",
    "date": "YYYY-MM-DD or estimated",
    "summary": "Summary in English (2-3 sentences max)",
    "categories_concerned": ["CAT3", "CAT9"],
    "markets": ["EU", "France"],
    "source_language": "en|fr|zh|es|de",
    "urgency": "HIGH|MEDIUM|LOW",
    "action_required": "Concrete action or 'Monitor only'",
    "url": "source URL if available"
  }}
]

Rules:
- Translate all content to English in the output
- Only include genuine regulatory content (directives, standards, laws, enforcement)
- Skip generic news unless they announce a specific regulatory change
- urgency HIGH = deadline < 6 months or already in force
- urgency MEDIUM = deadline 6-18 months
- urgency LOW = consultation or > 18 months
- If nothing relevant found, return []
"""

SYSTEM_TRANSLATE = """You are a regulatory translation assistant.
Translate the given regulatory watch topic into the target language.
Keep technical terms accurate. Return ONLY the translated query string, nothing else."""


# ── Sources loader ─────────────────────────────────────────────────────────────

def load_sources(sources_json_path: str = "data/sources.json") -> dict:
    try:
        with open(sources_json_path) as f:
            return json.load(f)
    except Exception:
        return DEFAULT_SOURCES


def save_sources(sources: dict, sources_json_path: str = "data/sources.json"):
    import os
    os.makedirs(os.path.dirname(sources_json_path), exist_ok=True)
    with open(sources_json_path, "w") as f:
        json.dump(sources, f, indent=2, ensure_ascii=False)


# ── Translation ────────────────────────────────────────────────────────────────

def translate_topic(anthropic_key: str, topic: str, target_lang: str) -> str:
    """Translate a watch topic into the target language using Claude Haiku."""
    if target_lang == "en":
        return topic

    lang_label = LANGUAGE_LABELS.get(target_lang, target_lang)
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 200,
        "system": SYSTEM_TRANSLATE,
        "messages": [{
            "role": "user",
            "content": f"Translate this regulatory watch topic into {lang_label}:\n\n{topic}"
        }]
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
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return data["content"][0]["text"].strip()
    except Exception:
        return topic  # fallback to English on error


# ── Tavily search ──────────────────────────────────────────────────────────────

def search_tavily(tavily_key: str, query: str, domains: list, timeframe: str = "month") -> list:
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
        raw_resp = resp.read()
        data = json.loads(raw_resp)

    # DEBUG — log raw response keys and result count
    import sys
    print(f"[TAVILY DEBUG] keys={list(data.keys())} results={len(data.get('results',[]))} query={query[:50]!r}", file=sys.stderr)

    results = data.get("results", [])

    # If include_domains filter returns nothing, retry without domain filter
    # This handles cases where Tavily's domain filtering is too strict
    if not results and domains:
        payload_open = json.dumps({
            "query": query,
            "search_depth": "advanced",
            "max_results": 10,
            "time_range": timeframe,
            "include_raw_content": False,
        }).encode("utf-8")
        req2 = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload_open,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {tavily_key}"
            },
            method="POST"
        )
        with urllib.request.urlopen(req2, timeout=30) as resp2:
            data2 = json.loads(resp2.read())
        results = data2.get("results", [])

    return [
        {
            "title": r.get("title", ""),
            "url":   r.get("url", ""),
            "content": r.get("content", "")[:800],
        }
        for r in results
    ]


# ── Jina enrichment ────────────────────────────────────────────────────────────

def fetch_with_jina(url: str) -> str:
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
    priority_domains = ["eur-lex.europa.eu", "cenelec.eu", "legifrance.gouv.fr",
                        "samr.gov.cn", "bsi.bund.de"]
    enriched = []
    jina_count = 0
    for r in results:
        url = r.get("url", "")
        should_enrich = (
            jina_count < max_enrich and
            (any(d in url for d in priority_domains) or url.endswith(".pdf"))
        )
        if should_enrich:
            deep = fetch_with_jina(url)
            if "[Jina fetch failed" not in deep:
                r["content"] = deep
                r["enriched_by_jina"] = True
            jina_count += 1
        enriched.append(r)
    return enriched


# ── Claude extraction ──────────────────────────────────────────────────────────

def extract_regulatory_entries(
    anthropic_key: str,
    topic_en: str,
    search_results: list,
    markets: list,
    source_lang: str = "en",
) -> tuple:
    """Extract regulatory entries. Returns (entries, token_usage)."""
    if not search_results:
        return [], {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    results_text = "\n\n".join([
        f"Title: {r['title']}\nURL: {r['url']}\n"
        f"{'[Jina enriched] ' if r.get('enriched_by_jina') else ''}"
        f"Content: {r['content']}"
        for r in search_results
    ])

    lang_note = (
        f"Note: search results are in {LANGUAGE_LABELS.get(source_lang, source_lang)}. "
        f"Translate all output to English."
        if source_lang != "en" else ""
    )

    user_message = (
        f"Extract regulatory entries from these search results.\n\n"
        f"Original topic (English): {topic_en}\n"
        f"Target markets: {', '.join(markets)}\n"
        f"Search date: {datetime.now().strftime('%Y-%m-%d')}\n"
        f"{lang_note}\n\n"
        f"Search results:\n{results_text}\n\n"
        f"Return JSON array only."
    )

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2048,
        "system": SYSTEM_EXTRACT,
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

    usage = data.get("usage", {})
    inp   = usage.get("input_tokens", 0)
    out   = usage.get("output_tokens", 0)
    cost  = (inp * HAIKU_INPUT_COST + out * HAIKU_OUTPUT_COST) / 1_000_000
    token_usage = {"input_tokens": inp, "output_tokens": out, "cost_usd": round(cost, 5)}

    raw = data["content"][0]["text"].strip()
    # Parser robuste
    start = raw.find("[")
    end   = raw.rfind("]")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end+1]), token_usage
        except Exception:
            pass
    return [], token_usage


# ── Deduplication ──────────────────────────────────────────────────────────────

def deduplicate_entries(entries: list) -> list:
    """Remove near-duplicate entries based on title similarity."""
    seen_titles = []
    unique = []
    for entry in entries:
        title = entry.get("title", "").lower().strip()
        # Consider duplicate if 70%+ of words overlap with a seen title
        title_words = set(title.split())
        is_dup = False
        for seen in seen_titles:
            seen_words = set(seen.split())
            if not title_words or not seen_words:
                continue
            overlap = len(title_words & seen_words) / max(len(title_words), len(seen_words))
            if overlap > 0.7:
                is_dup = True
                break
        if not is_dup:
            seen_titles.append(title)
            unique.append(entry)
    return unique


# ── Language group builder ─────────────────────────────────────────────────────

def build_language_groups(markets: list, sources: dict) -> dict:
    """
    Group markets by language.
    Language mapping is read from sources["_market_languages"] first,
    then falls back to the hardcoded MARKET_LANGUAGE_GROUP dict.
    Returns: { "en": {"markets": [...], "domains": [...]}, ... }
    """
    # Merge hardcoded defaults with any user-defined overrides in sources.json
    lang_map = {**MARKET_LANGUAGE_GROUP, **sources.get("_market_languages", {})}

    groups = {}
    for market in markets:
        lang = lang_map.get(market, "en")
        if lang not in groups:
            groups[lang] = {"markets": [], "domains": []}
        groups[lang]["markets"].append(market)
        domains = sources.get(market, [])
        groups[lang]["domains"].extend(domains)

    # Deduplicate domains per group
    for lang in groups:
        groups[lang]["domains"] = list(set(groups[lang]["domains"]))
    return groups


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run_watch(
    anthropic_key: str,
    tavily_key: str,
    topic: str,
    markets: list,
    timeframe_label: str = "⚡ Last 30 days",
    sources_override: dict = None,
    use_jina: bool = True,
) -> tuple:
    """
    Run a full multilingual regulatory watch session.

    Flow:
      1. Group markets by language
      2. For each language group:
         a. Translate topic into group language (if not English)
         b. Search Tavily on group domains
         c. Enrich with Jina.ai (optional)
         d. Extract entries with Claude (output always in English)
      3. Deduplicate across groups
      4. Return consolidated entries + stats

    Returns:
        (entries, stats)
    """
    sources  = sources_override or load_sources()
    timeframe = TIMEFRAMES.get(timeframe_label, "month")

    groups = build_language_groups(markets, sources)

    all_entries     = []
    total_tavily    = 0
    total_jina      = 0
    total_tokens    = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    group_stats     = []

    for lang, group in groups.items():
        group_markets = group["markets"]
        group_domains = group["domains"]

        if not group_domains:
            group_stats.append({
                "lang": lang, "markets": group_markets,
                "lang_label": LANGUAGE_LABELS.get(lang, lang),
                "warning": "No domains configured for this market group."
            })
            continue

        # Step 1 — Translate topic
        translated_topic = translate_topic(anthropic_key, topic, lang) if lang != "en" else topic

        # Step 2 — Tavily search
        try:
            results = search_tavily(tavily_key, translated_topic, group_domains, timeframe)
            total_tavily += len(results)
        except Exception as e:
            group_stats.append({
                "lang": lang, "markets": group_markets,
                "lang_label": LANGUAGE_LABELS.get(lang, lang),
                "warning": f"Tavily error: {e}"
            })
            continue

        # Step 3 — Jina enrichment
        jina_count = 0
        if use_jina and results:
            results = enrich_with_jina(results, max_enrich=3)
            jina_count = sum(1 for r in results if r.get("enriched_by_jina"))
            total_jina += jina_count

        # Step 4 — Claude extraction (always outputs English)
        entries, token_usage = extract_regulatory_entries(
            anthropic_key, topic, results, group_markets, source_lang=lang
        )

        # Tag entries with source language and group markets
        for entry in entries:
            entry["watch_topic"]     = topic
            entry["watch_date"]      = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry["timeframe"]       = timeframe_label
            entry["source_language"] = lang
            if "markets" not in entry or not entry["markets"]:
                entry["markets"] = group_markets

        all_entries += entries

        total_tokens["input_tokens"]  += token_usage["input_tokens"]
        total_tokens["output_tokens"] += token_usage["output_tokens"]
        total_tokens["cost_usd"]       = round(
            total_tokens["cost_usd"] + token_usage["cost_usd"], 5
        )

        group_stats.append({
            "lang": lang,
            "lang_label": LANGUAGE_LABELS.get(lang, lang),
            "markets": group_markets,
            "translated_topic": translated_topic if lang != "en" else None,
            "tavily_results": len(results),
            "jina_enriched": jina_count,
            "entries_found": len(entries),
            **token_usage,
        })

    # Step 5 — Deduplicate across language groups
    unique_entries = deduplicate_entries(all_entries)

    stats = {
        "tavily_results":  total_tavily,
        "jina_enriched":   total_jina,
        "entries_found":   len(unique_entries),
        "duplicates_removed": len(all_entries) - len(unique_entries),
        "language_groups": group_stats,
        **total_tokens,
    }

    return unique_entries, stats
