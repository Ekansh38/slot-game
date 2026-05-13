from dataclasses import dataclass


@dataclass(frozen=True)
class UpgradeDef:
    id: str
    name: str
    description: str
    base_cost: float
    max_levels: int
    is_active: bool = False


ALL_UPGRADES: list[UpgradeDef] = [
    # --- Early game (accessible in first ~10 minutes) ---
    UpgradeDef("better_fingers", "Better Fingers",  "+click value each level",               15,           21),
    UpgradeDef("auto_tap",       "Auto Tap",         "+passive $/s each level",               60,           21),
    UpgradeDef("click_combo",    "Click Combo",      "Rapid clicks stack a multiplier",        2_000,        10),
    UpgradeDef("loan_shark",     "Loan Shark",       "Borrow $100K, auto-repay $300K slowly",  0,             1),
    UpgradeDef("caffeine_rush",  "Caffeine Rush",    "Active: 10× clicks for 15s",            50_000,         5, is_active=True),

    # --- Mid game (~10-20 minutes) ---
    UpgradeDef("lucky_charm",    "Lucky Charm",      "Slot payouts ×1.15 per level",          25_000,        12),
    UpgradeDef("diamond_magnet", "Diamond Magnet",   "Diamonds appear more often on reels",  100_000,         8),
    UpgradeDef("slot_intuition", "Slot Intuition",   "RUNNING HOT boosts high-value symbols", 500_000,        1),
    UpgradeDef("hot_hands",      "Hot Hands",        "Win streak bonus starts at x2 streak",1_000_000,        8),
    UpgradeDef("auto_spin",      "Auto Spin",        "Automatically spins every few seconds",  750_000,        5),
    UpgradeDef("double_down",    "Double Down",      "5% chance per level to double any win",2_000_000,        5),
    UpgradeDef("risk_engine",    "Risk Engine",      "Near-miss pays out small consolation",  5_000_000,       5),

    # --- Late game (~20-27 minutes) ---
    UpgradeDef("the_syndicate",  "The Syndicate",    "+% bonus on every spin win",           25_000_000,      10),
    UpgradeDef("time_warp",      "Time Warp",        "Active: 5× passive for 30s",           50_000_000,       5, is_active=True),
    UpgradeDef("click_storm",    "Click Storm",      "Every N clicks triggers a bonus burst",100_000_000,      3),
    UpgradeDef("golden_reels",   "Golden Reels",     "All slot payouts ×1.5 per level",      500_000_000,      6),
    UpgradeDef("wild_symbol",    "Wild Symbol",      "8% chance per level for a wild reel", 5_000_000_000,     4),

    # --- End game (prestige territory) ---
    UpgradeDef("jackpot_boost",  "Jackpot Boost",    "💎 jackpot payout ×2 per level",      25_000_000_000,    5),
    UpgradeDef("hyper_fingers",  "Hyper Fingers",    "+mega click value tier each level",   100_000_000_000,   10),
    UpgradeDef("mega_passive",   "Mega Passive",     "+mega passive income tier each level", 250_000_000_000,   10),
]

UPGRADE_MAP: dict[str, UpgradeDef] = {u.id: u for u in ALL_UPGRADES}


def upgrade_cost(uid: str, current_level: int) -> float:
    defn = UPGRADE_MAP[uid]
    return defn.base_cost * (3.0 ** current_level)
