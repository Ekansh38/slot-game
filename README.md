# slot-game

A terminal clicker and slot machine game with fake money, upgrades, and procedural sound effects.

## Features

- Clicker mechanic: earn money one click at a time
- Classic 3-reel slot machine with animated reels stopping one by one
- 10 upgrades with exponentially scaling costs
- Active abilities: Caffeine Rush and Time Warp
- Win streaks, near-miss detection, and RUNNING HOT indicator
- Balance scales from $0 to billions with smart number formatting
- Persistent save file

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Controls

| Key | Action |
|-----|--------|
| `SPACE` | Click to earn money |
| `ENTER` | Spin the slots |
| `UP / DOWN` | Adjust bet or navigate upgrades |
| `U` | Open / close upgrades shop |
| `1` | Activate Caffeine Rush |
| `2` | Activate Time Warp |
| `Q` | Quit |

## Payouts

| Match | Payout |
|-------|--------|
| 3x Diamond | 100x bet |
| 3x Seven | 25x bet |
| 3x Bell | 10x bet |
| 3x BAR | 5x bet |
| 3x Cherry | 3x bet |
| 2x Diamond | 4x bet |
| 2x Seven | 3x bet |
| 2x anything else | 2x bet |
