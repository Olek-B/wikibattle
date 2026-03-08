#!/usr/bin/env python3
"""SQLite cache setup helper for WikiBattle.

Run this script to verify your SQLite cache is working correctly.
The cache is automatically created on first use, but this script
lets you test it explicitly.

Usage:
  python setup_cache.py

Optional:
  export WIKIBATTLE_CACHE_DB=/custom/path/cache.db
  python setup_cache.py
"""

import os
import sys
import sqlite3
import json

DB_PATH = os.environ.get("WIKIBATTLE_CACHE_DB", "/tmp/wikibattle_card_cache.db")


def main():
    print("=" * 60)
    print("WIKIBATTLE SQLITE CACHE SETUP")
    print("=" * 60)
    print()
    print(f"Cache database path: {DB_PATH}")
    print()

    # Test connection and table creation
    print("[1/3] Testing database connection...")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        print("  OK - Database connection successful")
    except Exception as e:
        print(f"  ERROR - Could not connect: {e}")
        sys.exit(1)

    # Create table
    print("[2/3] Creating card_effects_cache table...")
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
        print("  OK - Table created/verified")
    except Exception as e:
        print(f"  ERROR - Could not create table: {e}")
        conn.close()
        sys.exit(1)

    # Test write + read
    print("[3/3] Testing read/write...")
    try:
        test_key = "__wikibattle_setup_test__"
        test_data = {"test": True, "message": "setup verification"}

        # Write
        cursor.execute(
            """
            INSERT OR REPLACE INTO card_effects_cache (key, card_type, effects_data)
            VALUES (?, ?, ?)
            """,
            (test_key, "test", json.dumps(test_data))
        )
        conn.commit()

        # Read
        cursor.execute(
            "SELECT effects_data FROM card_effects_cache WHERE key = ?",
            (test_key,)
        )
        row = cursor.fetchone()
        if row and json.loads(row["effects_data"]).get("test"):
            print("  OK - Read/write working")
        else:
            print("  ERROR - Write succeeded but read returned unexpected data")
            conn.close()
            sys.exit(1)

        # Cleanup test row
        cursor.execute("DELETE FROM card_effects_cache WHERE key = ?", (test_key,))
        conn.commit()
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.close()
        sys.exit(1)

    conn.close()

    print()
    print("=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print()
    print("The SQLite cache is ready to use!")
    print()
    print("Optional environment variable:")
    print(f"  WIKIBATTLE_CACHE_DB={DB_PATH}")
    print()
    print("You can now run the game:")
    print("  export GROQ_API_KEY=your_key_here")
    print("  python server/app.py")
    print()


if __name__ == "__main__":
    main()
