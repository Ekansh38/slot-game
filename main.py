import sys
import time
import threading

import readchar
from rich.live import Live

import ui
from game import GameState
from upgrades import ALL_UPGRADES
from ui import get_selected_upgrade_id


def input_loop(state: GameState, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            key = readchar.readkey()
        except Exception:
            stop.set()
            break

        if key in (readchar.key.CTRL_C, "q", "Q"):
            stop.set()
            break

        elif key == " ":
            state.do_click()

        elif key in (readchar.key.ENTER, "\r", "\n"):
            if state.show_upgrades:
                uid = get_selected_upgrade_id(state)
                if uid:
                    state.buy_upgrade(uid)
            else:
                state.start_spin()

        elif key == readchar.key.UP:
            if state.show_upgrades:
                state.upgrade_cursor = max(0, state.upgrade_cursor - 1)
            else:
                state.adjust_bet(1)

        elif key == readchar.key.DOWN:
            if state.show_upgrades:
                state.upgrade_cursor = min(len(ALL_UPGRADES) - 1, state.upgrade_cursor + 1)
            else:
                state.adjust_bet(-1)

        elif key in ("u", "U"):
            state.show_upgrades = not state.show_upgrades

        elif key == "1":
            state.activate_ability("caffeine_rush")

        elif key == "2":
            state.activate_ability("time_warp")


def main() -> None:
    state = GameState.load()
    stop = threading.Event()

    thread = threading.Thread(target=input_loop, args=(state, stop), daemon=True)
    thread.start()

    last_save = time.time()
    frame_time = 1.0 / 60.0

    with Live(ui.render(state), refresh_per_second=60, screen=True) as live:
        while not stop.is_set():
            frame_start = time.time()
            state.tick()
            live.update(ui.render(state))

            now = time.time()
            if now - last_save >= 5.0:
                state.save()
                last_save = now

            elapsed = time.time() - frame_start
            sleep = frame_time - elapsed
            if sleep > 0:
                time.sleep(sleep)

    state.save()
    sys.exit(0)


if __name__ == "__main__":
    main()
