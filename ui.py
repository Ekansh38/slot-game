import time
from typing import Any

from rich import box
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from game import SYMBOLS, GameState, CLICK_LEVELS, PASSIVE_LEVELS, SYNDICATE_PCT
from upgrades import ALL_UPGRADES, upgrade_cost

UPGRADES_PER_PAGE = 6


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------

def fmt(n: float) -> str:
    if n < 0:
        return f"-{fmt(-n)}"
    tiers = [
        (1e18, "Qi"),
        (1e15, "Qa"),
        (1e12, "T"),
        (1e9,  "B"),
        (1e6,  "M"),
        (1e3,  "K"),
    ]
    for thresh, suffix in tiers:
        if n >= thresh:
            v = n / thresh
            dec = 2 if v < 10 else (1 if v < 100 else 0)
            return f"${v:.{dec}f}{suffix}"
    return f"${n:,.0f}"


# ---------------------------------------------------------------------------
# Reel helpers
# ---------------------------------------------------------------------------

def _reel_symbols(state: GameState, idx: int) -> tuple[str, str, str]:
    def neighbors(sym: str) -> tuple[str, str, str]:
        i = SYMBOLS.index(sym)
        return SYMBOLS[(i - 1) % len(SYMBOLS)], sym, SYMBOLS[(i + 1) % len(SYMBOLS)]

    if state.spin.active and not state.spin.revealed[idx]:
        speed = 10 + idx * 3
        i = int(time.time() * speed) % len(SYMBOLS)
        return SYMBOLS[(i - 1) % len(SYMBOLS)], SYMBOLS[i], SYMBOLS[(i + 1) % len(SYMBOLS)]

    if state.spin.active and state.spin.revealed[idx]:
        mid = state.spin.result[idx]
        i = SYMBOLS.index(mid)
        top = state.spin.near_miss_sym if (idx == 2 and state.spin.near_miss) else SYMBOLS[(i - 1) % len(SYMBOLS)]
        bot = SYMBOLS[(i + 1) % len(SYMBOLS)]
        return top, mid, bot

    return neighbors(state.last_symbols[idx])


def _payline_style(result: str, spin_active: bool) -> str:
    if spin_active:
        return "bold white"
    if result == "jackpot":
        return "bold bright_magenta"
    if result == "big_win":
        return "bold bright_cyan"
    if result == "win":
        return "bold bright_green"
    if result == "near_miss":
        return "bold yellow"
    return "bold white"


def _render_reels(state: GameState) -> Table:
    t = Table(show_header=False, box=None, padding=(0, 1), expand=False)
    t.add_column(justify="center", min_width=5, no_wrap=True)
    t.add_column(justify="center", min_width=1, no_wrap=True)
    t.add_column(justify="center", min_width=5, no_wrap=True)
    t.add_column(justify="center", min_width=1, no_wrap=True)
    t.add_column(justify="center", min_width=5, no_wrap=True)

    sep = Text("│", style="white")
    pay_sep = Text("┤", style="bright_white")  # brighter separator on payline
    mid_style = _payline_style(state.last_result, state.spin.active)

    tops, mids, bots = [], [], []
    for i in range(3):
        top, mid, bot = _reel_symbols(state, i)
        tops.append(Text(f" {top} ", style="bright_black", justify="center"))
        mids.append(Text(f"[{mid}]", style=mid_style, justify="center"))
        bots.append(Text(f" {bot} ", style="bright_black", justify="center"))

    t.add_row(tops[0], sep, tops[1], sep, tops[2])
    t.add_row(mids[0], pay_sep, mids[1], pay_sep, mids[2])
    t.add_row(bots[0], sep, bots[1], sep, bots[2])
    return t


# ---------------------------------------------------------------------------
# Left panel: clicker or upgrades
# ---------------------------------------------------------------------------

def _render_clicker(state: GameState) -> Panel:
    now = time.time()
    cv = state.click_value()
    pr = state.passive_rate()
    caffeine_active = now < state.caffeine_end
    warp_active = now < state.time_warp_end

    t = Table(show_header=False, box=None, padding=(0, 1), expand=False)
    t.add_column(style="white", no_wrap=True, min_width=14)
    t.add_column(style="bold bright_white", no_wrap=True)

    t.add_row("Click value:", fmt(cv))
    t.add_row("Per second:", f"{fmt(pr)}/s" if pr > 0 else "$0/s")

    combo_lv = state.level("click_combo")
    if state.combo_count > 1:
        if combo_lv > 0:
            multiplier = min(1.0 + state.combo_count * 0.1 * combo_lv, 5.0)
            combo_val = Text(f"x{state.combo_count}  ({multiplier:.1f}x value)", style="bold yellow")
        else:
            combo_val = Text(f"x{state.combo_count}  (buy Click Combo to boost)", style="yellow")
        t.add_row("Combo:", combo_val)
    else:
        t.add_row("", "")

    if state.loan_active:
        t.add_row("Loan debt:", Text(fmt(state.loan_debt), style="bold red"))

    t.add_row("", "")
    t.add_row("Clicks:", f"{state.total_clicks:,}")
    t.add_row("Spins:", f"{state.total_spins:,}")

    abilities: list[Text] = []
    if state.level("caffeine_rush") > 0:
        if caffeine_active:
            rem = state.caffeine_end - now
            abilities.append(Text(f"[1] Caffeine Rush  {rem:.0f}s left", style="bold bright_yellow"))
        elif now < state.caffeine_cd:
            cd = state.caffeine_cd - now
            abilities.append(Text(f"[1] Caffeine Rush  cooldown {cd:.0f}s", style="white"))
        else:
            abilities.append(Text("[1] Caffeine Rush  READY", style="bright_green"))

    if state.level("time_warp") > 0:
        if warp_active:
            rem = state.time_warp_end - now
            abilities.append(Text(f"[2] Time Warp  {rem:.0f}s left", style="bold bright_cyan"))
        elif now < state.time_warp_cd:
            cd = state.time_warp_cd - now
            abilities.append(Text(f"[2] Time Warp  cooldown {cd:.0f}s", style="white"))
        else:
            abilities.append(Text("[2] Time Warp  READY", style="bright_cyan"))

    controls = Text("\n[SPACE] Click\n[U]     Upgrades\n[M]     All-in bet\n[Q/ESC] Quit", style="white")

    content: list[Any] = [t]
    if abilities:
        content.append(Text(""))
        content.extend(abilities)
    content.append(Text(""))
    content.append(controls)

    title = Text("CLICKER", style="bold bright_white")
    return Panel(Group(*content), title=title, border_style="white", padding=(1, 2))


def _upgrade_next_desc(uid: str, cur: int) -> str:
    nxt = cur + 1
    if uid == "better_fingers":
        val = CLICK_LEVELS[min(nxt, len(CLICK_LEVELS) - 1)]
        return f"Next: ${val:,} per click"
    if uid == "auto_tap":
        val = PASSIVE_LEVELS[min(nxt, len(PASSIVE_LEVELS) - 1)]
        return f"Next: ${val:,}/s passive"
    if uid == "click_combo":
        return f"Next: +{nxt * 10}% per combo click (max 5×)"
    if uid == "lucky_charm":
        return f"Next: ×{1.0 + nxt * 0.2:.1f} slot payouts"
    if uid == "diamond_magnet":
        return f"Next: diamond weight +{nxt * 3} (more 💎 hits)"
    if uid == "the_syndicate":
        pct = SYNDICATE_PCT[min(nxt, len(SYNDICATE_PCT) - 1)] * 100
        return f"Next: +{pct:.0f}% bonus on every win"
    if uid == "caffeine_rush":
        return f"Next: 10× clicks for 15s, {60 // nxt}s cooldown"
    if uid == "time_warp":
        return f"Next: 5× passive for 30s, {120 // nxt}s cooldown"
    if uid == "hot_hands":
        threshold = max(1, 3 - nxt)
        return f"Next: streak bonus activates at x{threshold} wins"
    if uid == "risk_engine":
        return f"Next: near-miss pays {nxt * 10}% of bet back"
    return ""


def _render_upgrades(state: GameState) -> Panel:
    rows: list[Any] = []

    scroll = state.upgrade_scroll
    visible = ALL_UPGRADES[scroll : scroll + UPGRADES_PER_PAGE]

    if scroll > 0:
        rows.append(Text(f"  ... {scroll} more above", style="bright_black"))
        rows.append(Text(""))

    for i, defn in enumerate(visible):
        i = i + scroll  # absolute index
        cur = state.level(defn.id)
        maxed = cur >= defn.max_levels
        cost = upgrade_cost(defn.id, cur) if not maxed else 0.0
        affordable = state.balance >= cost and not maxed
        selected = i == state.upgrade_cursor

        cursor_str = "> " if selected else "  "

        if maxed:
            name_style = "bright_black"
            cost_str = "MAXED"
            cost_style = "bright_black"
        elif affordable:
            name_style = "bold bright_white"
            cost_str = fmt(cost)
            cost_style = "bright_green"
        else:
            name_style = "white"
            cost_str = fmt(cost)
            cost_style = "bright_red"

        label = Text()
        label.append(cursor_str, style="bright_yellow" if selected else "bright_black")
        label.append(defn.name, style=name_style)
        if cur > 0:
            label.append(f"  Lv{cur}", style="cyan")
        if defn.is_active:
            label.append(" [active]", style="yellow")

        desc_text = Text(f"   {defn.description}", style="white")
        cost_text = Text("   Cost: ", style="white") + Text(cost_str, style=cost_style)

        rows.append(label)
        rows.append(desc_text)
        if not maxed:
            next_desc = _upgrade_next_desc(defn.id, cur)
            if next_desc:
                rows.append(Text(f"   {next_desc}", style="bright_cyan"))
        rows.append(cost_text)
        rows.append(Text(""))

    remaining = len(ALL_UPGRADES) - scroll - len(visible)
    if remaining > 0:
        rows.append(Text(f"  ... {remaining} more below", style="bright_black"))
        rows.append(Text(""))

    controls = Text("[j/k] Navigate   [ENTER] Buy   [U/ESC] Close", style="white")
    rows.append(controls)

    title = Text("UPGRADES", style="bold bright_white")
    return Panel(Group(*rows), title=title, border_style="white", padding=(1, 2))


# ---------------------------------------------------------------------------
# Right panel: slots
# ---------------------------------------------------------------------------

def _render_slots(state: GameState) -> Panel:
    now = time.time()
    is_hot = state.level("slot_intuition") > 0 and now < state.hot_until

    reels = _render_reels(state)

    result_text = Text()
    if state.last_result == "jackpot":
        result_text.append("  JACKPOT!!!  ", style="bold bright_magenta")
        result_text.append(fmt(state.last_win), style="bold bright_magenta")
    elif state.last_result == "big_win":
        result_text.append("  BIG WIN!   ", style="bold bright_cyan")
        result_text.append(fmt(state.last_win), style="bold bright_cyan")
    elif state.last_result == "win":
        result_text.append("  Won  ", style="bold bright_green")
        result_text.append(fmt(state.last_win), style="bold bright_green")
    elif state.last_result == "near_miss":
        if state.last_win > 0:
            result_text.append("  So close...  ", style="bright_yellow")
            result_text.append(f"+{fmt(state.last_win)}", style="yellow")
        else:
            result_text.append("  So close...", style="bright_yellow")
    elif state.last_result == "loss":
        result_text.append("  Lost  ", style="bright_red")
        result_text.append(fmt(state.last_bet_placed), style="bright_red")
    else:
        result_text.append("  Press ENTER to spin", style="white")

    streak_text = Text()
    if state.win_streak >= 3:
        streak_text.append(f"  STREAK x{state.win_streak}", style="bold bright_yellow")

    hot_text = Text()
    if is_hot:
        hot_text.append("  *** RUNNING HOT ***", style="bold bright_red")

    bet_can_afford = state.balance >= state.bet and state.bet > 0
    bet_text = Text()
    bet_text.append("  Bet: ", style="white")
    if state.bet_all_in:
        bet_text.append("ALL IN ", style="bold bright_magenta")
        bet_text.append(f"({fmt(state.bet)})", style="bright_magenta")
    else:
        bet_text.append(fmt(state.bet), style="bold bright_white" if bet_can_afford else "bold bright_red")
    bet_text.append("   [j/k] adjust  [M] all-in", style="white")

    if state.spin.active:
        spin_hint = Text("  Spinning...", style="white")
    elif not bet_can_afford:
        spin_hint = Text("  Not enough funds", style="bright_red")
    else:
        spin_hint = Text("  [ENTER] Spin", style="white")

    content = Group(
        Text(""),
        reels,
        Text(""),
        result_text,
        streak_text,
        hot_text,
        Text(""),
        bet_text,
        Text(""),
        spin_hint,
        Text(""),
    )

    border_style = "white"
    if state.last_result == "jackpot" and not state.spin.active:
        border_style = "bright_magenta"
    elif state.last_result == "big_win" and not state.spin.active:
        border_style = "bright_cyan"
    elif state.win_streak >= 3:
        border_style = "bright_yellow"

    title = Text("SLOTS", style="bold bright_white")
    return Panel(content, title=title, border_style=border_style, padding=(0, 2))


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def _render_header(state: GameState) -> Panel:
    t = Table(show_header=False, box=None, expand=True, padding=(0, 2))
    t.add_column(justify="left")
    t.add_column(justify="center")
    t.add_column(justify="right")

    bal = Text()
    bal.append("Balance: ", style="white")
    bal.append(fmt(state.balance), style="bold bright_green")

    title = Text("SLOT GAME", style="bold bright_white")

    right = Text()
    if state.win_streak >= 3:
        right.append(f"Streak x{state.win_streak}", style="bold bright_yellow")

    t.add_row(bal, title, right)
    return Panel(t, box=box.HORIZONTALS, border_style="white", padding=(0, 0))


# ---------------------------------------------------------------------------
# Top-level render
# ---------------------------------------------------------------------------

def render(state: GameState) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1),
    )

    layout["header"].update(_render_header(state))
    layout["left"].update(_render_upgrades(state) if state.show_upgrades else _render_clicker(state))
    layout["right"].update(_render_slots(state))

    return layout


def get_selected_upgrade_id(state: GameState) -> str:
    if 0 <= state.upgrade_cursor < len(ALL_UPGRADES):
        return ALL_UPGRADES[state.upgrade_cursor].id
    return ""
