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

# Detailed effect reference the AI actually sees in the prompt
EFFECT_REFERENCE = """
EFFECT REFERENCE (type -> params -> what it does):

DAMAGE & HEALING:
  deal_damage: {target, amount} - Deal N damage to opponent or a creature
  heal: {target, amount} - Heal player or creature by N
  damage_all_enemies: {amount} - Deal N damage to ALL enemy creatures
  damage_all: {amount} - Deal N damage to ALL creatures on both sides
  life_drain: {amount} - Deal N damage to opponent AND heal yourself by N

CARD MANIPULATION:
  draw_cards: {count} - Draw N cards from your deck
  opponent_discard: {count} - Force opponent to discard N random cards
  steal_card: {} - Steal a random card from opponent's hand into yours
  swap_hands: {} - Swap your entire hand with opponent's hand
  resurrect: {} - Return a random creature from your graveyard to hand

CREATURE STATS:
  buff_attack: {target, amount} - Give +N attack to self or all friendly creatures
  buff_health: {target, amount} - Give +N health to self or all friendly creatures
  debuff_attack: {target, amount} - Give -N attack to target or all enemies
  debuff_health: {target, amount} - Give -N health to target or all enemies
  swap_stats: {target} - Swap a creature's attack and health values
  set_attack: {target, amount} - Set a creature's attack to exactly N
  set_health: {target, amount} - Set a creature's health to exactly N

BOARD CONTROL:
  destroy_creature: {target} - Instantly destroy a creature (target/random_enemy/weakest_enemy)
  destroy_terrain: {} - Destroy one of opponent's terrains (random)
  bounce: {target} - Return a creature to its owner's hand (target/random_enemy)
  freeze: {target, turns} - Freeze creature(s) so they can't attack for N turns
  shield: {target, amount} - Give N shield points that absorb damage before health
  taunt: {target} - This creature must be attacked before others

MANA:
  gain_mana: {amount} - Gain N bonus mana this turn
  drain_mana: {amount} - Opponent loses N mana
  untap_terrains: {count} - Untap N of your terrains so you can tap them again

CHAOS:
  random_effect: {} - Trigger a completely random effect (anything can happen!)
  cascade: {} - Reveal top card of deck, play it free if its cost <= this card's cost
  mutate: {target} - Randomize a creature's attack and health to new random values
  time_warp: {} - Take an EXTRA TURN after this one (very powerful, use rarely)
  mirror: {} - Copy whatever effect your opponent played last
  gamble: {win_effect, lose_effect} - 50/50 coin flip: win_effect or lose_effect happens
  chain_lightning: {amount, bounces} - Deal N damage, then bounce to N random targets
  summon_token: {attack, health, name} - Create a creature token with given stats and name

TERRAIN BONUSES:
  extra_mana: {} - This terrain produces 2 mana instead of 1
  heal_on_tap: {amount} - Heal player by N when this terrain is tapped
  damage_on_tap: {amount} - Deal N damage to opponent when this terrain is tapped

TARGET VALUES: "self", "opponent", "target" (player chooses), "random_enemy", "all_friendly", "all_enemies", "weakest_enemy", "strongest_enemy"
"""

# Effects that spells are NOT allowed to use (to force variety)
SPELL_BANNED_EFFECTS = {"deal_damage", "damage_all", "damage_all_enemies"}


SYSTEM_PROMPT = """You are the card effect designer for WikiBattle, a chaotic Wikipedia-powered trading card game.
You generate card effects based on real Wikipedia articles. Effects should be THEMATIC and FUN - connect the effect to what the article is about.

RULES:
- Go WILD with effects. Chaos is encouraged. Fun > Balance.
- BUT: No auto-win cards. No "opponent loses the game" or "deal 30 damage" effects.
- Creature attack should be 1-7, health should be 1-8. USE THE FULL RANGE! Not every creature is 3/5. A tiny bug might be 1/1, a god of war might be 7/6. Match the stats to the article.
- Creature mana cost should be 1-6 (roughly proportional to power level = attack + health + effect strength)
- Spell mana cost should be 1-5
- Effects should feel thematic - a volcano terrain should do fire damage, a scientist creature should have smart effects, a thief should steal cards, etc.
- Each card should have 1-3 effects, each with a trigger
- Be creative with the effect names and descriptions! The description should be a fun flavor text.
- Terrains always produce 1 mana base. Their effects are EXTRA bonuses (on_tap, passive, on_play, etc.)
- IMPORTANT: Use the FULL variety of effect types! Every card you generate should use DIFFERENT effect types. Do NOT fall into patterns.
- IMPORTANT: Vary your stats! Creatures should have widely different attack/health/cost values. Weak things should be cheap, strong things expensive.

You MUST respond with valid JSON only. No markdown, no explanation, just the JSON object."""


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

    type_instructions = ""
    if card_type == "creature":
        # Suggest a random stat range to break AI stat-clustering patterns
        atk_hint = _rng.randint(1, 7)
        hp_hint = _rng.randint(1, 8)
        cost_hint = max(1, min(6, (atk_hint + hp_hint) // 3))

        type_instructions = f"""For this CREATURE card, provide:
- "attack": integer 1-7 (SUGGESTION for this card: ~{atk_hint}, but adjust based on the subject!)
- "health": integer 1-8 (SUGGESTION for this card: ~{hp_hint}, but adjust based on the subject!)
  Stat examples: insect=1/1, child=1/2, scholar=2/3, soldier=4/4, knight=5/5, dragon=6/7, war god=7/8
  Low-stat creatures should have stronger effects. High-stat creatures can have weaker or no effects.
- "mana_cost": integer 1-6 (SUGGESTION: ~{cost_hint}. Proportional to total power: attack + health + effect strength)
- "abilities": list of 0-2 keyword strings from: ["flying", "shield", "taunt", "stealth", "lifesteal", "deathtouch", "haste", "ward"]
  Most creatures should have 0-1 abilities. Do NOT always pick "shield"! Match to the subject.
- "effect_description": flavorful description of what this creature does (1-2 sentences)
- "effects": list of effect objects (1-3 effects)

Each effect object has:
- "trigger": one of [on_play, on_death, on_attack, on_damaged, on_turn_start, on_turn_end, on_enemy_play, passive]
- "type": the effect type string
- "params": object with parameters for that effect type

VARIETY IS KEY: Don't just use draw_cards and buff effects. Consider deal_damage, freeze, destroy_creature, summon_token, steal_card, life_drain, mutate, gamble, chain_lightning, etc."""

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
Many boring terrains can have 0 effects - just producing mana is fine.
But interesting/famous places should have fun bonuses! Consider:
- extra_mana (powerful places produce more), heal_on_tap, damage_on_tap
- buff_attack/buff_health (passive auras), freeze, shield
- summon_token (the place spawns defenders), gain_mana, drain_mana
- deal_damage on_play (entering the battlefield has impact)
DO NOT default to draw_cards for everything! Match the effect to the place."""

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
IMPORTANT: Do NOT just use draw_cards + bounce + opponent_discard on every spell! That's boring!
Instead, pick effects thematic to this specific event. Consider ALL of these:
- freeze, destroy_creature, steal_card, swap_hands (disruption)
- chain_lightning, life_drain (damage alternatives)
- cascade, gamble, random_effect, mirror (chaos)
- mutate, swap_stats, set_attack, set_health (stat manipulation)
- summon_token (create creatures from the event)
- shield, buff_attack, buff_health (support)
- time_warp, resurrect, untap_terrains (powerful plays)
- gain_mana, drain_mana, destroy_terrain (resource control)
Combine 2-3 DIFFERENT and THEMATIC effects for interesting combos!"""

    available_triggers = ", ".join(TRIGGER_TYPES)

    # For spells, note which effects are banned
    ban_notice = ""
    if card_type == "spell":
        banned = ", ".join(sorted(SPELL_BANNED_EFFECTS))
        ban_notice = f"\n\nBANNED EFFECTS FOR SPELLS (do NOT use these): {banned}\nUse creative alternatives instead!"

    return f"""Generate effects for this {card_type.upper()} card:

Name: {name}
Description: {extract}
Categories: {categories}

{type_instructions}

{EFFECT_REFERENCE}
Available triggers: {available_triggers}
{ban_notice}

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


def _default_effects(card_type: str) -> list[dict]:
    """Simple default effects by card type."""
    if card_type == "creature":
        return []  # Vanilla creature, just attack/health
    elif card_type == "spell":
        return [_random_spell_fallback_effect()]
    return []


def _clamp(value: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(max_val, value))
