import json
import os
import random
import time
import threading

import sound
from upgrades import UPGRADE_MAP, upgrade_cost

SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")

SYMBOLS = ["💎", "7", "🔔", "BAR", "🍒"]
BASE_WEIGHTS = [2, 5, 10, 15, 20]

THREE_PAYOUTS = {"💎": 100, "7": 25, "🔔": 10, "BAR": 5, "🍒": 3}
TWO_PAYOUTS   = {"💎": 4,   "7": 3,  "🔔": 2,  "BAR": 2, "🍒": 2}

CLICK_LEVELS = [
    1, 2, 5, 15, 50, 150, 500, 2_000, 10_000, 40_000, 200_000, 1_000_000, 5_000_000,
    20_000_000, 80_000_000, 300_000_000, 1_200_000_000, 5_000_000_000,
    20_000_000_000, 80_000_000_000, 300_000_000_000, 1_200_000_000_000,
]
PASSIVE_LEVELS = [
    0, 1, 4, 12, 40, 150, 600, 2_500, 8_000, 30_000, 120_000, 500_000, 2_000_000,
    8_000_000, 30_000_000, 120_000_000, 500_000_000, 2_000_000_000,
    8_000_000_000, 30_000_000_000, 120_000_000_000, 500_000_000_000,
]
HYPER_CLICK_LEVELS = [
    0, 5_000_000_000_000, 20_000_000_000_000, 80_000_000_000_000,
    300_000_000_000_000, 1_200_000_000_000_000, 5_000_000_000_000_000,
    20_000_000_000_000_000, 80_000_000_000_000_000, 300_000_000_000_000_000,
    1_200_000_000_000_000_000,
]
MEGA_PASSIVE_LEVELS = [
    0, 2_000_000_000_000, 8_000_000_000_000, 30_000_000_000_000,
    120_000_000_000_000, 500_000_000_000_000, 2_000_000_000_000_000,
    8_000_000_000_000_000, 30_000_000_000_000_000, 120_000_000_000_000_000,
    500_000_000_000_000_000,
]
SYNDICATE_PCT = [0.0, 0.01, 0.03, 0.07, 0.15, 0.30, 0.50, 0.75, 1.00, 1.50, 2.00]
PRESTIGE_THRESHOLD = 1_000_000_000_000  # $1T to prestige

BET_STEPS = [
    1, 5, 10, 25, 50, 100, 250, 500,
    1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000,
    250_000, 500_000, 1_000_000, 5_000_000, 10_000_000,
    50_000_000, 100_000_000, 500_000_000,
    1_000_000_000, 5_000_000_000, 10_000_000_000,
    50_000_000_000, 100_000_000_000, 500_000_000_000,
    1_000_000_000_000,
]

REEL_STOP_TIMES = [0.7, 1.2, 1.7]

_SOUND_DISPATCH = {
    "reel_stop": sound.play_reel_stop,
    "tease":     sound.play_tease,
    "win":       sound.play_win,
    "big_win":   sound.play_big_win,
    "jackpot":   sound.play_jackpot,
    "loss":      sound.play_loss,
}


class SpinState:
    __slots__ = ["active", "result", "revealed", "start_time",
                 "snd_played", "near_miss", "near_miss_sym"]

    def __init__(self) -> None:
        self.active: bool = False
        self.result: list[str] = ["", "", ""]
        self.revealed: list[bool] = [False, False, False]
        self.start_time: float = 0.0
        self.snd_played: list[bool] = [False, False, False]
        self.near_miss: bool = False
        self.near_miss_sym: str = ""


class GameState:
    def __init__(self) -> None:
        self.balance: float = 0.0
        self.bet_index: int = 0
        self.upgrades: dict[str, int] = {}

        # Clicker
        self.last_click_time: float = 0.0
        self.combo_count: int = 0
        self.total_clicks: int = 0

        # Slots
        self.win_streak: int = 0
        self.last_result: str = ""
        self.last_win: float = 0.0
        self.last_bet_placed: float = 0.0
        self.bet_all_in: bool = False
        self.bet_custom: float | None = None
        self.bet_input_mode: bool = False
        self.bet_input_buf: str = ""
        self.last_symbols: list[str] = ["🍒", "🍒", "🍒"]
        self.total_spins: int = 0
        self.spin = SpinState()

        # Active abilities
        self.caffeine_end: float = 0.0
        self.caffeine_cd: float = 0.0
        self.time_warp_end: float = 0.0
        self.time_warp_cd: float = 0.0

        # Loan
        self.loan_active: bool = False
        self.loan_debt: float = 0.0

        # UI state
        self.show_upgrades: bool = False
        self.upgrade_cursor: int = 0
        self.upgrade_scroll: int = 0

        # Hot streak (slot_intuition)
        self.hot_until: float = 0.0

        # Stats tracking
        self.total_winnings: float = 0.0
        self.biggest_win: float = 0.0
        self.jackpot_count: int = 0
        self.last_doubled: bool = False

        # Auto-spin timer
        self.auto_spin_timer: float = 0.0

        # Prestige
        self.prestige_count: int = 0
        self.prestige_mult: float = 1.0  # 1.5^prestige_count

        # Click storm counter
        self._click_storm_counter: int = 0
        self.storm_bonus_pending: float = 0.0  # shown in UI briefly

        # Save tracking: increments on clicks + passive ticks, triggers save at 30
        self._change_count: int = 0
        self._save_now: bool = False  # set True when spin resolves or upgrade bought

        self._last_tick: float = time.time()
        self._lock = threading.Lock()

    @property
    def bet(self) -> float:
        if self.bet_all_in:
            return self.balance
        if self.bet_custom is not None:
            return self.bet_custom
        return BET_STEPS[self.bet_index]

    def level(self, uid: str) -> int:
        return self.upgrades.get(uid, 0)

    def click_value(self) -> float:
        lv = self.level("better_fingers")
        base = float(CLICK_LEVELS[min(lv, len(CLICK_LEVELS) - 1)])
        hyper_lv = self.level("hyper_fingers")
        base += float(HYPER_CLICK_LEVELS[min(hyper_lv, len(HYPER_CLICK_LEVELS) - 1)])
        base *= self.prestige_mult
        if time.time() < self.caffeine_end:
            base *= 10.0
        cl = self.level("click_combo")
        if cl > 0 and self.combo_count > 1:
            base *= min(1.0 + self.combo_count * 0.1 * cl, 5.0)
        return base

    def passive_rate(self) -> float:
        lv = self.level("auto_tap")
        base = float(PASSIVE_LEVELS[min(lv, len(PASSIVE_LEVELS) - 1)])
        mega_lv = self.level("mega_passive")
        base += float(MEGA_PASSIVE_LEVELS[min(mega_lv, len(MEGA_PASSIVE_LEVELS) - 1)])
        base *= self.prestige_mult
        if time.time() < self.time_warp_end:
            base *= 5.0
        return base

    def payout_mult(self) -> float:
        m = 1.0 + self.level("lucky_charm") * 0.15
        m *= 1.0 + self.level("golden_reels") * 0.5
        m *= self.prestige_mult
        streak_threshold = max(1, 3 - self.level("hot_hands"))
        if self.win_streak >= streak_threshold:
            m *= 1.0 + (self.win_streak - streak_threshold + 1) * 0.1
        return m

    def reel_weights(self) -> list[int]:
        w = BASE_WEIGHTS.copy()
        w[0] += self.level("diamond_magnet") * 3
        # Running hot actually boosts high-value symbol weights
        if self.level("slot_intuition") > 0 and time.time() < self.hot_until:
            w[0] += 3  # 💎
            w[1] += 4  # 7
            w[2] += 3  # 🔔
        return w

    def do_click(self) -> None:
        now = time.time()
        with self._lock:
            if now - self.last_click_time < 1.0:
                self.combo_count += 1
            else:
                self.combo_count = 1
            self.last_click_time = now
            cv = self.click_value()
            self.balance += cv
            self.total_clicks += 1
            self._change_count += 1
            # Click storm bonus
            cs_lv = self.level("click_storm")
            if cs_lv > 0:
                threshold = max(10, 50 - (cs_lv - 1) * 15)  # 50 / 35 / 20
                self._click_storm_counter += 1
                if self._click_storm_counter >= threshold:
                    self._click_storm_counter = 0
                    bonus = cv * 40 * cs_lv
                    self.balance += bonus
                    self.storm_bonus_pending = bonus
        sound.play_click()

    def can_spin(self) -> bool:
        return not self.spin.active and self.bet > 0 and self.balance >= self.bet

    def start_spin(self) -> bool:
        if not self.can_spin():
            return False
        with self._lock:
            self.last_bet_placed = self.bet  # capture before deducting (all-in uses balance)
            self.balance -= self.last_bet_placed
            self.total_spins += 1
            weights = self.reel_weights()
            result = random.choices(SYMBOLS, weights=weights, k=3)
            # Wild symbol: replace one reel with the most common other symbol
            wild_lv = self.level("wild_symbol")
            if wild_lv > 0 and random.random() < wild_lv * 0.08:
                wild_idx = random.randint(0, 2)
                others = [result[i] for i in range(3) if i != wild_idx]
                result[wild_idx] = max(set(others), key=others.count)
            counts: dict[str, int] = {}
            for s in result:
                counts[s] = counts.get(s, 0) + 1
            near_miss = max(counts.values()) < 2 and random.random() < 0.2
            sp = SpinState()
            sp.active = True
            sp.result = result
            sp.start_time = time.time()
            sp.near_miss = near_miss
            sp.near_miss_sym = result[0] if near_miss else ""
            self.spin = sp
            self.last_doubled = False
        sound.play_spin_start()
        return True

    def tick(self) -> None:
        sounds: list[str] = []
        _do_auto_spin = False
        now = time.time()
        with self._lock:
            dt = now - self._last_tick
            self._last_tick = now

            # Passive income
            rate = self.passive_rate()
            if rate > 0:
                self.balance += rate * dt
                self._change_count += 1

            # Loan repayment at $500/s
            if self.loan_active and self.loan_debt > 0:
                repay = min(self.loan_debt, 500.0 * dt)
                self.balance = max(0.0, self.balance - repay)
                self.loan_debt -= repay
                if self.loan_debt <= 0.0:
                    self.loan_active = False
                    self.loan_debt = 0.0

            # Spin reel reveals
            if self.spin.active:
                elapsed = now - self.spin.start_time
                for i, stop_t in enumerate(REEL_STOP_TIMES):
                    if elapsed >= stop_t and not self.spin.revealed[i]:
                        self.spin.revealed[i] = True
                        if not self.spin.snd_played[i]:
                            self.spin.snd_played[i] = True
                            if i == 1 and self.spin.result[0] == self.spin.result[1]:
                                sounds.append("tease")
                            else:
                                sounds.append("reel_stop")

                if all(self.spin.revealed):
                    self.spin.active = False
                    self.last_symbols = list(self.spin.result)
                    sounds.extend(self._resolve_spin())
                    self._save_now = True

            # Hot streak random activation
            if self.level("slot_intuition") and now >= self.hot_until:
                if random.random() < 0.05 * dt:
                    self.hot_until = now + random.uniform(5.0, 15.0)

            # Auto spin
            if not self.spin.active and self.level("auto_spin") > 0:
                _auto_intervals = [10.0, 8.0, 6.0, 4.0, 3.0]
                lv = min(self.level("auto_spin"), len(_auto_intervals))
                if now - self.auto_spin_timer >= _auto_intervals[lv - 1]:
                    self.auto_spin_timer = now
                    _do_auto_spin = self.can_spin()

        for snd in sounds:
            fn = _SOUND_DISPATCH.get(snd)
            if fn:
                fn()

        if _do_auto_spin:
            self.start_spin()

    def _resolve_spin(self) -> list[str]:
        """Must be called inside self._lock. Returns sound event names."""
        result = self.spin.result
        counts: dict[str, int] = {}
        for s in result:
            counts[s] = counts.get(s, 0) + 1

        mult = self.payout_mult()
        win = 0.0

        bet = self.last_bet_placed  # use captured amount — self.bet may be 0 if all-in
        if len(counts) == 1:
            win = bet * THREE_PAYOUTS[result[0]] * mult
        else:
            for sym, cnt in counts.items():
                if cnt == 2:
                    win = bet * TWO_PAYOUTS[sym] * mult
                    break

        if win > 0:
            # Jackpot Boost: jackpot wins multiplied per level
            if len(counts) == 1 and result[0] == "💎":
                jb = self.level("jackpot_boost")
                if jb > 0:
                    win *= 2.0 ** jb

            # Double Down: chance to double the win
            dd_lv = self.level("double_down")
            if dd_lv > 0 and random.random() < dd_lv * 0.05:
                win *= 2.0
                self.last_doubled = True

            syn_lv = min(self.level("the_syndicate"), len(SYNDICATE_PCT) - 1)
            win *= 1.0 + SYNDICATE_PCT[syn_lv]

            self.total_winnings += win
            if win > self.biggest_win:
                self.biggest_win = win

        self.balance += win
        self.last_win = win

        if win <= 0:
            self.win_streak = 0
            if self.spin.near_miss:
                risk_lv = self.level("risk_engine")
                if risk_lv > 0:
                    consolation = bet * 0.1 * risk_lv
                    self.balance += consolation
                    self.last_win = consolation
                self.last_result = "near_miss"
            else:
                self.last_result = "loss"
            return ["loss"]

        self.win_streak += 1
        ratio = win / bet
        if ratio >= THREE_PAYOUTS["💎"] * 0.8:
            self.jackpot_count += 1
            self.last_result = "jackpot"
            return ["jackpot"]
        if ratio >= THREE_PAYOUTS["7"] * 0.8:
            self.last_result = "big_win"
            return ["big_win"]
        self.last_result = "win"
        return ["win"]

    def adjust_bet(self, direction: int) -> None:
        self.bet_custom = None  # clear custom amount when stepping
        if direction > 0:
            if self.bet_all_in:
                return  # already at max
            if self.bet_index >= len(BET_STEPS) - 1:
                self.bet_all_in = True  # go past max → all in
            else:
                self.bet_index += 1
        else:
            if self.bet_all_in:
                self.bet_all_in = False  # come back from all-in
            else:
                self.bet_index = max(self.bet_index - 1, 0)

    def toggle_all_in(self) -> None:
        if self.bet_all_in:
            self.bet_all_in = False
        else:
            self.bet_all_in = True

    def buy_upgrade(self, uid: str) -> bool:
        defn = UPGRADE_MAP.get(uid)
        if defn is None:
            return False
        cur = self.level(uid)
        if cur >= defn.max_levels:
            return False
        cost = upgrade_cost(uid, cur)
        if self.balance < cost:
            return False
        with self._lock:
            self.balance -= cost
            self.upgrades[uid] = cur + 1
            if uid == "loan_shark":
                self.balance += 100_000.0
                self.loan_active = True
                self.loan_debt = 300_000.0
        sound.play_upgrade()
        self._save_now = True
        return True

    def can_prestige(self) -> bool:
        return self.balance >= PRESTIGE_THRESHOLD

    def do_prestige(self) -> None:
        if not self.can_prestige():
            return
        with self._lock:
            self.prestige_count += 1
            self.prestige_mult = 1.5 ** self.prestige_count
            # Reset progress but keep prestige fields and lifetime stats
            self.balance = 0.0
            self.bet_index = 0
            self.bet_all_in = False
            self.bet_custom = None
            self.upgrades = {}
            self.win_streak = 0
            self.loan_active = False
            self.loan_debt = 0.0
            self.last_symbols = ["🍒", "🍒", "🍒"]
            self.last_result = ""
            self.last_win = 0.0
            self.last_bet_placed = 0.0
            self.combo_count = 0
            self.caffeine_end = 0.0
            self.caffeine_cd = 0.0
            self.time_warp_end = 0.0
            self.time_warp_cd = 0.0
            self.hot_until = 0.0
            self.auto_spin_timer = 0.0
            self._click_storm_counter = 0
            self.storm_bonus_pending = 0.0
            self.spin = SpinState()
            self.show_upgrades = False
        self._save_now = True
        sound.play_jackpot()

    def activate_ability(self, uid: str) -> bool:
        now = time.time()
        lv = self.level(uid)
        if uid == "caffeine_rush" and lv > 0 and now >= self.caffeine_cd:
            self.caffeine_end = now + 15.0
            self.caffeine_cd = now + max(12, 60 // lv)
            sound.play_active_ability()
            return True
        if uid == "time_warp" and lv > 0 and now >= self.time_warp_cd:
            self.time_warp_end = now + 30.0
            self.time_warp_cd = now + max(24, 120 // lv)
            sound.play_active_ability()
            return True
        return False

    def save(self) -> None:
        data = {
            "balance": self.balance,
            "bet_index": self.bet_index,
            "bet_all_in": self.bet_all_in,
            "bet_custom": self.bet_custom,
            "upgrades": self.upgrades,
            "win_streak": self.win_streak,
            "total_clicks": self.total_clicks,
            "total_spins": self.total_spins,
            "loan_active": self.loan_active,
            "loan_debt": self.loan_debt,
            "last_symbols": self.last_symbols,
            "total_winnings": self.total_winnings,
            "biggest_win": self.biggest_win,
            "jackpot_count": self.jackpot_count,
            "prestige_count": self.prestige_count,
            "prestige_mult": self.prestige_mult,
        }
        try:
            with open(SAVE_PATH, "w") as f:
                json.dump(data, f)
        except OSError:
            pass

    @classmethod
    def load(cls) -> "GameState":
        state = cls()
        if not os.path.exists(SAVE_PATH):
            return state
        try:
            with open(SAVE_PATH) as f:
                data = json.load(f)
            state.balance = float(data.get("balance", 0.0))
            state.bet_index = int(data.get("bet_index", 0))
            state.bet_all_in = bool(data.get("bet_all_in", False))
            custom = data.get("bet_custom", None)
            state.bet_custom = float(custom) if custom is not None else None
            state.upgrades = {k: int(v) for k, v in data.get("upgrades", {}).items()}
            state.win_streak = int(data.get("win_streak", 0))
            state.total_clicks = int(data.get("total_clicks", 0))
            state.total_spins = int(data.get("total_spins", 0))
            state.loan_active = bool(data.get("loan_active", False))
            state.loan_debt = float(data.get("loan_debt", 0.0))
            state.last_symbols = data.get("last_symbols", ["🍒", "🍒", "🍒"])
            state.total_winnings = float(data.get("total_winnings", 0.0))
            state.biggest_win = float(data.get("biggest_win", 0.0))
            state.jackpot_count = int(data.get("jackpot_count", 0))
            state.prestige_count = int(data.get("prestige_count", 0))
            state.prestige_mult = float(data.get("prestige_mult", 1.0))
        except Exception:
            pass
        return state
