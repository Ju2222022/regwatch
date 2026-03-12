"""
data/referential.py — RegWatch Central Referential
Single source of truth for all agents.
Reads from data/legal_categories.json.

Usage:
    from data.referential import get_subcategories, get_cat_labels, get_watch_queries, get_classification_rules
"""

import json
import os
from pathlib import Path

_REFERENTIAL_PATH = Path(__file__).parent / "legal_categories.json"


def load_referential() -> dict:
    """Load the full referential from JSON."""
    with open(_REFERENTIAL_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_referential(data: dict):
    """Save the full referential to JSON."""
    with open(_REFERENTIAL_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Accessors ─────────────────────────────────────────────────────────────────

def get_legal_categories() -> list:
    """Return list of legal categories (top-level)."""
    return load_referential().get("legal_categories", [])


def get_legal_category(category_id: str) -> dict:
    """Return a specific legal category by id."""
    for cat in get_legal_categories():
        if cat["id"] == category_id:
            return cat
    return {}


def get_subcategories(legal_category_id: str = None) -> dict:
    """
    Return subcategories as {id: subcategory_dict}.
    If legal_category_id is None, returns all subcategories from all legal categories.
    """
    result = {}
    for legal_cat in get_legal_categories():
        if legal_category_id and legal_cat["id"] != legal_category_id:
            continue
        for sub in legal_cat.get("subcategories", []):
            result[sub["id"]] = {**sub, "_legal_category_id": legal_cat["id"], "_legal_category_label": legal_cat["label"]}
    return result


def get_cat_labels(legal_category_id: str = None) -> dict:
    """
    Return {cat_id: label} mapping.
    Used by all pages for display.
    """
    return {k: v["label"] for k, v in get_subcategories(legal_category_id).items()}


def get_cat_definitions(legal_category_id: str = None) -> dict:
    """
    Return full subcategory definitions — equivalent to old CAT_DEFINITIONS.
    Includes label, scope, key_regulations, keywords.
    """
    result = {}
    for cat_id, sub in get_subcategories(legal_category_id).items():
        result[cat_id] = {
            "label":            sub.get("label", ""),
            "scope":            sub.get("scope", ""),
            "key_regulations":  sub.get("key_regulations", []),
            "keywords":         sub.get("keywords", []),
        }
    return result


def get_watch_queries(cat_ids: list = None, legal_category_id: str = None) -> dict:
    """
    Return {cat_id: [queries]} for watch topics.
    If cat_ids is provided, filter to those only.
    """
    subcats = get_subcategories(legal_category_id)
    result = {}
    for cat_id, sub in subcats.items():
        if cat_ids and cat_id not in cat_ids:
            continue
        queries = sub.get("watch_queries", [])
        if queries:
            result[cat_id] = queries
    return result


def get_cat_descriptions_short(legal_category_id: str = None) -> dict:
    """
    Return {cat_id: keywords_string} — compact version for agent prompts.
    Replaces old CAT_DESCRIPTIONS in watcher.py.
    """
    return {
        cat_id: ", ".join(sub.get("keywords", [])[:8])
        for cat_id, sub in get_subcategories(legal_category_id).items()
    }


def get_classification_rules(legal_category_id: str) -> dict:
    """
    Return classification rules for a given legal category.
    Includes mandatory_fallback, fallback_rule, specificity_rule.
    """
    cat = get_legal_category(legal_category_id)
    return cat.get("classification_rules", {})


def get_referential_for_agent3(legal_category_id: str = None) -> str:
    """
    Build the REFERENTIEL text block for Agent 3 prompt.
    Replaces hardcoded REFERENTIEL string in classifier.py.
    """
    lines = []
    for legal_cat in get_legal_categories():
        if legal_category_id and legal_cat["id"] != legal_category_id:
            continue

        rules = legal_cat.get("classification_rules", {})
        if rules.get("mandatory_fallback"):
            lines.append(f"DOMAIN: {legal_cat['label']}")
            lines.append(f"MANDATORY FALLBACK: {rules['mandatory_fallback']} — {rules.get('fallback_rule', '')}")
            lines.append(f"SPECIFICITY RULE: {rules.get('specificity_rule', '')}")
            lines.append("")

        for sub in legal_cat.get("subcategories", []):
            lines.append(f"{sub['id']} — {sub['label']}")
            lines.append(sub.get("scope", ""))
            if sub.get("classification_rule"):
                lines.append(f"RULE: {sub['classification_rule']}")
            lines.append("")

    return "\n".join(lines)


def get_watch_queries_deduplicated(cat_ids: list, legal_category_id: str = None) -> list:
    """
    Return deduplicated watch query list for given cat_ids.
    Each item: {topic, categories, markets, timeframe}
    Replaces get_watch_queries_deduplicated in impact.py.
    """
    queries_by_cat = get_watch_queries(cat_ids, legal_category_id)
    seen = set()
    result = []
    for cat_id in cat_ids:
        for topic in queries_by_cat.get(cat_id, []):
            if topic not in seen:
                seen.add(topic)
                result.append({
                    "topic": topic,
                    "categories": [cat_id],
                    "markets": ["EU", "France"],
                    "timeframe": "📅 Last 12 months"
                })
    return result


# ── Mutators (used by Configuration page) ─────────────────────────────────────

def update_subcategory(legal_category_id: str, cat_id: str, updated_fields: dict) -> bool:
    """
    Update fields of a subcategory in the JSON.
    Returns True if successful.
    """
    data = load_referential()
    for legal_cat in data.get("legal_categories", []):
        if legal_cat["id"] != legal_category_id:
            continue
        for sub in legal_cat.get("subcategories", []):
            if sub["id"] == cat_id:
                sub.update(updated_fields)
                save_referential(data)
                return True
    return False


def update_legal_category(legal_category_id: str, updated_fields: dict) -> bool:
    """Update top-level fields of a legal category."""
    data = load_referential()
    for legal_cat in data.get("legal_categories", []):
        if legal_cat["id"] == legal_category_id:
            for k, v in updated_fields.items():
                if k not in ("subcategories",):  # protect subcategories
                    legal_cat[k] = v
            save_referential(data)
            return True
    return False


def add_legal_category(new_category: dict) -> bool:
    """Add a new legal category."""
    data = load_referential()
    ids = [c["id"] for c in data.get("legal_categories", [])]
    if new_category["id"] in ids:
        return False
    data.setdefault("legal_categories", []).append(new_category)
    save_referential(data)
    return True


def add_subcategory(legal_category_id: str, new_sub: dict) -> bool:
    """Add a new subcategory to a legal category."""
    data = load_referential()
    for legal_cat in data.get("legal_categories", []):
        if legal_cat["id"] == legal_category_id:
            existing_ids = [s["id"] for s in legal_cat.get("subcategories", [])]
            if new_sub["id"] in existing_ids:
                return False
            legal_cat.setdefault("subcategories", []).append(new_sub)
            save_referential(data)
            return True
    return False
