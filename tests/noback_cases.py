"""Run NoBack / Tick axis strokes through the real AxisPanel; print results as JSON.

Started by test_noback.py in its own interpreter (fakeqt patches globals).
Each case is (binds, samples, options); a sample is (axis %, output allowed).
The result for a case is the key sequence, with a down+up pair shown as a tap.

Since v108.138 NoBack + / NoBack - are set per bind. The options plus= /
minus= are the whole-side NoBack + / NoBack - of older profiles: the binds get
them the way an old profile is loaded (axis_panel.bind_noback_from). A bind
with its own "noback_plus" / "noback_minus" keeps them.
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
    ("+".join(combo).upper(), "down" if down else "up")
)


class _Main:
    activated = True
    hys_pct = 3
    min_hold_ms = 60
    hold_ignore_max = True
    tap_down_ms = 45


class _Taps:
    """The window's tap sender, recording each tap (and its Tap Dwell) as one event (v108.167)."""

    def tap(self, combo, dwell_ms):
        EVENTS.append(("+".join(combo).upper(), "tap", dwell_ms))

    def release_all(self):
        pass


def panel(binds, plus=True, minus=True, dead=5, ignore_max=True):
    p = object.__new__(axis_panel.AxisPanel)
    p.mainwin = _Main()
    p.mainwin._tap_sender = _Taps()
    p.mainwin.hold_ignore_max = ignore_max
    p._status_cb = lambda s: None
    p.dead = dead
    p._reset_noback()
    p.binds = []
    for b in binds:
        full = {
            "direction": "Plus",
            "combo": None,
            "mode": "Hold",
            "min": 0,
            "max": 100,
            "comment": "",
            "active": False,
            "last_tap": 0.0,
            "repeat_ms": 60,
            "last_on_ts": 0.0,
            "dead": dead,
        }
        full.update(b)
        full["noback_plus"], full["noback_minus"] = axis_panel.bind_noback_from(
            b, {"suppress_plus": plus, "suppress_minus": minus}
        )
        p.binds.append(full)
    p._refresh_slot_btn = lambda *a, **k: None
    p._pulse_bind_button = lambda *a: None
    p.axis_name = "X"  # its value is shown in the panel's border title
    p._motion_timer = fakeqt.QTimer()
    p._motion_idle = fakeqt.QTimer()
    p.setStyleSheet = lambda *a: None
    return p


def sweep(*points, step=4):
    out = []
    for a, b in zip(points, points[1:]):
        n = max(1, int(abs(b - a) / step))
        out += [a + (b - a) * i / n for i in range(1, n + 1)]
    return out


def taps(events):
    out, i = [], 0
    while i < len(events):
        if events[i][1] == "tap":
            out.append(events[i][0])
            i += 1
        elif i + 1 < len(events) and events[i][1] == "down" and events[i + 1] == (events[i][0], "up"):
            out.append(events[i][0])
            i += 2
        else:
            out.append(f"{events[i][0]} {events[i][1]}")
            i += 1
    return out


def run(binds, samples, **options):
    EVENTS.clear()
    p = panel(binds, **options)
    for pct, allow in samples:
        env.advance(16)
        p.update_val(pct / 100.0, allow)
    return taps(list(EVENTS))


def on(path):
    return [(x, True) for x in path]


PR = lambda k, lo, hi, d="Plus": dict(combo=[k], mode="Press/Release", min=lo, max=hi, direction=d)
HOLD = lambda k, lo, hi, d="Plus": dict(combo=[k], mode="Hold", min=lo, max=hi, direction=d)
TICK = lambda k, at, d="Plus": dict(combo=[k], mode="Tick", min=at, direction=d)
AB = [PR("a", 10, 40), PR("b", 40, 100)]
# NoBack + / NoBack - set on this bind only (both by default).
NB = lambda bind, plus=True, minus=True: dict(bind, noback_plus=plus, noback_minus=minus)
OFF = dict(plus=False, minus=False)

CASES = {
    "noback off, push and return": (AB, on(sweep(0, 80, 0) + [0]), dict(plus=False, minus=False)),
    "push and return": (AB, on(sweep(0, 80, 0) + [0]), {}),
    "second push rearms after centring": (AB, on(sweep(0, 80, 0) + [0, 0] + sweep(0, 80, 0) + [0]), {}),
    "flick to the other side": (
        AB + [PR("c", 10, 40, "Minus"), PR("d", 40, 100, "Minus")],
        on(sweep(0, 80, step=8) + [-60, -30, -10, 0]),
        {},
    ),
    "partial return, push again": (AB, on(sweep(0, 80, 20, 80, 0) + [0]), {}),
    "hold binds": ([HOLD("a", 10, 40), HOLD("b", 40, 100)], on(sweep(0, 80, 0) + [0]), {}),
    "minus side": ([PR("c", 10, 40, "Minus"), PR("d", 40, 100, "Minus")], on(sweep(0, -80, 0) + [0]), {}),
    "noback plus only leaves minus alone": (
        [PR("c", 10, 40, "Minus"), PR("d", 40, 100, "Minus")],
        on(sweep(0, -80, 0) + [0]),
        dict(minus=False),
    ),
    "fast spring return": (AB, on([20, 35, 50, 65, 80, 50, 25, 0, 0]), {}),
    "rearm without dead zone": (AB, on(sweep(0.4, 80, 0.4) + [0.4, 0.4] + sweep(0.4, 80, 0.4)), dict(dead=0)),
    "rearm below every band": (AB, on(sweep(0, 80, 10, 80, 0) + [0]), {}),
    "focus lost mid-stroke": (
        AB,
        [(20, True), (50, True), (80, True), (70, False), (60, False), (30, True), (20, True), (0, True)],
        {},
    ),
    "hold jump past both bands": ([HOLD("a", 10, 40), HOLD("b", 40, 100)], on([8, 55, 70, 70, 0, 0]), {}),
    "tick counts as a higher band": ([PR("a", 10, 40), TICK("t", 60)], on(sweep(0, 80, 0) + [0]), {}),
    "lower tick ignores noback": (
        [PR("a", 10, 40), TICK("t", 30), PR("b", 40, 100)],
        on(sweep(0, 80, 20, 80, 0) + [0]),
        {},
    ),
    "tick crossed with a higher band still fires": (
        [TICK("t", 20), PR("b", 40, 100)],
        on([10, 70, 70, 0, 0]),
        {},
    ),
    "tick rearms after centring": (
        [PR("a", 10, 40), TICK("t", 60)],
        on(sweep(0, 80, 0) + [0, 0] + sweep(0, 80, 0) + [0]),
        {},
    ),
    # v108.138: NoBack per bind.
    "only the lowest bind has noback": (
        [NB(PR("a", 10, 40)), PR("b", 40, 70), PR("c", 70, 100)],
        on(sweep(0, 90, 0) + [0]),
        OFF,
    ),
    "only the middle bind has noback": (
        [PR("a", 10, 40), NB(PR("b", 40, 70)), PR("c", 70, 100)],
        on(sweep(0, 90, 0) + [0]),
        OFF,
    ),
    "noback on the highest bind changes nothing": (
        [PR("a", 10, 40), NB(PR("b", 40, 100))],
        on(sweep(0, 80, 0) + [0]),
        OFF,
    ),
    "a bind without noback fires below one with it": (
        [PR("a", 10, 40), NB(PR("b", 40, 70)), PR("c", 70, 100)],
        on(sweep(0, 90, 0) + [0, 0] + sweep(0, 90, 0) + [0]),
        OFF,
    ),
    "noback hold bind lets go on the way back": (
        [NB(HOLD("a", 10, 40)), HOLD("b", 40, 100)],
        on(sweep(0, 80, 0) + [0]),
        OFF,
    ),
    "noback on a tick bind is ignored": (
        [PR("a", 10, 40), NB(TICK("t", 30)), PR("b", 40, 100)],
        on(sweep(0, 80, 20, 80, 0) + [0]),
        OFF,
    ),
    "full bind with noback works on both sides": (
        [NB(PR("a", 10, 40, "Full")), PR("b", 40, 100, "Full")],
        on(sweep(0, 80, 0) + [0] + sweep(0, -80, 0) + [0]),
        OFF,
    ),
    "full bind with noback + only": (
        [NB(PR("a", 10, 40, "Full"), minus=False), PR("b", 40, 100, "Full")],
        on(sweep(0, 80, 0) + [0] + sweep(0, -80, 0) + [0]),
        OFF,
    ),
    "own setting wins over an old side setting": (
        [NB(PR("a", 10, 40), False, False), PR("b", 40, 100)],
        on(sweep(0, 80, 0) + [0]),
        dict(plus=True),
    ),
}

RESULTS = {name: run(b, s, **o) for name, (b, s, o) in CASES.items()}

# v108.166: each tap holds its key for its bind's Tap Dwell (the profile's when
# the bind has none; 0 to 200 ms).
RESULTS["tap dwell keys"] = run(
    [
        dict(PR("a", 10, 30), tap_ms=80),
        dict(TICK("t", 35), tap_ms=0),
        PR("b", 40, 60),
        dict(PR("c", 65, 100), tap_ms=250),
    ],
    on(sweep(0, 90) + [90]),
    **OFF,
)
RESULTS["tap dwell ms"] = [event[2] for event in EVENTS if event[1] == "tap"]

print(json.dumps(RESULTS))
