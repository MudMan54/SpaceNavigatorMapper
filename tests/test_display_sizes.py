"""Display 85% / 100% / 110%: every step makes the text, the menus and the controls larger (v108.154)."""

import json
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
FACTORS = (0.85, 1.0, 1.1)


@pytest.fixture(scope="module")
def sizes():
    out = {}
    for factor in FACTORS:
        run = subprocess.run(
            [sys.executable, "-I", str(HERE / "display_size_cases.py"), str(HERE.parent), str(factor)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert run.returncode == 0, run.stderr
        out[factor] = json.loads(run.stdout.strip().splitlines()[-1])
    return out


def test_text_follows_the_display_size(sizes):
    assert [sizes[f]["text"] for f in FACTORS] == [6.8, 8.0, 8.8]


def test_menus_grow_with_every_step(sizes):
    # Before v108.154 the headings were 9.8 pt at 85% but 8 pt at 100%, and the
    # menus 8.8 pt at 85% and 9 pt at 100%: only 85% added points.
    assert [sizes[f]["menu bar headings"] for f in FACTORS] == [9.8, 11.0, 11.8]
    assert [sizes[f]["menus"] for f in FACTORS] == [[8.8], [10.0], [10.8]]


def test_controls_grow_with_every_step(sizes):
    # Before v108.154 only 85% fitted the controls to their text: the axis
    # windows' boxes were no taller at 100% (the Bind Dir and Mode boxes, and
    # the - / + buttons, were shorter) although the text was larger.
    for name in sizes[1.0]["heights"]:
        heights = [sizes[f]["heights"][name] for f in FACTORS]
        assert heights[0] < heights[1] < heights[2], (name, heights)


def test_85_percent_is_unchanged(sizes):
    assert sizes[0.85]["heights"] == {
        "Bind button": 22,
        "comment": 22,
        "Bind Dir box": 26,
        "Mode box": 26,
        "- / + button": 22,
        "Button 1": 22,
    }
