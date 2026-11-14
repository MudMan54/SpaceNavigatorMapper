"""The macro step format and player (v108.141); no Qt needed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spnav_mapper import macros  # noqa: E402


class Clock:
    """schedule(ms, fn) on a virtual clock; run(ms) fires what is due."""

    def __init__(self):
        self.now, self.pending, self.log = 0, [], []

    def schedule(self, ms, fn):
        self.pending.append((self.now + ms, fn))

    def send(self, tokens, down):
        self.log.append((self.now, "+".join(tokens).upper(), "down" if down else "up"))

    def run(self, ms):
        end = self.now + ms
        while True:
            due = sorted((t, i) for i, (t, _) in enumerate(self.pending) if t <= end)
            if not due:
                break
            t, i = due[0]
            _, fn = self.pending.pop(i)
            self.now = t
            fn()
        self.now = end


def play(steps, run_ms=10_000, stop_at=None, tap_ms=45):
    clock, done = Clock(), []
    run = macros.MacroRun(
        steps, clock.send, clock.schedule, tap_ms=tap_ms, on_done=lambda: done.append(clock.now)
    )
    run.start()
    if stop_at is not None:
        clock.run(stop_at)
        run.stop()
    clock.run(run_ms)
    return clock.log, done, run


def test_normalize_keeps_valid_steps_only():
    raw = [
        {"tap": ["Ctrl", "S"]},
        {"delay": "250"},
        {"delay": 99_999},
        {"down": "shift"},
        {"up": []},
        {"nonsense": 1},
        "tap",
    ]
    assert macros.normalize_macro(raw) == [
        {"tap": ["ctrl", "s"]},
        {"delay": 250},
        {"delay": macros.MAX_DELAY_MS},
        {"down": ["shift"]},
    ]
    assert macros.normalize_macro(None) == []
    assert len(macros.normalize_macro([{"tap": ["a"]}] * 80)) == macros.MAX_STEPS


def test_step_text():
    assert [
        macros.step_text(s)
        for s in ({"tap": ["ctrl", "s"]}, {"down": ["shift"]}, {"up": ["shift"]}, {"delay": 100})
    ] == [
        "Tap CTRL+S",
        "Down SHIFT",
        "Up SHIFT",
        "Delay 100 ms",
    ]


def test_steps_play_in_order_with_their_timing():
    log, done, run = play(
        [{"tap": ["q"]}, {"delay": 100}, {"down": ["shift"]}, {"tap": ["w"]}, {"up": ["shift"]}]
    )
    assert log == [
        (0, "Q", "down"),
        (45, "Q", "up"),  # a tap holds the key for the tap time
        (145, "SHIFT", "down"),
        (145, "W", "down"),
        (190, "W", "up"),
        (190, "SHIFT", "up"),
    ]
    assert done == [190] and run.running is False


def test_stopping_releases_held_keys_and_plays_nothing_more():
    log, done, _ = play([{"down": ["shift"]}, {"tap": ["a"]}, {"delay": 500}, {"tap": ["b"]}], stop_at=20)
    # Stopped during the tap of A: A and Shift are released at once, B never plays.
    assert log == [(0, "SHIFT", "down"), (0, "A", "down"), (20, "A", "up"), (20, "SHIFT", "up")]
    assert done == [20]


def test_a_down_without_an_up_is_released_at_the_end():
    log, done, _ = play([{"down": ["ctrl"]}, {"delay": 30}])
    assert log == [(0, "CTRL", "down"), (30, "CTRL", "up")]
    assert done == [30]


def test_a_run_plays_once():
    log, _, run = play([{"tap": ["q"]}])
    run.start()  # a finished run does not play again
    assert [e[1:] for e in log] == [("Q", "down"), ("Q", "up")]


# ---------------------------------------------------------------------------
# Macro binds in the real AxisPanel (tests/macro_cases.py, fake Qt)
# ---------------------------------------------------------------------------
import json  # noqa: E402
import subprocess  # noqa: E402

import pytest  # noqa: E402

HERE = Path(__file__).resolve().parent
RUN = [["Q", "down"], ["Q", "up"], ["W", "down"], ["W", "up"]]


@pytest.fixture(scope="module")
def cases():
    out = subprocess.run(
        [sys.executable, "-I", str(HERE / "macro_cases.py")], capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def keys(events):
    return [e[1:] for e in events]


def starts(events, key="Q"):
    return [e[0] for e in events if e[1:] == [key, "down"]]


def test_once_plays_one_run_per_band_entry(cases):
    assert keys(cases["once"]) == RUN
    w_down = [e[0] for e in cases["once"] if e[1:] == ["W", "down"]][0]
    assert w_down - cases["once"][1][0] == 100  # the Delay step
    assert keys(cases["once per entry"]) == RUN * 2


def test_repeat_plays_every_repeat_ms_while_in_the_band(cases):
    runs = starts(cases["repeat"])
    assert keys(cases["repeat"]) == RUN * len(runs) and len(runs) == 4
    assert all(300 <= b - a < 320 for a, b in zip(runs, runs[1:]))


def test_repeat_never_overlaps_a_run(cases):
    events = cases["repeat never overlaps"]
    assert keys(events) == RUN * (len(events) // 4)
    ends = [e[0] for e in events if e[1:] == ["W", "up"]]
    assert all(start >= end for start, end in zip(starts(events)[1:], ends))


def test_leaving_the_band_finishes_the_run(cases):
    assert keys(cases["leaving finishes the run"]) == RUN


def test_stopping_releases_held_keys(cases):
    assert keys(cases["not allowed stops it"]) == [["SHIFT", "down"], ["SHIFT", "up"]]
    stopped = cases["clear keys stops it"]
    assert keys(stopped)[:2] == [["SHIFT", "down"], ["SHIFT", "up"]]
    assert stopped[1][0] < 300  # released at once, not after the 300 ms delay


def test_a_macro_bind_counts_as_a_band_for_noback(cases):
    assert keys(cases["noback below a macro bind"]) == [["A", "down"], ["A", "up"]] + RUN


def test_an_empty_macro_sends_nothing(cases):
    assert cases["empty macro"] == []
