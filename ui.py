import time
from typing import Any

from rich import box
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from game import SYMBOLS, GameState
from upgrades import ALL_UPGRADES, upgrade_cost


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


def fmt_plain(n: float) -> str:
    """Like fmt but no dollar sign, for use inside existing labels."""
    return fmt(n).lstrip("$")


# ---------------------------------------------------------------------------
# Reel helpers
# ---------------------------------------------------------------------------

def _reel_symbols(state: GameState, idx: int) -> tuple[str, str, str]:
    """Returns (top, mid, bot) symbols for reel idx."""
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


def _sym_style(_sym: str, is_payline: bool, result: str, spin_active: bool) -> str:
    if not is_payline:
        return "dim white"
    if spin_active:
        return "bold bright_white"
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

    sep = Text("│", style="dim white")
    tops, mids, bots = [], [], []
    for i in range(3):
        top, mid, bot = _reel_symbols(state, i)
        tops.append(Text(top, style="dim white", justify="center"))
        mids.append(Text(mid, style=_sym_style(mid, True, state.last_result, state.spin.active), justify="center"))
        bots.append(Text(bot, style="dim white", justify="center"))

    t.add_row(tops[0], sep, tops[1], sep, tops[2])
    t.add_row(mids[0], sep, mids[1], sep, mids[2])
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

    t = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    t.add_column(style="dim white", no_wrap=True)
    t.add_column(style="bright_white", no_wrap=True)

    t.add_row("Click value:", fmt(cv))
    t.add_row("Per second:", f"{fmt(pr)}/s" if pr > 0 else "0/s")

    if state.combo_count > 1:
        t.add_row("Combo:", Text(f"x{state.combo_count}", style="bold yellow"))

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
            abilities.append(Text(f"[1] Caffeine Rush  CD {cd:.0f}s", style="dim"))
        else:
            abilities.append(Text("[1] Caffeine Rush  READY", style="green"))

    if state.level("time_warp") > 0:
        if warp_active:
            rem = state.time_warp_end - now
            abilities.append(Text(f"[2] Time Warp  {rem:.0f}s left", style="bold bright_cyan"))
        elif now < state.time_warp_cd:
            cd = state.time_warp_cd - now
            abilities.append(Text(f"[2] Time Warp  CD {cd:.0f}s", style="dim"))
        else:
            abilities.append(Text("[2] Time Warp  READY", style="cyan"))

    controls = Text("\n[SPACE] Click\n[U] Upgrades\n[Q] Quit", style="dim white")

    content: list[Any] = [t]
    if abilities:
        content.append(Text(""))
        content.extend(abilities)
    content.append(Text(""))
    content.append(controls)

    title = Text("CLICKER", style="bold bright_white")
    return Panel(Group(*content), title=title, border_style="bright_black", padding=(1, 2))


def _render_upgrades(state: GameState) -> Panel:
    rows: list[Any] = []

    for i, defn in enumerate(ALL_UPGRADES):
        cur = state.level(defn.id)
        maxed = cur >= defn.max_levels
        cost = upgrade_cost(defn.id, cur) if not maxed else 0.0
        affordable = state.balance >= cost and not maxed

        cursor = "> " if i == state.upgrade_cursor else "  "

        if maxed:
            name_style = "dim"
            cost_str = "MAXED"
            cost_style = "dim"
        elif affordable:
            name_style = "bold bright_white"
            cost_str = fmt(cost)
            cost_style = "bright_green"
        else:
            name_style = "white"
            cost_str = fmt(cost)
            cost_style = "red"

        label = Text()
        label.append(cursor, style="bright_yellow" if i == state.upgrade_cursor else "dim")
        label.append(f"{defn.name}", style=name_style)
        if cur > 0:
            label.append(f"  Lv{cur}", style="dim cyan")
        if defn.is_active:
            label.append(" [A]", style="dim yellow")

        desc_text = Text(f"   {defn.description}", style="dim white")
        cost_text = Text(f"   Cost: ", style="dim") + Text(cost_str, style=cost_style)

        rows.append(label)
        rows.append(desc_text)
        rows.append(cost_text)
        rows.append(Text(""))

    controls = Text("[↑/↓] Navigate   [ENTER] Buy   [U] Close", style="dim white")
    rows.append(controls)

    title = Text("UPGRADES", style="bold bright_white")
    return Panel(Group(*rows), title=title, border_style="bright_black", padding=(1, 2))


# ---------------------------------------------------------------------------
# Right panel: slots
# ---------------------------------------------------------------------------

def _render_slots(state: GameState) -> Panel:
    now = time.time()
    is_hot = state.level("slot_intuition") > 0 and now < state.hot_until

    reels = _render_reels(state)

    # Result line
    result_text = Text()
    if state.last_result == "jackpot":
        result_text.append("  JACKPOT!!! ", style="bold bright_magenta blink")
        result_text.append(fmt(state.last_win), style="bold bright_magenta")
    elif state.last_result == "big_win":
        result_text.append("  BIG WIN!  ", style="bold bright_cyan")
        result_text.append(fmt(state.last_win), style="bold bright_cyan")
    elif state.last_result == "win":
        result_text.append("  Won ", style="bold bright_green")
        result_text.append(fmt(state.last_win), style="bold bright_green")
    elif state.last_result == "near_miss":
        result_text.append("  So close...", style="yellow")
    elif state.last_result == "loss":
        result_text.append("  Lost ", style="dim red")
        result_text.append(fmt(state.bet), style="dim red")
    else:
        result_text.append("  Press ENTER to spin", style="dim white")

    # Streak
    streak_text = Text()
    if state.win_streak >= 3:
        streak_text.append(f"  STREAK x{state.win_streak}  ", style="bold bright_yellow")

    # Hot indicator
    hot_text = Text()
    if is_hot:
        hot_text.append("  *** RUNNING HOT ***", style="bold bright_red blink")

    # Bet
    bet_can_afford = state.balance >= state.bet
    bet_style = "bold bright_white" if bet_can_afford else "bold red"
    bet_text = Text()
    bet_text.append("  Bet: ", style="dim white")
    bet_text.append(fmt(state.bet), style=bet_style)
    bet_text.append("   [↑/↓] adjust", style="dim white")

    # Spin hint
    if state.spin.active:
        spin_hint = Text("  Spinning...", style="dim white")
    elif not bet_can_afford:
        spin_hint = Text("  Not enough funds", style="dim red")
    else:
        spin_hint = Text("  [ENTER] Spin", style="dim white")

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

    border_style = "bright_black"
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
    bal.append("Balance: ", style="dim white")
    bal.append(fmt(state.balance), style="bold bright_green")

    title = Text("SLOT GAME", style="bold bright_white")

    streak = Text()
    if state.win_streak >= 3:
        streak.append(f"Streak: x{state.win_streak}", style="bold yellow")

    t.add_row(bal, title, streak)
    return Panel(t, box=box.HORIZONTALS, border_style="bright_black", padding=(0, 0))


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
