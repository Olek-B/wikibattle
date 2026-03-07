/* WikiBattle - Client Game Logic */

// --- State ---
let gameId = null;
let playerToken = null;
let playerIdx = null;
let gameState = null;
let pollingInterval = null;
let selectedCard = null;       // {type: 'hand'|'field', idx: number}
let targetingMode = null;      // {action: string, ...params}
let lastLogLength = 0;

const API_BASE = '';  // Same origin
const POLL_MS = 2000;

// --- Lobby ---

async function createGame() {
    const name = document.getElementById('player-name').value.trim() || 'Player 1';
    const errEl = document.getElementById('lobby-error');
    errEl.classList.add('hidden');

    try {
        const resp = await fetch(`${API_BASE}/api/create-game`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name}),
        });
        const data = await resp.json();
        if (!data.success) throw new Error(data.error);

        gameId = data.game_id;
        playerToken = data.player_token;
        playerIdx = data.player_idx;

        // Show waiting room
        document.getElementById('waiting-room').classList.remove('hidden');
        document.getElementById('display-code').textContent = gameId;
        document.getElementById('btn-create').disabled = true;
        document.getElementById('btn-join').disabled = true;

        // Start polling for opponent
        startPolling();
    } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.remove('hidden');
    }
}

async function joinGame(code) {
    const name = document.getElementById('player-name').value.trim() || 'Player 2';
    const errEl = document.getElementById('lobby-error');
    errEl.classList.add('hidden');

    const gameCode = code || document.getElementById('game-code').value.trim();
    if (!gameCode) {
        errEl.textContent = 'Enter a game code';
        errEl.classList.remove('hidden');
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/api/join-game`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameCode, name}),
        });
        const data = await resp.json();
        if (!data.success) throw new Error(data.error);

        gameId = data.game_id;
        playerToken = data.player_token;
        playerIdx = data.player_idx;

        // Switch to loading screen
        showScreen('loading');
        startPolling();
    } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.remove('hidden');
    }
}

async function refreshGames() {
    try {
        const resp = await fetch(`${API_BASE}/api/list-games`);
        const data = await resp.json();
        const listEl = document.getElementById('games-list');

        if (!data.games || data.games.length === 0) {
            listEl.innerHTML = '<p class="muted">No games available</p>';
            return;
        }

        listEl.innerHTML = data.games.map(g => `
            <div class="game-listing" onclick="joinGame('${escapeHtml(g.game_id)}')">
                <span>${escapeHtml(g.host)}'s game</span>
                <span class="muted">${escapeHtml(g.game_id)}</span>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to list games:', e);
    }
}

// --- Polling ---

function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollGameState();
    pollingInterval = setInterval(pollGameState, POLL_MS);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

async function pollGameState() {
    if (!gameId || !playerToken) return;

    try {
        const resp = await fetch(
            `${API_BASE}/api/game-state?game_id=${gameId}&token=${playerToken}`
        );
        const data = await resp.json();
        if (!data.success) {
            console.error('Poll error:', data.error);
            return;
        }

        const prevStatus = gameState?.status;
        const prevTurn = gameState?.turn;
        gameState = data.state;

        // Play turn start sound when it's our turn
        if (gameState.status === 'active' && gameState.is_your_turn && 
            (!prevTurn || gameState.turn !== prevTurn)) {
            SoundManager.play('turn_start');
        }

        // Handle screen transitions
        if (gameState.status === 'waiting') {
            // Still in lobby, waiting for opponent
        } else if (gameState.status === 'loading') {
            showScreen('loading');
            updateLoadingLog();
        } else if (gameState.status === 'active') {
            if (prevStatus !== 'active') {
                showScreen('game');
            }
            renderGame();
        } else if (gameState.status === 'finished') {
            showScreen('gameover');
            renderGameOver();
            stopPolling();
        } else if (gameState.status === 'error') {
            showScreen('loading');
            updateLoadingLog();
        }
    } catch (e) {
        console.error('Poll failed:', e);
    }
}

// --- Screen Management ---

function showScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(name).classList.add('active');
}

// --- Loading Screen ---

function updateLoadingLog() {
    const logEl = document.getElementById('loading-log');
    if (gameState && gameState.log) {
        logEl.innerHTML = gameState.log.map(l => `<p>${escapeHtml(l)}</p>`).join('');
        logEl.scrollTop = logEl.scrollHeight;
    }
}

// --- Game Rendering ---

function renderGame() {
    if (!gameState) return;
    const gs = gameState;
    const isMyTurn = gs.is_your_turn;

    // Turn indicator
    document.getElementById('turn-indicator').textContent = `Turn ${gs.turn}`;
    document.getElementById('turn-indicator').style.color =
        isMyTurn ? 'var(--gold)' : 'var(--text-muted)';

    // Your info
    document.getElementById('your-name').textContent = gs.you.name + (isMyTurn ? ' (Your Turn)' : '');
    updateHpBar('your', gs.you.hp, gs.max_hp);
    document.getElementById('your-mana').textContent = `Mana: ${gs.you.mana}`;
    document.getElementById('your-deck-count').textContent = `Deck: ${gs.you.deck_count}`;

    // Opponent info
    if (gs.opponent) {
        document.getElementById('opp-name').textContent = gs.opponent.name + (!isMyTurn ? ' (Their Turn)' : '');
        updateHpBar('opp', gs.opponent.hp, gs.max_hp);
        document.getElementById('opp-mana').textContent = `Mana: ${gs.opponent.mana}`;
        document.getElementById('opp-deck-count').textContent = `Deck: ${gs.opponent.deck_count}`;
        document.getElementById('opp-hand-count').textContent = `Hand: ${gs.opponent.hand_count}`;
    }

    // Enable/disable action buttons
    document.getElementById('btn-end-turn').disabled = !isMyTurn;
    document.getElementById('btn-tap-all').disabled = !isMyTurn;

    // Render zones
    renderHand(gs.you.hand, isMyTurn);
    renderField('your-field', gs.you.field, true, isMyTurn);
    renderField('opp-field', gs.opponent ? gs.opponent.field : [], false, isMyTurn);
    renderTerrains('your-terrains', gs.you.terrains, true, isMyTurn);
    renderTerrains('opp-terrains', gs.opponent ? gs.opponent.terrains : [], false, false);

    // Show attack player button if we have a selected attacker AND opponent has no creatures
    const atkBtn = document.getElementById('btn-attack-player');
    const oppHasCreatures = gs.opponent && gs.opponent.field && gs.opponent.field.length > 0;
    if (selectedCard && selectedCard.type === 'field' && isMyTurn && !oppHasCreatures) {
        atkBtn.classList.remove('hidden');
    } else {
        atkBtn.classList.add('hidden');
    }

    // Update game log
    renderLog(gs.log, gs.log_total);

    // Request effect generation for cards in hand that don't have effects yet
    requestEffectGeneration(gs.you.hand);
}

function updateHpBar(prefix, hp, maxHp) {
    const pct = Math.max(0, Math.min(100, (hp / maxHp) * 100));
    document.getElementById(`${prefix}-hp-fill`).style.width = `${pct}%`;
    document.getElementById(`${prefix}-hp-text`).textContent = `${hp}/${maxHp}`;
}

function renderHand(hand, isMyTurn) {
    const container = document.getElementById('your-hand');
    container.innerHTML = '';

    hand.forEach((card, idx) => {
        const el = createCardElement(card, 'hand', idx, isMyTurn);
        container.appendChild(el);
    });
}

function renderField(containerId, creatures, isMine, isMyTurn) {
    const container = document.getElementById(containerId);
    // Keep zone label
    container.innerHTML = `<div class="zone-label">${isMine ? "Your" : "Opponent's"} Creatures</div>`;

    creatures.forEach((card, idx) => {
        const el = createCardElement(card, isMine ? 'field' : 'opp-field', idx, isMyTurn);
        el.classList.add('field-card');
        container.appendChild(el);
    });
}

function renderTerrains(containerId, terrains, isMine, isMyTurn) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="zone-label">${isMine ? "Your" : "Opponent's"} Terrains</div>`;

    terrains.forEach((card, idx) => {
        const el = createTerrainElement(card, isMine, idx, isMyTurn);
        container.appendChild(el);
    });
}

function createCardElement(card, location, idx, isMyTurn) {
    const el = document.createElement('div');
    el.className = `card ${card.card_type}`;

    if (card.hidden) {
        el.innerHTML = `<div class="card-name" style="padding:2rem 0.5rem; text-align:center; color:var(--text-muted);">?</div>`;
        return el;
    }

    // State classes
    if (card.is_tapped) el.classList.add('tapped');
    if (!card.effects_generated) el.classList.add('generating');

    if (location === 'hand' && !isMyTurn) {
        el.classList.add('disabled');
    }

    if (location === 'field' && card.can_attack && !card.is_tapped && isMyTurn) {
        el.classList.add('can-attack');
    }

    if (selectedCard && selectedCard.type === location && selectedCard.idx === idx) {
        el.classList.add('selected');
    }

    // Targeting mode: mark enemy creatures as targetable
    if (targetingMode && location === 'opp-field') {
        el.classList.add('targetable');
    }

    // Mana cost
    const manaHtml = card.card_type !== 'terrain'
        ? `<div class="card-mana">${card.mana_cost}</div>`
        : '';

    // Image
    const imgHtml = card.image
        ? `<img class="card-image" src="${card.image}" alt="" loading="lazy">`
        : `<div class="card-image"></div>`;

    // Stats (creatures only)
    let statsHtml = '';
    if (card.card_type === 'creature') {
        const shieldBadge = card.shield ? ` <span style="color:var(--mana-blue)">+${card.shield}</span>` : '';
        const tauntBadge = card.has_taunt ? ' <span style="color:var(--gold)" title="Taunt">T</span>' : '';
        const frozenBadge = card.frozen_turns ? ' <span style="color:#88ccff" title="Frozen">F</span>' : '';
        statsHtml = `<div class="card-stats">
            <span class="card-attack" title="Attack">${card.attack}${tauntBadge}</span>
            <span class="card-health" title="Health">${card.health}${shieldBadge}${frozenBadge}</span>
        </div>`;
    }

    // Effect text
    const effectText = card.effect_description
        ? `<div class="card-effect">${escapeHtml(card.effect_description)}</div>`
        : (card.effects_generated ? '' : '<div class="card-effect generating-text">Generating...</div>');

    // Mechanical effects breakdown
    const mechanicalHtml = (card.effects && card.effects.length)
        ? `<div class="card-effects-list">${formatEffectsForCard(card.effects)}</div>`
        : '';

    el.innerHTML = `
        ${manaHtml}
        ${imgHtml}
        <div class="card-name" title="${escapeHtml(card.name)}">${escapeHtml(card.name)}</div>
        <div class="card-type-badge ${card.card_type}">${card.card_type}</div>
        ${effectText}
        ${mechanicalHtml}
        ${statsHtml}
    `;

    // Click handlers
    el.addEventListener('click', (e) => {
        e.stopPropagation();
        handleCardClick(card, location, idx);
    });

    // Right-click for detail
    el.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        showCardDetail(card);
    });

    // Double-click for detail
    el.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        showCardDetail(card);
    });

    return el;
}

function createTerrainElement(card, isMine, idx, isMyTurn) {
    const el = document.createElement('div');
    el.className = `card terrain terrain-card`;

    if (card.is_tapped) el.classList.add('tapped');

    const imgHtml = card.image
        ? `<img class="card-image" src="${card.image}" alt="" loading="lazy">`
        : `<div class="card-image"></div>`;

    const manaText = card.mana_production > 1 ? `${card.mana_production}` : '1';

    // Terrain effect text
    const terrainEffectHtml = card.effect_description
        ? `<div class="card-effect">${escapeHtml(card.effect_description)}</div>`
        : '';
    const terrainMechanicalHtml = (card.effects && card.effects.length)
        ? `<div class="card-effects-list">${formatEffectsForCard(card.effects)}</div>`
        : '';

    el.innerHTML = `
        ${imgHtml}
        <div class="card-name" title="${escapeHtml(card.name)}">${escapeHtml(card.name)}</div>
        <div class="card-mana-prod" title="Mana production">${manaText}</div>
        ${terrainEffectHtml}
        ${terrainMechanicalHtml}
    `;

    // Click to tap for mana
    if (isMine && isMyTurn && !card.is_tapped) {
        el.style.cursor = 'pointer';
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            tapTerrain(idx);
        });
    }

    // Right-click/double-click for detail
    el.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        showCardDetail(card);
    });
    el.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        showCardDetail(card);
    });

    return el;
}

// --- Card Interactions ---

function handleCardClick(card, location, idx) {
    if (!gameState || !gameState.is_your_turn) return;

    // If we're in targeting mode, handle target selection
    if (targetingMode) {
        if (location === 'opp-field') {
            executeTargetedAction(idx);
        }
        return;
    }

    if (location === 'hand') {
        // Play card from hand
        const c = gameState.you.hand[idx];
        if (c.card_type === 'terrain') {
            // Terrains play directly
            SoundManager.play('terrain_play');
            doAction('play_card', {hand_idx: idx});
        } else if (c.card_type === 'spell') {
            // Check if spell needs a target
            if (needsTarget(c)) {
                SoundManager.play('spell_play');
                enterTargetingMode('play_card', {hand_idx: idx}, 'Select a target for ' + c.name);
            } else {
                SoundManager.play('spell_play');
                doAction('play_card', {hand_idx: idx});
            }
        } else if (c.card_type === 'creature') {
            // Check if creature has targetable on_play effects
            if (needsTarget(c)) {
                SoundManager.play('creature_play');
                enterTargetingMode('play_card', {hand_idx: idx}, 'Select a target for ' + c.name);
            } else {
                SoundManager.play('creature_play');
                doAction('play_card', {hand_idx: idx});
            }
        }
    } else if (location === 'field') {
        // Select/deselect creature for attack
        if (selectedCard && selectedCard.type === 'field' && selectedCard.idx === idx) {
            deselectCard();
        } else if (card.can_attack && !card.is_tapped) {
            SoundManager.play('select');
            selectCard('field', idx);
        }
    } else if (location === 'opp-field') {
        // If we have a selected attacker, attack this creature
        if (selectedCard && selectedCard.type === 'field') {
            doAction('attack', {
                attacker_idx: selectedCard.idx,
                target: 'creature',
                target_idx: idx,
            });
            deselectCard();
        }
    }
}

function needsTarget(card) {
    if (!card.effects) return false;
    return card.effects.some(e => {
        const params = e.params || {};
        return params.target === 'target';
    });
}

function selectCard(type, idx) {
    selectedCard = {type, idx};
    renderGame();
}

function deselectCard() {
    selectedCard = null;
    renderGame();
}

function enterTargetingMode(action, params, promptText) {
    targetingMode = {action, params};
    document.getElementById('target-overlay').classList.remove('hidden');
    document.getElementById('target-prompt-text').textContent = promptText;
    SoundManager.play('select');
    renderGame();
}

function cancelTargeting() {
    targetingMode = null;
    document.getElementById('target-overlay').classList.add('hidden');
    SoundManager.play('cancel');
    renderGame();
}

function executeTargetedAction(targetIdx) {
    if (!targetingMode) return;
    const params = {...targetingMode.params, target_idx: targetIdx};
    doAction(targetingMode.action, params);
    cancelTargeting();
}

// --- Game Actions ---

async function doAction(action, params = {}) {
    if (!gameId || !playerToken) return;

    try {
        const resp = await fetch(`${API_BASE}/api/action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                game_id: gameId,
                token: playerToken,
                action,
                ...params,
            }),
        });
        const data = await resp.json();
        if (!data.success) {
            showToast(data.error || 'Action failed');
            return;
        }
        // Immediately poll for updated state
        await pollGameState();
    } catch (e) {
        showToast('Connection error');
    }
}

function attackPlayer() {
    if (!selectedCard || selectedCard.type !== 'field') return;
    SoundManager.play('attack_player');
    doAction('attack', {
        attacker_idx: selectedCard.idx,
        target: 'player',
    });
    deselectCard();
}

async function tapTerrain(idx) {
    await doAction('tap_terrain', {terrain_idx: idx});
}

async function tapAllTerrains() {
    await doAction('tap_all_terrains', {});
}

async function endTurn() {
    selectedCard = null;
    SoundManager.play('turn_end');
    await doAction('end_turn', {});
}

// --- Effect Generation ---

async function requestEffectGeneration(hand) {
    for (const card of hand) {
        if (!card.effects_generated && !card._generating) {
            card._generating = true;
            try {
                const resp = await fetch(`${API_BASE}/api/generate-effect`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        game_id: gameId,
                        token: playerToken,
                        card_id: card.id,
                    }),
                });
                const data = await resp.json();
                if (data.success && data.card) {
                    // Update card locally
                    card.effects_generated = true;
                    card.effect_description = data.card.effect_description;
                    card.mana_cost = data.card.mana_cost ?? card.mana_cost;
                    card.attack = data.card.attack ?? card.attack;
                    card.health = data.card.health ?? card.health;
                    card.abilities = data.card.abilities ?? card.abilities;
                    card.effects = data.card.effects ?? card.effects;
                    renderGame();
                }
            } catch (e) {
                console.error('Effect generation failed:', e);
            }
            card._generating = false;
        }
    }
}

// --- Card Detail ---

function showCardDetail(card) {
    const overlay = document.getElementById('card-detail');
    const body = document.getElementById('card-detail-body');

    const imgHtml = card.image
        ? `<img class="detail-image" src="${card.image}" alt="${escapeHtml(card.name)}">`
        : '';

    let statsHtml = '';
    if (card.card_type === 'creature') {
        statsHtml = `<div class="detail-stats">
            <div class="detail-stat"><span class="card-attack">ATK: ${card.attack}</span></div>
            <div class="detail-stat"><span class="card-health">HP: ${card.health}/${card.max_health || card.health}</span></div>
            <div class="detail-stat">Cost: ${card.mana_cost}</div>
        </div>`;
        // Status effects
        const statuses = [];
        if (card.frozen_turns > 0) statuses.push(`<span style="color:#88ccff">Frozen (${card.frozen_turns} turn${card.frozen_turns > 1 ? 's' : ''} remaining)</span>`);
        if (card.has_taunt) statuses.push('<span style="color:var(--gold)">Taunt - must be attacked first</span>');
        if (card.shield > 0) statuses.push(`<span style="color:var(--mana-blue)">Shield - absorbs ${card.shield} damage</span>`);
        if (card.abilities && card.abilities.length) {
            statuses.push(`<span style="color:var(--gold)">${card.abilities.join(', ')}</span>`);
        }
        if (statuses.length) {
            statsHtml += `<div style="margin-top:0.3rem;font-size:0.8rem">${statuses.join('<br>')}</div>`;
        }
    } else if (card.card_type === 'terrain') {
        statsHtml = `<div class="detail-stats">
            <div class="detail-stat" style="color:var(--mana-blue)">Produces ${card.mana_production || 1} mana</div>
        </div>`;
        if (card.coordinates) {
            statsHtml += `<div style="margin-top:0.3rem;font-size:0.75rem;color:var(--text-muted)">
                Coords: ${card.coordinates.lat.toFixed(2)}, ${card.coordinates.lon.toFixed(2)}
            </div>`;
        }
    } else if (card.card_type === 'spell') {
        statsHtml = `<div class="detail-stats">
            <div class="detail-stat">Cost: ${card.mana_cost}</div>
        </div>`;
    }

    const effectHtml = card.effect_description
        ? `<div class="detail-effect">"${escapeHtml(card.effect_description)}"</div>`
        : '';

    const mechanicalDetailHtml = (card.effects && card.effects.length)
        ? `<div class="detail-effects-list">${formatEffectsForDetail(card.effects)}</div>`
        : '';

    const wikiLink = card.wiki_url
        ? `<a href="${card.wiki_url}" target="_blank" rel="noopener" class="detail-wiki-link">View on Wikipedia</a>`
        : '';

    body.innerHTML = `
        ${imgHtml}
        <h2 class="detail-title">${escapeHtml(card.name)}</h2>
        <span class="detail-type ${card.card_type}">${card.card_type}</span>
        ${statsHtml}
        ${effectHtml}
        ${mechanicalDetailHtml}
        <p class="detail-extract">${escapeHtml(card.extract || '')}</p>
        ${wikiLink}
    `;

    overlay.classList.remove('hidden');
}

function closeCardDetail(event) {
    document.getElementById('card-detail').classList.add('hidden');
}

// --- Game Log ---

function renderLog(log, logTotal) {
    if (!log) return;
    const content = document.getElementById('log-content');

    // Use total log length from server for change detection (not truncated array length)
    const totalLen = logTotal || log.length;
    
    // Play sounds for new log entries
    if (totalLen > lastLogLength && lastLogLength > 0) {
        const newEntries = log.slice(-(totalLen - lastLogLength));
        playSoundsForLogEntries(newEntries);
    }
    
    lastLogLength = totalLen;

    content.innerHTML = log.map(entry => {
        const cls = entry.includes('---') ? 'log-entry-highlight' : '';
        return `<p class="${cls}">${escapeHtml(entry)}</p>`;
    }).join('');

    content.scrollTop = content.scrollHeight;
}

function playSoundsForLogEntries(entries) {
    if (!SoundManager.enabled) return;
    
    // Delay sounds slightly to match visual update
    setTimeout(() => {
        entries.forEach(entry => {
            const lowerEntry = entry.toLowerCase();
            
            // Combat sounds
            if (lowerEntry.includes('attacks') && lowerEntry.includes('for')) {
                if (lowerEntry.includes('battle')) {
                    SoundManager.play('attack_creature');
                } else {
                    SoundManager.play('attack_player');
                }
            }
            
            // Effect sounds based on keywords
            if (lowerEntry.includes('destroyed') || lowerEntry.includes('fallen')) {
                SoundManager.play('creature_death');
            }
            
            if (lowerEntry.includes('heal')) {
                SoundManager.play('heal');
            }
            
            if (lowerEntry.includes('draw')) {
                SoundManager.play('draw_card');
            }
            
            if (lowerEntry.includes('discard')) {
                SoundManager.play('discard');
            }
            
            if (lowerEntry.includes('gain') || lowerEntry.includes('gains')) {
                SoundManager.play('buff');
            }
            
            if (lowerEntry.includes('reduces') || lowerEntry.includes('drain')) {
                SoundManager.play('debuff');
            }
            
            if (lowerEntry.includes('lightning')) {
                SoundManager.play('lightning');
            }
            
            if (lowerEntry.includes('fire') || lowerEntry.includes('flame') || lowerEntry.includes('burn')) {
                SoundManager.play('fire');
            }
            
            if (lowerEntry.includes('freeze') || lowerEntry.includes('ice')) {
                SoundManager.play('ice');
            }
            
            if (lowerEntry.includes('earth') || lowerEntry.includes('earthquake')) {
                SoundManager.play('earth');
            }
            
            if (lowerEntry.includes('arcane') || lowerEntry.includes('magic') || lowerEntry.includes('mystical')) {
                SoundManager.play('arcane');
            }
        });
    }, 50);
}

function toggleLog() {
    const logEl = document.getElementById('game-log');
    logEl.classList.toggle('collapsed');
    const toggle = document.getElementById('log-toggle');
    toggle.innerHTML = logEl.classList.contains('collapsed') ? '&#9650;' : '&#9660;';
}

// --- Game Over ---

function renderGameOver() {
    if (!gameState) return;
    const title = document.getElementById('gameover-title');
    const msg = document.getElementById('gameover-message');

    if (gameState.winner === null) {
        title.textContent = 'DRAW!';
        msg.textContent = 'Both players have fallen simultaneously!';
    } else if (gameState.winner === gameState.your_idx) {
        title.textContent = 'VICTORY!';
        msg.textContent = 'You have won the WikiBattle!';
        SoundManager.play('victory');
    } else {
        title.textContent = 'DEFEAT';
        msg.textContent = 'You have been defeated in WikiBattle.';
        SoundManager.play('defeat');
    }
}

function backToLobby() {
    gameId = null;
    playerToken = null;
    playerIdx = null;
    gameState = null;
    selectedCard = null;
    targetingMode = null;
    lastLogLength = 0;
    stopPolling();

    // Reset lobby
    document.getElementById('waiting-room').classList.add('hidden');
    document.getElementById('btn-create').disabled = false;
    document.getElementById('btn-join').disabled = false;
    document.getElementById('game-code').value = '';
    document.getElementById('lobby-error').classList.add('hidden');

    showScreen('lobby');
    refreshGames();
}

// --- Toast notifications ---

function showToast(message) {
    // Create a floating toast notification
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => toast.classList.add('show'));

    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// --- Utilities ---

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatEffectType(type) {
    // Convert snake_case to readable: "deal_damage" -> "Deal Damage"
    return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatEffectParams(params) {
    if (!params) return '';
    const parts = [];
    if (params.amount != null) parts.push(`${params.amount}`);
    if (params.count != null) parts.push(`${params.count}`);
    if (params.target && params.target !== 'self') parts.push(`-> ${params.target.replace(/_/g, ' ')}`);
    if (params.turns) parts.push(`${params.turns} turns`);
    if (params.bounces) parts.push(`${params.bounces} bounces`);
    if (params.name) parts.push(`"${params.name}"`);
    return parts.length ? ` (${parts.join(', ')})` : '';
}

function formatTrigger(trigger) {
    const map = {
        on_play: 'Play',
        on_death: 'Death',
        on_attack: 'Attack',
        on_damaged: 'Damaged',
        on_turn_start: 'Turn Start',
        on_turn_end: 'Turn End',
        on_enemy_play: 'Enemy Play',
        passive: 'Passive',
        on_tap: 'Tap',
    };
    return map[trigger] || trigger;
}

function formatEffectsForCard(effects) {
    if (!effects || !effects.length) return '';
    return effects.map(e => {
        const trigger = formatTrigger(e.trigger);
        const type = formatEffectType(e.type);
        const params = formatEffectParams(e.params);
        return `<span class="effect-trigger">[${trigger}]</span> ${type}${params}`;
    }).join('<br>');
}

function formatEffectsForDetail(effects) {
    if (!effects || !effects.length) return '';
    return effects.map(e => {
        const trigger = formatTrigger(e.trigger);
        const type = formatEffectType(e.type);
        const params = formatEffectParams(e.params);
        return `<div class="detail-effect-line"><span class="effect-trigger">[${trigger}]</span> ${type}${params}</div>`;
    }).join('');
}

// --- Init ---

// Sound toggle function
function toggleSound() {
    const btn = document.getElementById('btn-sound-toggle');
    const enabled = SoundManager.toggle();
    btn.textContent = enabled ? '🔊' : '🔇';
    btn.classList.toggle('muted', !enabled);
    
    // Initialize audio on first toggle
    if (enabled && !SoundManager.audioContext) {
        SoundManager.init();
    }
    
    showToast(enabled ? 'Sound effects enabled' : 'Sound effects muted');
}

document.addEventListener('DOMContentLoaded', () => {
    refreshGames();
    
    // Initialize sound manager on first interaction
    SoundManager.init();

    // Click outside cards to deselect
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.card') && selectedCard) {
            deselectCard();
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Don't trigger shortcuts when typing in inputs
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        if (e.key === 'Escape') {
            if (targetingMode) cancelTargeting();
            if (selectedCard) deselectCard();
            closeCardDetail();
        }
        if (e.key === 'e' || e.key === 'E') {
            if (gameState && gameState.is_your_turn) endTurn();
        }
        if (e.key === 't' || e.key === 'T') {
            if (gameState && gameState.is_your_turn) tapAllTerrains();
        }
        if (e.key === 'm' || e.key === 'M') {
            toggleSound();
        }
    });
});
