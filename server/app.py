"""WikiBattle - Flask server.

Serves the game client and provides API endpoints for game actions.
Designed to run on PythonAnywhere (WSGI, no WebSockets).
"""

import os
import sys
import time
import logging
import threading
from flask import Flask, request, jsonify, send_from_directory

# Add server directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_engine import (
    create_game, add_player, initialize_decks, get_player_idx_by_token,
    get_game_state_for_player, play_card, tap_terrain, tap_all_terrains,
    attack, end_turn,
)
from ai_effects import generate_card_effects
from card_cache import list_all_cards, search_cards, get_card_count

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CLIENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'client')

app = Flask(__name__,
            static_folder=CLIENT_DIR,
            static_url_path='/static')

# In-memory game storage
games: dict[str, dict] = {}

# Lock for the games dict itself (adding/removing games)
games_lock = threading.Lock()

# Per-game locks to avoid blocking unrelated games during mutations
game_locks: dict[str, threading.Lock] = {}

# Rate limiting for game creation: IP -> list of creation timestamps
_create_timestamps: dict[str, list[float]] = {}
MAX_GAMES_PER_IP = 5       # max games per IP within the window
RATE_LIMIT_WINDOW = 600    # 10 minute window

# Cleanup interval (seconds)
GAME_EXPIRY = 3600  # 1 hour
CLEANUP_INTERVAL = 300  # 5 minutes
_last_cleanup = time.time()


def _maybe_cleanup():
    """Run cleanup if enough time has passed. Safe to call on every request."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    try:
        cleanup_expired_games()
    except Exception as e:
        logger.error(f"Request-based cleanup failed: {e}")


@app.before_request
def before_request_cleanup():
    """Fallback cleanup triggered by incoming requests.

    PythonAnywhere free tier may kill background threads, so this ensures
    expired games are still cleaned up as long as the app receives traffic.
    """
    _maybe_cleanup()


def _get_game_and_lock(game_id: str) -> tuple:
    """Get a game dict and its per-game lock. Returns (game, lock) or (None, None)."""
    with games_lock:
        game = games.get(game_id)
        if game is None:
            return None, None
        lock = game_locks.get(game_id)
        if lock is None:
            lock = threading.Lock()
            game_locks[game_id] = lock
        return game, lock


# --- Static file serving ---

@app.route('/')
def index():
    return send_from_directory(CLIENT_DIR, 'index.html')



# --- API Endpoints ---

@app.route('/api/create-game', methods=['POST'])
def api_create_game():
    """Create a new game and join as player 1."""
    # Rate limit game creation by IP
    ip = request.remote_addr or 'unknown'
    now = time.time()
    timestamps = _create_timestamps.get(ip, [])
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(timestamps) >= MAX_GAMES_PER_IP:
        return jsonify({'success': False, 'error': 'Too many games created. Try again later.'}), 429
    timestamps.append(now)
    _create_timestamps[ip] = timestamps

    data = request.get_json() or {}
    player_name = data.get('name', 'Player 1')
    
    # Deck configuration
    deck_config = data.get('deck_config')
    if deck_config:
        # Validate and sanitize deck config
        creatures = max(4, min(30, int(deck_config.get('creatures', 16))))
        terrains = max(4, min(30, int(deck_config.get('terrains', 16))))
        spells = max(2, min(20, int(deck_config.get('spells', 8))))
        deck_config = {'creatures': creatures, 'terrains': terrains, 'spells': spells}
    
    # Guaranteed cards (max 5)
    guaranteed_cards = data.get('guaranteed_cards', [])
    if isinstance(guaranteed_cards, list):
        guaranteed_cards = [str(c) for c in guaranteed_cards[:5]]
    else:
        guaranteed_cards = []

    game = create_game(deck_config=deck_config, guaranteed_cards=guaranteed_cards)
    player_info = add_player(game, player_name)

    with games_lock:
        games[game['game_id']] = game
        game_locks[game['game_id']] = threading.Lock()

    return jsonify({
        'success': True,
        'game_id': game['game_id'],
        'player_token': player_info['player_token'],
        'player_idx': player_info['player_idx'],
    })


@app.route('/api/join-game', methods=['POST'])
def api_join_game():
    """Join an existing game as player 2."""
    data = request.get_json() or {}
    game_id = data.get('game_id', '').strip()
    player_name = data.get('name', 'Player 2')

    game, lock = _get_game_and_lock(game_id)

    if not game:
        return jsonify({'success': False, 'error': 'Game not found'}), 404

    with lock:
        if game['status'] != 'waiting':
            return jsonify({'success': False, 'error': 'Game already started or full'}), 400

        try:
            player_info = add_player(game, player_name)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

        # Start deck generation in background
        if game['status'] == 'loading':
            thread = threading.Thread(target=_init_game_decks, args=(game, lock))
            thread.daemon = True
            thread.start()

    return jsonify({
        'success': True,
        'game_id': game_id,
        'player_token': player_info['player_token'],
        'player_idx': player_info['player_idx'],
    })


def _init_game_decks(game: dict, lock: threading.Lock):
    """Initialize decks in background thread."""
    try:
        # Deck generation involves Wikipedia API calls - don't hold lock for that
        initialize_decks(game)
    except Exception as e:
        logger.error(f"Failed to initialize decks: {e}")
        with lock:
            game['log'].append(f"Error generating decks: {e}")
            game['status'] = 'error'


@app.route('/api/game-state', methods=['GET'])
def api_game_state():
    """Get current game state (filtered for the requesting player)."""
    game_id = request.args.get('game_id', '')
    token = request.args.get('token', '')

    game, lock = _get_game_and_lock(game_id)

    if not game:
        return jsonify({'success': False, 'error': 'Game not found'}), 404

    with lock:
        player_idx = get_player_idx_by_token(game, token)
        if player_idx is None:
            return jsonify({'success': False, 'error': 'Invalid token'}), 403

        state = get_game_state_for_player(game, player_idx)
        return jsonify({'success': True, 'state': state})


@app.route('/api/action', methods=['POST'])
def api_action():
    """Execute a game action."""
    data = request.get_json() or {}
    game_id = data.get('game_id', '')
    token = data.get('token', '')
    action = data.get('action', '')

    game, lock = _get_game_and_lock(game_id)

    if not game:
        return jsonify({'success': False, 'error': 'Game not found'}), 404

    with lock:
        player_idx = get_player_idx_by_token(game, token)
        if player_idx is None:
            return jsonify({'success': False, 'error': 'Invalid token'}), 403

        try:
            if action == 'play_card':
                hand_idx = data.get('hand_idx', 0)
                target_idx = data.get('target_idx')
                result = play_card(game, player_idx, hand_idx, target_idx)

            elif action == 'tap_terrain':
                terrain_idx = data.get('terrain_idx', 0)
                result = tap_terrain(game, player_idx, terrain_idx)

            elif action == 'tap_all_terrains':
                result = tap_all_terrains(game, player_idx)

            elif action == 'attack':
                attacker_idx = data.get('attacker_idx', 0)
                target = data.get('target', 'player')  # "player" or "creature"
                target_idx = data.get('target_idx')
                result = attack(game, player_idx, attacker_idx, target, target_idx)

            elif action == 'end_turn':
                result = end_turn(game, player_idx)

            else:
                return jsonify({'success': False, 'error': f'Unknown action: {action}'}), 400

        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Action error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

    return jsonify(result)


@app.route('/api/generate-effect', methods=['POST'])
def api_generate_effect():
    """Generate effects for a specific card (called when drawn).

    This is called by the client when it sees a card without effects.
    The server generates effects and updates the card in-place.
    """
    data = request.get_json() or {}
    game_id = data.get('game_id', '')
    token = data.get('token', '')
    card_id = data.get('card_id', '')

    game, lock = _get_game_and_lock(game_id)

    if not game:
        return jsonify({'success': False, 'error': 'Game not found'}), 404

    with lock:
        player_idx = get_player_idx_by_token(game, token)
        if player_idx is None:
            return jsonify({'success': False, 'error': 'Invalid token'}), 403

        player = game['players'][player_idx]

        # Find the card in the player's hand
        card = None
        for c in player['hand']:
            if c['id'] == card_id:
                card = c
                break

        if not card:
            return jsonify({'success': False, 'error': 'Card not found in hand'}), 404

        if card.get('effects_generated'):
            return jsonify({'success': True, 'message': 'Effects already generated'})

    # Generate effects outside the lock (it calls external API)
    generate_card_effects(card)

    return jsonify({
        'success': True,
        'card': {
            'id': card['id'],
            'effect_description': card.get('effect_description', ''),
            'effects': card.get('effects', []),
            'mana_cost': card.get('mana_cost', 0),
            'attack': card.get('attack'),
            'health': card.get('health'),
            'abilities': card.get('abilities', []),
        }
    })


@app.route('/api/list-games', methods=['GET'])
def api_list_games():
    """List available games to join."""
    with games_lock:
        available = []
        for gid, game in games.items():
            if game['status'] == 'waiting':
                available.append({
                    'game_id': gid,
                    'host': game['players'][0]['name'] if game['players'] else '?',
                    'created_at': game.get('created_at', 0),
                })
    return jsonify({'success': True, 'games': available})


@app.route('/api/card-database', methods=['GET'])
def api_card_database():
    """Browse cards in the database.
    
    Query params:
        type: Optional filter by card type (creature, terrain, spell)
        search: Optional search query
        limit: Max results (default 100)
    """
    card_type = request.args.get('type', None)
    search_query = request.args.get('search', None)
    limit = min(int(request.args.get('limit', 100)), 500)
    
    if search_query:
        cards = search_cards(search_query, limit=limit)
    elif card_type:
        cards = list_all_cards(limit=limit, card_type=card_type)
    else:
        cards = list_all_cards(limit=limit)
    
    return jsonify({'success': True, 'cards': cards})


@app.route('/api/card-count', methods=['GET'])
def api_card_count():
    """Get count of cards in database by type."""
    counts = get_card_count()
    return jsonify({'success': True, 'counts': counts})


# --- Cleanup ---

def cleanup_expired_games():
    """Remove games that have been inactive for too long."""
    now = time.time()
    with games_lock:
        expired = [
            gid for gid, game in games.items()
            if now - game.get('last_activity', game.get('created_at', 0)) > GAME_EXPIRY
        ]
        for gid in expired:
            del games[gid]
            game_locks.pop(gid, None)
            logger.info(f"Cleaned up expired game: {gid}")


# Run cleanup periodically
def _cleanup_loop():
    while True:
        time.sleep(300)  # Every 5 minutes
        cleanup_expired_games()


def start_cleanup_thread():
    """Start the background cleanup thread. Call once on server startup."""
    cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    cleanup_thread.start()


if __name__ == '__main__':
    start_cleanup_thread()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
