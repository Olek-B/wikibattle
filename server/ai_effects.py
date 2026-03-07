"""AI effect generation for WikiBattle cards using Groq API.

Generates thematic card effects based on Wikipedia article content.
Uses a structured DSL that the effect engine can execute.
"""

import os
import json
import logging
from typing import Optional

from card_cache import get_cached_effects, store_effects

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

# All available effect types the AI can use
EFFECT_TYPES = [
    # Damage & Healing
    "deal_damage",           # {target: "opponent"/"creature", amount: N}
    "heal",                  # {target: "self"/"creature", amount: N}
    "damage_all_enemies",    # {amount: N} - damages all enemy creatures
    "damage_all",            # {amount: N} - damages ALL creatures (earthquake)
    "life_drain",            # {amount: N} - deal damage to opponent, heal self

    # Card manipulation
    "draw_cards",            # {count: N}
    "opponent_discard",      # {count: N} - opponent discards random cards
    "steal_card",            # {} - steal random card from opponent's hand
    "swap_hands",            # {} - swap entire hands
    "resurrect",             # {} - return random creature from your graveyard to hand

    # Creature stats
    "buff_attack",           # {target: "self"/"all_friendly", amount: N}
    "buff_health",           # {target: "self"/"all_friendly", amount: N}
    "debuff_attack",         # {target: "target"/"all_enemies", amount: N}
    "debuff_health",         # {target: "target"/"all_enemies", amount: N}
    "swap_stats",            # {target: "self"/"target"} - swap attack/health
    "set_attack",            # {target: "self", amount: N}
    "set_health",            # {target: "self", amount: N}

    # Board control
    "destroy_creature",      # {target: "target"/"random_enemy"/"weakest_enemy"}
    "destroy_terrain",       # {} - destroy opponent's terrain (random)
    "bounce",                # {target: "target"/"random_enemy"} - return to hand
    "freeze",                # {target: "target"/"all_enemies", turns: N}
    "shield",                # {target: "self"/"all_friendly", amount: N}
    "taunt",                 # {target: "self"} - must be attacked first

    # Mana
    "gain_mana",             # {amount: N} - bonus mana this turn
    "drain_mana",            # {amount: N} - opponent loses mana
    "untap_terrains",        # {count: N} - untap N of your terrains

    # Chaos effects
    "random_effect",         # {} - pick a random effect and apply it
    "cascade",               # {} - reveal top card of deck, play it free if cost <= this
    "mutate",                # {target: "self"/"target"} - randomize creature stats
    "time_warp",             # {} - take an extra turn (RARE)
    "mirror",                # {} - copy the last card effect your opponent played
    "gamble",                # {win_effect: {...}, lose_effect: {...}} - 50/50
    "chain_lightning",       # {amount: N, bounces: N} - damage that bounces randomly
    "summon_token",          # {attack: N, health: N, name: str} - create a creature token

    # Terrain-specific extras
    "extra_mana",            # {} - this terrain produces 1 extra mana (total 2)
    "heal_on_tap",           # {amount: N} - heal player when this terrain is tapped
    "damage_on_tap",         # {amount: N} - damage opponent when tapped
]

TRIGGER_TYPES = [
    "on_play",       # When card is played from hand
    "on_death",      # When this creature dies
    "on_attack",     # When this creature attacks
    "on_damaged",    # When this creature takes damage
    "on_turn_start", # At start of controller's turn
    "on_turn_end",   # At end of controller's turn
    "on_enemy_play", # When opponent plays any card
    "passive",       # Always active while on field
    "on_tap",        # When terrain is tapped for mana
]


SYSTEM_PROMPT = """You are the card effect designer for WikiBattle, a chaotic Wikipedia-powered trading card game.
You generate card effects based on real Wikipedia articles. Effects should be THEMATIC and FUN - connect the effect to what the article is about.

RULES:
- Go WILD with effects. Chaos is encouraged. Fun > Balance.
- BUT: No auto-win cards. No "opponent loses the game" or "deal 30 damage" effects.
- Creature attack should be 1-7, health should be 1-8
- Creature mana cost should be 1-6 (roughly proportional to power)
- Spell mana cost should be 1-5
- Effects should feel thematic - a volcano terrain should do fire damage, a scientist creature should have smart effects, etc.
- Each card should have 1-3 effects, each with a trigger
- Be creative with the effect names and descriptions! The description should be a fun flavor text.
- Terrains always produce 1 mana base. Their effects are EXTRA bonuses (on_tap, passive, on_play, etc.)
- IMPORTANT: Do NOT default to deal_damage for every card! Use the FULL variety of effect types.
  Spells especially should use diverse effects: draw_cards, bounce, freeze, steal_card, swap_hands,
  buff/debuff, shield, resurrect, summon_token, chain_lightning, cascade, gamble, mutate, etc.
  deal_damage should be used at MOST on 1 out of every 4 spell cards.
- Combine multiple different effect types on a single card for interesting combos.

You MUST respond with valid JSON only. No markdown, no explanation, just the JSON object."""


def _build_prompt_for_card(card: dict) -> str:
    """Build the user prompt for effect generation."""
    card_type = card["card_type"]
    name = card["name"]
    extract = card.get("extract", "")
    categories = ", ".join(card.get("categories", [])[:10])

    type_instructions = ""
    if card_type == "creature":
        type_instructions = """For this CREATURE card, provide:
- "attack": integer 1-7
- "health": integer 1-8
- "mana_cost": integer 1-6
- "abilities": list of keyword strings (e.g. ["flying", "shield", "taunt"])
- "effect_description": flavorful description of what this creature does (1-2 sentences)
- "effects": list of effect objects

Each effect object has:
- "trigger": one of [on_play, on_death, on_attack, on_damaged, on_turn_start, on_turn_end, on_enemy_play, passive]
- "type": the effect type string
- "params": object with parameters for that effect type"""

    elif card_type == "terrain":
        type_instructions = """For this TERRAIN card, provide:
- "mana_cost": 0 (terrains are always free)
- "mana_production": 1 (base mana, can be modified by effects)
- "effect_description": flavorful description of this terrain's bonus effect (1-2 sentences)
- "effects": list of effect objects (the BONUS effects, not the base mana production)

Each effect object has:
- "trigger": one of [on_play, on_tap, on_turn_start, on_turn_end, passive, on_enemy_play]
- "type": the effect type string
- "params": object with parameters for that effect type

Terrain effects should feel like the PLACE is influencing the battle.
Many terrains can have no extra effects - just producing mana is fine. But interesting places should have fun bonuses."""

    elif card_type == "spell":
        type_instructions = """For this SPELL card, provide:
- "mana_cost": integer 1-5
- "effect_description": flavorful description of what this spell does (1-2 sentences)
- "effects": list of effect objects (all should have trigger "on_play" since spells are one-time)

Each effect object has:
- "trigger": "on_play"
- "type": the effect type string
- "params": object with parameters for that effect type

Spells should feel like the EVENT is happening on the battlefield.
AVOID making every spell just deal_damage! Use creative effects like:
draw_cards, bounce, freeze, steal_card, swap_hands, destroy_creature,
chain_lightning, cascade, gamble, mutate, shield, summon_token, life_drain,
damage_all_enemies, resurrect, opponent_discard, time_warp, etc.
Combine 2-3 different effects for interesting combos!"""

    available_effects = ", ".join(EFFECT_TYPES)
    available_triggers = ", ".join(TRIGGER_TYPES)

    return f"""Generate effects for this {card_type.upper()} card:

Name: {name}
Description: {extract}
Categories: {categories}

{type_instructions}

Available effect types: {available_effects}
Available triggers: {available_triggers}

Target values for params can be: "self", "opponent", "target" (chosen by player), "random_enemy", "all_friendly", "all_enemies", "weakest_enemy", "strongest_enemy"

Respond with a single JSON object. No markdown wrapping."""


def generate_card_effects(card: dict) -> dict:
    """Generate effects for a card using the Groq API.

    Checks the Supabase cache first; on miss, calls Groq and caches the result.
    Returns the updated card dict with effects filled in.
    Falls back to simple defaults if API fails.
    """
    article_title = card.get("name", "")
    card_type = card.get("card_type", "creature")

    # --- Check cache first ---
    cached = get_cached_effects(article_title, card_type)
    if cached is not None:
        return _apply_ai_effects(card, cached)

    # --- No cache hit, call Groq ---
    if not GROQ_API_KEY:
        logger.warning("No GROQ_API_KEY set, using fallback effects")
        return _fallback_effects(card)

    try:
        import groq
        client = groq.Groq(api_key=GROQ_API_KEY)

        prompt = _build_prompt_for_card(card)

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,  # High creativity
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            return _fallback_effects(card)

        data = json.loads(content)

        # Store in cache for future reuse
        store_effects(article_title, card_type, data)

        return _apply_ai_effects(card, data)

    except Exception as e:
        logger.error(f"Groq API error for card '{card.get('name', '?')}': {e}")
        return _fallback_effects(card)


def _apply_ai_effects(card: dict, data: dict) -> dict:
    """Apply AI-generated effects to a card, with validation."""
    card["effects_generated"] = True
    card["effect_description"] = data.get("effect_description", "A mysterious card...")

    # Apply type-specific stats
    if card["card_type"] == "creature":
        card["attack"] = _clamp(data.get("attack", 2), 1, 7)
        card["health"] = _clamp(data.get("health", 2), 1, 8)
        card["max_health"] = card["health"]
        card["mana_cost"] = _clamp(data.get("mana_cost", 1), 1, 6)
        card["abilities"] = data.get("abilities", [])[:5]

    elif card["card_type"] == "terrain":
        card["mana_cost"] = 0
        card["mana_production"] = data.get("mana_production", 1)

    elif card["card_type"] == "spell":
        card["mana_cost"] = _clamp(data.get("mana_cost", 1), 1, 5)

    # Parse and validate effects
    raw_effects = data.get("effects", [])
    validated_effects = []
    for eff in raw_effects[:3]:  # Max 3 effects per card
        if not isinstance(eff, dict):
            continue
        effect_type = eff.get("type", "")
        trigger = eff.get("trigger", "on_play")
        params = eff.get("params", {})

        if effect_type not in EFFECT_TYPES:
            continue
        if trigger not in TRIGGER_TYPES:
            trigger = "on_play"

        # Sanitize params - clamp numeric values
        sanitized = {}
        for k, v in params.items():
            if isinstance(v, (int, float)):
                sanitized[k] = _clamp(int(v), -10, 10)
            elif isinstance(v, str):
                sanitized[k] = v[:50]
            elif isinstance(v, dict):
                sanitized[k] = v  # For nested effect objects (gamble)
            elif isinstance(v, list):
                sanitized[k] = v[:5]
            else:
                sanitized[k] = str(v)[:50]

        validated_effects.append({
            "trigger": trigger,
            "type": effect_type,
            "params": sanitized,
        })

    card["effects"] = validated_effects if validated_effects else _default_effects(card["card_type"])
    return card


def _fallback_effects(card: dict) -> dict:
    """Generate simple fallback effects when AI is unavailable."""
    import random

    card["effects_generated"] = True

    if card["card_type"] == "creature":
        attack = random.randint(1, 5)
        health = random.randint(1, 6)
        cost = max(1, (attack + health) // 3)
        card["attack"] = attack
        card["health"] = health
        card["max_health"] = health
        card["mana_cost"] = cost
        card["abilities"] = []
        card["effect_description"] = f"A {card['name']} appears on the battlefield!"
        card["effects"] = _default_effects("creature")

    elif card["card_type"] == "terrain":
        card["mana_cost"] = 0
        card["mana_production"] = 1
        card["effect_description"] = f"The land of {card['name']} provides mana."
        card["effects"] = []  # Basic terrains can have no effects

    elif card["card_type"] == "spell":
        cost = random.randint(1, 4)
        card["mana_cost"] = cost
        card["effect_description"] = f"The event of {card['name']} strikes!"
        card["effects"] = [{
            "trigger": "on_play",
            "type": "deal_damage",
            "params": {"target": "opponent", "amount": cost + 1},
        }]

    return card


def _default_effects(card_type: str) -> list[dict]:
    """Simple default effects by card type."""
    if card_type == "creature":
        return []  # Vanilla creature, just attack/health
    elif card_type == "spell":
        return [{"trigger": "on_play", "type": "deal_damage", "params": {"target": "opponent", "amount": 2}}]
    return []


def _clamp(value: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(max_val, value))
