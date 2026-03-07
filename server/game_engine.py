"""Game engine for WikiBattle.

Manages game state, turn flow, combat, mana (terrain-based), and win conditions.
"""

import uuid
import time
import logging
from typing import Optional
from card_generator import generate_deck, card_to_client_view
from effect_engine import resolve_effects, cleanup_dead_creatures
from ai_effects import generate_card_effects

logger = logging.getLogger(__name__)

# Game constants
STARTING_HP = 30
STARTING_HAND_SIZE = 5
MAX_HAND_SIZE = 10
MAX_FIELD_SIZE = 7
MAX_TERRAINS = 10
CARDS_PER_DRAW = 2
DECK_SIZE = 40


def create_game() -> dict:
    """Create a new game and return the game state.

    Returns dict with game_id and the initial state.
    The game waits for two players before starting.
    """
    game_id = str(uuid.uuid4())[:8]

    game = {
        "game_id": game_id,
        "status": "waiting",  # waiting -> loading -> active -> finished
        "created_at": time.time(),
        "last_activity": time.time(),
        "turn": 0,
        "current_player": 0,  # Index of player whose turn it is
        "phase": "waiting",   # waiting, main, combat, end
        "terrain_played_this_turn": False,
        "winner": None,
        "log": [],
        "last_played_effects": {},  # For mirror effect
        "players": [],
    }
    return game


def add_player(game: dict, player_name: str) -> dict:
    """Add a player to the game. Returns player info with token."""
    if len(game["players"]) >= 2:
        raise ValueError("Game is full")

    player_token = str(uuid.uuid4())
    player_idx = len(game["players"])

    player = {
        "name": player_name,
        "token": player_token,
        "idx": player_idx,
        "hp": STARTING_HP,
        "mana": 0,
        "bonus_mana": 0,
        "extra_turns": 0,
        "deck": [],
        "hand": [],
        "field": [],       # Creatures on the battlefield
        "terrains": [],    # Terrain cards in play
        "graveyard": [],
    }
    game["players"].append(player)

    if len(game["players"]) == 2:
        game["status"] = "loading"
        game["log"].append("Both players joined! Generating decks from Wikipedia...")

    return {
        "player_token": player_token,
        "player_idx": player_idx,
        "player_name": player_name,
    }


def initialize_decks(game: dict):
    """Generate decks for both players from Wikipedia.

    Called after both players join. This can be slow due to API calls.
    """
    game["log"].append("Fetching cards from Wikipedia...")

    for i, player in enumerate(game["players"]):
        deck = generate_deck(target_size=DECK_SIZE)
        player["deck"] = deck
        game["log"].append(f"Player {player['name']} received a {len(deck)}-card deck!")

    # Draw starting hands
    for player in game["players"]:
        for _ in range(STARTING_HAND_SIZE):
            if player["deck"]:
                card = player["deck"].pop(0)
                player["hand"].append(card)

    game["status"] = "active"
    game["turn"] = 1
    game["current_player"] = 0
    game["phase"] = "main"
    game["terrain_played_this_turn"] = False
    game["log"].append(f"Game started! {game['players'][0]['name']} goes first.")


def get_player_idx_by_token(game: dict, token: str) -> Optional[int]:
    """Find player index from their auth token."""
    for i, p in enumerate(game["players"]):
        if p["token"] == token:
            return i
    return None


def get_game_state_for_player(game: dict, player_idx: int) -> dict:
    """Build a client-safe view of the game state for a specific player.

    Hides opponent's hand cards and deck information.
    """
    opponent_idx = 1 - player_idx

    state = {
        "game_id": game["game_id"],
        "status": game["status"],
        "turn": game["turn"],
        "current_player": game["current_player"],
        "phase": game["phase"],
        "terrain_played_this_turn": game["terrain_played_this_turn"],
        "winner": game["winner"],
        "log": game["log"][-50:],  # Last 50 log entries
        "log_total": len(game["log"]),  # Total log size for change detection
        "your_idx": player_idx,
        "is_your_turn": game["current_player"] == player_idx,
        "max_hp": STARTING_HP,
    }

    # Your info (full visibility)
    me = game["players"][player_idx]
    state["you"] = {
        "name": me["name"],
        "hp": me["hp"],
        "mana": me["mana"],
        "bonus_mana": me.get("bonus_mana", 0),
        "deck_count": len(me["deck"]),
        "hand": [card_to_client_view(c, reveal=True) for c in me["hand"]],
        "field": [card_to_client_view(c, reveal=True) for c in me["field"]],
        "terrains": [card_to_client_view(c, reveal=True) for c in me["terrains"]],
        "graveyard_count": len(me["graveyard"]),
    }

    # Opponent info (hidden hand)
    if opponent_idx < len(game["players"]):
        opp = game["players"][opponent_idx]
        state["opponent"] = {
            "name": opp["name"],
            "hp": opp["hp"],
            "mana": opp["mana"],
            "deck_count": len(opp["deck"]),
            "hand_count": len(opp["hand"]),
            "field": [card_to_client_view(c, reveal=True) for c in opp["field"]],
            "terrains": [card_to_client_view(c, reveal=True) for c in opp["terrains"]],
            "graveyard_count": len(opp["graveyard"]),
        }
    else:
        state["opponent"] = None

    return state


# --- Game Actions ---


def play_card(game: dict, player_idx: int, hand_idx: int,
              target_idx: Optional[int] = None) -> dict:
    """Play a card from hand.

    For creatures/spells: spend mana, place on field, trigger on_play effects.
    For terrains: free, place in terrain zone, max 1 per turn.
    """
    _validate_turn(game, player_idx)
    player = game["players"][player_idx]

    if hand_idx < 0 or hand_idx >= len(player["hand"]):
        return {"success": False, "error": "Invalid card index"}

    card = player["hand"][hand_idx]

    # Generate effects if not already done
    if not card.get("effects_generated"):
        card = generate_card_effects(card)
        player["hand"][hand_idx] = card

    # Terrain: free to play, max 1 per turn
    if card["card_type"] == "terrain":
        if game["terrain_played_this_turn"]:
            return {"success": False, "error": "Already played a terrain this turn"}
        if len(player["terrains"]) >= MAX_TERRAINS:
            return {"success": False, "error": "Maximum terrains reached"}

        player["hand"].pop(hand_idx)
        card["is_tapped"] = False
        # Store base mana production for passive effect recalculation
        card["base_mana_production"] = card.get("mana_production", 1)
        player["terrains"].append(card)
        game["terrain_played_this_turn"] = True
        game["log"].append(f"{player['name']} plays terrain: {card['name']}")

        # Trigger on_play effects
        logs = resolve_effects(game, player_idx, card, "on_play", target_idx)
        game["log"].extend(logs)

    # Creature: pay mana, place on field
    elif card["card_type"] == "creature":
        mana_cost = card.get("mana_cost", 1)
        if player["mana"] < mana_cost:
            return {"success": False, "error": f"Not enough mana (need {mana_cost}, have {player['mana']})"}
        if len(player["field"]) >= MAX_FIELD_SIZE:
            return {"success": False, "error": "Battlefield is full"}

        player["mana"] -= mana_cost
        player["hand"].pop(hand_idx)
        card["can_attack"] = False  # Summoning sickness
        card["is_tapped"] = False
        # Store base stats for passive effect recalculation
        card["base_attack"] = card.get("attack", 0)
        card["base_health"] = card.get("health", 0)
        player["field"].append(card)
        game["log"].append(f"{player['name']} summons {card['name']} ({card.get('attack', '?')}/{card.get('health', '?')}) for {mana_cost} mana")

        # Store effects for mirror
        game["last_played_effects"][str(player_idx)] = card.get("effects", [])

        # Trigger on_play effects
        logs = resolve_effects(game, player_idx, card, "on_play", target_idx)
        game["log"].extend(logs)

        # Trigger on_enemy_play for opponent's cards
        opponent_idx = 1 - player_idx
        for opp_card in game["players"][opponent_idx]["field"]:
            opp_logs = resolve_effects(game, opponent_idx, opp_card, "on_enemy_play")
            game["log"].extend(opp_logs)

    # Spell: pay mana, trigger effects, go to graveyard
    elif card["card_type"] == "spell":
        mana_cost = card.get("mana_cost", 1)
        if player["mana"] < mana_cost:
            return {"success": False, "error": f"Not enough mana (need {mana_cost}, have {player['mana']})"}

        player["mana"] -= mana_cost
        player["hand"].pop(hand_idx)
        game["log"].append(f"{player['name']} casts {card['name']} for {mana_cost} mana!")

        # Store effects for mirror
        game["last_played_effects"][str(player_idx)] = card.get("effects", [])

        # Trigger on_play effects
        logs = resolve_effects(game, player_idx, card, "on_play", target_idx)
        game["log"].extend(logs)

        # Spells go to graveyard after resolving
        player["graveyard"].append(card)

        # Trigger on_enemy_play for opponent's cards
        opponent_idx = 1 - player_idx
        for opp_card in game["players"][opponent_idx]["field"]:
            opp_logs = resolve_effects(game, opponent_idx, opp_card, "on_enemy_play")
            game["log"].extend(opp_logs)

    # Clean up dead creatures
    cleanup_dead_creatures(game)

    # Check win condition
    _check_win(game)

    game["last_activity"] = time.time()
    return {"success": True}


def tap_terrain(game: dict, player_idx: int, terrain_idx: int) -> dict:
    """Tap a terrain to produce mana."""
    _validate_turn(game, player_idx)
    player = game["players"][player_idx]

    if terrain_idx < 0 or terrain_idx >= len(player["terrains"]):
        return {"success": False, "error": "Invalid terrain index"}

    terrain = player["terrains"][terrain_idx]
    if terrain.get("is_tapped"):
        return {"success": False, "error": "Terrain is already tapped"}

    terrain["is_tapped"] = True
    mana_gained = terrain.get("mana_production", 1)
    player["mana"] += mana_gained

    game["log"].append(f"{player['name']} taps {terrain['name']} for {mana_gained} mana")

    # Trigger on_tap effects
    logs = resolve_effects(game, player_idx, terrain, "on_tap")
    game["log"].extend(logs)

    # Clean up dead creatures (some terrains deal damage on tap)
    cleanup_dead_creatures(game)
    _check_win(game)

    game["last_activity"] = time.time()
    return {"success": True}


def tap_all_terrains(game: dict, player_idx: int) -> dict:
    """Tap all untapped terrains at once."""
    _validate_turn(game, player_idx)
    player = game["players"][player_idx]

    tapped_count = 0
    for terrain in player["terrains"]:
        if not terrain.get("is_tapped"):
            terrain["is_tapped"] = True
            mana_gained = terrain.get("mana_production", 1)
            player["mana"] += mana_gained
            tapped_count += 1

            # Trigger on_tap effects
            logs = resolve_effects(game, player_idx, terrain, "on_tap")
            game["log"].extend(logs)

    if tapped_count > 0:
        game["log"].append(f"{player['name']} taps {tapped_count} terrain(s) for mana (total: {player['mana']})")
    else:
        return {"success": False, "error": "No untapped terrains"}

    cleanup_dead_creatures(game)
    _check_win(game)

    game["last_activity"] = time.time()
    return {"success": True}


def attack(game: dict, player_idx: int, attacker_idx: int,
           target: str, target_idx: Optional[int] = None) -> dict:
    """Attack with a creature.

    target: "player" to attack opponent directly, or "creature" to attack a creature
    target_idx: index of target creature on opponent's field (if target=="creature")
    """
    _validate_turn(game, player_idx)
    player = game["players"][player_idx]
    opponent_idx = 1 - player_idx
    opponent = game["players"][opponent_idx]

    if attacker_idx < 0 or attacker_idx >= len(player["field"]):
        return {"success": False, "error": "Invalid attacker index"}

    attacker = player["field"][attacker_idx]

    if not attacker.get("can_attack"):
        return {"success": False, "error": f"{attacker['name']} can't attack (summoning sickness or frozen)"}

    if attacker.get("is_tapped"):
        return {"success": False, "error": f"{attacker['name']} is already tapped"}

    # Can only attack the player directly if opponent has no creatures
    if target == "player" and len(opponent["field"]) > 0:
        return {"success": False, "error": "Cannot attack player directly while they have creatures on the field"}

    # Check for taunt - must attack taunt creatures first
    if target == "creature" and target_idx is not None:
        taunt_creatures = [c for c in opponent["field"] if c.get("has_taunt")]
        if taunt_creatures:
            target_card = opponent["field"][target_idx] if 0 <= target_idx < len(opponent["field"]) else None
            if target_card and not target_card.get("has_taunt"):
                return {"success": False, "error": f"Must attack taunt creature first ({taunt_creatures[0]['name']})"}

    # Trigger on_attack effects
    attack_logs = resolve_effects(game, player_idx, attacker, "on_attack")
    game["log"].extend(attack_logs)

    attacker["is_tapped"] = True
    attacker_damage = attacker.get("attack", 1)

    if target == "player":
        # Direct attack to opponent
        # Apply shield if opponent has any shielded creatures... no, shield is on creatures
        opponent["hp"] = max(0, opponent["hp"] - attacker_damage)
        game["log"].append(f"{attacker['name']} attacks {opponent['name']} for {attacker_damage}! (HP: {opponent['hp']})")

    elif target == "creature":
        if target_idx is None or target_idx < 0 or target_idx >= len(opponent["field"]):
            return {"success": False, "error": "Invalid target creature index"}

        defender = opponent["field"][target_idx]
        defender_damage = defender.get("attack", 1)

        # Handle shields
        attacker_shield = attacker.get("shield", 0)
        defender_shield = defender.get("shield", 0)

        # Damage to defender
        remaining_damage = attacker_damage
        if defender_shield > 0:
            absorbed = min(defender_shield, remaining_damage)
            defender["shield"] -= absorbed
            remaining_damage -= absorbed
        defender["health"] -= remaining_damage

        # Damage to attacker (counter-attack)
        remaining_counter = defender_damage
        if attacker_shield > 0:
            absorbed = min(attacker_shield, remaining_counter)
            attacker["shield"] -= absorbed
            remaining_counter -= absorbed
        attacker["health"] -= remaining_counter

        game["log"].append(
            f"{attacker['name']} ({attacker.get('attack')}/{attacker.get('health')}) "
            f"battles {defender['name']} ({defender.get('attack')}/{defender.get('health')})"
        )

        # Trigger on_damaged effects
        if remaining_damage > 0:
            dmg_logs = resolve_effects(game, opponent_idx, defender, "on_damaged")
            game["log"].extend(dmg_logs)
        if remaining_counter > 0:
            dmg_logs = resolve_effects(game, player_idx, attacker, "on_damaged")
            game["log"].extend(dmg_logs)

    # Clean up dead creatures
    cleanup_dead_creatures(game)
    _check_win(game)

    game["last_activity"] = time.time()
    return {"success": True}


def end_turn(game: dict, player_idx: int) -> dict:
    """End the current player's turn."""
    _validate_turn(game, player_idx)
    player = game["players"][player_idx]

    # Trigger end-of-turn effects
    for card in player["field"]:
        logs = resolve_effects(game, player_idx, card, "on_turn_end")
        game["log"].extend(logs)
    for terrain in player["terrains"]:
        logs = resolve_effects(game, player_idx, terrain, "on_turn_end")
        game["log"].extend(logs)

    cleanup_dead_creatures(game)

    # Drain unused mana
    player["mana"] = 0
    player["bonus_mana"] = 0

    # Discard excess cards
    while len(player["hand"]) > MAX_HAND_SIZE:
        discarded = player["hand"].pop()
        player["graveyard"].append(discarded)
        game["log"].append(f"{player['name']} discards {discarded['name']} (hand too full)")

    # Check for extra turns
    if player.get("extra_turns", 0) > 0:
        player["extra_turns"] -= 1
        game["log"].append(f"EXTRA TURN for {player['name']}!")
        _start_turn(game, player_idx)
    else:
        # Switch to opponent
        next_player = 1 - player_idx
        game["turn"] += 1
        _start_turn(game, next_player)

    _check_win(game)
    game["last_activity"] = time.time()
    return {"success": True}


def _start_turn(game: dict, player_idx: int):
    """Begin a player's turn."""
    game["current_player"] = player_idx
    game["phase"] = "main"
    game["terrain_played_this_turn"] = False
    player = game["players"][player_idx]

    game["log"].append(f"--- Turn {game['turn']}: {player['name']}'s turn ---")

    # Untap all terrains and creatures
    for terrain in player["terrains"]:
        terrain["is_tapped"] = False
    for creature in player["field"]:
        creature["is_tapped"] = False
        # Remove summoning sickness (they've survived a turn cycle)
        creature["can_attack"] = True
        # Handle freeze
        if creature.get("frozen_turns", 0) > 0:
            creature["frozen_turns"] -= 1
            creature["can_attack"] = False
            if creature["frozen_turns"] <= 0:
                game["log"].append(f"{creature['name']} thaws out!")

    # Draw cards
    cards_drawn = 0
    for _ in range(CARDS_PER_DRAW):
        if player["deck"]:
            drawn = player["deck"].pop(0)
            player["hand"].append(drawn)
            cards_drawn += 1
    if cards_drawn > 0:
        game["log"].append(f"{player['name']} draws {cards_drawn} card{'s' if cards_drawn > 1 else ''}")

        # Effects will be generated when the client requests them via
        # /api/generate-effect, or as a fallback when the card is played.
        # We don't generate here to avoid holding the game lock during
        # a potentially slow Groq API call.
    else:
        # Fatigue damage if deck is empty
        fatigue = game.get(f"fatigue_{player_idx}", 1)
        player["hp"] -= fatigue
        game[f"fatigue_{player_idx}"] = fatigue + 1
        game["log"].append(f"{player['name']} takes {fatigue} fatigue damage! (empty deck)")

    # Add bonus mana
    player["mana"] += player.get("bonus_mana", 0)
    player["bonus_mana"] = 0

    # Trigger start-of-turn effects
    for card in player["field"]:
        logs = resolve_effects(game, player_idx, card, "on_turn_start")
        game["log"].extend(logs)
    for terrain in player["terrains"]:
        logs = resolve_effects(game, player_idx, terrain, "on_turn_start")
        game["log"].extend(logs)

    # Trigger passive effects (reapply each turn from base stats)
    for card in player["field"]:
        # Reset to base stats before reapplying passive buffs to prevent stacking
        if "base_attack" in card:
            card["attack"] = card["base_attack"]
        if "base_health" in card:
            damage_taken = max(0, card.get("max_health", card["base_health"]) - card.get("health", card["base_health"]))
            card["max_health"] = card["base_health"]
            card["health"] = card["base_health"] - damage_taken
        logs = resolve_effects(game, player_idx, card, "passive")
        game["log"].extend(logs)
    for terrain in player["terrains"]:
        logs = resolve_effects(game, player_idx, terrain, "passive")
        game["log"].extend(logs)

    cleanup_dead_creatures(game)


def _validate_turn(game: dict, player_idx: int):
    """Raise error if it's not this player's turn or game isn't active."""
    if game["status"] != "active":
        raise ValueError(f"Game is not active (status: {game['status']})")
    if game["current_player"] != player_idx:
        raise ValueError("Not your turn!")


def _check_win(game: dict):
    """Check if someone has won."""
    if game["status"] != "active":
        return

    p0_dead = game["players"][0]["hp"] <= 0
    p1_dead = game["players"][1]["hp"] <= 0

    if p0_dead and p1_dead:
        game["status"] = "finished"
        game["winner"] = None  # Draw
        game["log"].append("DRAW! Both players have fallen!")
    elif p0_dead:
        game["status"] = "finished"
        game["winner"] = 1
        game["log"].append(f"{game['players'][1]['name']} WINS!")
    elif p1_dead:
        game["status"] = "finished"
        game["winner"] = 0
        game["log"].append(f"{game['players'][0]['name']} WINS!")
