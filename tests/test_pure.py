"""Unit tests for the modules that need neither Qt nor Windows."""

import json

import pytest

from spnav_mapper import auto_profiles, backups, devices, keyboard_io, win32
from spnav_mapper.ui import monitor_scale, scaling, system_font, window_placement


# --- HID report decoding -----------------------------------------------------
def test_translation_and_rotation_reports():
    assert devices._parse_sn_report([1, 0x5E, 0x01, 0xA2, 0xFE, 0, 0]) == ("translation", (350, -350, 0))
    assert devices._parse_sn_report([2, 1, 0, 2, 0, 3, 0]) == ("rotation", (1, 2, 3))
    assert devices._parse_sn_report([3, 0x03, 0x00]) == ("buttons", 3)
    assert devices._parse_sn_report([9, 0]) is None
    assert devices._sat(1.4) == 1.0 and devices._sat(-2) == -1.0 and devices._sat(0.25) == 0.25


# --- Key combinations -----------------------------------------------------------
def test_key_combinations():
    assert keyboard_io.key_to_scancode("A") == (0x1E, False)
    assert keyboard_io.key_to_scancode("left") == (0x4B, True)
    assert keyboard_io.normalize_combo_tokens(["ctrl", "s"]) == (["ctrl"], ["s"])
    assert keyboard_io.combo_to_text(["ctrl", "shift", "f5"]) == "CTRL+SHIFT+F5"
    assert keyboard_io.combo_to_text(None) == ""


# --- Target filter ------------------------------------------------------------------
@pytest.mark.parametrize(
    "title, exe, cls, omitted",
    [
        ("My Game", r"D:\Games\game.exe", "UnityWndClass", False),
        ("Command Prompt", r"D:\Tools\cmd.exe", "ConsoleWindowClass", True),
        ("Notepad", r"C:\Windows\notepad.exe", "Notepad", True),
        ("Windows PowerShell", r"D:\ps\pwsh.exe", "x", True),
        ("SpaceNavigator Mapper — game", r"D:\Apps\SpaceNavigatorMapper.exe", "Qt", False),
        ("SPNav Key Mapper — v108", r"D:\Apps\python.exe", "Qt", True),
    ],
)
def test_target_filter(monkeypatch, title, exe, cls, omitted):
    monkeypatch.setattr(win32, "OMIT_PATH_PREFIXES", [r"c:\windows"])
    assert win32.is_omitted_target(title, exe, cls) is omitted


def test_matches_any_is_case_insensitive():
    assert win32.matches_any("PowerShell.EXE", ["powershell*.exe"])
    assert not win32.matches_any("game.exe", ["cmd.exe"])


# --- Auto-Profiles rules --------------------------------------------------------------
def test_auto_profiles_pick_by_priority(tmp_path):
    for name in ("racing.json", "racing_alt.json", "notes.json"):
        (tmp_path / name).write_text("{}")
    cfg = tmp_path / "auto_profiles.json"
    cfg.write_text(
        json.dumps(
            {
                "groups": [
                    {
                        "name": "Racing",
                        "match": {"exe": ["race*.exe"]},
                        "profiles": [
                            {"path": str(tmp_path / "racing_alt.json"), "priority": 5},
                            {"path": str(tmp_path / "racing.json"), "priority": 1},
                            {"path": str(tmp_path / "missing.json"), "priority": 0},
                        ],
                    },
                    {
                        "name": "Off",
                        "enabled": False,
                        "match": {"exe": ["notes.exe"]},
                        "profiles": [{"path": str(tmp_path / "notes.json")}],
                    },
                ]
            }
        )
    )
    manager = auto_profiles.AutoProfileManager(str(cfg))
    manager.load()
    assert manager.pick_profile_for("Race2026.exe", "", "") == str(tmp_path / "racing.json")
    assert manager.pick_profile_for("notes.exe", "", "") == ""  # disabled group
    assert [p for p, _ in manager.candidates_for_current("race.exe", "", "")] == [
        str(tmp_path / "racing.json"),
        str(tmp_path / "racing_alt.json"),
    ]


# --- Backups -------------------------------------------------------------------------------
def test_save_with_backup_and_restore(tmp_path):
    profile = tmp_path / "game.json"
    backup_dir = tmp_path / "backups"
    backups.save_with_backup(profile, {"axes": {"X": {}}, "n": 1}, backup_dir)
    backups.save_with_backup(profile, {"axes": {"X": {}}, "n": 2}, backup_dir)
    assert json.loads(profile.read_text())["n"] == 2
    saved = backups.list_backups(backup_dir)
    assert len(saved) == 2
    restored = backups.restore_backup(saved[-1], tmp_path)
    assert json.loads(restored.read_text())["axes"] == {"X": {}}
    bad = tmp_path / "not_a_profile.json"
    bad.write_text("[1, 2]")
    with pytest.raises(ValueError):
        backups.restore_backup(bad, tmp_path)


# --- Window placement records ----------------------------------------------------------------
def test_read_views_understands_every_layout():
    assert window_placement.read_views({"views": {"compact": {"x": 1}, "junk": {}}}) == {"compact": {"x": 1}}
    assert window_placement.read_views({"compact_geometry_v10863": {"x": 2}}) == {"compact": {"x": 2}}
    legacy = window_placement.read_views({"window_geometry": {"x": 3}, "mode": "full"})
    assert legacy["full"]["x"] == 3


def test_client_rect_keeps_window_on_screen():
    area = (0, 0, 1920, 1040)
    margins = (8, 31, 8, 8)
    assert window_placement.client_rect({"relative_x": 100, "relative_y": 50}, area, (400, 200), margins) == (
        100,
        50,
        400,
        200,
    )
    x, y, w, h = window_placement.client_rect(
        {"relative_x": 5000, "relative_y": -50}, area, (400, 200), margins
    )
    assert (x, y) == (1920 - 8 - 400, 31) and (w, h) == (400, 200)


def test_saved_view_record():
    # v108.137: the editor's record first; files from older versions may hold
    # only the removed compact view's record, which still names the monitor.
    both = {"views": {"compact": {"screen_name": "A"}, "full": {"screen_name": "F"}}}
    assert scaling.saved_view_record(both)["screen_name"] == "F"
    assert scaling.saved_view_record({"views": {"compact": {"screen_name": "A"}}})["screen_name"] == "A"
    assert scaling.saved_view_record({"compact_geometry_v10863": {"screen_name": "B"}})["screen_name"] == "B"
    assert scaling.saved_view_record(None) == {}


# --- Per-monitor scaling -------------------------------------------------------------------------
def mon(name, w, h, dpi, primary=False):
    return {"name": name, "work_w": w, "work_h": h, "dpi": dpi, "primary": primary}


@pytest.mark.parametrize(
    "monitors",
    [
        [mon("A", 3840, 2100, 144, True), mon("B", 1920, 1040, 96)],
        [mon("A", 2560, 1400, 96, True), mon("B", 1920, 1040, 96)],
        [mon("A", 1920, 1032, 120, True), mon("B", 3840, 2100, 168)],
    ],
)
@pytest.mark.parametrize("ui_factor", [0.85, 1.0, 1.10])
def test_each_monitor_gets_its_own_physical_size(monitors, ui_factor):
    factors, home = monitor_scale.screen_factors([dict(m) for m in monitors], "", ui_factor)
    home_monitor = next(m for m in monitors if m["name"] == home)
    baked = monitor_scale.monitor_layout_scale(home_monitor, ui_factor)
    for m in monitors:
        wanted = monitor_scale.monitor_layout_scale(m, ui_factor) * m["dpi"] / 96
        assert abs(baked * factors[m["name"]] - wanted) / wanted < 0.002
        assert factors[m["name"]] >= 0.999  # Qt 5 loses 1-px lines below 1.0


# --- Fitting the editor to smaller screens (v108.151) ---------------------------------------------
def test_fit_factor():
    # Qt's available area (logical pixels) -> how much smaller the editor is drawn.
    assert scaling.fit_factor(1706, 912) == 1.0  # 3840x2160 at 225%: the reference look
    assert scaling.fit_factor(1920, 1032) == 1.0  # 1920x1080 at 100%
    assert scaling.fit_factor(1536, 816) == 0.904  # 1920x1080 at 125%
    assert scaling.fit_factor(1280, 672) == 0.747  # 1920x1080 at 150%
    assert scaling.fit_factor(400, 300) == scaling.FIT_MIN
    assert scaling.fit_factor(None, 0) == 1.0 and scaling.fit_factor("x", 900) == 1.0


@pytest.mark.parametrize("dpi, taskbar", [(96, 48), (120, 60), (144, 72)])
@pytest.mark.parametrize("ui_factor", [0.85, 1.0])
def test_1080p_editor_is_no_larger_a_share_of_the_screen_than_4k_at_225(dpi, taskbar, ui_factor):
    # Before v108.151 the editor took 12% more of a 1080p screen at 125%, and
    # 36% more at 150%, than of a 3840x2160 screen at 225%.
    def share(m):
        return monitor_scale.monitor_layout_scale(m, ui_factor) * m["dpi"] / 96 / m["work_h"]

    reference = share(mon("4K", 3840, 2160 - 108, 216))
    small = share(mon("1080p", 1920, 1080 - taskbar, dpi))
    assert small <= reference * 1.03


def test_layout_scale_floor():
    assert scaling.effective_scale(0.45, 0.85 * 0.5) == 0.24
    assert scaling.effective_scale(0.45, 0.85 * 0.747) == 0.286


def test_axis_history_noback():
    # v108.158: NoBack shown in white: its binds' start lines, the highest band
    # reached while it is in force (shaded to centre), and the binds it held back.
    from spnav_mapper import axis_history

    clock = [0.0]
    history = axis_history.AxisHistory(keep_s=30, clock=lambda: clock[0])
    for t, side, level in [(1.0, "+", 16), (1.5, "+", 40), (1.6, "+", 40), (3.0, None, 40), (4.0, "-", -1)]:
        clock[0] = t
        history.set_noback(side, level)
    # only changes are kept: on at 16, up to 40, off (centre), still off
    assert list(history.noback) == [(1.0, "+", 16), (1.5, "+", 40), (3.0, None, -1)]
    assert history.noback_span(10.0, 8.4) == [(1.5, "+", 40), (3.0, None, -1)]  # with the state at the start
    bands = [(0, "+", 16, "A", "+"), (1, "+", 40, "B", ""), (2, "-", 20, "C", "-")]
    shapes = axis_history.drawing([], [], bands, 5, 10.0, 10, 456, 240, noback=history.noback_span(10.0, 10))
    # 10 s over the plot (x 56..x1); +100% at y 14, centre 114
    x1 = next(s for s in shapes if s[0] == "line" and s[5] == "plus100")[3]
    per_s = (x1 - 56) / 10
    # v108.161: a thin dashed line, no shading (it looked like blocks around the axis's line)
    assert not [s for s in shapes if s[0] == "rect" and s[5] != "deadzone"]
    level = [s for s in shapes if s[0] == "line" and s[5] == "noback"][1]
    assert level[1:] == (
        pytest.approx(56 + 1.5 * per_s),
        74.0,
        pytest.approx(56 + 3 * per_s),
        74.0,
        "noback",
        1.0,
        True,
    )
    labels = {s[3]: s[4] for s in shapes if s[0] == "text"}
    assert labels["NoBack 16%"] == labels["NoBack 40%"] == "noback"
    # In the labels' column: NoBack for Bind #1 (Bind #2 is higher on that side), none for
    # Bind #2, and Bind #3 alone on its side: nothing to hold.
    assert labels["NoBack"] == "noback" and labels["NoBack: nothing to hold"] == "noback"
    assert labels["16%"] == "bind1" and labels["40%"] == "bind2" and labels["−20%"] == "bind3"
    held = axis_history.drawing([], [(5.0, "held", 0, "A", 0.2)], bands, 5, 10.0, 10, 900, 240)
    assert [s[4:] for s in held if s[0] == "circle" and s[3] == 5.0] == [("noback", False)]  # hollow, light
    assert ("A held by NoBack", "noback") in [(s[3], s[4]) for s in held if s[0] == "text"]


def test_axis_history_keys_not_sent():
    # v108.156: what binds would have sent while output was off, marked "not sent".
    from spnav_mapper import axis_history

    assert axis_history.unsent("tap") == "unsent-tap" and axis_history.unsent("held") == "held"
    history, clock = _history(
        [(0.0, 0.0), (0.5, 0.3), (1.0, 0.6), (1.5, 0.0)],
        [(0.5, "unsent-tap", 0, "A"), (1.0, "tap", 0, "A"), (1.5, "unsent-down", 1, "B")],
    )
    samples, events = history.span(clock[0], 10)
    assert axis_history.summary(samples, events) == (
        "Peak +60%, −0% · Bind #1 tapped 1× · Bind #1 tapped 1× (not sent) · Bind #2 pressed 1× (not sent)"
    )
    rows = axis_history.csv_rows([("X", samples, events)])
    assert ("X", "0.500", "30.0", "tap (not sent)", "Bind #1", "A", "") in rows
    shapes = axis_history.drawing(samples, events, [], 5, clock[0], 10, 456, 240)
    # v108.159: in the bind's colour, hollow when not sent
    assert [s[4:] for s in shapes if s[0] == "circle"] == [
        ("bind1", False),
        ("bind1", True),
        ("bind2", False),
    ]
    assert ("A tap (not sent)", "bind1") in [(s[3], s[4]) for s in shapes if s[0] == "text"]


def test_axis_history_drawing_follows_the_text_size():
    # v108.155: larger text gets wider margins, larger dots and offsets, and a title line.
    from spnav_mapper import axis_history

    history, clock = _history([(t / 10, 0.5) for t in range(0, 101)], [(6.0, "down", 0, "A")])
    samples, events = history.span(clock[0], 10)
    big = axis_history.drawing(
        samples, events, [], 5, clock[0], 10, 900, 400, title="X", colour="X", text_px=26, char_px=14
    )
    assert big[0] == ("rect", 98, 190.375, 790, 16.25, "deadzone")  # x 98..888, y 36..361
    assert ("text", 98, 28, "X", "X", "left") in big  # the axis's name, in its colour
    dot = next(shape for shape in big if shape[0] == "circle")
    assert dot[3] == 9.1 and dot[4] == "bind1"  # Bind #1's colour (v108.159)
    assert next(shape for shape in big if shape[0] == "polyline")[2] == "trace"  # white (v108.159)
    assert [shape[2] for shape in big if shape[0] == "text" and shape[3] == "now"] == [361 + 26 + 5]


def test_axis_history_drawing_together():
    from spnav_mapper import axis_history

    x, clock = _history([(t / 10, 0.5) for t in range(0, 101)], [(6.0, "down", 0, "A")])
    y, _ = _history([(t / 10, -0.25) for t in range(0, 101)])
    series = [("X", *x.span(clock[0], 10)), ("Ry", *y.span(clock[0], 10))]
    shapes = axis_history.drawing_together(series, clock[0], 10, 456, 240)
    assert [s[2] for s in shapes if s[0] == "polyline"] == ["X", "Ry"]  # each in its axis's colour
    assert [s[3] for s in shapes if s[0] == "text" and s[4] in ("X", "Ry")] == ["X", "Ry"]  # the names on top
    assert "X: A down" in [s[3] for s in shapes if s[0] == "text"]
    # v108.159: the dots and their labels in their binds' colours; the lines in the axes' colours.
    assert {s[4] for s in shapes if s[0] == "circle"} == {"bind1"}
    assert [s[4] for s in shapes if s[0] == "text" and s[3] == "X: A down"] == ["bind1"]
    assert not [
        s for s in shapes if s[0] == "rect" or (s[0] == "line" and s[7] == "dot")
    ]  # no dead zone or bands


def test_axis_history_window_view_and_size():
    from spnav_mapper import axis_history as ahw

    assert ahw.load_view({}) == ahw.DEFAULT_VIEW
    assert ahw.load_view("junk") == ahw.DEFAULT_VIEW
    # v108.187: attached to the editor unless unticked; the time span is no longer a choice
    # (a "seconds" remembered by an older version is dropped).
    assert ahw.DEFAULT_VIEW["attached"] is True and "seconds" not in ahw.DEFAULT_VIEW
    view = ahw.load_view(
        {
            "axes": ["Rz", "X", "Q"],
            "together": 1,
            "seconds": 30,
            "text_size": 1.6,
            "size": [1200, 700],
            "attached": 0,
            "legend": 1,
        }
    )
    assert view == {
        "axes": ["X", "Rz"],
        "together": True,
        "text_size": 1.5,
        "size": [1200, 700],
        "attached": False,
        "legend": True,
        "editor_spots": {},
    }
    # v108.188: the editor's remembered places, per monitor; one that makes no sense is dropped.
    spots = ahw.load_view(
        {"editor_spots": {"A": [10, 20, None, None], "B": "x", "C": [1, 2, 300, 400], "D": [1, 2, 3]}}
    )["editor_spots"]
    assert spots == {"A": [10, 20, None, None], "C": [1, 2, 300, 400]}
    assert ahw.load_view({})["editor_spots"] is not ahw.DEFAULT_VIEW["editor_spots"]
    assert ahw.load_view({"axes": [], "seconds": 7, "size": [10, 10]})["axes"] == ["X"]
    assert ahw.load_view({"seconds": 7, "size": [10, 10]})["size"] is None
    # 80% of the screen at first; a remembered size, but never larger than the screen.
    assert ahw.fit_size(None, (1920, 1032)) == (1536, 826)
    assert ahw.fit_size([1200, 700], (1920, 1032)) == (1200, 700)
    assert ahw.fit_size([2400, 1300], (1920, 1032)) == (1920, 1032)


# --- Qt's default font after the Windows scale changed since sign-in (v108.152) ---------------------
@pytest.mark.parametrize(
    "qt_points, gui_font",
    [
        (8.0, (-24, "MS Shell Dlg", 216)),  # 225%
        (8.0, (-16, "MS Shell Dlg", 144)),  # 150%
        (8.0, (-13, "MS Shell Dlg", 120)),  # 125%: Windows' 7.8 pt, rounded by Qt
        (7.8, (-13, "MS Shell Dlg", 120)),
        (8.25, (-11, "MS Shell Dlg", 96)),  # 100%
    ],
)
def test_default_font_left_alone_when_nothing_changed(qt_points, gui_font):
    assert system_font.corrected_default_points(qt_points, "MS Shell Dlg 2", gui_font) is None


@pytest.mark.parametrize(
    "qt_points, gui_font, wanted",
    [
        (18.0, (-24, "MS Shell Dlg", 216), 8.0),  # signed in at 225%, now 100%
        (14.4, (-24, "MS Shell Dlg", 216), 8.0),  # signed in at 225%, now 125%
        (5.5, (-11, "MS Shell Dlg", 96), 8.25),  # signed in at 100%, now 150%
    ],
)
def test_default_font_gets_the_size_windows_meant(qt_points, gui_font, wanted):
    assert system_font.corrected_default_points(qt_points, "MS Shell Dlg 2", gui_font) == wanted


def test_default_font_needs_windows_answer_and_the_same_family():
    assert system_font.corrected_default_points(18.0, "Segoe UI", (-24, "MS Shell Dlg", 216)) is None
    assert system_font.corrected_default_points(18.0, "MS Shell Dlg 2", None) is None
    assert system_font.corrected_default_points(18.0, "MS Shell Dlg 2", (-24, "MS Shell Dlg", 0)) is None
    assert system_font.corrected_default_points(-1, "MS Shell Dlg 2", (-24, "MS Shell Dlg", 216)) is None
    assert system_font.corrected_default_points("x", "MS Shell Dlg 2", (-24, "MS Shell Dlg", 216)) is None


def test_home_monitor_keeps_its_windows_scale():
    factors, home = monitor_scale.screen_factors(
        [mon("A", 1920, 1032, 120, True), mon("B", 3840, 2100, 168)], "A", 1.0
    )
    assert home == "A" and factors["A"] == 1.25


def test_scale_from_metrics_matches_the_original_formula():
    def original(w, h, dpi, dpr):
        r = min(max(640, w) / 2560, max(480, h) / 1440)
        s = 0.60 * r * (max(72, min(288, dpi)) / 96) ** 0.33 * max(1, min(4, dpr)) ** 0.12
        return float(f"{max(0.45, min(1.15, s)):.3f}")

    for args in [
        (2560, 1400, 96, 1),
        (1920, 1040, 96, 1),
        (2560, 1400, 96, 1.5),
        (1280, 688, 72, 2),
        (5120, 2800, 96, 1),
    ]:
        assert scaling.scale_from_metrics(*args)[0] == original(*args)


def test_colours_save_reload_red_and_menu_bar_gray():
    # v108.134: Save/Reload red with white letters; the menu-bar headings
    # highlight in medium gray.
    import pathlib

    ui = pathlib.Path(__file__).resolve().parents[1] / "spnav_mapper" / "ui"
    full = (ui / "main_window.py").read_text(encoding="utf-8")
    assert "QPushButton#QuickYellow { background-color: #dc2626; color: #ffffff;" in full
    for state in ("selected", "hover", "pressed"):
        rule = full.split(f"QMenuBar::item:{state} {{", 1)[1].split("}", 1)[0]
        assert "background-color:#6b7280;" in rule and "color:#ffffff;" in rule


def test_save_as_white_with_black_letters():
    # v108.135: Save as is white with black letters.
    import pathlib

    ui = pathlib.Path(__file__).resolve().parents[1] / "spnav_mapper" / "ui"
    full = (ui / "main_window.py").read_text(encoding="utf-8")
    assert 'saveb.setObjectName("SaveAsButton")' in full
    assert "QPushButton#SaveAsButton { background-color: #ffffff; color: #000000;" in full


def test_compact_view_is_gone():
    # v108.137: the editor is the only view.
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "spnav_mapper"
    assert not (root / "ui" / "compact_view.py").exists()
    assert not (root / "ui" / "compact_fit.py").exists()
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in ("_compact_mode_active", "show_compact_window", "compact_sync", "CompactViewMixin"):
            assert name not in text, (path.name, name)


def test_build_exe_batch_file():
    # v108.143: BUILD_EXE_WINDOWS.bat builds the EXE with Nuitka.
    import pathlib
    import re
    import subprocess
    import sys

    root = pathlib.Path(__file__).resolve().parents[1]
    raw = (root / "BUILD_EXE_WINDOWS.bat").read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")  # Windows line endings throughout
    text = raw.decode("ascii")
    for needed in ("--onefile", "--enable-plugin=pyqt5", "--windows-console-mode=disable", "main.py"):
        assert needed in text
    # Every file it names exists.
    icon = re.search(r"--windows-icon-from-ico=(\S+)", text).group(1)
    data = re.search(r"--include-data-dir=(\S+?)=", text).group(1)
    for path in (icon, data, "requirements.txt", "main.py"):
        assert (root / path.replace("\\", "/")).exists(), path
    # v108.145: the README (PDF and Markdown) is in the resources folder the EXE includes.
    assert "--include-data-files" not in text
    for name in ("SpaceNavigator_Mapper_README.pdf", "SpaceNavigator_Mapper_README.md"):
        assert (root / data.replace("\\", "/") / name).is_file(), name
    # Its version one-liner gives the four numbers Windows wants.
    code = re.search(r'-c "(.+?)"`', text).group(1)
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, check=True)
    from spnav_mapper.version import VERSION

    assert out.stdout.strip() == VERSION.lstrip("v") + ".0.0"
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", out.stdout.strip())


# --- The README (v108.145) ------------------------------------------------------
def _readme_builder():
    import importlib.util
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("build_readme_pdf", root / "tools" / "build_readme_pdf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_function_has_a_purpose():
    # The README's function reference takes each purpose from the docstring.
    missing = [f"{m}::{n}" for m, n, _line, text in _readme_builder().function_inventory() if not text]
    assert missing == []


def test_readme_markdown_matches_the_source():
    # Version line and section 8 are written by tools/build_readme_pdf.py; run it after code changes.
    builder = _readme_builder()
    version, date = builder.read_version()
    text = builder.MARKDOWN.read_text(encoding="utf-8")
    reference = builder.reference_markdown(builder.function_inventory(), version)
    assert builder.update_markdown(text, version, date, reference) == text
    assert f"**Version:** {version} ({date})" in text
    assert text.startswith("# SpaceNavigator Mapper — Full Editor README\n")
    for n in range(1, 10):
        assert f"\n## {n}. " in text


def test_readme_pdf_is_shipped():
    builder = _readme_builder()
    data = builder.PDF.read_bytes()
    assert data[:5] == b"%PDF-" and len(data) > 50_000
    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(str(builder.PDF))
    version, _date = builder.read_version()
    assert version in (reader.metadata.title or "")  # printed from the current Markdown
    first = reader.pages[0].extract_text()
    assert "SpaceNavigator Mapper" in first and version in first


# --- Axis history (v108.149) ------------------------------------------------------
def _history(points, events=()):
    from spnav_mapper import axis_history

    clock = [0.0]
    history = axis_history.AxisHistory(keep_s=30, clock=lambda: clock[0])
    pending = sorted(events)
    for t, value in points:
        clock[0] = t
        history.add_sample(value)
        while pending and pending[0][0] <= t:
            _t, kind, index, key = pending.pop(0)
            history.add_event(kind, index, key, value)
    return history, clock


def test_axis_history_keeps_thirty_seconds():
    history, clock = _history([(i * 0.5, 0.1) for i in range(0, 121)], [(1.0, "down", 0, "A")])
    assert history.samples[0][0] == 30.0 and history.samples[-1][0] == 60.0  # the first 30 s are gone
    assert not history.events  # the event at 1 s too
    samples, events = history.span(clock[0], 5)
    assert [t for t, _v in samples] == [55.0 + i * 0.5 for i in range(11)]


def test_axis_history_bands_summary_and_csv():
    from spnav_mapper import axis_history

    binds = [
        {"direction": "Plus", "combo": ["a"], "mode": "Hold", "min": 11, "dead": 5, "noback_plus": True},
        {"direction": "Full", "combo": ["b"], "mode": "Tick", "min": 30, "dead": 9, "noback_minus": True},
        {"direction": None, "combo": ["c"], "mode": "Hold", "min": 0},  # no Bind Dir: not drawn
        {"direction": "Minus", "combo": None, "mode": "Hold", "min": 0},  # no key: not drawn
        {
            "direction": "Minus",
            "combo": None,
            "mode": "Macro",
            "macro": [{"tap": ["q"]}],
            "min": 20,
            "dead": 5,
        },
    ]
    bands = axis_history.bind_bands(
        binds, 5, lambda b: "macro" if b["mode"] == "Macro" else b["combo"][0].upper()
    )
    assert bands == [
        (0, "+", 16, "A", "+"),
        (1, "+-", 30, "B", ""),  # v108.162: a Tick has no NoBack
        (4, "-", 25, "macro", ""),
    ]
    history, clock = _history(
        [(0.0, 0.0), (0.5, 0.3), (1.0, 0.72), (1.5, 0.1), (2.0, -0.4), (2.5, 0.0)],
        [(0.5, "down", 0, "A"), (1.0, "tap", 1, "B"), (1.5, "held", 0, "A"), (2.0, "macro", 4, "macro")],
    )
    samples, events = history.span(clock[0], 10)
    assert axis_history.summary(samples, events) == (
        "Peak +72%, −40% · Bind #1 pressed 1× · Bind #2 tapped 1× · Bind #5 played 1× · NoBack held 1×"
    )
    assert axis_history.summary([], []) == "Nothing recorded yet: move the axis."
    rows = axis_history.csv_rows([("X", samples, events)])
    # v108.187: the last column, held_ms (see test_axis_history_hold_times_and_key_log).
    assert rows[0] == ("axis", "time_s", "value_percent", "event", "bind", "key", "held_ms")
    assert rows[1] == ("X", "0.000", "0.0", "", "", "", "")
    assert ("X", "0.500", "30.0", "down", "Bind #1", "A", "") in rows
    assert ("X", "1.500", "10.0", "held by NoBack", "Bind #1", "A", "") in rows
    assert len(rows) == 1 + 6 + 4
    # v108.155: several axes in one file, in time order, timed from the first.
    later = [(t + 0.25, v) for t, v in samples[:2]]
    both = axis_history.csv_rows([("X", samples, events), ("Ry", later, [])])
    assert len(both) == 1 + 6 + 4 + 2
    assert both[1] == ("X", "0.000", "0.0", "", "", "", "")
    assert both[2] == ("Ry", "0.250", "0.0", "", "", "", "")
    assert axis_history.csv_rows([("X", [], []), ("Y", [], [])]) == [rows[0]]


def test_axis_history_drawing():
    from spnav_mapper import axis_history

    history, clock = _history(
        [(t / 10, 0.5 if t > 50 else 0.0) for t in range(0, 101)], [(6.0, "down", 0, "A")]
    )
    samples, events = history.span(clock[0], 10)
    bands = [(0, "+-", 40, "A", "")]
    shapes = axis_history.drawing(samples, events, bands, 5, clock[0], 10, 456, 240)
    # Plot: x 56..291 (the binds' labels to the right), y 14..214 (centre 114, 100 px per 100%).
    assert shapes[0] == ("rect", 56, 109.0, 235, 10.0, "deadzone")
    # v108.159: +100% green, 0 blue, −100% red, dashed; ±50% faint; labels in the same colours.
    lines = {s[2]: s[5:] for s in shapes if s[0] == "line" and s[1] == 56}
    assert lines[14.0] == ("plus100", 1.5, True) and lines[114.0] == ("zero", 1.5, True)
    assert lines[214.0] == ("minus100", 1.5, True) and lines[64.0] == ("grid", 1.0, False)
    assert [(s[3], s[4]) for s in shapes if s[0] == "text" and s[1] == 50] == [
        ("+100%", "plus100"),
        ("+50%", "label"),
        ("0", "zero"),
        ("−50%", "label"),
        ("−100%", "minus100"),
    ]
    # The axis's line is white; the bind's start lines dotted in its colour (Bind #1: red).
    polyline = next(s for s in shapes if s[0] == "polyline")
    assert polyline[1][0] == (56.0, 114.0) and polyline[1][-1] == (291.0, 64.0) and polyline[2] == "trace"
    assert lines[74.0] == ("bind1", 1.0, "dot") and lines[154.0] == ("bind1", 1.0, "dot")
    dot = next(s for s in shapes if s[0] == "circle")
    assert dot == ("circle", pytest.approx(291 - 4 * 23.5), 64.0, 5.0, "bind1", True)
    # The labels' column: "Bind", "#1", "(A)" and the percent, each in its column.
    rows = [[(s[1], s[3]) for s in shapes if s[0] == "text" and s[2] == y] for y in (79.0, 159.0)]
    assert rows == [
        [(325, "Bind"), (362, "#1"), (385, "(A)"), (445, "40%")],
        [(325, "Bind"), (362, "#1"), (385, "(A)"), (445, "−40%")],
    ]
    labels = [s[3] for s in shapes if s[0] == "text"]
    assert "A down" in labels and labels[-3:] == ["−10 s", "−5 s", "now"]
    # Many events: dots only.
    many = [(clock[0] - i * 0.1, "tap", 0, "A", 0.5) for i in range(20)]
    crowded = axis_history.drawing(samples, many, bands, 5, clock[0], 10, 456, 240)
    assert not [s for s in crowded if s[0] == "text" and s[3].startswith("A ")]
    # No binds: no labels' column.
    bare = axis_history.drawing(samples, events, [], 5, clock[0], 10, 456, 240)
    assert bare[0] == ("rect", 56, 109.0, 388, 10.0, "deadzone")


def test_axis_history_labels_never_overlap():
    # v108.159: binds starting close together (and both sides) get rows at least a line apart,
    # in order, each joined to its start line; the columns line up.
    from spnav_mapper import axis_history

    bands = [
        (0, "+", 15, "A", "+"),
        (1, "+", 18, "Shift+Q", ""),
        (2, "+", 20, "Ctrl+B", ""),
        (3, "+", 45, "D", "+"),
        (4, "-", 20, "Space", ""),
        (5, "+-", 22, "F", ""),
    ]
    assert axis_history.label_rows(bands) == [
        (3, "+", 45, "D", "NoBack: nothing to hold"),
        (5, "+", 22, "F", ""),
        (2, "+", 20, "Ctrl+B", ""),
        (1, "+", 18, "Shift+Q", ""),
        (0, "+", 15, "A", "NoBack"),
        (4, "-", 20, "Space", ""),
        (5, "-", 22, "F", ""),
    ]
    for width, height, text_px, char_px in ((1400, 330, 21, 11), (700, 240, 15, 8), (600, 160, 13, 7)):
        shapes = axis_history.drawing(
            [], [], bands, 5, 0.0, 10, width, height, text_px=text_px, char_px=char_px
        )
        numbers = [s for s in shapes if s[0] == "text" and s[3].startswith("#")]
        ys = [s[2] for s in numbers]
        assert [s[3] for s in numbers] == ["#4", "#6", "#3", "#2", "#1", "#5", "#6"]
        assert all(b - a >= text_px + 1 - 1e-6 for a, b in zip(ys, ys[1:], strict=False)), (width, ys)
        assert len({s[1] for s in numbers}) == 1  # one column
        percents = [s for s in shapes if s[0] == "text" and s[3].endswith("%") and s[4].startswith("bind")]
        assert len({s[1] for s in percents}) == 1 and {s[5] for s in percents} == {"right"}
        assert all(s[1] <= width for s in shapes if s[0] == "text")
        leaders = [s for s in shapes if s[0] == "line" and s[7] is False and s[5].startswith("bind")]
        assert len(leaders) == 7
        assert all(s[4] == y - round(text_px * 0.35) for s, y in zip(leaders, ys, strict=True))
    # Narrow: the keys, then the word "Bind", are left out before the column takes over the graph.
    narrow = axis_history.drawing([], [], bands, 5, 0.0, 10, 300, 240)
    assert not [s for s in narrow if s[0] == "text" and s[3] in ("Bind", "(A)")]
    assert axis_history.spread([10, 12, 13], 0, 100, 5) == [10, 15, 20]
    assert axis_history.spread([90, 95, 99], 0, 100, 5) == [90, 95, 100]
    assert axis_history.spread([98, 99, 99], 0, 100, 5) == [90, 95, 100]


def test_axis_history_dot_labels_never_overlap():
    # v108.159: a dot's label goes where it covers no other label or dot, inside the plot, or not at all.
    from spnav_mapper import axis_history

    events = [(9.0, "tap", 0, "A", 0.5), (9.05, "tap", 2, "Ctrl+B", 0.5), (9.1, "tap", 3, "D", 0.48)]
    shapes = axis_history.drawing([], events, [], 5, 10.0, 10, 456, 240)
    texts = [s for s in shapes if s[0] == "text" and s[4].startswith("bind")]
    boxes = [(s[1], s[2] - 13 * 0.8, s[1] + axis_history.text_width(s[3]), s[2] + 13 * 0.2) for s in texts]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert not (a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3])
    assert [s[4:] for s in shapes if s[0] == "circle"] == [("bind1", True), ("bind3", True), ("bind4", True)]
    assert all(56 <= s[1] and s[1] + axis_history.text_width(s[3]) <= 444 for s in texts)


# --- Restart after a Display size change (v108.164) ---------------------------
def test_restart_starts_the_exe_the_user_started_not_its_onefile_copy(tmp_path):
    from spnav_mapper import restart

    app_dir, unpacked = tmp_path / "Mapper", tmp_path / "Temp" / "onefile_4242_1731"
    app_dir.mkdir()
    unpacked.mkdir(parents=True)
    exe, copy = app_dir / "SpaceNavigatorMapper.exe", unpacked / "SpaceNavigatorMapper.exe"
    exe.write_bytes(b"MZ")
    copy.write_bytes(b"MZ")
    # Onefile: sys.executable is the copy in the temporary folder, argv[0] the EXE started.
    command = restart.build_restart_command(str(copy), str(exe), project_root=app_dir, compiled=True)
    assert command == [str(exe), "--restart-ui-scale"]
    # argv[0] without its folder (started from the EXE's folder): found beside it.
    assert restart.compiled_program(str(copy), "SpaceNavigatorMapper.exe", app_dir) == exe
    # Nuitka's original_argv0 comes first.
    assert restart.compiled_program(str(copy), "x.exe", None, str(exe)) == exe
    # Standalone (no temporary copy): the EXE itself.
    assert restart.compiled_program(str(exe), str(exe), app_dir) == exe
    # Nothing better found: sys.executable, as before.
    assert restart.compiled_program(str(copy), str(tmp_path / "gone.exe")) == copy


def test_restarted_copy_keeps_the_folder_and_its_configs(tmp_path, monkeypatch):
    from spnav_mapper import paths, restart

    env = restart.successor_environment(
        tmp_path, {"PATH": "x", "NUITKA_ONEFILE_PARENT": "77", "Nuitka_x": "1"}
    )
    assert env == {"PATH": "x", restart.APP_DIR_ENV: str(tmp_path)}
    monkeypatch.setenv(restart.APP_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(paths.sys, "argv", ["SpaceNavigatorMapper.exe", "--restart-ui-scale"])
    assert paths._restart_app_dir() == str(tmp_path.resolve())
    assert restart.APP_DIR_ENV not in paths.os.environ  # not passed on
    # Only for a restart, and only for a folder that exists.
    monkeypatch.setenv(restart.APP_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(paths.sys, "argv", ["SpaceNavigatorMapper.exe"])
    assert paths._restart_app_dir() == ""
    monkeypatch.setenv(restart.APP_DIR_ENV, str(tmp_path / "missing"))
    monkeypatch.setattr(paths.sys, "argv", ["SpaceNavigatorMapper.exe", "--restart-ui-scale"])
    assert paths._restart_app_dir() == ""


# --- The taskbar button's right-click menu (v108.165) -------------------------
def test_taskbar_menu_restore_and_exit_items():
    import ctypes

    from spnav_mapper.ui import taskbar

    exe = r"C:\Games\SpaceNavigator Mapper\SpaceNavigatorMapper.exe"
    commands = {"restore": [exe, "--restore"], "exit": [exe, "--exit"]}
    assert taskbar.relaunch_properties(commands) == [
        (taskbar.KEY_ID, "MudMan54.SpaceNavigatorMapper"),
        (taskbar.KEY_RELAUNCH_COMMAND, f'"{exe}" --restore'),
        (taskbar.KEY_RELAUNCH_NAME, "Restore SpaceNavigator Mapper"),
        (taskbar.KEY_RELAUNCH_ICON, f"{exe},0"),
    ]
    assert taskbar.user_tasks(commands) == [
        ("Exit SpaceNavigator Mapper", exe, "--exit", "Stop the Mapper: no more keys are sent.")
    ]
    # Run from source: pythonw.exe and the .pyw; the icon is the Mapper's .ico file.
    source = [r"C:\Python\pythonw.exe", r"C:\Mapper\SpaceNavigatorMapper.pyw", "--restore"]
    properties = dict(taskbar.relaunch_properties({"restore": source, "exit": source[:2] + ["--exit"]}))
    assert (
        properties[taskbar.KEY_RELAUNCH_COMMAND]
        == r"C:\Python\pythonw.exe C:\Mapper\SpaceNavigatorMapper.pyw --restore"
    )
    assert properties[taskbar.KEY_RELAUNCH_ICON].endswith("SpaceNavigatorMapper.ico,0")
    # PROPVARIANT: 16 bytes in 32-bit Windows, 24 in 64-bit.
    assert ctypes.sizeof(taskbar._PROPVARIANT) == 8 + 2 * ctypes.sizeof(ctypes.c_void_p)
    assert ctypes.sizeof(taskbar._PROPERTYKEY) == 20
    link = taskbar._guid(taskbar.CLSID_ShellLink)  # {00021401-0000-0000-C000-000000000046}
    assert (link.data1, link.data2, link.data3, list(link.data4)) == (
        0x21401,
        0,
        0,
        [0xC0, 0, 0, 0, 0, 0, 0, 0x46],
    )
    # Not on Windows: nothing is attempted.
    assert taskbar.install_taskbar_menu(object()) is False


# --- Taps that do not stop the Mapper (v108.167) ------------------------------
class _TapRig:
    """A TapSender with a clock and timers that only move when told to."""

    def __init__(self):
        from spnav_mapper.ui.taps import TapSender

        self.now, self.timers, self.events = 0.0, [], []
        self.sender = TapSender(
            send=lambda combo, down: self.events.append((round(self.now * 1000), "+".join(combo), down)),
            schedule=lambda ms, callback: self.timers.append(
                (self.now + ms / 1000.0, len(self.timers), callback)
            ),
            clock=lambda: self.now,
        )

    def advance(self, ms):
        end = self.now + ms / 1000.0
        while True:
            due = sorted(t for t in self.timers if t[0] <= end + 1e-9)
            if not due:
                break
            self.timers.remove(due[0])
            self.now = max(self.now, due[0][0])
            due[0][2]()
        self.now = end


def test_a_tap_is_released_after_its_dwell_without_waiting():
    rig = _TapRig()
    assert rig.sender.tap(["a"], 45) == "sent"
    assert rig.events == [(0, "a", True)]  # tap() returned at once: the Mapper keeps running
    rig.advance(10)
    assert rig.sender.tap(["b"], 45) == "sent"  # other keys are not held up
    rig.advance(100)
    assert rig.events == [(0, "a", True), (10, "b", True), (45, "a", False), (55, "b", False)]


def test_a_key_tapped_again_is_up_long_enough_first():
    from spnav_mapper.ui.taps import MIN_UP_MS

    rig = _TapRig()
    rig.sender.tap(["a"], 45)
    rig.advance(20)
    assert rig.sender.tap(["a"], 45) == "waiting"  # still down
    assert rig.sender.tap(["a"], 45) == "joined"  # one tap waits, not a queue
    rig.advance(200)
    downs = [t for t, _key, down in rig.events if down]
    ups = [t for t, _key, down in rig.events if not down]
    assert downs == [0, 45 + MIN_UP_MS] and ups == [45, 45 + MIN_UP_MS + 45]
    # Tapped during its time up: it waits for the rest of it.
    rig = _TapRig()
    rig.sender.tap(["a"], 45)
    rig.advance(50)  # up at 45, may go down again from 75
    assert rig.sender.tap(["a"], 45) == "waiting"
    rig.advance(100)
    assert [t for t, _key, down in rig.events if down] == [0, 75]


def test_release_all_lets_go_of_taps_in_their_dwell():
    rig = _TapRig()
    rig.sender.tap(["ctrl", "s"], 200)
    rig.sender.tap(["a"], 45)
    rig.advance(20)
    rig.sender.tap(["a"], 45)  # waits for A
    rig.sender.release_all()  # output switched off
    assert rig.events[-2:] == [(20, "ctrl+s", False), (20, "a", False)]
    assert rig.sender.held() == []
    rig.advance(300)  # the scheduled releases and the waiting tap do nothing
    assert len(rig.events) == 4
    assert rig.sender.tap(["a"], 0) == "sent"  # a dwell of 0: released at the next turn
    rig.advance(1)
    assert rig.events[-2:] == [(320, "a", True), (320, "a", False)]


def test_press_repeat_interval_leaves_the_key_up():
    from spnav_mapper.ui.taps import repeat_interval_ms

    assert repeat_interval_ms(100, 45) == 100  # room enough: Repeat every
    assert repeat_interval_ms(60, 45) == 75  # 45 ms down, then at least 30 ms up
    assert repeat_interval_ms(10, 200) == 230


def test_macro_taps_of_one_key_in_a_row_are_two_presses():
    from spnav_mapper.macros import expand

    twice = [{"tap": ["a"]}, {"tap": ["a"]}]
    assert expand(twice, 45) == [("down", ["a"]), ("wait", 45), ("up", ["a"])] * 2  # as before
    assert expand(twice, 45, 30) == [
        ("down", ["a"]),
        ("wait", 45),
        ("up", ["a"]),
        ("wait", 30),
        ("down", ["a"]),
        ("wait", 45),
        ("up", ["a"]),
    ]
    # A Delay between them counts; a long enough one adds nothing.
    assert ("wait", 20) in expand([{"tap": ["a"]}, {"delay": 10}, {"tap": ["a"]}], 45, 30)
    assert expand([{"tap": ["a"]}, {"delay": 50}, {"tap": ["a"]}], 45, 30).count(("wait", 50)) == 1
    assert len(expand([{"tap": ["a"]}, {"delay": 50}, {"tap": ["a"]}], 45, 30)) == 7
    # Only a modifier in common: nothing to wait for.
    assert len(expand([{"tap": ["ctrl", "a"]}, {"tap": ["ctrl", "b"]}], 45, 30)) == 6


# --- A profile with a target program is in its Auto-Profiles group (v108.170) --
def test_profiles_saved_with_a_target_are_listed_for_its_program(tmp_path):
    rules = tmp_path / "auto_profiles.json"
    one, two = tmp_path / "race_easy.json", tmp_path / "race_hard.json"
    for path in (one, two):
        path.write_text(json.dumps({"axes": {}, "target_exe": r"C:\Games\Race\race.exe"}))
    link = auto_profiles.link_profile_to_program
    # No rules file yet: a group is made for the program.
    assert link(str(one), r"C:\Games\Race\race.exe", "Race 2026", str(rules)) == "added"
    # A second profile with the same target joins it, after the first.
    assert link(str(two), r"C:\Games\Race\race.exe", "Race 2026", str(rules)) == "added"
    assert link(str(one), r"C:\Games\Race\race.exe", "Race 2026", str(rules)) == "present"
    data = json.loads(rules.read_text())
    assert data["groups"] == [
        {
            "name": "Race 2026",
            "enabled": True,
            "match": {"exe": ["race.exe"]},
            "profiles": [
                {"path": "race_easy.json", "priority": 1, "enabled": True},
                {"path": "race_hard.json", "priority": 2, "enabled": True},
            ],
        }
    ]
    manager = auto_profiles.AutoProfileManager(str(rules))
    manager.load()
    assert manager.candidates_for_current("race.exe", "", "") == [(str(one), 1), (str(two), 2)]
    assert manager.pick_profile_for("race.exe", "", "") == str(one)
    # Never last_config.json; and a rules file that cannot be read is left as it is.
    assert link(str(tmp_path / "last_config.json"), "race.exe", "", str(rules)) == ""
    rules.write_text("{ being edited")
    assert link(str(two), "race.exe", "", str(rules)) == "" and rules.read_text() == "{ being edited"


def test_linking_keeps_hand_made_rules(tmp_path):
    rules = tmp_path / "auto_profiles.json"
    profile = tmp_path / "notes.json"
    profile.write_text("{}")
    hand_made = {
        "groups": [
            # By window title: not the program's plain group, left alone.
            {"name": "Notes, big", "match": {"exe": ["notes.exe"], "title": ["*Big*"]}, "profiles": []},
            {
                "name": "Notes",
                "enabled": False,
                "match": {"exe": ["NOTES.EXE"]},
                "profiles": [
                    {"path": str(tmp_path / "other.json"), "priority": 7},
                    {"path": "notes.json", "priority": 3, "enabled": False},
                ],
            },
        ]
    }
    rules.write_text(json.dumps(hand_made))
    # Already there (turned off by hand): nothing changes.
    assert auto_profiles.link_profile_to_program(str(profile), "notes.exe", "", str(rules)) == "present"
    assert json.loads(rules.read_text()) == hand_made
    other = tmp_path / "notes2.json"
    other.write_text("{}")
    assert auto_profiles.link_profile_to_program(str(other), "notes.exe", "", str(rules)) == "added"
    added = json.loads(rules.read_text())["groups"][1]["profiles"][-1]
    assert added == {"path": "notes2.json", "priority": 8, "enabled": True}
    # Outside the configs folder: its full path.
    elsewhere = tmp_path / "sub" / "x.json"
    assert auto_profiles._rule_path(str(elsewhere), str(tmp_path)) == str(elsewhere)


def test_a_group_without_patterns_matches_no_program(tmp_path):
    rules = tmp_path / "auto_profiles.json"
    profile = tmp_path / "copy.json"
    profile.write_text("{}")
    rules.write_text(
        json.dumps({"groups": [{"name": "copy", "match": {}, "profiles": [{"path": str(profile)}]}]})
    )
    manager = auto_profiles.AutoProfileManager(str(rules))
    manager.load()
    # Before v108.170 it matched every program, and its profiles were loaded for all of them.
    assert manager.pick_profile_for("anything.exe", "Some window", "") == ""
    assert manager.candidates_for_current("anything.exe", "", "") == []


# --- Settle: the spring's bounce is not a new push (v108.177) -------------------
def test_settle_guard_holds_a_bind_through_the_bounce_only():
    from spnav_mapper.settle import SettleGuard

    guard, held = SettleGuard(), []

    def at(ms, magnitude, higher=False):
        held.append(guard.sample(ms / 1000.0, magnitude, 37, higher, 150))

    at(0, 40)  # the way out: past the bind's start
    at(16, 80, higher=True)  # ... and into the higher band, on the same push
    assert held == [False, False]  # the way out is never held
    at(32, 20)  # let go: below the bind's start
    at(96, 42)  # the bounce, 64 ms later
    assert held[-1] is True
    at(112, 10)  # below again: the rest starts over
    at(250, 45)  # 138 ms later: still too soon
    assert held[-1] is True
    at(266, 0)
    at(420, 45)  # after more than 150 ms at rest: a hand's push
    assert held[-1] is False and guard.armed is False
    at(432, 30)
    at(448, 45)  # nothing higher was reached since: free to start at once
    assert held[-1] is False


def test_settle_guard_counts_the_rest_between_samples_and_at_the_centre():
    from spnav_mapper.settle import SettleGuard, clamp_settle_ms, settle_text

    guard = SettleGuard()
    guard.sample(0.0, 80, 37, True, 150)
    guard.sample(0.016, 0, 37, False, 150)  # at the centre (or on the other side)
    # No sample while it rested: the rest is measured up to the next one.
    assert guard.sample(0.5, 45, 37, False, 150) is False
    # A bind that starts at 0 can only rest at the centre.
    zero = SettleGuard()
    zero.sample(0.0, 50, 0, True, 150)
    assert zero.sample(0.016, 5, 0, False, 150) is True
    zero.sample(0.032, 0, 0, False, 150)
    assert zero.sample(0.2, 5, 0, False, 150) is False
    # v108.179: off unless a time is given (150 ms in the v108.177/178 tests).
    assert [clamp_settle_ms(v) for v in (None, "x", -5, 0, 120, 9999)] == [0, 0, 0, 0, 120, 500]
    assert [settle_text(v) for v in (0, 150)] == ["Off", "150 ms"]


def test_axis_history_rebound_mark():
    from spnav_mapper import axis_history

    events = [(1.0, "tap", 0, "C", 0.4), (1.5, "rebound-held", 0, "C", 0.42)]
    line = axis_history.summary([(0.0, 0.0), (1.0, 0.8)], events)
    assert line.endswith("Bind #1 tapped 1× · Rebound held 1×")
    assert axis_history.unsent("rebound-held") == "rebound-held"  # nothing was sent either way
    assert axis_history.EVENT_TEXT["rebound-held"] == "held by Rebound"


# --- Where a hover tip goes (v108.178) ------------------------------------------
def test_tip_goes_to_an_edge_of_what_it_explains_inside_the_window():
    from spnav_mapper.tip_place import place_tip

    window, screen = (100, 100, 900, 600), (0, 0, 1920, 1080)
    size = (200, 40)
    # A button in the middle: after its right edge, level with its top.
    assert place_tip((400, 300, 80, 30), size, window, (420, 310), outer=screen) == (486, 300)
    # At the window's right side there is no room after it: before its left edge.
    assert place_tip((880, 300, 80, 30), size, window, (900, 310), outer=screen) == (674, 300)
    # A comment box as wide as the window: below it, from where its text begins.
    assert place_tip((110, 300, 880, 24), size, window, (500, 310), outer=screen) == (110, 330)
    # ... and above it at the bottom of the window.
    assert place_tip((110, 670, 880, 24), size, window, (500, 680), outer=screen) == (110, 624)
    # Level with the button's top, but never out of the window's bottom.
    assert place_tip((400, 680, 80, 18), size, window, (420, 690), outer=screen) == (486, 660)


def test_tip_is_never_under_the_pointer_or_over_an_open_drop_down():
    from spnav_mapper.tip_place import _hits, place_tip

    window, screen = (100, 100, 900, 600), (0, 0, 1920, 1080)
    size = (260, 60)
    # A drop-down's item (the row is the drop-down's width) with its submenu open to the right:
    # the tip goes to the left of the drop-down, off both.
    menu, submenu = (300, 124, 220, 200), (520, 160, 160, 120)
    x, y = place_tip((300, 160, 220, 24), size, window, (400, 170), avoid=[menu, submenu], outer=screen)
    assert (x, y) == (34, 160)  # 300 - 6 - 260: still inside the screen, though left of the window
    assert not _hits(x, y, *size, menu) and not _hits(x, y, *size, submenu)
    # With no submenu: to the right of the drop-down.
    assert place_tip((300, 160, 220, 24), size, window, (400, 170), avoid=[menu], outer=screen) == (526, 160)
    # Something large (an axis panel): beside the pointer, not at the panel's far edge.
    x, y = place_tip((120, 150, 280, 300), size, window, (200, 380), outer=screen)
    assert abs(x - 200) < 300 and abs(y - 380) < 80
    assert not _hits(x, y, *size, (198, 378, 5, 5))
    # A window too small for the tip: it may leave the window, not the screen.
    small = (800, 400, 180, 90)
    x, y = place_tip((820, 420, 60, 20), size, small, (830, 425), outer=screen)
    assert 0 <= x and x + size[0] <= 1920 and 0 <= y and y + size[1] <= 1080
    assert not _hits(x, y, *size, (828, 423, 5, 5))
    # No screen given and no room off the pointer: inside the area all the same.
    x, y = place_tip((0, 0, 300, 100), size, (0, 0, 300, 100), (150, 50))
    assert 0 <= x <= 40 and 0 <= y <= 40


# --- Copy and paste of a bind (v108.181) ------------------------------------------
def test_bind_copy_keeps_its_own_copy_of_the_settings_and_the_comment():
    from spnav_mapper import bind_copy

    bind_copy.clear()
    assert bind_copy.copied() is None and bind_copy.source() == ""
    bind = {
        "direction": "Plus", "combo": ["ctrl", "c"], "mode": "Macro", "min": 37, "max": 66, "dead": 12,
        "repeat_ms": 140, "tap_ms": 45, "min_hold_ms": 175, "settle_ms": 250,
        "noback_plus": True, "noback_minus": False,
        "macro": [["tap", "a"], ["delay", 50]], "macro_repeat": True, "enabled": False,
        "active": True, "last_tap": 12.5, "last_on_ts": 3.0, "comment": "old",
    }  # fmt: skip
    bind_copy.copy_bind(bind, "crouch", "Z Bind #2")
    bind["combo"].append("x")
    bind["macro"][0][1] = "b"
    taken = bind_copy.copied()
    assert bind_copy.source() == taken["source"] == "Z Bind #2" and taken["comment"] == "crouch"
    assert set(taken["settings"]) == set(bind_copy.SETTINGS)  # settings only: not its running state
    assert taken["settings"]["combo"] == ["ctrl", "c"] and taken["settings"]["macro"][0] == ["tap", "a"]
    taken["settings"]["combo"].clear()  # what is handed out is a copy too
    assert bind_copy.copied()["settings"]["combo"] == ["ctrl", "c"]
    # v108.182: what a bind was before a paste, for Undo Paste.
    owner, other = object(), object()
    assert bind_copy.before_paste() is None and bind_copy.undo_name() == ""
    bind_copy.remember_before_paste(owner, 3, bind, "lean left", "X Bind #4")
    bind["min"] = 99
    kept = bind_copy.before_paste()
    assert (kept["owner"], kept["index"], kept["comment"], kept["name"]) == (
        owner,
        3,
        "lean left",
        "X Bind #4",
    )
    assert kept["settings"]["min"] == 37 and bind_copy.undo_name() == "X Bind #4"
    bind_copy.forget_paste(other)  # another axis: not its paste
    assert bind_copy.undo_name() == "X Bind #4"
    bind_copy.forget_paste(owner)
    assert bind_copy.before_paste() is None
    bind_copy.remember_before_paste(owner, 3, bind, "", "X Bind #4")
    bind_copy.clear()
    assert bind_copy.copied() is None and bind_copy.before_paste() is None


# --- v108.187: Min Hold's times, the keys' list, the scroll bar, attached to the editor -------------
def test_axis_history_keeps_ten_seconds_and_shows_five():
    from spnav_mapper import axis_history

    assert axis_history.KEEP_S == 10.0 and axis_history.VIEW_S == 5
    clock = [0.0]
    history = axis_history.AxisHistory(clock=lambda: clock[0])
    for i in range(41):  # 20 s
        clock[0] = i * 0.5
        history.add_sample(0.1)
    assert history.samples[0][0] == 10.0 and history.samples[-1][0] == 20.0


def test_axis_history_hold_times_and_key_log():
    # Each key-up carries how long its key was held, each tap its Tap Dwell; key_log()
    # makes one row of a press and its key-up, with the time since the row before.
    from spnav_mapper import axis_history as ah

    clock = [0.0]
    history = ah.AxisHistory(clock=lambda: clock[0])

    def at(t, kind, index, key, value, ms=None):
        clock[0] = t
        history.add_event(kind, index, key, value, ms)

    at(1.000, "down", 0, "C", 0.40)
    at(1.080, "down", 1, "CTRL", 0.62)
    at(1.256, "up", 1, "CTRL", 0.30, 176.04)
    at(1.400, "noback-up", 0, "C", 0.20, 400)
    at(2.000, "unsent-tap", 2, "W", -0.5, 175)
    at(2.500, "held", 0, "C", 0.35)
    at(3.000, "up", 3, "G", -0.3)  # a Release-only bind: a key-up with no press before it
    at(4.000, "down", 1, "CTRL", 0.7)  # still held
    events = list(history.events)
    assert events[2] == (1.256, "up", 1, "CTRL", 0.30, 176.0) and ah.event_ms(events[0]) is None
    assert ah.event_ms((1.0, "down", 0, "C", 0.4)) is None  # an event without the sixth item
    assert ah.event_label("up", 176.0) == "up · held 176 ms"
    assert ah.event_label("unsent-tap", 175) == "tap (not sent) · 175 ms"
    assert ah.event_label("down") == "down" and ah.event_label("held", 5) == "held by NoBack"
    assert ah.ms_text(4.26) == "4.3 ms" and ah.ms_text(43.2) == "43 ms" and ah.ms_text(None) == ""
    rows = ah.key_log([("Z", [], events)])
    assert [(r["key"], ah.key_log_text(r)) for r in rows] == [
        ("C", "held 400 ms (NoBack let go)"),
        ("CTRL", "held 176 ms"),
        ("W", "tap 175 ms (not sent)"),
        ("C", "held by NoBack"),
        ("G", "up"),
        ("CTRL", "down, still held"),
    ]
    assert [round(r["gap_ms"]) if r["gap_ms"] is not None else None for r in rows] == [
        None,
        80,
        920,
        500,
        500,
        1000,
    ]
    assert rows[1]["value"] == 62.0 and rows[1]["end_value"] == pytest.approx(30.0)
    assert [r["sent"] for r in rows] == [True, True, False, True, True, True]
    # Two axes: one list, in time order.
    both = ah.key_log([("Z", [], events[:2]), ("X", [], [(1.04, "tap", 0, "A", 0.5, 45.0)])])
    assert [(r["axis"], r["key"]) for r in both] == [("Z", "C"), ("X", "A"), ("Z", "CTRL")]
    # The CSV's last column, and the dots' labels with the times.
    csv = ah.csv_rows([("Z", [], events)])
    assert ("Z", "0.256", "30.0", "up", "Bind #2", "CTRL", "176.0") in csv
    assert ("Z", "1.000", "-50.0", "tap (not sent)", "Bind #3", "W", "175.0") in csv
    shapes = ah.drawing([], events[:3], [], 5, 2.0, 5, 900, 300, labelled=True)
    texts = [s[3] for s in shapes if s[0] == "text"]
    assert "CTRL up · held 176 ms" in texts and "C down" in texts
    assert ah.summary([(1.0, 0.4)], events).startswith("Peak +40%, −0% · Bind #1 pressed 1×")


def test_axis_history_scrolled_back_and_dots_without_labels():
    # The window scrolled back: the times under the plot say how far. While the graphs
    # run the dots have no labels (labelled=False): text that moves cannot be read.
    from spnav_mapper import axis_history as ah

    events = [(8.0, "down", 0, "A", 0.5, None), (8.2, "up", 0, "A", 0.3, 200.0)]
    live = ah.drawing([], events, [], 5, 10.0, 5, 900, 300, labelled=False)
    assert [s[3] for s in live if s[0] == "text"][-3:] == ["−5 s", "−2.5 s", "now"]
    assert len([s for s in live if s[0] == "circle"]) == 2
    assert not [s for s in live if s[0] == "text" and s[3].startswith("A ")]
    back = ah.drawing([], events, [], 5, 6.5, 5, 900, 300, ago=3.5)
    assert [s[3] for s in back if s[0] == "text"][-3:] == ["−8.5 s", "−6 s", "−3.5 s"]
    together = ah.drawing_together([("X", [], events)], 10.0, 5, 900, 300, ago=5, labelled=False)
    assert [s[3] for s in together if s[0] == "text"][-3:] == ["−10 s", "−7.5 s", "−5 s"]
    assert not [s for s in together if s[0] == "text" and "A " in s[3]]
    # A dot's label keeps clear of NoBack's labels, and goes a line or two further away
    # rather than being left out.
    noback = [(7.9, "+", 40)]
    clear = ah.drawing(
        [], events, [(0, "+", 40, "A", "+")], 5, 10.0, 5, 900, 300, noback=noback, labelled=True
    )
    boxes = {
        s[3]: (s[1], s[2] - 13 * 0.8, s[1] + ah.text_width(s[3]), s[2] + 13 * 0.2)
        for s in clear
        if s[0] == "text" and (s[3].startswith("A ") or s[3].startswith("NoBack 40"))
    }
    assert set(boxes) == {"A down", "A up · held 200 ms", "NoBack 40%"}
    names = sorted(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = boxes[a], boxes[b]
            assert not (ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1), (a, b)


def test_axis_history_window_goes_beside_the_editor():
    # v108.188: attached, the window takes the rest of the monitor beside the editor at full
    # height; the editor goes to the top left meanwhile, or where it was last put then.
    from spnav_mapper.axis_history import editor_spot, history_beside, spot_to_remember

    area = (0, 0, 3840, 2120)
    editor = (960, 100, 1684, 1300)  # its frame's corner and its own size
    # The top left of the area, the size unchanged; 7 pixels of invisible border past the edge.
    assert editor_spot(editor, area) == (0, 0, 1684, 1300)
    assert editor_spot(editor, area, None, bleed=7) == (-7, 0, 1684, 1300)
    # A second monitor to the right of the first: its own top left.
    assert editor_spot(editor, (3840, 0, 2560, 1400), None, 7) == (3833, 0, 1684, 1300)
    # Where it was last put while the window was open, and its size then, if it was resized.
    assert spot_to_remember((300, 50, 1684, 1300), area, (1684, 1300)) == [300, 50, None, None]
    assert spot_to_remember((300, 50, 1500, 1200), area, (1684, 1300)) == [300, 50, 1500, 1200]
    assert spot_to_remember((4140, 50, 1684, 1300), (3840, 0, 2560, 1400), (1684, 1300))[:2] == [300, 50]
    assert editor_spot(editor, area, [300, 50, None, None], 7) == (300, 50, 1684, 1300)
    assert editor_spot(editor, area, [300, 50, 1500, 1200], 7) == (300, 50, 1500, 1200)
    # Kept on the monitor; a size larger than the monitor, or a place that is no place, is not used.
    assert editor_spot(editor, area, [9000, 9000, None, None]) == (3840 - 120, 2120 - 120, 1684, 1300)
    assert editor_spot(editor, area, [-500, -500, 9000, 9000], 7) == (-7, 0, 1684, 1300)
    assert editor_spot(editor, area, ["x"], 7) == (-7, 0, 1684, 1300)
    # The window: from the editor's right edge to the area's right edge, the area's full height.
    frame = (-7, 0, 1700, 1339)  # the editor's frame at the top left
    assert history_beside(frame, area, 640) == (1693, 0, 2147, 2120)
    # The frames' invisible borders laid over each other (14), and past the screen's edges (7).
    assert history_beside(frame, area, 640, overlap=14, bleed=(7, 7)) == (1679, 0, 2168, 2127)
    # Whatever the editor's own top and height: the area's.
    assert history_beside((300, 400, 1700, 900), area, 640) == (2000, 0, 1840, 2120)
    # Less than the least width beside the editor: the window keeps it and covers the editor's right.
    assert history_beside((1500, 0, 1700, 1339), (0, 0, 2560, 1400), 640) == (1920, 0, 640, 1400)
    assert history_beside((4140, 50, 1700, 900), (3840, 0, 2560, 1400), 640) == (5760, 0, 640, 1400)


def test_profile_note_is_kept_with_the_profile(tmp_path):
    from spnav_mapper import profile_note as pn

    assert pn.clean_note("  one\r\ntwo\rthree  ") == "one\ntwo\nthree"
    assert pn.clean_note(None) == "" and len(pn.clean_note("x" * 5000)) == pn.NOTE_MAX_CHARS
    assert pn.note_from_config({}) == ("", False) and pn.note_from_config("junk") == ("", False)
    assert pn.note_from_config({"note": {"text": " Run as admin ", "important": 1}}) == ("Run as admin", True)
    assert pn.note_from_config({"note": {"text": "", "important": True}}) == ("", False)  # nothing to read
    assert pn.note_from_config({"note": "by hand"}) == ("by hand", False)
    # Written only when there is text: a profile without a note is as before.
    assert pn.put_note({"axes": {}}, "", True) == {"axes": {}}
    assert pn.put_note({"axes": {}, "note": {"text": "old"}}, "  ", False) == {"axes": {}}
    assert pn.put_note({}, "Set Prone to Hold", True) == {
        "note": {"text": "Set Prone to Hold", "important": True}
    }
    # What the profile name shows: it flashes until the note has been opened, then stays red.
    assert pn.name_state("text", True, False) == pn.UNREAD and pn.name_state("text", True, True) == pn.READ
    assert pn.name_state("text", False, False) == pn.PLAIN and pn.name_state("", True, False) == pn.PLAIN
    assert [pn.flash_colour(pn.UNREAD, phase) for phase in (True, False)] == [pn.RED, pn.WHITE]
    assert pn.flash_colour(pn.READ, False) == pn.RED and pn.flash_colour(pn.PLAIN, True) is None
    assert pn.FLASH_MS == 500  # one flash a second
    assert pn.tray_line("text", True, False).startswith("\n⚠") and pn.tray_line("text", True, True) == ""
    assert pn.name_tip("", False, True).startswith("Click: choose the target program's window.")
    assert pn.name_tip("Set Prone to Hold", True, False).splitlines()[0].startswith("⚠ Important note")
    assert pn.name_tip("x" * 700, False, True).endswith("…")
    # v108.189: that a note has been opened is remembered on this PC by what the note says:
    # the same text however its line ends are written, another mark for another text.
    mark = pn.note_mark("Run as admin\r\nSet Prone to Hold  ")
    assert mark == pn.note_mark("Run as admin\nSet Prone to Hold") and len(mark) == 16
    assert mark != pn.note_mark("Run as admin\nSet Prone to Tick")
    assert not pn.note_read(None, "Run as admin") and not pn.note_read({"junk": 1}, "Run as admin")
    assert pn.note_read(None, "") and pn.note_read([], "  ")  # no text: nothing to read
    read = pn.with_note_read(None, "Run as admin")
    assert read == [pn.note_mark("Run as admin")] and pn.note_read(read, " Run as admin\n")
    assert not pn.note_read(read, "Run as admin!")  # the text changed: unread again
    assert pn.with_note_read(read, "") == read and pn.with_note_read(read, "Run as admin") == read
    # The newest is last, each once; beyond `keep` the oldest are dropped. Junk in the file is dropped.
    more = pn.with_note_read(pn.with_note_read(read, "two"), "Run as admin")
    assert more == [pn.note_mark("two"), pn.note_mark("Run as admin")]
    assert pn.with_note_read(more, "three", keep=2) == [pn.note_mark("Run as admin"), pn.note_mark("three")]
    assert pn.clean_read(["a", "a", 3, "", None, "b"]) == ["a", "b"] and pn.clean_read("a") == []
    # Save Note writes the note, and only the note, into the file; the old file goes to the backups.
    import json

    path = tmp_path / "game.json"
    path.write_text(json.dumps({"axes": {"X": 1}, "hys_pct": 3}), encoding="utf-8")
    pn.write_note_to_profile(str(path), "Run as admin", True, str(tmp_path / "backups"))
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "axes": {"X": 1},
        "hys_pct": 3,
        "note": {"text": "Run as admin", "important": True},
    }
    assert len(list((tmp_path / "backups").iterdir())) == 1
    pn.write_note_to_profile(str(path), "", False, str(tmp_path / "backups"))
    assert json.loads(path.read_text(encoding="utf-8")) == {"axes": {"X": 1}, "hys_pct": 3}
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        pn.write_note_to_profile(str(path), "x", False, str(tmp_path / "backups"))


def test_axis_history_report_has_the_chart_and_every_setting():
    # Export's chart report: the graph as SVG, the axis's binds with all their settings
    # (the ones that fired marked) and the keys in time order with how long each was held.
    from spnav_mapper import axis_history as ah
    from spnav_mapper import axis_history_report as report

    binds = [
        {"direction": "Plus", "combo": ["c"], "mode": "Hold", "min": 0, "max": 54, "dead": 32,
         "noback_plus": True, "comment": "Crouch <1>"},
        {"direction": "Plus", "combo": ["ctrl"], "mode": "Hold", "min": 59, "max": 100, "dead": 0,
         "min_hold_ms": 175, "comment": "Prone"},
        {"direction": "Minus", "combo": ["w"], "mode": "Tick", "min": 12, "tap_ms": 80, "settle_ms": 150},
        {"direction": "Full", "combo": ["r"], "mode": "Press/Repeat", "min": 70, "max": 100, "dead": 5,
         "repeat_ms": 120, "enabled": False},
        {"direction": None, "combo": None, "mode": "Hold", "min": 0, "max": 100},
    ]  # fmt: skip
    key_text = lambda bind: "+".join(bind["combo"]).upper() if bind.get("combo") else ""
    events = [
        (1.0, "down", 1, "CTRL", 0.62, None),
        (1.176, "up", 1, "CTRL", 0.2, 176.0),
        (2.0, "unsent-tap", 2, "W", -0.2, 80.0),
    ]
    samples = [(t / 10, 0.62 if 10 <= t <= 11 else 0.0) for t in range(0, 101)]
    table = report.bind_table(binds, 5, key_text, 45, report.fired_counts(events))
    assert [row["bind"] for row in table] == ["Bind #1", "Bind #2", "Bind #3", "Bind #4"]  # #5 is not set up
    crouch, prone, walk, repeat = table
    assert (crouch["start"], crouch["dead"], crouch["hold"], crouch["noback"]) == (
        "32%",
        "32%",
        "0 (off)",
        "NoBack −",
    )
    assert (prone["start"], prone["hold"], prone["fired"], prone["tap"]) == (
        "59%",
        "175 ms",
        "pressed 1×",
        "",
    )
    assert (walk["start"], walk["min"], walk["tap"], walk["rebound"]) == (
        "−12%",
        "Tick 12%",
        "80 ms",
        "150 ms",
    )
    assert walk["fired"] == "tapped 1× (not sent)" and walk["max"] == walk["dead"] == walk["hold"] == ""
    assert (repeat["start"], repeat["repeat"], repeat["on"]) == ("±75%", "120 ms", "switched off")
    # A column no bind of the axis uses is left out.
    assert [c[0] for c in report.bind_columns(table[:2])][-4:] == ["hold", "noback", "fired", "comment"]
    assert "repeat" in [c[0] for c in report.bind_columns(table)]
    shapes = ah.drawing(samples, events, ah.bind_bands(binds, 5, key_text), 5, 10.0, 10, 1200, 380)
    picture = report.svg(shapes, 1200, 380)
    assert picture.startswith("<svg ") and picture.endswith("</svg>") and 'viewBox="0 0 1200 380"' in picture
    assert picture.count("<circle") == 3 + 5  # the three keys, and a swatch for each of the five label rows
    assert (
        "<polyline" in picture and "CTRL up · held 176 ms" in picture and "rgba(148,163,184,0.18)" in picture
    )
    page = report.report_html(
        {
            "version": "v108.187",
            "saved": "2026-11-21 12:00:00",
            "profile": "MW4 & co",
            "target": "game.exe",
            "mode": "Manual On",
            "note": "Set <Prone> to Hold",
            "important": True,
            "csv": "capture.csv",
            "not_shown": "X",
        },
        [{"axis": "Z", "samples": samples, "events": events, "binds": binds, "dead": 5, "noback": [],
          "now": 10.0, "key_text": key_text}],
    )  # fmt: skip
    assert page.startswith("<!DOCTYPE html>") and page.count("<svg") == 1 and "<script" not in page
    assert "http" not in page.replace("http://www.w3.org/2000/svg", "")  # nothing to fetch
    assert "MW4 &amp; co" in page and "Set &lt;Prone&gt; to Hold" in page and "Important profile note" in page
    assert "Crouch &lt;1&gt;" in page and "<h2>Z axis</h2>" in page and "the last 10 seconds" in page
    assert "held 176 ms" in page and "tap 80 ms (not sent)" in page and "Binds also fired on X" in page
    rows = report.key_rows([("Z", samples, events)])
    assert [(r["time"], r["gap"], r["what"], r["ms"]) for r in rows] == [
        ("1.000", "", "held 176 ms", "176"),
        ("2.000", "1000 ms", "tap 80 ms (not sent)", "80"),
    ]
    empty = report.report_html({}, [{"axis": "X", "samples": [], "events": [], "binds": [], "dead": 5,
                                     "now": 0.0, "key_text": key_text}])  # fmt: skip
    assert "No bind is set up on this axis." in empty and "No bind did anything in this capture." in empty
