/* WikiBattle - Sound Effects System */

// --- Sound Manager ---

const SoundManager = {
    enabled: true,
    volume: 0.5,
    audioContext: null,
    
    // Sound categories
    categories: {
        // Card type sounds
        creature_play: null,
        spell_play: null,
        terrain_play: null,
        
        // Combat sounds
        attack_player: null,
        attack_creature: null,
        creature_death: null,
        
        // Effect sounds
        damage: null,
        heal: null,
        buff: null,
        debuff: null,
        draw_card: null,
        discard: null,
        
        // Special effects
        lightning: null,
        fire: null,
        ice: null,
        earth: null,
        arcane: null,
        
        // UI sounds
        select: null,
        cancel: null,
        turn_start: null,
        turn_end: null,
        error: null,
        victory: null,
        defeat: null,
    },
    
    // Initialize audio context
    init() {
        if (this.audioContext) return;
        
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.generateSounds();
        } catch (e) {
            console.warn('Web Audio API not supported:', e);
            this.enabled = false;
        }
    },
    
    // Generate synthesized sounds using Web Audio API
    generateSounds() {
        const ctx = this.audioContext;
        
        // Creature play - deep, powerful sound
        this.categories.creature_play = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(150, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(80, ctx.currentTime + 0.3);
            gain.gain.setValueAtTime(this.volume * 0.4, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
        };
        
        // Spell play - magical, ethereal sound
        this.categories.spell_play = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(400, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.2);
            gain.gain.setValueAtTime(this.volume * 0.3, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.4);
            
            // Add harmonics
            setTimeout(() => {
                const osc2 = ctx.createOscillator();
                const gain2 = ctx.createGain();
                osc2.type = 'triangle';
                osc2.frequency.setValueAtTime(600, ctx.currentTime);
                osc2.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.15);
                gain2.gain.setValueAtTime(this.volume * 0.2, ctx.currentTime);
                gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
                osc2.connect(gain2);
                gain2.connect(ctx.destination);
                osc2.start();
                osc2.stop(ctx.currentTime + 0.2);
            }, 50);
        };
        
        // Terrain play - earthy, solid sound
        this.categories.terrain_play = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'square';
            osc.frequency.setValueAtTime(100, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(50, ctx.currentTime + 0.4);
            gain.gain.setValueAtTime(this.volume * 0.3, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.4);
        };
        
        // Attack player - sharp, aggressive sound
        this.categories.attack_player = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(200, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(100, ctx.currentTime + 0.2);
            gain.gain.setValueAtTime(this.volume * 0.4, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
        };
        
        // Attack creature - impact sound
        this.categories.attack_creature = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'square';
            osc.frequency.setValueAtTime(180, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(60, ctx.currentTime + 0.15);
            gain.gain.setValueAtTime(this.volume * 0.35, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.15);
        };
        
        // Creature death - descending mournful sound
        this.categories.creature_death = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(300, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(50, ctx.currentTime + 0.5);
            gain.gain.setValueAtTime(this.volume * 0.3, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.5);
        };
        
        // Damage - sharp negative sound
        this.categories.damage = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(250, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(100, ctx.currentTime + 0.1);
            gain.gain.setValueAtTime(this.volume * 0.25, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.1);
        };
        
        // Heal - pleasant ascending sound
        this.categories.heal = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(400, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(600, ctx.currentTime + 0.2);
            gain.gain.setValueAtTime(this.volume * 0.25, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
        };
        
        // Buff - positive ascending chime
        this.categories.buff = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(300, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(500, ctx.currentTime + 0.15);
            gain.gain.setValueAtTime(this.volume * 0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.15);
        };
        
        // Debuff - negative descending sound
        this.categories.debuff = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(400, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(200, ctx.currentTime + 0.15);
            gain.gain.setValueAtTime(this.volume * 0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.15);
        };
        
        // Draw card - light positive sound
        this.categories.draw_card = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(600, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.1);
            gain.gain.setValueAtTime(this.volume * 0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.1);
        };
        
        // Discard - negative sound
        this.categories.discard = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(300, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(150, ctx.currentTime + 0.15);
            gain.gain.setValueAtTime(this.volume * 0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.15);
        };
        
        // Lightning - electric crackle
        this.categories.lightning = () => {
            // Create noise buffer for lightning effect
            const bufferSize = ctx.sampleRate * 0.3;
            const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
            const data = buffer.getChannelData(0);
            for (let i = 0; i < bufferSize; i++) {
                data[i] = Math.random() * 2 - 1;
            }
            
            const noise = ctx.createBufferSource();
            noise.buffer = buffer;
            
            const filter = ctx.createBiquadFilter();
            filter.type = 'highpass';
            filter.frequency.value = 1000;
            
            const gain = ctx.createGain();
            gain.gain.setValueAtTime(this.volume * 0.3, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
            
            noise.connect(filter);
            filter.connect(gain);
            gain.connect(ctx.destination);
            noise.start();
        };
        
        // Fire - warm rumbling sound
        this.categories.fire = () => {
            const bufferSize = ctx.sampleRate * 0.4;
            const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
            const data = buffer.getChannelData(0);
            for (let i = 0; i < bufferSize; i++) {
                data[i] = Math.random() * 2 - 1;
            }
            
            const noise = ctx.createBufferSource();
            noise.buffer = buffer;
            
            const filter = ctx.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.value = 400;
            
            const gain = ctx.createGain();
            gain.gain.setValueAtTime(this.volume * 0.25, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
            
            noise.connect(filter);
            filter.connect(gain);
            gain.connect(ctx.destination);
            noise.start();
        };
        
        // Ice - crystalline tinkle
        this.categories.ice = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(1200, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.3);
            gain.gain.setValueAtTime(this.volume * 0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
        };
        
        // Earth - deep rumble
        this.categories.earth = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'square';
            osc.frequency.setValueAtTime(80, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(40, ctx.currentTime + 0.4);
            gain.gain.setValueAtTime(this.volume * 0.3, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.4);
        };
        
        // Arcane - mystical shimmer
        this.categories.arcane = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(500, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1000, ctx.currentTime + 0.3);
            gain.gain.setValueAtTime(this.volume * 0.25, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
            
            // Add vibrato
            const lfo = ctx.createOscillator();
            const lfoGain = ctx.createGain();
            lfo.frequency.value = 8;
            lfoGain.gain.value = 50;
            lfo.connect(lfoGain);
            lfoGain.connect(osc.frequency);
            lfo.start();
            lfo.stop(ctx.currentTime + 0.3);
        };
        
        // Select - light click
        this.categories.select = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(800, ctx.currentTime);
            gain.gain.setValueAtTime(this.volume * 0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.05);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.05);
        };
        
        // Cancel - soft negative sound
        this.categories.cancel = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(400, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(300, ctx.currentTime + 0.1);
            gain.gain.setValueAtTime(this.volume * 0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.1);
        };
        
        // Turn start - fanfare
        this.categories.turn_start = () => {
            const notes = [440, 554, 659]; // A major arpeggio
            notes.forEach((freq, i) => {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'triangle';
                osc.frequency.value = freq;
                const startTime = ctx.currentTime + i * 0.1;
                gain.gain.setValueAtTime(this.volume * 0.2, startTime);
                gain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.2);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(startTime);
                osc.stop(startTime + 0.2);
            });
        };
        
        // Turn end - descending sound
        this.categories.turn_end = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(500, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(250, ctx.currentTime + 0.2);
            gain.gain.setValueAtTime(this.volume * 0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
        };
        
        // Error - harsh buzz
        this.categories.error = () => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(150, ctx.currentTime);
            osc.frequency.setValueAtTime(120, ctx.currentTime + 0.1);
            gain.gain.setValueAtTime(this.volume * 0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
        };
        
        // Victory - triumphant fanfare
        this.categories.victory = () => {
            const notes = [523, 659, 784, 1047]; // C major arpeggio
            notes.forEach((freq, i) => {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'triangle';
                osc.frequency.value = freq;
                const startTime = ctx.currentTime + i * 0.12;
                gain.gain.setValueAtTime(this.volume * 0.3, startTime);
                gain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.4);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(startTime);
                osc.stop(startTime + 0.4);
            });
        };
        
        // Defeat - somber descending notes
        this.categories.defeat = () => {
            const notes = [392, 349, 311, 261]; // Descending minor
            notes.forEach((freq, i) => {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'sine';
                osc.frequency.value = freq;
                const startTime = ctx.currentTime + i * 0.2;
                gain.gain.setValueAtTime(this.volume * 0.3, startTime);
                gain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.5);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(startTime);
                osc.stop(startTime + 0.5);
            });
        };
    },
    
    // Play a sound by category
    play(category) {
        if (!this.enabled || !this.audioContext) return;
        
        // Resume audio context if suspended (browser autoplay policy)
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }
        
        const sound = this.categories[category];
        if (sound && typeof sound === 'function') {
            try {
                sound();
            } catch (e) {
                console.warn(`Failed to play sound: ${category}`, e);
            }
        }
    },
    
    // Play sound based on effect type
    playForEffect(effectType) {
        if (!this.enabled) return;
        
        const effectSoundMap = {
            // Damage effects
            'deal_damage': 'damage',
            'damage_all_enemies': 'lightning',
            'damage_all': 'earth',
            'life_drain': 'arcane',
            'chain_lightning': 'lightning',
            
            // Healing effects
            'heal': 'heal',
            'heal_on_tap': 'heal',
            
            // Buff effects
            'buff_attack': 'buff',
            'buff_health': 'buff',
            'shield': 'ice',
            'taunt': 'earth',
            'gain_mana': 'arcane',
            'extra_mana': 'arcane',
            
            // Debuff effects
            'debuff_attack': 'debuff',
            'debuff_health': 'debuff',
            'drain_mana': 'arcane',
            'freeze': 'ice',
            
            // Card manipulation
            'draw_cards': 'draw_card',
            'opponent_discard': 'discard',
            'steal_card': 'arcane',
            'swap_hands': 'arcane',
            'resurrect': 'arcane',
            'bounce': 'ice',
            'cascade': 'arcane',
            
            // Special effects
            'destroy_creature': 'fire',
            'destroy_terrain': 'earth',
            'swap_stats': 'arcane',
            'set_attack': 'buff',
            'set_health': 'buff',
            'mutate': 'arcane',
            'random_effect': 'arcane',
            'time_warp': 'arcane',
            'mirror': 'arcane',
            'gamble': 'arcane',
            'summon_token': 'arcane',
            
            // Terrain effects
            'damage_on_tap': 'fire',
            'untap_terrains': 'earth',
        };
        
        const soundCategory = effectSoundMap[effectType];
        if (soundCategory) {
            this.play(soundCategory);
        }
    },
    
    // Toggle sound on/off
    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    },
    
    // Set volume (0.0 to 1.0)
    setVolume(vol) {
        this.volume = Math.max(0, Math.min(1, vol));
    },
    
    // Get current volume
    getVolume() {
        return this.volume;
    },
};

// Export for use in game.js
window.SoundManager = SoundManager;

// Initialize on first user interaction (to comply with autoplay policies)
document.addEventListener('click', () => {
    SoundManager.init();
}, { once: true });

document.addEventListener('keydown', () => {
    SoundManager.init();
}, { once: true });
