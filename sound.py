import queue
import threading
import numpy as np

try:
    import sounddevice as sd
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

SAMPLE_RATE = 44100

# Single worker thread — portaudio is not thread-safe; only ever call sd.play()
# from one thread.
_q: queue.Queue = queue.Queue(maxsize=4)  # drop old sounds if flooded


def _worker() -> None:
    while True:
        samples = _q.get()
        if samples is None:
            return
        try:
            sd.play(samples, SAMPLE_RATE)
            sd.wait()
        except Exception:
            pass


if _AVAILABLE:
    _thread: threading.Thread | None = threading.Thread(target=_worker, daemon=True)
    _thread.start()
else:
    _thread = None


def stop() -> None:
    """Stop audio cleanly. Call before process exit to avoid PortAudio errors."""
    if not _AVAILABLE:
        return
    try:
        sd.stop()
    except Exception:
        pass
    try:
        _q.put_nowait(None)  # sentinel — tells worker to exit
    except queue.Full:
        pass


def _play(samples: np.ndarray) -> None:
    if not _AVAILABLE:
        return
    try:
        _q.put_nowait(samples)
    except queue.Full:
        pass  # drop if worker is busy — never block the game loop


def _sine(freq: float, dur: float, vol: float = 0.3) -> np.ndarray:
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), False)
    w = np.sin(2 * np.pi * freq * t) * vol
    fade = min(int(0.015 * SAMPLE_RATE), len(w))
    w[-fade:] *= np.linspace(1, 0, fade)
    return w.astype(np.float32)


def _square(freq: float, dur: float, vol: float = 0.2) -> np.ndarray:
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), False)
    w = np.sign(np.sin(2 * np.pi * freq * t)) * vol
    fade = min(int(0.015 * SAMPLE_RATE), len(w))
    w[-fade:] *= np.linspace(1, 0, fade)
    return w.astype(np.float32)


def _sweep(f0: float, f1: float, dur: float, vol: float = 0.3) -> np.ndarray:
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), False)
    freqs = np.linspace(f0, f1, len(t))
    phase = np.cumsum(freqs / SAMPLE_RATE) * 2 * np.pi
    w = np.sin(phase) * vol
    fade = min(int(0.015 * SAMPLE_RATE), len(w))
    w[-fade:] *= np.linspace(1, 0, fade)
    return w.astype(np.float32)


def _gap(dur: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * dur), dtype=np.float32)


def play_click() -> None:
    _play(_sine(660, 0.04, 0.18))


def play_spin_start() -> None:
    _play(_sweep(200, 900, 0.15))


def play_reel_stop() -> None:
    _play(_square(220, 0.08, 0.22))


def play_tease() -> None:
    parts = []
    for f in [523, 659, 784]:
        parts += [_sine(f, 0.07, 0.22), _gap(0.02)]
    _play(np.concatenate(parts))


def play_win() -> None:
    _play(np.concatenate([_sine(f, 0.09, 0.22) for f in [523, 659, 784]]))


def play_big_win() -> None:
    chord = sum(_sine(f, 0.45, 0.13) for f in [523, 659, 784])  # type: ignore[arg-type]
    _play(chord.astype(np.float32))


def play_jackpot() -> None:
    seq = [(523, 0.10), (659, 0.10), (784, 0.10), (1047, 0.12),
           (784, 0.10), (1047, 0.12), (1319, 0.50)]
    _play(np.concatenate([_sine(f, d, 0.28) for f, d in seq]))


def play_loss() -> None:
    _play(_sweep(300, 120, 0.30, 0.18))


def play_upgrade() -> None:
    _play(np.concatenate([_sine(880, 0.07, 0.22), _sine(1100, 0.13, 0.22)]))


def play_active_ability() -> None:
    _play(_sweep(400, 1400, 0.20, 0.28))
