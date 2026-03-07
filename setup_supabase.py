#!/usr/bin/env python3
"""Supabase setup helper for WikiBattle.

Run this script to verify your Supabase connection and create the
required table if it doesn't exist.

Usage:
  export SUPABASE_URL=https://your-project-id.supabase.co
  export SUPABASE_KEY=your_anon_public_key
  python setup_supabase.py
"""

import os
import sys
import json
import requests


def main():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        print("=" * 60)
        print("SUPABASE SETUP GUIDE")
        print("=" * 60)
        print()
        print("1. Go to https://supabase.com and create a free project")
        print("2. Wait for the project to finish setting up")
        print("3. Go to Settings > API in the Supabase dashboard")
        print("4. Copy the 'Project URL' and 'anon public' key")
        print("5. Set them as environment variables:")
        print()
        print("   export SUPABASE_URL=https://your-project-id.supabase.co")
        print("   export SUPABASE_KEY=eyJhbGciOi...")
        print()
        print("6. Run this script again: python setup_supabase.py")
        print()

        if not url:
            url = input("Or paste your Supabase URL now (or Enter to skip): ").strip()
        if url and not key:
            key = input("Paste your Supabase anon key: ").strip()

        if not url or not key:
            print("\nSkipped. You can set these up later.")
            sys.exit(0)

    print(f"\nSupabase URL: {url}")
    print(f"Supabase Key: {key[:20]}...")
    print()

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # Test connection
    print("[1/3] Testing connection...")
    try:
        resp = requests.get(f"{url}/rest/v1/", headers=headers, timeout=10)
        if resp.status_code == 200:
            print("  OK - Connected to Supabase")
        else:
            print(f"  ERROR - Status {resp.status_code}: {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"  ERROR - Could not connect: {e}")
        sys.exit(1)

    # Check if table exists
    print("[2/3] Checking for card_effects_cache table...")
    try:
        resp = requests.get(
            f"{url}/rest/v1/card_effects_cache",
            headers=headers,
            params={"select": "key", "limit": "1"},
            timeout=10,
        )
        if resp.status_code == 200:
            print("  OK - Table already exists")
            count_resp = requests.get(
                f"{url}/rest/v1/card_effects_cache",
                headers={**headers, "Prefer": "count=exact"},
                params={"select": "key"},
                timeout=10,
            )
            total = count_resp.headers.get("content-range", "unknown")
            print(f"  Cached cards: {total}")
        elif resp.status_code == 404 or "relation" in resp.text.lower():
            print("  Table not found - creating it now...")
            _create_table(url, key)
        else:
            print(f"  WARNING - Unexpected response ({resp.status_code}): {resp.text[:200]}")
            print("  Attempting to create table anyway...")
            _create_table(url, key)
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    # Test write + read
    print("[3/3] Testing read/write...")
    try:
        test_key = "__wikibattle_setup_test__"
        test_data = {"test": True, "message": "setup verification"}

        # Write
        write_headers = {**headers, "Prefer": "resolution=merge-duplicates,return=minimal"}
        resp = requests.post(
            f"{url}/rest/v1/card_effects_cache",
            headers=write_headers,
            json={"key": test_key, "card_type": "test", "effects_data": test_data},
            timeout=10,
        )
        if resp.status_code not in (200, 201, 204):
            print(f"  WRITE ERROR ({resp.status_code}): {resp.text[:200]}")
            sys.exit(1)

        # Read
        resp = requests.get(
            f"{url}/rest/v1/card_effects_cache",
            headers=headers,
            params={"select": "effects_data", "key": f"eq.{test_key}"},
            timeout=10,
        )
        rows = resp.json()
        if rows and rows[0].get("effects_data", {}).get("test"):
            print("  OK - Read/write working")
        else:
            print(f"  WARNING - Write succeeded but read returned unexpected data: {rows}")

        # Cleanup test row
        requests.delete(
            f"{url}/rest/v1/card_effects_cache",
            headers=headers,
            params={"key": f"eq.{test_key}"},
            timeout=10,
        )
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print()
    print("Add these to your environment (or PythonAnywhere env vars):")
    print(f"  SUPABASE_URL={url}")
    print(f"  SUPABASE_KEY={key}")
    print()


def _create_table(url, key):
    """Create the card_effects_cache table via Supabase SQL endpoint."""
    sql = """
    CREATE TABLE IF NOT EXISTS card_effects_cache (
        key TEXT PRIMARY KEY,
        card_type TEXT NOT NULL,
        effects_data JSONB NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now()
    );

    ALTER TABLE card_effects_cache ENABLE ROW LEVEL SECURITY;

    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies WHERE policyname = 'Allow all access' AND tablename = 'card_effects_cache'
        ) THEN
            CREATE POLICY "Allow all access" ON card_effects_cache
                FOR ALL USING (true) WITH CHECK (true);
        END IF;
    END $$;
    """

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # Use the Supabase SQL endpoint (available via the management API)
    # Note: This requires the service_role key for direct SQL. With the anon
    # key, we need the user to run the SQL manually.
    resp = requests.post(
        f"{url}/rest/v1/rpc/",
        headers=headers,
        json={"query": sql},
        timeout=15,
    )

    if resp.status_code in (200, 201, 204):
        print("  OK - Table created successfully")
    else:
        print("  Could not create table automatically (this is normal with the anon key).")
        print()
        print("  Please create the table manually:")
        print("  1. Go to your Supabase dashboard")
        print("  2. Click 'SQL Editor' in the left sidebar")
        print("  3. Paste and run this SQL:")
        print()
        print("  --------- COPY BELOW THIS LINE ---------")
        print()
        print("  CREATE TABLE card_effects_cache (")
        print("    key TEXT PRIMARY KEY,")
        print("    card_type TEXT NOT NULL,")
        print("    effects_data JSONB NOT NULL,")
        print("    created_at TIMESTAMPTZ DEFAULT now()")
        print("  );")
        print()
        print("  ALTER TABLE card_effects_cache ENABLE ROW LEVEL SECURITY;")
        print()
        print('  CREATE POLICY "Allow all access" ON card_effects_cache')
        print("    FOR ALL USING (true) WITH CHECK (true);")
        print()
        print("  --------- COPY ABOVE THIS LINE ---------")
        print()
        print("  4. After running the SQL, re-run this script to verify.")


if __name__ == "__main__":
    main()
