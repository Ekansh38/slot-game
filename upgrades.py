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
    UpgradeDef("better_fingers", "Better Fingers",  "+click value each level",              10,        8),
    UpgradeDef("auto_tap",       "Auto Tap",         "+passive $/s each level",              25,        8),
    UpgradeDef("click_combo",    "Click Combo",      "Rapid clicks stack a multiplier",      200,       5),
    UpgradeDef("lucky_charm",    "Lucky Charm",      "Slot payouts x1.2 per level",          500,       5),
    UpgradeDef("diamond_magnet", "Diamond Magnet",   "Diamonds appear more often on reels",  2_000,     3),
    UpgradeDef("slot_intuition", "Slot Intuition",   "Shows RUNNING HOT near jackpots",      10_000,    1),
    UpgradeDef("caffeine_rush",  "Caffeine Rush",    "Active: 10x clicks for 15s (60s CD)",  5_000,     3, is_active=True),
    UpgradeDef("the_syndicate",  "The Syndicate",    "+% of every spin win as bonus",        50_000,    4),
    UpgradeDef("time_warp",      "Time Warp",        "Active: 5x passive for 30s (2m CD)",   500_000,   3, is_active=True),
    UpgradeDef("loan_shark",     "Loan Shark",       "Borrow $10K, auto-repay $25K slowly",  0,         1),
]

UPGRADE_MAP: dict[str, UpgradeDef] = {u.id: u for u in ALL_UPGRADES}


def upgrade_cost(uid: str, current_level: int) -> float:
    defn = UPGRADE_MAP[uid]
    return defn.base_cost * (2.0 ** current_level)
