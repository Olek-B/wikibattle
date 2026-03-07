# WikiBattle Sound Effects

This document describes the sound effects system added to WikiBattle.

## Overview

WikiBattle now features a comprehensive sound effects system powered by the Web Audio API. All sounds are synthesized in real-time, requiring no external audio files.

## Features

### Sound Categories

#### Card Type Sounds
- **Creature Play**: Deep, powerful sawtooth sound when summoning creatures
- **Spell Play**: Magical, ethereal chime when casting spells
- **Terrain Play**: Earthy, solid square wave when playing terrains

#### Combat Sounds
- **Attack Player**: Sharp, aggressive sound when attacking the opponent directly
- **Attack Creature**: Impact sound when creatures battle each other
- **Creature Death**: Descending mournful sound when a creature is destroyed

#### Effect Sounds
- **Damage**: Sharp negative sound for damage effects
- **Heal**: Pleasant ascending sound for healing
- **Buff**: Positive ascending chime for stat increases
- **Debuff**: Negative descending sound for stat decreases
- **Draw Card**: Light positive sound when drawing cards
- **Discard**: Negative sound when discarding cards

#### Elemental/Special Effects
- **Lightning**: Electric crackle for lightning-based effects
- **Fire**: Warm rumbling for fire effects
- **Ice**: Crystalline tinkle for ice/freeze effects
- **Earth**: Deep rumble for earthquake/terrain effects
- **Arcane**: Mystical shimmer for magical effects

#### UI Sounds
- **Select**: Light click when selecting cards
- **Cancel**: Soft negative sound when canceling actions
- **Turn Start**: Fanfare when your turn begins
- **Turn End**: Descending sound when ending turn
- **Error**: Harsh buzz for invalid actions
- **Victory**: Triumphant fanfare when winning
- **Defeat**: Somber descending notes when losing

## Controls

### Sound Toggle Button
- Located in the bottom-right corner of the game screen
- Click to toggle sound effects on/off
- Shows 🔊 when enabled, 🔇 when muted

### Keyboard Shortcut
- Press **M** to toggle sound effects on/off

## Technical Details

### Web Audio API
The sound system uses the Web Audio API for real-time sound synthesis:
- No external audio files required
- Low latency playback
- Dynamic volume control
- Browser autoplay policy compliant

### Initialization
- Audio context is initialized on first user interaction
- Sounds are automatically enabled by default
- Volume defaults to 50%

### Sound Mapping

The system automatically plays appropriate sounds based on:
1. **Card Type**: Different sounds for creatures, spells, and terrains
2. **Game Log Keywords**: Analyzes log entries to determine which sound to play
3. **Effect Types**: Maps effect types to appropriate sound categories

## Integration Points

### Client Files Modified
- `client/sound.js` - New sound manager module
- `client/game.js` - Integrated sound calls throughout
- `client/index.html` - Added sound toggle button
- `client/style.css` - Added sound toggle button styling

### Key Integration Points in game.js
- Card playing (creature/spell/terrain)
- Card selection and targeting
- Attack actions
- Turn management
- Game log updates
- Victory/defeat screens

## Browser Compatibility

The sound system works in all modern browsers that support the Web Audio API:
- Chrome/Edge 57+
- Firefox 53+
- Safari 10+
- Opera 44+

## Future Enhancements

Potential improvements for the sound system:
1. Volume slider for fine-grained control
2. Mute/unmute persistence across sessions
3. Additional sound variations for different effect types
4. Background music option
5. Sound quality settings
