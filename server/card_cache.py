"""Card effect cache using Supabase.

Caches AI-generated card effects so we don't re-call Groq for the same
Wikipedia article. Uses Supabase's REST API (PostgREST) - no special
database driver needed, just `requests`.

Environment variables:
  SUPABASE_URL  - e.g. https://abcdef.supabase.co
  SUPABASE_KEY  - the anon/public API key (not the service role key)

Supabase table setup (run in SQL Editor):

  CREATE TABLE card_effects_cache (
    key TEXT PRIMARY KEY,
    card_type TEXT NOT NULL,
    effects_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
  );

  -- Allow anon read/write (or use service key instead)
  ALTER TABLE card_effects_cache ENABLE ROW LEVEL SECURITY;
  CREATE POLICY "Allow all access" ON card_effects_cache
    FOR ALL USING (true) WITH CHECK (true);
"""

import os
import json
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
TABLE = "card_effects_cache"


def _headers() -> dict:
    """Build request headers for Supabase REST API."""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _make_key(article_title: str, card_type: str) -> str:
    """Build cache key from article title and card type."""
    return f"{article_title}|{card_type}"


def get_cached_effects(article_title: str, card_type: str) -> Optional[dict]:
    """Look up cached AI-generated effects for a card.

    Returns the effects_data dict if found, or None on cache miss.
    Silently returns None on any error (cache is best-effort).
    """
    if not _is_configured():
        return None

    key = _make_key(article_title, card_type)

    try:
        url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
        params = {
            "select": "effects_data",
            "key": f"eq.{key}",
        }
        resp = requests.get(url, headers=_headers(), params=params, timeout=5)
        resp.raise_for_status()

        rows = resp.json()
        if rows and len(rows) > 0:
            data = rows[0].get("effects_data")
            if isinstance(data, str):
                data = json.loads(data)
            logger.info(f"Cache HIT for '{article_title}' ({card_type})")
            return data

    except Exception as e:
        logger.warning(f"Cache lookup failed for '{article_title}': {e}")

    return None


def store_effects(article_title: str, card_type: str, effects_data: dict) -> None:
    """Store AI-generated effects in the cache.

    Uses upsert so re-generating a card just overwrites the old entry.
    Silently ignores errors (cache is best-effort).
    """
    if not _is_configured():
        return

    key = _make_key(article_title, card_type)

    try:
        url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
        headers = _headers()
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"

        payload = {
            "key": key,
            "card_type": card_type,
            "effects_data": effects_data,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info(f"Cache STORED for '{article_title}' ({card_type})")

    except Exception as e:
        logger.warning(f"Cache store failed for '{article_title}': {e}")
