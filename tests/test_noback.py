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
