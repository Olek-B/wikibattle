"""Card effect cache using SQLite.

Caches AI-generated card effects so we don't re-call Groq for the same
Wikipedia article. Uses SQLite for simple file-based storage.

The cache database is stored at: /tmp/wikibattle_card_cache.db
This location works well on PythonAnywhere's free tier.

Table schema:
  CREATE TABLE card_effects_cache (
    key TEXT PRIMARY KEY,
    card_type TEXT NOT NULL,
    effects_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
"""

import os
import json
import sqlite3
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# SQLite database path - use /tmp for PythonAnywhere compatibility
DB_PATH = os.environ.get("WIKIBATTLE_CACHE_DB", "/tmp/wikibattle_card_cache.db")

_initialized = False


def _get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table() -> None:
    """Create the cache table if it doesn't exist."""
    global _initialized
    if _initialized:
        return

    try:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS card_effects_cache (
                    key TEXT PRIMARY KEY,
                    card_type TEXT NOT NULL,
                    effects_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            _initialized = True
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to initialize cache table: {e}")


def _make_key(article_title: str, card_type: str) -> str:
    """Build cache key from article title and card type."""
    return f"{article_title}|{card_type}"


def get_cached_effects(article_title: str, card_type: str) -> Optional[dict]:
    """Look up cached AI-generated effects for a card.

    Returns the effects_data dict if found, or None on cache miss.
    Silently returns None on any error (cache is best-effort).
    """
    try:
        _ensure_table()
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            key = _make_key(article_title, card_type)
            cursor.execute(
                "SELECT effects_data FROM card_effects_cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            if row:
                data = row["effects_data"]
                if isinstance(data, str):
                    data = json.loads(data)
                logger.info(f"Cache HIT for '{article_title}' ({card_type})")
                return data
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Cache lookup failed for '{article_title}': {e}")

    return None


def store_effects(article_title: str, card_type: str, effects_data: dict) -> None:
    """Store AI-generated effects in the cache.

    Uses INSERT OR REPLACE so re-generating a card just overwrites the old entry.
    Silently ignores errors (cache is best-effort).
    """
    try:
        _ensure_table()
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            key = _make_key(article_title, card_type)
            cursor.execute(
                """
                INSERT OR REPLACE INTO card_effects_cache (key, card_type, effects_data)
                VALUES (?, ?, ?)
                """,
                (key, card_type, json.dumps(effects_data))
            )
            conn.commit()
            logger.info(f"Cache STORED for '{article_title}' ({card_type})")
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Cache store failed for '{article_title}': {e}")


def list_all_cards(limit: int = 100, card_type: Optional[str] = None) -> List[Dict]:
    """List all cached cards from the database.
    
    Args:
        limit: Maximum number of cards to return
        card_type: Optional filter by card type ('creature', 'terrain', 'spell')
    
    Returns:
        List of card dicts with name, card_type, and effects_data
    """
    try:
        _ensure_table()
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if card_type:
                cursor.execute(
                    "SELECT key, card_type, effects_data FROM card_effects_cache WHERE card_type = ? ORDER BY created_at DESC LIMIT ?",
                    (card_type, limit)
                )
            else:
                cursor.execute(
                    "SELECT key, card_type, effects_data FROM card_effects_cache ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            rows = cursor.fetchall()
            cards = []
            for row in rows:
                key = row["key"]
                name = key.rsplit("|", 1)[0] if "|" in key else key
                data = row["effects_data"]
                if isinstance(data, str):
                    data = json.loads(data)
                cards.append({
                    "key": key,
                    "name": name,
                    "card_type": row["card_type"],
                    "effects_data": data,
                })
            return cards
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to list cards: {e}")
        return []


def search_cards(query: str, limit: int = 50) -> List[Dict]:
    """Search for cards by name.
    
    Args:
        query: Search query string
        limit: Maximum number of cards to return
    
    Returns:
        List of matching card dicts
    """
    try:
        _ensure_table()
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            cursor.execute(
                """
                SELECT key, card_type, effects_data 
                FROM card_effects_cache 
                WHERE key LIKE ? 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (search_pattern, limit)
            )
            rows = cursor.fetchall()
            cards = []
            for row in rows:
                key = row["key"]
                name = key.rsplit("|", 1)[0] if "|" in key else key
                data = row["effects_data"]
                if isinstance(data, str):
                    data = json.loads(data)
                cards.append({
                    "key": key,
                    "name": name,
                    "card_type": row["card_type"],
                    "effects_data": data,
                })
            return cards
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to search cards: {e}")
        return []


def get_card_count() -> Dict[str, int]:
    """Get count of cards by type.
    
    Returns:
        Dict with counts for each card type
    """
    try:
        _ensure_table()
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT card_type, COUNT(*) as count FROM card_effects_cache GROUP BY card_type"
            )
            rows = cursor.fetchall()
            counts = {"creature": 0, "terrain": 0, "spell": 0, "total": 0}
            for row in rows:
                counts[row["card_type"]] = row["count"]
                counts["total"] += row["count"]
            return counts
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to get card count: {e}")
        return {"creature": 0, "terrain": 0, "spell": 0, "total": 0}
