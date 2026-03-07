#!/usr/bin/env python3
"""CLI tool for testing WikiBattle card effect generation.

Usage:
    python test_effects.py                      # Random article, auto-detect type
    python test_effects.py --type spell          # Random article, forced type
    python test_effects.py --title "Napoleon"    # Specific article
    python test_effects.py --raw                 # Show raw AI response
    python test_effects.py --count 5             # Generate 5 cards
    python test_effects.py --no-cache            # Skip cache, always call Groq
"""

import argparse
import json
import os
import sys
import logging

# Ensure imports work from server/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wikipedia_api import fetch_random_articles, classify_article
from card_generator import build_card_from_article
from ai_effects import (
    generate_card_effects,
    _build_prompt_for_card,
    _fallback_effects,
    GROQ_API_KEY,
    GROQ_MODEL,
    SPELL_BANNED_EFFECTS,
)


def fetch_article_by_title(title: str) -> dict | None:
    """Fetch a specific Wikipedia article by title."""
    import requests

    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts|pageimages|categories|coordinates",
        "exintro": True,
        "explaintext": True,
        "exsectionformat": "plain",
        "pithumbsize": 300,
        "cllimit": 20,
        "colimit": 50,
        "redirects": 1,
    }

    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            headers={"User-Agent": "WikiBattle/1.0 (card game; educational)"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching article: {e}")
        return None

    pages = data.get("query", {}).get("pages", {})
    for page_id, page in pages.items():
        if int(page_id) < 0:
            print(f"Article not found: {title}")
            return None

        extract = page.get("extract", "")
        categories = [
            c["title"].replace("Category:", "")
            for c in page.get("categories", [])
        ]
        coords = None
        if "coordinates" in page:
            c = page["coordinates"][0]
            coords = {"lat": c["lat"], "lon": c["lon"]}

        return {
            "pageid": int(page_id),
            "title": page.get("title", title),
            "extract": extract,
            "thumbnail": page.get("thumbnail", {}).get("source"),
            "categories": categories,
            "coordinates": coords,
            "url": f"https://en.wikipedia.org/wiki/{page.get('title', title).replace(' ', '_')}",
        }
    return None


def print_card(card: dict, show_raw: bool = False, raw_data: dict | None = None):
    """Pretty-print a card with its effects."""
    t = card["card_type"].upper()
    name = card["name"]

    print()
    print("=" * 60)
    print(f"  [{t}] {name}")
    print("=" * 60)

    # Stats line
    stats = []
    if card["card_type"] == "creature":
        stats.append(f"ATK: {card.get('attack', '?')}")
        stats.append(f"HP: {card.get('health', '?')}/{card.get('max_health', '?')}")
    if "mana_cost" in card:
        stats.append(f"Mana: {card['mana_cost']}")
    if card["card_type"] == "terrain":
        stats.append(f"Mana production: {card.get('mana_production', 1)}")
    if stats:
        print(f"  {' | '.join(stats)}")

    # Abilities
    if card.get("abilities"):
        print(f"  Abilities: {', '.join(card['abilities'])}")

    # Description
    desc = card.get("effect_description", "")
    if desc:
        print(f"  \"{desc}\"")

    # Effects
    effects = card.get("effects", [])
    if effects:
        print()
        print("  Effects:")
        for i, eff in enumerate(effects, 1):
            trigger = eff.get("trigger", "?")
            etype = eff.get("type", "?")
            params = eff.get("params", {})
            params_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else ""
            print(f"    {i}. [{trigger}] {etype}({params_str})")
    else:
        print("  Effects: (none)")

    # Wikipedia extract (truncated)
    extract = card.get("extract", "")
    if extract:
        print()
        truncated = extract[:200] + ("..." if len(extract) > 200 else "")
        print(f"  Wikipedia: {truncated}")

    # Wiki URL
    if card.get("wiki_url"):
        print(f"  URL: {card['wiki_url']}")

    print("-" * 60)

    # Raw AI response
    if show_raw and raw_data:
        print()
        print("  Raw AI response:")
        print(json.dumps(raw_data, indent=2))
        print()


def generate_with_raw(card: dict, skip_cache: bool = False) -> tuple[dict, dict | None]:
    """Generate effects and optionally capture raw AI response.

    Returns (updated_card, raw_data_or_None).
    """
    import groq
    from ai_effects import (
        _build_prompt_for_card,
        _apply_ai_effects,
        SYSTEM_PROMPT,
    )
    from card_cache import get_cached_effects, store_effects

    article_title = card.get("name", "")
    card_type = card.get("card_type", "creature")

    # Check cache unless skipping
    if not skip_cache:
        cached = get_cached_effects(article_title, card_type)
        if cached is not None:
            print("  (from cache)")
            return _apply_ai_effects(card, cached), cached

    if not GROQ_API_KEY:
        print("  (no GROQ_API_KEY, using fallback)")
        return _fallback_effects(card), None

    try:
        client = groq.Groq(api_key=GROQ_API_KEY)
        prompt = _build_prompt_for_card(card)

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            print("  (empty AI response, using fallback)")
            return _fallback_effects(card), None

        data = json.loads(content)

        # Store in cache
        if not skip_cache:
            store_effects(article_title, card_type, data)

        return _apply_ai_effects(card, data), data

    except Exception as e:
        print(f"  (Groq API error: {e}, using fallback)")
        return _fallback_effects(card), None


def main():
    parser = argparse.ArgumentParser(
        description="Test WikiBattle card effect generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python test_effects.py                       # Random article
  python test_effects.py --type spell          # Force spell type
  python test_effects.py --title "Napoleon"    # Specific article
  python test_effects.py --raw                 # Show raw AI JSON
  python test_effects.py --count 5             # Generate 5 cards
  python test_effects.py --count 3 --type spell --raw  # 3 spell cards with raw output
  python test_effects.py --fallback            # Test fallback effects only
  python test_effects.py --prompt              # Show the prompt that would be sent
""",
    )
    parser.add_argument("--title", "-t", help="Specific Wikipedia article title")
    parser.add_argument(
        "--type", "-T",
        choices=["creature", "terrain", "spell"],
        help="Force card type (default: auto-detect)",
    )
    parser.add_argument("--raw", "-r", action="store_true", help="Show raw AI JSON response")
    parser.add_argument("--count", "-c", type=int, default=1, help="Number of cards to generate (default: 1)")
    parser.add_argument("--no-cache", action="store_true", help="Skip cache, always call Groq API")
    parser.add_argument("--fallback", "-f", action="store_true", help="Test fallback effects only (no AI)")
    parser.add_argument("--prompt", "-p", action="store_true", help="Show the prompt that would be sent to AI")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Status
    if GROQ_API_KEY:
        print(f"Groq API: configured (model: {GROQ_MODEL})")
    else:
        print("Groq API: NOT configured (GROQ_API_KEY not set, will use fallback)")

    if SPELL_BANNED_EFFECTS:
        print(f"Spell banned effects: {', '.join(sorted(SPELL_BANNED_EFFECTS))}")

    for i in range(args.count):
        if args.count > 1:
            print(f"\n--- Card {i + 1}/{args.count} ---")

        # Get article
        if args.title:
            article = fetch_article_by_title(args.title)
            if not article:
                sys.exit(1)
        else:
            print("Fetching random Wikipedia article...")
            articles = fetch_random_articles(count=1)
            if not articles:
                print("Error: Could not fetch any articles from Wikipedia")
                sys.exit(1)
            article = articles[0]

        # Classify
        forced_type = args.type
        detected_type = classify_article(article)
        card_type = forced_type or detected_type
        if forced_type and forced_type != detected_type:
            print(f"  Auto-detected type: {detected_type} (overridden to: {forced_type})")
        else:
            print(f"  Type: {card_type}")

        # Build card
        card = build_card_from_article(article, card_type=card_type)

        # Show prompt if requested
        if args.prompt:
            prompt = _build_prompt_for_card(card)
            print("\n  === PROMPT ===")
            print(prompt)
            print("  === END PROMPT ===\n")
            if not args.fallback:
                continue  # Only show prompt, don't generate

        # Generate effects
        if args.fallback:
            card = _fallback_effects(card)
            print_card(card)
        else:
            card, raw = generate_with_raw(card, skip_cache=args.no_cache)
            print_card(card, show_raw=args.raw, raw_data=raw)


if __name__ == "__main__":
    main()
