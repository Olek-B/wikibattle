"""Effect execution engine for WikiBattle.

Resolves card effects against the game state. Each effect type has a handler
function that mutates the game state and returns a log of what happened.
"""

import random
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


def resolve_effects(game_state: dict, player_idx: int, card: dict,
                    trigger: str, target_idx: Optional[int] = None) -> list[str]:
    """Resolve all effects on a card that match the given trigger.

    Args:
        game_state: The full game state dict
        player_idx: Index of the player who owns the card (0 or 1)
        card: The card whose effects we're resolving
        trigger: The trigger type to match
        target_idx: Index of target creature on opponent's field (if applicable)

    Returns:
        List of log messages describing what happened
    """
    logs = []
    opponent_idx = 1 - player_idx

    for effect in card.get("effects", []):
        if effect.get("trigger") != trigger:
            continue

        effect_type = effect.get("type", "")
        params = effect.get("params", {})

        handler = EFFECT_HANDLERS.get(effect_type)
        if handler:
            try:
                result = handler(game_state, player_idx, opponent_idx, card, params, target_idx)
                if result:
                    logs.extend(result if isinstance(result, list) else [result])
            except Exception as e:
                logger.error(f"Error resolving effect {effect_type}: {e}")
                logs.append(f"Effect {effect_type} fizzled!")

    return logs


def _get_player(gs: dict, idx: int) -> dict:
    return gs["players"][idx]


def _get_opponent(gs: dict, idx: int) -> dict:
    return gs["players"][1 - idx]


# --- Effect Handlers ---
# Each takes (game_state, player_idx, opponent_idx, card, params, target_idx)
# Returns a string or list of strings describing what happened


def _deal_damage(gs, pi, oi, card, params, ti):
    target = params.get("target", "opponent")
    amount = params.get("amount", 1)

    if target == "opponent":
        gs["players"][oi]["hp"] = max(0, gs["players"][oi]["hp"] - amount)
        return f"{card['name']} deals {amount} damage to opponent! (HP: {gs['players'][oi]['hp']})"
    elif target == "target" and ti is not None:
        field = gs["players"][oi]["field"]
        if 0 <= ti < len(field):
            field[ti]["health"] -= amount
            msg = f"{card['name']} deals {amount} damage to {field[ti]['name']}!"
            if field[ti]["health"] <= 0:
                msg += f" {field[ti]['name']} is destroyed!"
            return msg
    elif target == "random_enemy":
        field = gs["players"][oi]["field"]
        if field:
            victim = random.choice(field)
            victim["health"] -= amount
            msg = f"{card['name']} deals {amount} damage to {victim['name']}!"
            if victim["health"] <= 0:
                msg += f" {victim['name']} is destroyed!"
            return msg
    return None


def _heal(gs, pi, oi, card, params, ti):
    target = params.get("target", "self")
    amount = params.get("amount", 1)

    if target == "self":
        gs["players"][pi]["hp"] = min(30, gs["players"][pi]["hp"] + amount)
        return f"{card['name']} heals you for {amount}! (HP: {gs['players'][pi]['hp']})"
    elif target == "creature" and ti is not None:
        field = gs["players"][pi]["field"]
        if 0 <= ti < len(field):
            max_hp = field[ti].get("max_health", field[ti]["health"])
            field[ti]["health"] = min(max_hp, field[ti]["health"] + amount)
            return f"{card['name']} heals {field[ti]['name']} for {amount}!"
    return None


def _damage_all_enemies(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 1)
    logs = []
    for c in gs["players"][oi]["field"]:
        c["health"] -= amount
        msg = f"{card['name']} deals {amount} to {c['name']}!"
        if c["health"] <= 0:
            msg += " Destroyed!"
        logs.append(msg)
    return logs if logs else [f"{card['name']} hits an empty field!"]


def _damage_all(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 1)
    logs = [f"EARTHQUAKE! {card['name']} deals {amount} to ALL creatures!"]
    for p in [pi, oi]:
        for c in gs["players"][p]["field"]:
            c["health"] -= amount
            if c["health"] <= 0:
                logs.append(f"  {c['name']} is destroyed!")
    return logs


def _life_drain(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 1)
    gs["players"][oi]["hp"] = max(0, gs["players"][oi]["hp"] - amount)
    gs["players"][pi]["hp"] = min(30, gs["players"][pi]["hp"] + amount)
    return f"{card['name']} drains {amount} life! (You: {gs['players'][pi]['hp']}, Opp: {gs['players'][oi]['hp']})"


def _draw_cards(gs, pi, oi, card, params, ti):
    count = min(params.get("count", 1), 3)  # Cap at 3
    drawn = []
    for _ in range(count):
        if gs["players"][pi]["deck"]:
            c = gs["players"][pi]["deck"].pop(0)
            gs["players"][pi]["hand"].append(c)
            drawn.append(c["name"])
    if drawn:
        return f"{card['name']} draws {len(drawn)} card(s)!"
    return f"{card['name']} tries to draw but deck is empty!"


def _opponent_discard(gs, pi, oi, card, params, ti):
    count = min(params.get("count", 1), 2)  # Cap at 2
    discarded = []
    for _ in range(count):
        hand = gs["players"][oi]["hand"]
        if hand:
            idx = random.randint(0, len(hand) - 1)
            c = hand.pop(idx)
            gs["players"][oi]["graveyard"].append(c)
            discarded.append(c["name"])
    if discarded:
        return f"{card['name']} forces opponent to discard: {', '.join(discarded)}!"
    return None


def _steal_card(gs, pi, oi, card, params, ti):
    hand = gs["players"][oi]["hand"]
    if hand:
        idx = random.randint(0, len(hand) - 1)
        stolen = hand.pop(idx)
        gs["players"][pi]["hand"].append(stolen)
        return f"{card['name']} steals {stolen['name']} from opponent's hand!"
    return f"{card['name']} tries to steal but opponent's hand is empty!"


def _swap_hands(gs, pi, oi, card, params, ti):
    gs["players"][pi]["hand"], gs["players"][oi]["hand"] = \
        gs["players"][oi]["hand"], gs["players"][pi]["hand"]
    return f"{card['name']} SWAPS HANDS! Chaos ensues!"


def _resurrect(gs, pi, oi, card, params, ti):
    gy = gs["players"][pi]["graveyard"]
    creatures = [c for c in gy if c.get("card_type") == "creature"]
    if creatures:
        revived = random.choice(creatures)
        gy.remove(revived)
        revived["health"] = revived.get("max_health", 1)
        revived["can_attack"] = False
        gs["players"][pi]["hand"].append(revived)
        return f"{card['name']} resurrects {revived['name']} from the graveyard!"
    return f"{card['name']} finds no creatures to resurrect..."


def _buff_attack(gs, pi, oi, card, params, ti):
    target = params.get("target", "self")
    amount = params.get("amount", 1)

    if target == "self":
        card["attack"] = card.get("attack", 0) + amount
        return f"{card['name']} gains +{amount} attack! ({card['attack']})"
    elif target == "all_friendly":
        for c in gs["players"][pi]["field"]:
            if c.get("card_type") == "creature":
                c["attack"] = c.get("attack", 0) + amount
        return f"{card['name']} gives +{amount} attack to all friendly creatures!"
    return None


def _buff_health(gs, pi, oi, card, params, ti):
    target = params.get("target", "self")
    amount = params.get("amount", 1)

    if target == "self":
        card["health"] = card.get("health", 0) + amount
        card["max_health"] = card.get("max_health", 0) + amount
        return f"{card['name']} gains +{amount} health! ({card['health']})"
    elif target == "all_friendly":
        for c in gs["players"][pi]["field"]:
            if c.get("card_type") == "creature":
                c["health"] = c.get("health", 0) + amount
                c["max_health"] = c.get("max_health", 0) + amount
        return f"{card['name']} gives +{amount} health to all friendly creatures!"
    return None


def _debuff_attack(gs, pi, oi, card, params, ti):
    target = params.get("target", "target")
    amount = params.get("amount", 1)

    if target == "target" and ti is not None:
        field = gs["players"][oi]["field"]
        if 0 <= ti < len(field):
            field[ti]["attack"] = max(0, field[ti].get("attack", 0) - amount)
            return f"{card['name']} reduces {field[ti]['name']}'s attack by {amount}!"
    elif target == "all_enemies":
        for c in gs["players"][oi]["field"]:
            if c.get("card_type") == "creature":
                c["attack"] = max(0, c.get("attack", 0) - amount)
        return f"{card['name']} reduces ALL enemy creatures' attack by {amount}!"
    return None


def _debuff_health(gs, pi, oi, card, params, ti):
    target = params.get("target", "target")
    amount = params.get("amount", 1)

    if target == "target" and ti is not None:
        field = gs["players"][oi]["field"]
        if 0 <= ti < len(field):
            field[ti]["health"] -= amount
            msg = f"{card['name']} reduces {field[ti]['name']}'s health by {amount}!"
            if field[ti]["health"] <= 0:
                msg += f" {field[ti]['name']} is destroyed!"
            return msg
    elif target == "all_enemies":
        logs = []
        for c in gs["players"][oi]["field"]:
            if c.get("card_type") == "creature":
                c["health"] -= amount
                if c["health"] <= 0:
                    logs.append(f"  {c['name']} is destroyed!")
        return [f"{card['name']} saps {amount} health from all enemies!"] + logs
    return None


def _swap_stats(gs, pi, oi, card, params, ti):
    target = params.get("target", "self")
    if target == "self":
        card["attack"], card["health"] = card.get("health", 1), card.get("attack", 1)
        return f"{card['name']} swaps stats! Now {card['attack']}/{card['health']}"
    elif target == "target" and ti is not None:
        field = gs["players"][oi]["field"]
        if 0 <= ti < len(field):
            t = field[ti]
            t["attack"], t["health"] = t.get("health", 1), t.get("attack", 1)
            return f"{card['name']} swaps {t['name']}'s stats! Now {t['attack']}/{t['health']}"
    return None


def _set_attack(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 1)
    card["attack"] = amount
    return f"{card['name']}'s attack set to {amount}!"


def _set_health(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 1)
    card["health"] = amount
    card["max_health"] = max(card.get("max_health", 0), amount)
    return f"{card['name']}'s health set to {amount}!"


def _destroy_creature(gs, pi, oi, card, params, ti):
    target = params.get("target", "target")
    field = gs["players"][oi]["field"]

    if target == "target" and ti is not None:
        if 0 <= ti < len(field):
            victim = field[ti]
            victim["health"] = 0
            return f"{card['name']} DESTROYS {victim['name']}!"
    elif target == "random_enemy" and field:
        victim = random.choice(field)
        victim["health"] = 0
        return f"{card['name']} DESTROYS {victim['name']}!"
    elif target == "weakest_enemy" and field:
        victim = min(field, key=lambda c: c.get("health", 0))
        victim["health"] = 0
        return f"{card['name']} DESTROYS the weakest: {victim['name']}!"
    return f"{card['name']} finds no target to destroy!"


def _destroy_terrain(gs, pi, oi, card, params, ti):
    terrains = gs["players"][oi]["terrains"]
    if terrains:
        victim = random.choice(terrains)
        terrains.remove(victim)
        gs["players"][oi]["graveyard"].append(victim)
        return f"{card['name']} destroys terrain: {victim['name']}!"
    return f"{card['name']} finds no terrain to destroy!"


def _bounce(gs, pi, oi, card, params, ti):
    target = params.get("target", "target")
    field = gs["players"][oi]["field"]

    if target == "target" and ti is not None:
        if 0 <= ti < len(field):
            bounced = field.pop(ti)
            bounced["can_attack"] = False
            gs["players"][oi]["hand"].append(bounced)
            return f"{card['name']} bounces {bounced['name']} to opponent's hand!"
    elif target == "random_enemy" and field:
        idx = random.randint(0, len(field) - 1)
        bounced = field.pop(idx)
        bounced["can_attack"] = False
        gs["players"][oi]["hand"].append(bounced)
        return f"{card['name']} bounces {bounced['name']} to opponent's hand!"
    return None


def _freeze(gs, pi, oi, card, params, ti):
    target = params.get("target", "target")
    turns = params.get("turns", 1)

    if target == "target" and ti is not None:
        field = gs["players"][oi]["field"]
        if 0 <= ti < len(field):
            field[ti]["frozen_turns"] = turns
            field[ti]["can_attack"] = False
            return f"{card['name']} freezes {field[ti]['name']} for {turns} turn(s)!"
    elif target == "all_enemies":
        for c in gs["players"][oi]["field"]:
            c["frozen_turns"] = turns
            c["can_attack"] = False
        return f"{card['name']} freezes ALL enemy creatures for {turns} turn(s)!"
    return None


def _shield(gs, pi, oi, card, params, ti):
    target = params.get("target", "self")
    amount = params.get("amount", 1)

    if target == "self":
        card["shield"] = card.get("shield", 0) + amount
        return f"{card['name']} gains {amount} shield!"
    elif target == "all_friendly":
        for c in gs["players"][pi]["field"]:
            if c.get("card_type") == "creature":
                c["shield"] = c.get("shield", 0) + amount
        return f"{card['name']} gives {amount} shield to all friendly creatures!"
    return None


def _taunt(gs, pi, oi, card, params, ti):
    card["has_taunt"] = True
    return f"{card['name']} TAUNTS! Must be attacked first."


def _gain_mana(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 1)
    gs["players"][pi]["bonus_mana"] = gs["players"][pi].get("bonus_mana", 0) + amount
    return f"{card['name']} grants {amount} bonus mana!"


def _drain_mana(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 1)
    gs["players"][oi]["mana"] = max(0, gs["players"][oi].get("mana", 0) - amount)
    return f"{card['name']} drains {amount} mana from opponent!"


def _untap_terrains(gs, pi, oi, card, params, ti):
    count = params.get("count", 1)
    untapped = 0
    for t in gs["players"][pi]["terrains"]:
        if t.get("is_tapped") and untapped < count:
            t["is_tapped"] = False
            untapped += 1
    return f"{card['name']} untaps {untapped} terrain(s)!"


def _random_effect(gs, pi, oi, card, params, ti):
    # Pick a random simple effect and apply it
    random_effects = [
        ("deal_damage", {"target": "opponent", "amount": random.randint(1, 4)}),
        ("heal", {"target": "self", "amount": random.randint(1, 4)}),
        ("draw_cards", {"count": 1}),
        ("buff_attack", {"target": "self", "amount": random.randint(1, 3)}),
        ("damage_all_enemies", {"amount": random.randint(1, 3)}),
        ("gain_mana", {"amount": random.randint(1, 2)}),
    ]
    etype, eparams = random.choice(random_effects)
    handler = EFFECT_HANDLERS.get(etype)
    if handler:
        result = handler(gs, pi, oi, card, eparams, ti)
        prefix = f"RANDOM EFFECT from {card['name']}: "
        if isinstance(result, list):
            return [prefix + result[0]] + result[1:]
        return prefix + (result or "nothing happened!")
    return f"{card['name']}'s random effect fizzles!"


def _cascade(gs, pi, oi, card, params, ti):
    deck = gs["players"][pi]["deck"]
    if deck:
        top = deck[0]
        mana_cost = card.get("mana_cost", 0)
        if top.get("mana_cost", 99) <= mana_cost:
            deck.pop(0)
            # Add to hand for now - the game engine will handle playing it
            gs["players"][pi]["hand"].append(top)
            return f"CASCADE! {card['name']} reveals {top['name']} - added to hand for free!"
        else:
            return f"CASCADE from {card['name']} reveals {top['name']} but it's too expensive!"
    return f"{card['name']} cascades into an empty deck!"


def _mutate(gs, pi, oi, card, params, ti):
    target = params.get("target", "self")
    if target == "self":
        card["attack"] = random.randint(1, 7)
        card["health"] = random.randint(1, 8)
        card["max_health"] = card["health"]
        return f"{card['name']} MUTATES! Now {card['attack']}/{card['health']}!"
    elif target == "target" and ti is not None:
        field = gs["players"][oi]["field"]
        if 0 <= ti < len(field):
            t = field[ti]
            t["attack"] = random.randint(1, 7)
            t["health"] = random.randint(1, 8)
            t["max_health"] = t["health"]
            return f"{card['name']} MUTATES {t['name']}! Now {t['attack']}/{t['health']}!"
    return None


def _time_warp(gs, pi, oi, card, params, ti):
    gs["players"][pi]["extra_turns"] = gs["players"][pi].get("extra_turns", 0) + 1
    return f"TIME WARP! {card['name']} grants an extra turn!"


def _mirror(gs, pi, oi, card, params, ti):
    last_effects = gs.get("last_played_effects", {}).get(str(oi))
    if last_effects:
        logs = [f"{card['name']} MIRRORS opponent's last play!"]
        for eff in last_effects:
            handler = EFFECT_HANDLERS.get(eff.get("type"))
            if handler:
                result = handler(gs, pi, oi, card, eff.get("params", {}), ti)
                if result:
                    if isinstance(result, list):
                        logs.extend(result)
                    else:
                        logs.append(result)
        return logs
    return f"{card['name']} tries to mirror but nothing was played!"


def _gamble(gs, pi, oi, card, params, ti):
    if random.random() < 0.5:
        win_effect = params.get("win_effect", {"type": "draw_cards", "params": {"count": 2}})
        handler = EFFECT_HANDLERS.get(win_effect.get("type", ""))
        if handler:
            result = handler(gs, pi, oi, card, win_effect.get("params", {}), ti)
            prefix = f"GAMBLE WIN! {card['name']}: "
            if isinstance(result, list):
                return [prefix + result[0]] + result[1:]
            return prefix + (result or "you won... nothing?")
    else:
        lose_effect = params.get("lose_effect", {"type": "deal_damage", "params": {"target": "opponent", "amount": 2}})
        # Lose effects hurt the player who gambled
        handler = EFFECT_HANDLERS.get(lose_effect.get("type", ""))
        if handler:
            # Swap player/opponent for lose effect (hurts yourself)
            result = handler(gs, oi, pi, card, lose_effect.get("params", {}), ti)
            prefix = f"GAMBLE LOSS! {card['name']}: "
            if isinstance(result, list):
                return [prefix + result[0]] + result[1:]
            return prefix + (result or "bad luck!")
    return f"{card['name']} gambles and... nothing happens?"


def _chain_lightning(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 2)
    bounces = min(params.get("bounces", 3), 5)
    logs = [f"CHAIN LIGHTNING from {card['name']}!"]

    targets = list(gs["players"][oi]["field"])
    for i in range(bounces):
        if not targets:
            # Hit the player instead
            gs["players"][oi]["hp"] = max(0, gs["players"][oi]["hp"] - amount)
            logs.append(f"  Bolt hits opponent for {amount}! (HP: {gs['players'][oi]['hp']})")
            break
        victim = random.choice(targets)
        victim["health"] -= amount
        logs.append(f"  Bolt hits {victim['name']} for {amount}!")
        if victim["health"] <= 0:
            logs.append(f"  {victim['name']} is destroyed!")
            targets.remove(victim)
    return logs


def _summon_token(gs, pi, oi, card, params, ti):
    attack = params.get("attack", 1)
    health = params.get("health", 1)
    name = params.get("name", f"{card['name']}'s Token")
    token = {
        "id": f"token_{random.randint(1000,9999)}",
        "name": name,
        "card_type": "creature",
        "image": card.get("image"),
        "wiki_url": "",
        "extract": f"A token summoned by {card['name']}",
        "attack": attack,
        "health": health,
        "max_health": health,
        "mana_cost": 0,
        "abilities": [],
        "effects": [],
        "effects_generated": True,
        "effect_description": f"Summoned by {card['name']}",
        "can_attack": False,
        "is_tapped": False,
    }
    if len(gs["players"][pi]["field"]) < 7:  # Max 7 creatures on field
        gs["players"][pi]["field"].append(token)
        return f"{card['name']} summons {name} ({attack}/{health})!"
    return f"{card['name']} tries to summon but the field is full!"


def _extra_mana(gs, pi, oi, card, params, ti):
    card["mana_production"] = card.get("mana_production", 1) + 1
    return f"{card['name']} now produces {card['mana_production']} mana!"


def _heal_on_tap(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 1)
    gs["players"][pi]["hp"] = min(30, gs["players"][pi]["hp"] + amount)
    return f"{card['name']} heals you for {amount} when tapped! (HP: {gs['players'][pi]['hp']})"


def _damage_on_tap(gs, pi, oi, card, params, ti):
    amount = params.get("amount", 1)
    gs["players"][oi]["hp"] = max(0, gs["players"][oi]["hp"] - amount)
    return f"{card['name']} zaps opponent for {amount} when tapped! (Opp HP: {gs['players'][oi]['hp']})"


# Effect handler registry
EFFECT_HANDLERS: dict[str, Callable] = {
    "deal_damage": _deal_damage,
    "heal": _heal,
    "damage_all_enemies": _damage_all_enemies,
    "damage_all": _damage_all,
    "life_drain": _life_drain,
    "draw_cards": _draw_cards,
    "opponent_discard": _opponent_discard,
    "steal_card": _steal_card,
    "swap_hands": _swap_hands,
    "resurrect": _resurrect,
    "buff_attack": _buff_attack,
    "buff_health": _buff_health,
    "debuff_attack": _debuff_attack,
    "debuff_health": _debuff_health,
    "swap_stats": _swap_stats,
    "set_attack": _set_attack,
    "set_health": _set_health,
    "destroy_creature": _destroy_creature,
    "destroy_terrain": _destroy_terrain,
    "bounce": _bounce,
    "freeze": _freeze,
    "shield": _shield,
    "taunt": _taunt,
    "gain_mana": _gain_mana,
    "drain_mana": _drain_mana,
    "untap_terrains": _untap_terrains,
    "random_effect": _random_effect,
    "cascade": _cascade,
    "mutate": _mutate,
    "time_warp": _time_warp,
    "mirror": _mirror,
    "gamble": _gamble,
    "chain_lightning": _chain_lightning,
    "summon_token": _summon_token,
    "extra_mana": _extra_mana,
    "heal_on_tap": _heal_on_tap,
    "damage_on_tap": _damage_on_tap,
}


def cleanup_dead_creatures(game_state: dict):
    """Remove creatures with 0 or less health from the field.

    Triggers on_death effects before removal.
    """
    for pi in [0, 1]:
        field = game_state["players"][pi]["field"]
        dead = [c for c in field if c.get("health", 0) <= 0]
        for corpse in dead:
            # Trigger on_death effects
            death_logs = resolve_effects(game_state, pi, corpse, "on_death")
            game_state["log"].extend(death_logs)
            field.remove(corpse)
            game_state["players"][pi]["graveyard"].append(corpse)
            game_state["log"].append(f"{corpse['name']} has fallen!")
