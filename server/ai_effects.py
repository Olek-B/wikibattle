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

# Compact effect reference for the AI prompt
EFFECT_REFERENCE = (
    "EFFECTS (type | params | what it does):\n"
    "deal_damage | target,amount | damage opponent/creature\n"
    "heal | target,amount | heal player/creature\n"
    "damage_all_enemies | amount | damage ALL enemy creatures\n"
    "damage_all | amount | damage ALL creatures both sides\n"
    "life_drain | amount | damage opponent + heal self\n"
    "draw_cards | count | draw N cards\n"
    "opponent_discard | count | opponent discards N random cards\n"
    "steal_card | - | steal random card from opponent\n"
    "swap_hands | - | swap entire hands\n"
    "resurrect | - | return random creature from graveyard to hand\n"
    "buff_attack | target,amount | +N attack\n"
    "buff_health | target,amount | +N health\n"
    "debuff_attack | target,amount | -N attack to enemy\n"
    "debuff_health | target,amount | -N health to enemy\n"
    "swap_stats | target | swap attack and health\n"
    "set_attack | target,amount | set attack to N\n"
    "set_health | target,amount | set health to N\n"
    "destroy_creature | target | destroy (target/random_enemy/weakest_enemy)\n"
    "destroy_terrain | - | destroy random enemy terrain\n"
    "bounce | target | return creature to owner's hand\n"
    "freeze | target,turns | can't attack for N turns\n"
    "shield | target,amount | absorb N damage before health\n"
    "taunt | target | must be attacked first\n"
    "gain_mana | amount | bonus mana this turn\n"
    "drain_mana | amount | opponent loses N mana\n"
    "untap_terrains | count | untap N of your terrains\n"
    "random_effect | - | trigger a random effect\n"
    "cascade | - | play top deck card free if cost <= this\n"
    "mutate | target | randomize creature stats\n"
    "time_warp | - | extra turn (rare/powerful!)\n"
    "mirror | - | copy opponent's last effect\n"
    "gamble | win_effect,lose_effect | 50/50 coin flip\n"
    "chain_lightning | amount,bounces | damage bouncing to N random targets\n"
    "summon_token | attack,health,name | create a creature token\n"
    "extra_mana | - | this terrain produces 2 mana instead of 1\n"
    "heal_on_tap | amount | heal player when terrain tapped\n"
    "damage_on_tap | amount | damage opponent when terrain tapped\n"
    "Targets: self / opponent / target / random_enemy / all_friendly / all_enemies / weakest_enemy / strongest_enemy"
)

# Effects that spells are NOT allowed to use (to force variety)
SPELL_BANNED_EFFECTS = {"deal_damage", "damage_all", "damage_all_enemies"}


SYSTEM_PROMPT = (
    "You design card effects for WikiBattle, a chaotic Wikipedia TCG. "
    "Effects must be THEMATIC to the article and FUN. Chaos > balance, but no auto-win cards. "
    "Use the FULL variety of effect types - never fall into patterns. "
    "Respond with valid JSON only, no markdown."
)


def _build_prompt_for_card(card: dict) -> str:
    """Build the user prompt for effect generation."""
    import random as _rng

    card_type = card["card_type"]
    name = card["name"]
    extract = card.get("extract", "")
    categories = ", ".join(card.get("categories", [])[:10])

    # Truncate extract to first ~500 chars (2-3 sentences) to save tokens.
    # The AI only needs a brief summary to generate thematic effects.
    if len(extract) > 500:
        # Try to cut at a sentence boundary
        cut = extract[:500].rfind(". ")
        if cut > 200:
            extract = extract[:cut + 1]
        else:
            extract = extract[:500] + "..."

    has_image = bool(card.get("image"))

    type_instructions = ""
    if card_type == "creature":
        # Suggest random stats to break AI stat-clustering patterns
        atk_hint = _rng.randint(1, 7)
        hp_hint = _rng.randint(1, 8)
        cost_hint = max(1, min(6, (atk_hint + hp_hint) // 3))

        if has_image:
            stats_note = "This card has a visible image - it MUST have at least 1 effect, even with high stats."
        else:
            stats_note = "Low stats = stronger effects. High stats = weaker/no effects."

        type_instructions = (
            f"CREATURE - return JSON with:\n"
            f"attack: 1-7 (suggest ~{atk_hint}), health: 1-8 (suggest ~{hp_hint}), "
            f"mana_cost: 1-6 (suggest ~{cost_hint})\n"
            f"Stats should match the subject! insect=1/1, scholar=2/3, soldier=4/4, knight=5/5, dragon=6/7, war god=7/8\n"
            f"{stats_note}\n"
            f"abilities: 0-2 from [flying, shield, taunt, stealth, lifesteal, deathtouch, haste, ward] - match to subject\n"
            f"effect_description: 1-2 sentence flavor text\n"
            f"effects: 1-3 objects, each with trigger (on_play/on_death/on_attack/on_damaged/on_turn_start/on_turn_end/on_enemy_play/passive), type, params\n"
            f"Use varied effects! Not just draw_cards and buffs."
        )

    elif card_type == "terrain":
        if has_image:
            effects_note = (
                "effects: 1-2 BONUS effects (not base mana). This card has a visible image so it MUST have at least 1 effect."
            )
        else:
            effects_note = (
                "effects: 0-2 BONUS effects (not base mana). Boring places can have 0 effects."
            )

        type_instructions = (
            "TERRAIN - return JSON with:\n"
            "mana_cost: 0, mana_production: 1\n"
            "effect_description: 1-2 sentence flavor text\n"
            f"{effects_note} Each has trigger (on_play/on_tap/on_turn_start/on_turn_end/passive/on_enemy_play), type, params\n"
            "Match effects to the place! NOT just draw_cards. Consider: extra_mana, heal_on_tap, damage_on_tap, buff auras, freeze, summon_token, drain_mana."
        )

    elif card_type == "spell":
        banned = ", ".join(sorted(SPELL_BANNED_EFFECTS))
        type_instructions = (
            "SPELL - return JSON with:\n"
            "mana_cost: 1-5, effect_description: 1-2 sentence flavor text\n"
            "effects: 1-3 objects, all with trigger: on_play, plus type and params\n"
            f"BANNED: {banned} - use creative alternatives!\n"
            "NOT just draw_cards+bounce+opponent_discard every time! Use the full variety:\n"
            "freeze, destroy_creature, steal_card, swap_hands, chain_lightning, life_drain,\n"
            "cascade, gamble, mutate, summon_token, shield, time_warp, resurrect, mirror, etc."
        )

    return (
        f"{card_type.upper()}: {name}\n"
        f"{extract}\n"
        f"Categories: {categories}\n\n"
        f"{type_instructions}\n\n"
        f"{EFFECT_REFERENCE}"
    )


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
        # Enforce spell bans
        if card["card_type"] == "spell" and effect_type in SPELL_BANNED_EFFECTS:
            logger.info(f"Filtered banned spell effect '{effect_type}' from '{card.get('name', '?')}'")
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

    if validated_effects:
        card["effects"] = validated_effects
    else:
        card["effects"] = _default_effects(card["card_type"], has_image=bool(card.get("image")))
    return card


def _fallback_effects(card: dict) -> dict:
    """Generate simple fallback effects when AI is unavailable."""
    import random

    card["effects_generated"] = True
    has_image = bool(card.get("image"))

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
        card["effects"] = _default_effects("creature", has_image=has_image)

    elif card["card_type"] == "terrain":
        card["mana_cost"] = 0
        card["mana_production"] = 1
        card["effect_description"] = f"The land of {card['name']} provides mana."
        card["effects"] = _default_effects("terrain", has_image=has_image)

    elif card["card_type"] == "spell":
        cost = random.randint(1, 4)
        card["mana_cost"] = cost
        card["effect_description"] = f"The event of {card['name']} strikes!"
        card["effects"] = [_random_spell_fallback_effect()]

    return card


# Pool of interesting non-damage fallback effects for spells
_SPELL_FALLBACK_POOL = [
    {"trigger": "on_play", "type": "draw_cards", "params": {"count": 2}},
    {"trigger": "on_play", "type": "bounce", "params": {"target": "random_enemy"}},
    {"trigger": "on_play", "type": "freeze", "params": {"target": "all_enemies", "turns": 1}},
    {"trigger": "on_play", "type": "steal_card", "params": {}},
    {"trigger": "on_play", "type": "buff_attack", "params": {"target": "all_friendly", "amount": 1}},
    {"trigger": "on_play", "type": "shield", "params": {"target": "all_friendly", "amount": 2}},
    {"trigger": "on_play", "type": "destroy_creature", "params": {"target": "weakest_enemy"}},
    {"trigger": "on_play", "type": "heal", "params": {"target": "self", "amount": 4}},
    {"trigger": "on_play", "type": "opponent_discard", "params": {"count": 1}},
    {"trigger": "on_play", "type": "gain_mana", "params": {"amount": 3}},
    {"trigger": "on_play", "type": "resurrect", "params": {}},
    {"trigger": "on_play", "type": "summon_token", "params": {"attack": 2, "health": 2, "name": "Spirit"}},
    {"trigger": "on_play", "type": "life_drain", "params": {"amount": 2}},
    {"trigger": "on_play", "type": "mutate", "params": {"target": "random_enemy"}},
    {"trigger": "on_play", "type": "chain_lightning", "params": {"amount": 1, "bounces": 3}},
]


def _random_spell_fallback_effect() -> dict:
    """Pick a random non-damage spell effect from the fallback pool."""
    import random
    return random.choice(_SPELL_FALLBACK_POOL).copy()


# Pool of fallback effects for terrains that need at least one effect
_TERRAIN_FALLBACK_POOL = [
    {"trigger": "on_tap", "type": "heal_on_tap", "params": {"amount": 1}},
    {"trigger": "on_tap", "type": "damage_on_tap", "params": {"amount": 1}},
    {"trigger": "passive", "type": "extra_mana", "params": {}},
    {"trigger": "on_play", "type": "draw_cards", "params": {"count": 1}},
    {"trigger": "on_play", "type": "gain_mana", "params": {"amount": 1}},
]

# Pool of fallback effects for creatures that need at least one effect
_CREATURE_FALLBACK_POOL = [
    {"trigger": "on_play", "type": "draw_cards", "params": {"count": 1}},
    {"trigger": "on_death", "type": "deal_damage", "params": {"target": "opponent", "amount": 2}},
    {"trigger": "on_attack", "type": "buff_attack", "params": {"target": "self", "amount": 1}},
    {"trigger": "on_play", "type": "shield", "params": {"target": "self", "amount": 2}},
    {"trigger": "on_play", "type": "heal", "params": {"target": "self", "amount": 3}},
    {"trigger": "on_death", "type": "summon_token", "params": {"attack": 1, "health": 1, "name": "Spirit"}},
]


def _default_effects(card_type: str, has_image: bool = False) -> list[dict]:
    """Simple default effects by card type.

    Cards with images always get at least one effect.
    """
    import random
    if card_type == "creature":
        if has_image:
            return [random.choice(_CREATURE_FALLBACK_POOL).copy()]
        return []  # Vanilla creature, just attack/health
    elif card_type == "spell":
        return [_random_spell_fallback_effect()]
    elif card_type == "terrain":
        if has_image:
            return [random.choice(_TERRAIN_FALLBACK_POOL).copy()]
    return []


def _clamp(value: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(max_val, value))
