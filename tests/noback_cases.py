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
            "settle_ms": 0,  # the cases above "v108.177" run without Settle, as before it
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

# v108.177: Settle. A sample is 16 ms. The puck let go from 80%: it falls
# through the centre, swings to the other side and bounces back out to 42%.
SETTLE = lambda bind, ms=150: dict(bind, settle_ms=ms)
BOUNCE = [80, 40, 0, -15, 0, 20, 42, 30, 10, 0]  # back above 37% 64 ms after falling below it
REST = [0] * 12  # 192 ms at the centre
CROUCH_PRONE = lambda ms: [SETTLE(NB(HOLD("c", 37, 100)), ms), HOLD("ctrl", 68, 100)]
TICKS = lambda ms: [SETTLE(TICK("c", 37), ms), TICK("ctrl", 68)]
CASES.update(
    {
        "bounce, hold with noback, settle off": (CROUCH_PRONE(0), on(sweep(0, 80) + BOUNCE + REST), OFF),
        "bounce, hold with noback, settle on": (CROUCH_PRONE(150), on(sweep(0, 80) + BOUNCE + REST), OFF),
        "bounce, ticks, settle off": (TICKS(0), on(sweep(0, 80) + BOUNCE + REST), OFF),
        "bounce, ticks, settle on": (TICKS(150), on(sweep(0, 80) + BOUNCE + REST), OFF),
        # A hand comes back after the axis has rested: the lower bind works again.
        "settle: a push after resting": (
            TICKS(150),
            on(sweep(0, 80) + BOUNCE + REST + sweep(0, 45, 0)),
            OFF,
        ),
        # The rest must be unbroken: a push 64 ms after the bounce is still the spring's.
        "settle: a push too soon after the bounce": (
            TICKS(150),
            on(sweep(0, 80) + BOUNCE + [0, 0, 20, 45, 20, 0] + REST + sweep(0, 45, 0)),
            OFF,
        ),
        # The way out is never held: one fast push through both bands.
        "settle: fast push through both": (TICKS(150), on([10, 80, 80, 0] + REST + [10, 80, 0]), OFF),
        # Nothing above the bind: Settle never holds it.
        "settle: a bind with nothing above it": (
            [SETTLE(TICK("c", 37))],
            on(sweep(0, 80) + BOUNCE + REST),
            OFF,
        ),
        # A higher band that was not reached arms nothing.
        "settle: higher band not reached": (
            TICKS(150),
            on(sweep(0, 50) + [20, 0, -15, 0, 20, 42, 30, 0]),
            OFF,
        ),
        # Without NoBack (and not a Tick) Settle does not apply.
        "settle: not for a bind without noback": (
            [SETTLE(HOLD("c", 37, 100)), HOLD("ctrl", 68, 100)],
            on([20, 50, 80, 20, 0, -15, 0, 20, 42, 30, 10, 0]),
            OFF,
        ),
        # The other side has its own guard: the minus side is not held by the plus side.
        "settle: the other side is not held": (
            [SETTLE(TICK("c", 37, "Full")), TICK("ctrl", 68)],
            on(sweep(0, 80) + [80, 40, 0, -20, -42, -20, 0] + REST),
            OFF,
        ),
        # Press/Release with NoBack: quiet through the bounce, like Hold.
        "settle: press/release with noback": (
            [SETTLE(NB(PR("c", 37, 60))), PR("ctrl", 68, 100)],
            on(sweep(0, 80) + BOUNCE + REST + sweep(0, 45, 0)),
            OFF,
        ),
        # Output off during the bounce: the guard follows the stroke all the same.
        "settle: follows the stroke with output off": (
            TICKS(150),
            on(sweep(0, 80)) + [(x, False) for x in BOUNCE[:5]] + on(BOUNCE[5:] + REST),
            OFF,
        ),
    }
)

# v108.183: a bind switched off on its menu takes no part.
SWITCHED_OFF = lambda bind: dict(bind, enabled=False)
CASES.update(
    {
        "switched off: a hold sends nothing": (
            [SWITCHED_OFF(HOLD("c", 37, 100)), HOLD("ctrl", 68, 100)],
            on(sweep(0, 80, 0) + [0]),
            OFF,
        ),
        "switched off: a tick sends nothing": (
            [SWITCHED_OFF(TICK("c", 37)), TICK("ctrl", 68)],
            on(sweep(0, 80, 0) + [0]),
            OFF,
        ),
        # The higher bind is on: NoBack lets the lower one go on the way back from it.
        "higher bind on: noback sees it": (
            [NB(HOLD("c", 37, 100)), HOLD("ctrl", 68, 100)],
            on(sweep(0, 80, 50) + [50, 50]),
            OFF,
        ),
        # The higher bind is switched off: for the lower one it is not there.
        "higher bind switched off: no band for noback": (
            [NB(HOLD("c", 37, 100)), SWITCHED_OFF(HOLD("ctrl", 68, 100))],
            on(sweep(0, 80, 50) + [50, 50]),
            OFF,
        ),
        # ... nor for Rebound: the bounce after it taps the lower Tick, as with nothing above it.
        "higher bind switched off: no band for rebound": (
            [SETTLE(TICK("c", 37)), SWITCHED_OFF(TICK("ctrl", 68))],
            on(sweep(0, 80) + BOUNCE + REST),
            OFF,
        ),
    }
)

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


def history_marks(binds, samples):
    """What Axis History records for a stroke: (kind, bind number) of each event."""
    from spnav_mapper import axis_history

    EVENTS.clear()
    p = panel(binds, **OFF)
    p.history = axis_history.AxisHistory()
    for pct, allow in samples:
        env.advance(16)
        p.update_val(pct / 100.0, allow)
    return [[event[1], event[2] + 1] for event in p.history.events]


# v108.177: Axis History marks where Settle kept a bind quiet ("held by Settle").
RESULTS["settle marks, ticks"] = history_marks(TICKS(150), on(sweep(0, 80) + BOUNCE + REST))
RESULTS["settle marks, hold with noback"] = history_marks(CROUCH_PRONE(150), on(sweep(0, 80) + BOUNCE + REST))


# v108.187: Min Hold, per bind: a Hold bind's key stays down at least that long.
def hold_times(binds, samples, history=False):
    """[key, how long it was down in ms] for each press of a stroke (16 ms a sample).

    With `history`, what Axis History records instead: [kind, bind number, ms].
    """
    from spnav_mapper import axis_history

    down, held = {}, []

    def send(combo, is_down, status_callback=None):
        key = "+".join(combo).upper()
        if is_down:
            down[key] = fakeqt.CLOCK.ms
        else:
            held.append([key, round(fakeqt.CLOCK.ms - down.pop(key))])

    saved, axis_panel.send_combo = axis_panel.send_combo, send
    try:
        p = panel(binds, **OFF)
        if history:
            p.history = axis_history.AxisHistory()
        for pct, allow in samples:
            env.advance(16)
            p.update_val(pct / 100.0, allow)
    finally:
        axis_panel.send_combo = saved
    if history:
        return [[event[1], event[2] + 1, event[5]] for event in p.history.events]
    return held + [[key, "still down"] for key in down]


MIN_HOLD = lambda bind, ms: dict(bind, min_hold_ms=ms)
PRONE = HOLD("ctrl", 59, 100)  # starts at 64% with the 5% dead zone
FLICK = [0, 70, 30, 0] + [0] * 14  # in the band for one sample only
RESULTS["min hold: none, a flick lets go at once"] = hold_times([PRONE], on(FLICK))
RESULTS["min hold: 175 ms, a flick"] = hold_times([MIN_HOLD(PRONE, 175)], on(FLICK))
RESULTS["min hold: 175 ms, held longer"] = hold_times(
    [MIN_HOLD(PRONE, 175)], on([0] + [70] * 20 + [30, 0, 0])
)
RESULTS["min hold: back in the band meanwhile"] = hold_times(
    [MIN_HOLD(PRONE, 175)], on([0, 70, 30, 30, 70, 70, 30] + [0] * 14)
)
RESULTS["min hold: output goes off"] = hold_times(
    [MIN_HOLD(PRONE, 175)], [(0, True), (70, True), (70, True), (70, False), (70, False), (0, True)]
)
# NoBack lets the lower bind go on the way back from the higher one, but not before its Min Hold.
CROUCH = NB(HOLD("c", 32, 100))
QUICK = [0, 45, 80, 80, 50, 50] + [0] * 14
RESULTS["min hold: noback lets go at once without it"] = hold_times([CROUCH, PRONE], on(QUICK))
RESULTS["min hold: noback waits for it"] = hold_times([MIN_HOLD(CROUCH, 175), PRONE], on(QUICK))
# Axis History: each key-up with how long the key was held, each tap with its Tap Dwell.
RESULTS["min hold: history"] = hold_times(
    [MIN_HOLD(PRONE, 175), dict(TICK("t", 20), tap_ms=80)], on(FLICK), history=True
)
# 600 ms asked for: at most 500.
RESULTS["min hold: at most 500 ms"] = hold_times([MIN_HOLD(PRONE, 600)], on([0, 70, 0] + [0] * 40))

print(json.dumps(RESULTS))
