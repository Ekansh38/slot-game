import os
import select
import sys
import termios
import time

from rich.live import Live

import ui
from game import GameState
from upgrades import ALL_UPGRADES
from ui import get_selected_upgrade_id, UPGRADES_PER_PAGE


def _read_key() -> str | None:
    """Non-blocking read. Terminal must already be in raw mode."""
    if not select.select([sys.stdin], [], [], 0)[0]:
        return None
    ch = os.read(sys.stdin.fileno(), 1).decode("utf-8", errors="ignore")
    if ch == "\x1b":
        if select.select([sys.stdin], [], [], 0.05)[0]:
            ch2 = os.read(sys.stdin.fileno(), 1).decode("utf-8", errors="ignore")
            if ch2 == "[" and select.select([sys.stdin], [], [], 0.05)[0]:
                ch3 = os.read(sys.stdin.fileno(), 1).decode("utf-8", errors="ignore")
                return "\x1b[" + ch3
            return ch2
    return ch


def _handle_key(key: str, state: GameState) -> bool:
    """Returns True if the game should quit."""
    if key in ("\x03", "\x04", "q", "Q"):
        return True

    if key == " ":
        state.do_click()
    elif key in ("\r", "\n"):
        if state.show_upgrades:
            uid = get_selected_upgrade_id(state)
            if uid:
                state.buy_upgrade(uid)
        else:
            state.start_spin()
    elif key == "\x1b":  # bare ESC — close shop, or quit if shop already closed
        if state.show_upgrades:
            state.show_upgrades = False
        else:
            return True
    elif key in ("\x1b[A", "k"):  # up arrow or k
        if state.show_upgrades:
            state.upgrade_cursor = max(0, state.upgrade_cursor - 1)
            state.upgrade_scroll = min(state.upgrade_scroll, state.upgrade_cursor)
        else:
            state.adjust_bet(1)
    elif key in ("\x1b[B", "j"):  # down arrow or j
        if state.show_upgrades:
            state.upgrade_cursor = min(len(ALL_UPGRADES) - 1, state.upgrade_cursor + 1)
            if state.upgrade_cursor >= state.upgrade_scroll + UPGRADES_PER_PAGE:
                state.upgrade_scroll = state.upgrade_cursor - UPGRADES_PER_PAGE + 1
        else:
            state.adjust_bet(-1)
    elif key in ("u", "U"):
        state.show_upgrades = not state.show_upgrades
    elif key == "1":
        state.activate_ability("caffeine_rush")
    elif key == "2":
        state.activate_ability("time_warp")

    return False


def main() -> None:
    state = GameState.load()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    frame_time = 1.0 / 60.0

    # Enter Live first so Rich initializes the screen cleanly,
    # then switch to raw mode so our non-blocking reads work.
    # auto_refresh=False disables Rich's internal render timer —
    # we drive every repaint ourselves via update(refresh=True).
    with Live(ui.render(state), auto_refresh=False, screen=True) as live:
        # Custom terminal mode: disable echo, canonical, and signal generation
        # (so Ctrl-C sends \x03 as a raw char) but keep OPOST so that Rich's
        # \n output is still converted to \r\n by the terminal driver.
        # setraw() kills OPOST and breaks Rich's rendering entirely.
        new = termios.tcgetattr(fd)
        new[3] &= ~(termios.ECHO | termios.ICANON | termios.ISIG)
        new[6][termios.VMIN] = 1
        new[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        try:
            while True:
                frame_start = time.time()

                key = _read_key()
                if key and _handle_key(key, state):
                    break

                state.tick()
                live.update(ui.render(state), refresh=True)

                if state._save_now or state._change_count >= 30:
                    state.save()
                    state._change_count = 0
                    state._save_now = False

                elapsed = time.time() - frame_start
                remaining = frame_time - elapsed
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    state.save()


if __name__ == "__main__":
    main()
