"""
RegWatch — Periodic Review Script
Exécuté par GitHub Actions (manuel ou cron).

Flow :
  1. Charger la config (CAT sélectionnées, marchés, destinataires email)
  2. Lancer Agent 1 sur chaque CAT active
  3. Comparer avec la dernière revue → identifier les nouveautés
  4. Sauvegarder les résultats dans data/review_history.json
  5. Envoyer un email récapitulatif via SendGrid

Variables d'environnement requises (GitHub Secrets) :
  ANTHROPIC_API_KEY
  TAVILY_API_KEY
  RESEND_API_KEY        (clé API Resend.com, ex: re_xxxxxxxxxxxx)
  REVIEW_EMAIL_TO       (destinataire, ex: ju@decathlon.com)
  REVIEW_EMAIL_FROM     (expéditeur, ex: regwatch@resend.dev ou domaine vérifié)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── Chemins ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DATA_DIR           = ROOT / "data"
REVIEW_HISTORY     = DATA_DIR / "review_history.json"
REVIEW_CONFIG      = DATA_DIR / "review_config.json"
SOURCES_FILE       = DATA_DIR / "sources.json"

# ── Config par défaut ─────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "active_categories": ["CAT1", "CAT3", "CAT4", "CAT7", "CAT8", "CAT9"],
    "markets": ["EU", "France"],
    "timeframe": "📅 Last 12 months",
    "email_recipients": [],
    "frequency": "weekly",   # weekly | biweekly | monthly
    "enabled": True,
}


def load_config() -> dict:
    if REVIEW_CONFIG.exists():
        with open(REVIEW_CONFIG) as f:
            cfg = json.load(f)
        # Merge avec defaults pour les clés manquantes
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return DEFAULT_CONFIG.copy()


def load_history() -> dict:
    if REVIEW_HISTORY.exists():
        with open(REVIEW_HISTORY) as f:
            return json.load(f)
    return {"_meta": {}, "reviews": []}


def save_history(history: dict):
    with open(REVIEW_HISTORY, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def load_sources() -> dict:
    if SOURCES_FILE.exists():
        with open(SOURCES_FILE) as f:
            return json.load(f)
    return {"EU": ["eur-lex.europa.eu", "europa.eu"], "France": ["legifrance.gouv.fr"]}


# ── Agent 1 — Tavily search ───────────────────────────────────────────────────

def search_tavily(tavily_key: str, query: str, domains: list) -> list:
    payload = json.dumps({
        "query": query,
        "search_depth": "advanced",
        "max_results": 10,
        "time_range": "month",
        "include_raw_content": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {tavily_key}",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
    except Exception:
        results = []

    # Fallback sans filtre domaine si vide
    if not results:
        payload2 = json.dumps({
            "query": query,
            "search_depth": "advanced",
            "max_results": 10,
            "time_range": "month",
            "include_raw_content": False,
        }).encode("utf-8")
        req2 = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload2,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {tavily_key}",
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req2, timeout=30) as resp2:
                data2 = json.loads(resp2.read())
            results = data2.get("results", [])
        except Exception:
            results = []

    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")[:800]}
        for r in results
    ]


def extract_entries_claude(anthropic_key: str, topic: str, results: list, markets: list) -> list:
    if not results:
        return []

    results_text = "\n\n".join([
        f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content']}"
        for r in results
    ])

    system = """You are Agent 1, a regulatory intelligence extractor for Decathlon Electronics.
Extract structured regulatory entries from search results.
Return ONLY a valid JSON array. Each entry:
{
  "title": "regulation title",
  "source": "domain",
  "date": "YYYY-MM-DD",
  "summary": "2-3 sentence summary in English",
  "urgency": "HIGH|MEDIUM|LOW",
  "url": "source url"
}
If no relevant regulatory content, return [].
urgency HIGH = deadline < 6 months or already in force
urgency MEDIUM = deadline 6-18 months
urgency LOW = consultation or > 18 months"""

    user = f"""Extract regulatory entries.
Topic: {topic}
Markets: {', '.join(markets)}
Date: {datetime.now().strftime('%Y-%m-%d')}

Results:
{results_text}

Return JSON array only."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2048,
        "system": system,
        "messages": [{"role": "user", "content": user}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        raw = data["content"][0]["text"].strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                try:
                    return json.loads(part)
                except Exception:
                    continue
        return json.loads(raw)
    except Exception:
        return []


# ── Comparaison avec historique ───────────────────────────────────────────────

def find_new_entries(current: list, previous_titles: set) -> list:
    """Retourne les entrées dont le titre n'était pas dans la revue précédente."""
    new = []
    for entry in current:
        title = entry.get("title", "").strip().lower()
        if title and title not in previous_titles:
            new.append(entry)
    return new


def get_previous_titles(history: dict) -> set:
    """Collecte tous les titres des revues précédentes."""
    titles = set()
    for review in history.get("reviews", []):
        for cat_data in review.get("results", {}).values():
            for entry in cat_data.get("entries", []):
                t = entry.get("title", "").strip().lower()
                if t:
                    titles.add(t)
    return titles


# ── Email Gmail SMTP ──────────────────────────────────────────────────────────




def send_email_resend(
    resend_key: str,
    from_email: str,
    to_emails: list,
    subject: str,
    html_body: str,
):
    """Envoie un email via Resend.com API (3000 emails/mois gratuits)."""
    if not to_emails:
        print("No recipients configured — skipping email.")
        return

    payload = json.dumps({
        "from":    f"RegWatch <{from_email}>",
        "to":      to_emails,
        "subject": subject,
        "html":    html_body,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {resend_key}",
            "User-Agent": "RegWatch/1.0 (github-actions)",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            print(f"✅ Email sent — id: {data.get('id', '?')}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"❌ Email error {e.code}: {body}")
        print(f"   from={from_email}")
        print(f"   to={to_emails}")


def build_email_html(review_date: str, results: dict, new_counts: dict) -> str:
    total_new  = sum(new_counts.values())
    high_count = sum(
        1 for cat_data in results.values()
        for e in cat_data.get("new_entries", [])
        if e.get("urgency") == "HIGH"
    )

    rows = ""
    for cat, cat_data in results.items():
        new_entries = cat_data.get("new_entries", [])
        if not new_entries:
            continue
        for entry in new_entries:
            urgency = entry.get("urgency", "LOW")
            color   = {"HIGH": "#d32f2f", "MEDIUM": "#f57c00", "LOW": "#388e3c"}.get(urgency, "#666")
            title   = entry.get("title", "")
            url     = entry.get("url", "#")
            summary = entry.get("summary", "")[:150]
            rows += f"""
            <tr>
              <td style="padding:8px;border-bottom:1px solid #eee;font-weight:600;color:#1a3a8f">{cat}</td>
              <td style="padding:8px;border-bottom:1px solid #eee">
                <a href="{url}" style="color:#2554d4">{title}</a>
              </td>
              <td style="padding:8px;border-bottom:1px solid #eee;color:{color};font-weight:700">{urgency}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;font-size:12px;color:#666">{summary}…</td>
            </tr>"""

    if not rows:
        rows = '<tr><td colspan="4" style="padding:16px;text-align:center;color:#666">No new regulatory alerts this period.</td></tr>'

    high_note = f"· <span style='color:#d32f2f;font-weight:700'>{high_count} HIGH urgency</span>" if high_count else ""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Segoe UI,sans-serif;max-width:800px;margin:0 auto;padding:20px">
  <div style="background:#1a3a8f;color:white;padding:20px;border-radius:8px 8px 0 0">
    <h1 style="margin:0;font-size:24px">📡 RegWatch — Periodic Review</h1>
    <p style="margin:4px 0 0;opacity:0.85">{review_date} · Decathlon Electronics</p>
  </div>
  <div style="background:#f8f9ff;padding:16px;border-left:4px solid #1a3a8f">
    <strong>{total_new} new alert(s)</strong> identified this period {high_note}
  </div>
  <table style="width:100%;border-collapse:collapse;margin-top:16px">
    <thead>
      <tr style="background:#e8ecf5">
        <th style="padding:10px;text-align:left">Category</th>
        <th style="padding:10px;text-align:left">Alert</th>
        <th style="padding:10px;text-align:left">Urgency</th>
        <th style="padding:10px;text-align:left">Summary</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="margin-top:24px;font-size:12px;color:#999">
    Generated by RegWatch · <a href="https://regwatch.streamlit.app">Open app</a>
  </p>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def run_review():
    print(f"\n{'='*60}")
    print(f"RegWatch Periodic Review — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # Clés API
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    tavily_key    = os.environ.get("TAVILY_API_KEY", "")
    resend_key  = os.environ.get("RESEND_API_KEY", "")
    email_to    = os.environ.get("REVIEW_EMAIL_TO", "")
    email_from  = os.environ.get("REVIEW_EMAIL_FROM", "regwatch@resend.dev")

    if not anthropic_key or not tavily_key:
        print("❌ Missing ANTHROPIC_API_KEY or TAVILY_API_KEY")
        sys.exit(1)

    # Config + historique
    config  = load_config()
    history = load_history()
    sources = load_sources()

    active_cats = config.get("active_categories", [])
    markets     = config.get("markets", ["EU", "France"])
    recipients = config.get("email_recipients", [])
    if email_to:
        recipients = list(set(recipients + [email_to]))

    print(f"Categories : {', '.join(active_cats)}")
    print(f"Markets    : {', '.join(markets)}")
    print(f"Recipients : {', '.join(recipients) if recipients else 'none'}\n")

    # Domaines par marché
    all_domains = []
    for market in markets:
        all_domains.extend(sources.get(market, []))
    all_domains = list(set(all_domains))

    # Titres déjà vus
    previous_titles = get_previous_titles(history)
    print(f"Known titles from previous reviews: {len(previous_titles)}\n")

    # Watch queries depuis le référentiel
    try:
        from data.referential import get_cat_definitions, get_watch_queries
        cat_defs    = get_cat_definitions()
        watch_queries = get_watch_queries(active_cats)
    except Exception:
        cat_defs      = {}
        watch_queries = {cat: [f"{cat} regulation EU update"] for cat in active_cats}

    # Lancer la veille par CAT
    review_results = {}
    total_new      = 0

    for cat in active_cats:
        print(f"[{cat}] Searching...")
        queries = watch_queries.get(cat, [f"{cat} Decathlon regulation update"])
        all_entries = []

        for query in queries[:2]:  # Max 2 requêtes par CAT pour limiter les coûts
            results = search_tavily(tavily_key, query, all_domains)
            if results:
                entries = extract_entries_claude(anthropic_key, query, results, markets)
                all_entries.extend(entries)
            time.sleep(2)

        # Dédoublonner par titre
        seen = set()
        unique_entries = []
        for e in all_entries:
            t = e.get("title", "").strip().lower()
            if t and t not in seen:
                seen.add(t)
                unique_entries.append(e)

        # Nouvelles entrées seulement
        new_entries = find_new_entries(unique_entries, previous_titles)
        total_new  += len(new_entries)

        review_results[cat] = {
            "entries":     unique_entries,
            "new_entries": new_entries,
            "total":       len(unique_entries),
            "new_count":   len(new_entries),
        }
        print(f"  → {len(unique_entries)} entries found, {len(new_entries)} new")

    # Sauvegarder dans l'historique
    review_record = {
        "date":        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "categories":  active_cats,
        "markets":     markets,
        "total_new":   total_new,
        "results":     review_results,
    }
    history["reviews"].append(review_record)
    # Garder les 52 dernières revues (1 an si hebdo)
    history["reviews"] = history["reviews"][-52:]
    save_history(history)
    print(f"\n✅ Review saved — {total_new} new alert(s) total")

    # Email
    if resend_key and recipients:
        review_date = datetime.now().strftime("%B %d, %Y")
        subject = f"RegWatch Weekly Review — {total_new} new alert(s) · {datetime.now().strftime('%Y-%m-%d')}"
        html    = build_email_html(review_date, review_results, {cat: d["new_count"] for cat, d in review_results.items()})
        send_email_resend(resend_key, email_from, recipients, subject, html)
    else:
        print("⚠️  No Resend key or recipients — email skipped")

    print(f"\n{'='*60}")
    print("Review complete.")
    print(f"{'='*60}\n")
    return review_record


if __name__ == "__main__":
    run_review()
