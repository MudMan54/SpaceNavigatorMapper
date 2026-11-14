"""Macro binds in the real AxisPanel under the fake Qt (v108.141); prints JSON.

Like noback_cases: a panel is driven with axis samples every 16 ms of the
virtual clock; every key sent is recorded with its time.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import fakeqt  # noqa: E402

env = fakeqt.install()
from spnav_mapper.ui import axis_panel  # noqa: E402

EVENTS = []
axis_panel.send_combo = lambda combo, down, status_callback=None: EVENTS.append(
    (round(fakeqt.CLOCK.ms), "+".join(combo).upper(), "down" if down else "up")
)


class _Main:
    activated = True
    hys_pct = 3
    min_hold_ms = 60
    hold_ignore_max = True
    tap_down_ms = 45


def panel(binds):
    p = object.__new__(axis_panel.AxisPanel)
    p.mainwin = _Main()
    p._status_cb = lambda s: None
    p.dead = 0
    p._reset_noback()
    p.binds = []
    for b in binds:
        full = {
            "direction": "Plus",
            "combo": None,
            "mode": "Hold",
            "min": 0,
            "max": 100,
            "active": False,
            "last_tap": 0.0,
            "repeat_ms": 100,
            "last_on_ts": 0.0,
            "dead": 0,
            "macro": [],
            "macro_repeat": False,
        }
        full.update(b)
        p.binds.append(full)
    p._refresh_slot_btn = lambda *a, **k: None
    p._pulse_bind_button = lambda *a: None
    p.axis_name = "X"
    p._motion_timer = fakeqt.QTimer()
    p._motion_idle = fakeqt.QTimer()
    p.setStyleSheet = lambda *a: None
    return p


def drive(p, samples, after_ms=1000):
    """Each sample is (axis %, output allowed) or ("stop",) to clear keys there."""
    start = round(fakeqt.CLOCK.ms)
    for sample in samples:
        env.advance(16)
        if sample == ("stop",):
            p.clear_keys()
            continue
        pct, allow = sample
        p.update_val(pct / 100.0, allow)
    env.advance(after_ms)
    return [[t - start, key, how] for t, key, how in EVENTS]


def hold(pct, ms, allow=True):
    return [(pct, allow)] * max(1, ms // 16)


def case(binds, samples, after_ms=1000):
    EVENTS.clear()
    return drive(panel(binds), samples, after_ms)


QW = [{"tap": ["q"]}, {"delay": 100}, {"tap": ["w"]}]  # 190 ms a run
MACRO = lambda steps=QW, repeat=False, lo=20, hi=100, **k: dict(
    mode="Macro", macro=steps, macro_repeat=repeat, min=lo, max=hi, **k
)

CASES = {
    # Plays once on entering the band, even while the axis stays there.
    "once": case([MACRO()], [(0, True)] + hold(50, 800) + [(0, True)]),
    # Each entry plays it again.
    "once per entry": case([MACRO()], hold(50, 400) + hold(0, 100) + hold(50, 400) + [(0, True)]),
    # Repeat: every 300 ms (start to start) while in the band.
    "repeat": case([MACRO(repeat=True, repeat_ms=300)], hold(50, 1000) + [(0, True)]),
    # A Repeat shorter than the macro never overlaps: the next run waits.
    "repeat never overlaps": case([MACRO(repeat=True, repeat_ms=50)], hold(50, 600) + [(0, True)]),
    # Leaving the band lets the playing run finish, then nothing more.
    "leaving finishes the run": case([MACRO(repeat=True, repeat_ms=300)], hold(50, 60) + hold(0, 600)),
    # Output not allowed (Target off / other window): stopped at once, keys released.
    "not allowed stops it": case(
        [MACRO(steps=[{"down": ["shift"]}, {"delay": 300}, {"tap": ["e"]}])],
        hold(50, 100) + hold(50, 100, allow=False) + [(0, True)],
    ),
    # clear_keys (Target OFF, exit) stops it and releases its keys.
    "clear keys stops it": case(
        [MACRO(steps=[{"down": ["shift"]}, {"delay": 300}, {"tap": ["e"]}])],
        hold(50, 100) + [("stop",)] + hold(50, 300) + [(0, True)],
    ),
    # A macro bind is a band for NoBack: the lower bind stays quiet on the way back.
    "noback below a macro bind": case(
        [
            dict(combo=["a"], mode="Press/Release", min=10, max=40, noback_plus=True),
            MACRO(lo=40),
        ],
        [(x, True) for x in list(range(0, 81, 4)) + list(range(80, -1, -4))],
    ),
    # Macro mode with no steps sends nothing.
    "empty macro": case([MACRO(steps=[])], hold(50, 300) + [(0, True)]),
}

print(json.dumps(CASES))
