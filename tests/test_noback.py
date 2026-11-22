"""NoBack and Tick behaviour of the real AxisPanel (README: v108.101, v108.117, v108.138).

The cases above "v108.138" were written for NoBack + / NoBack - on a whole
axis side; they now run with those settings loaded into each bind the way an
old profile is, and must behave exactly as before.
"""

import json
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent

EXPECTED = {
    # Without NoBack the lower bind fires again on the way back.
    "noback off, push and return": ["A", "B", "A"],
    "push and return": ["A", "B"],
    "second push rearms after centring": ["A", "B", "A", "B"],
    "flick to the other side": ["A", "B", "D"],
    "partial return, push again": ["A", "B", "B"],
    "hold binds": ["A down", "B down", "A up", "B up"],
    "minus side": ["C", "D"],
    "noback plus only leaves minus alone": ["C", "D", "C"],
    "fast spring return": ["A", "B"],
    "rearm without dead zone": ["A", "B", "A", "B"],
    "rearm below every band": ["A", "B", "A", "B"],
    "focus lost mid-stroke": ["A", "B", "B up"],
    "hold jump past both bands": ["A down", "B down", "A up", "B up"],
    "tick counts as a higher band": ["A", "T"],
    # v108.162: a Tick has no NoBack: it fires each time it is crossed going out.
    "lower tick ignores noback": ["A", "T", "B", "T", "B"],
    "tick crossed with a higher band still fires": ["T", "B"],
    "tick rearms after centring": ["A", "T", "A", "T"],
    # v108.138: NoBack + / NoBack - per bind. Every bind still counts as a
    # band; only the binds with NoBack on that side stay quiet on the way back.
    "only the lowest bind has noback": ["A", "B", "C", "B"],
    "only the middle bind has noback": ["A", "B", "C", "A"],
    "noback on the highest bind changes nothing": ["A", "B", "A"],
    "a bind without noback fires below one with it": ["A", "B", "C", "A", "A", "B", "C", "A"],
    "noback hold bind lets go on the way back": ["A down", "B down", "A up", "B up"],
    "noback on a tick bind is ignored": ["A", "T", "B", "A", "T", "B", "A"],
    "full bind with noback works on both sides": ["A", "B", "A", "B"],
    "full bind with noback + only": ["A", "B", "A", "B", "A"],
    "own setting wins over an old side setting": ["A", "B", "A"],
    # v108.177: Settle. The puck let go from the higher band bounces back out
    # past the lower bind: without Settle the spring sends the lower key.
    "bounce, hold with noback, settle off": ["C down", "CTRL down", "C up", "CTRL up", "C"],
    "bounce, hold with noback, settle on": ["C down", "CTRL down", "C up", "CTRL up"],
    "bounce, ticks, settle off": ["C", "CTRL", "C"],
    "bounce, ticks, settle on": ["C", "CTRL"],
    "settle: a push after resting": ["C", "CTRL", "C"],
    "settle: a push too soon after the bounce": ["C", "CTRL", "C"],
    "settle: fast push through both": ["C", "CTRL", "C", "CTRL"],
    "settle: a bind with nothing above it": ["C", "C"],
    "settle: higher band not reached": ["C", "C"],
    "settle: not for a bind without noback": ["C down", "CTRL down", "C up", "CTRL up", "C"],
    "settle: the other side is not held": ["C", "CTRL", "C"],
    "settle: press/release with noback": ["C", "CTRL", "C"],
    "settle: follows the stroke with output off": ["C", "CTRL"],
    # v108.183: a bind switched off on its menu sends nothing ...
    "switched off: a hold sends nothing": ["CTRL"],
    "switched off: a tick sends nothing": ["CTRL"],
    # ... and is no band for the others: NoBack lets the lower bind go on the way back from a
    # higher one that is on, and holds it on when the higher one is switched off;
    "higher bind on: noback sees it": ["C down", "CTRL down", "C up", "CTRL up"],
    "higher bind switched off: no band for noback": ["C down"],
    # Rebound has nothing above the lower Tick to guard against.
    "higher bind switched off: no band for rebound": ["C", "C"],
}


@pytest.fixture(scope="module")
def results():
    out = subprocess.run(
        [sys.executable, "-I", str(HERE / "noback_cases.py")],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(out.stdout)


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_noback(results, case):
    assert results[case] == EXPECTED[case]


def test_each_tap_holds_its_binds_tap_dwell(results):
    # v108.166: A has a Tap Dwell of 80 ms, the Tick 0 ms, B none (the profile's 45 ms),
    # C 250 ms (held at most 200 ms).
    assert results["tap dwell keys"] == ["A", "T", "B", "C"]
    assert results["tap dwell ms"] == [80, 0, 45, 200]


def test_axis_history_marks_where_settle_kept_a_bind_quiet(results):
    # v108.177: the bounce's crossing is marked "held by Rebound" for the lower bind,
    # and only once: nothing more is marked while the axis rests.
    assert results["settle marks, ticks"] == [["tap", 1], ["tap", 2], ["rebound-held", 1]]
    assert results["settle marks, hold with noback"] == [
        ["down", 1],
        ["down", 2],
        ["noback-up", 1],
        ["up", 2],
        ["rebound-held", 1],
    ]


def test_min_hold_keeps_a_hold_binds_key_down(results):
    # v108.187: without a Min Hold, a flick through the band holds the key for one 16 ms sample
    # (the profile's 60 ms guard is passed by well below the band); with one, for that long.
    assert results["min hold: none, a flick lets go at once"] == [["CTRL", 16]]
    assert results["min hold: 175 ms, a flick"] == [["CTRL", 176]]  # the first sample at or past 175 ms
    # Held longer than its Min Hold, the key is let go at once on leaving the band.
    assert results["min hold: 175 ms, held longer"] == [["CTRL", 320]]
    # Back in the band before the Min Hold is over: still one press.
    assert results["min hold: back in the band meanwhile"] == [["CTRL", 176]]
    # Output off (the Target, another window in front) lets go at once, Min Hold or not.
    assert results["min hold: output goes off"] == [["CTRL", 32]]
    assert results["min hold: at most 500 ms"] == [["CTRL", 512]]


def test_min_hold_is_kept_when_noback_lets_go(results):
    # v108.187: NoBack lets the lower bind go on the way back from the higher one,
    # but not before the lower bind's Min Hold.
    assert results["min hold: noback lets go at once without it"] == [["C", 48], ["CTRL", 32]]
    assert results["min hold: noback waits for it"] == [["CTRL", 32], ["C", 176]]


def test_axis_history_records_how_long_a_key_was_held(results):
    # v108.187: a key-up carries the time its key was down, a tap its Tap Dwell.
    assert results["min hold: history"] == [["down", 1, None], ["tap", 2, 80.0], ["up", 1, 176.0]]
