import os
import select
import sys
import termios
import time

from rich.live import Live

import sound
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
    """Returns True if the game should quit. Space is handled by the main loop."""
    if key in ("\x03", "\x04", "q", "Q"):
        return True

    if key in ("\r", "\n"):
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
    elif key in ("m", "M"):
        if not state.show_upgrades:
            state.toggle_all_in()
    elif key in ("b", "B"):
        if not state.show_upgrades:
            state.bet_input_mode = True
            state.bet_input_buf = ""
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

    space_dirty = False

    with Live(ui.render(state), auto_refresh=False, screen=True) as live:
        new = termios.tcgetattr(fd)
        new[3] &= ~(termios.ECHO | termios.ICANON)  # keep ISIG so Ctrl-C raises KeyboardInterrupt
        new[6][termios.VMIN] = 1
        new[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        try:
            while True:
                frame_start = time.time()

                space_seen = False
                quit_requested = False
                while True:
                    key = _read_key()
                    if key is None:
                        break
                    if key in ("\x03", "\x04", "q", "Q"):
                        quit_requested = True
                        break
                    elif key == " ":
                        space_seen = True
                    elif state.bet_input_mode:
                        if key in ("\r", "\n"):
                            if state.bet_input_buf:
                                try:
                                    amount = float(state.bet_input_buf)
                                    if amount > 0:
                                        state.bet_custom = amount
                                        state.bet_all_in = False
                                except ValueError:
                                    pass
                            state.bet_input_mode = False
                            state.bet_input_buf = ""
                        elif key == "\x1b":
                            state.bet_input_mode = False
                            state.bet_input_buf = ""
                        elif key in ("\x7f", "\x08"):
                            state.bet_input_buf = state.bet_input_buf[:-1]
                        elif key.isdigit() or (key == "." and "." not in state.bet_input_buf):
                            state.bet_input_buf += key
                        elif key.lower() in ("k", "m", "b", "t"):
                            _MULT = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "t": 1_000_000_000_000}
                            try:
                                base = float(state.bet_input_buf) if state.bet_input_buf else 1.0
                                amount = base * _MULT[key.lower()]
                                if amount > 0:
                                    state.bet_custom = amount
                                    state.bet_all_in = False
                            except ValueError:
                                pass
                            state.bet_input_mode = False
                            state.bet_input_buf = ""
                    elif _handle_key(key, state):
                        quit_requested = True
                        break
                if quit_requested:
                    break

                if space_seen:
                    if not space_dirty:
                        state.do_click()
                    space_dirty = True
                else:
                    space_dirty = False

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
            sound.stop()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    state.save()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "restart":
        if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")):
            os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json"))
            print("Save deleted. Starting fresh.")
        else:
            print("No save found. Starting fresh.")
    main()
