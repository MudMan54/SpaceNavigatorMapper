"""Window placement on two monitors with different scale factors (v108.119, v108.130, v108.137)."""

import json
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
D1, D2 = r"\\.\DISPLAY1", r"\\.\DISPLAY2"


@pytest.fixture(scope="module")
def results():
    out = subprocess.run(
        [sys.executable, "-I", str(HERE / "placement_cases.py")],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_save_uses_the_monitor_windows_reports(results):
    # Before v108.119 this saved nothing and the next start (for example the
    # restart after a Display % change) used an older record on the other monitor.
    assert results["save in the logical gap"] == [D2, 100, 200]
    assert results["gap without Windows' answer saves nothing"] is None


def test_native_offsets_are_scaled_to_the_monitor(results):
    assert results["save on the 150% monitor"] == [D1, 200, 100]


def test_qt_geometry_still_used_without_windows(results):
    assert results["save without Windows' answer"] == [D2, 100, 200]


@pytest.mark.parametrize(
    "case, moved_back",
    [
        ("restore on the saved monitor", 0),
        ("restore that strays is moved back", 1),
        ("restore keeps straying", 2),  # bounded: never fights Windows forever
    ],
)
def test_restore_returns_to_the_saved_monitor(results, case, moved_back):
    result = results[case]
    assert result["screen"] == D2
    assert result["rect"] == [3940, 200, 300, 120]
    assert result["moved_back"] == moved_back
    assert result["checking"] is False


def test_restore_on_primary(results):
    result = results["restore on the primary monitor"]
    assert (result["screen"], result["rect"], result["moved_back"]) == (D1, [40, 60, 300, 120], 0)


# v108.130: Display > Positions Saved.
def test_checked_monitor_is_always_used(results):
    saved = results["positions saved"]
    assert saved["checked: start-up"] == [D2, 3840 + 500, 300]
    assert saved["checked: shown again"] == [D2, 3840 + 500, 300]
    # v108.132: no position saved on the checked monitor: centred there. v108.137:
    # the removed compact view's position there does not count.
    assert saved["checked: not saved yet"] == [D2, 3840 + (1920 - 300) // 2, (1040 - 120) // 2]


def test_checked_monitor_missing_uses_primary(results):
    assert results["positions saved"]["checked monitor missing"] == [D1, 700, 500]


def test_nothing_checked(results):
    saved = results["positions saved"]
    assert saved["none checked: start-up"] == [D1, (2560 - 300) // 2, (1400 - 120) // 2]
    # v108.133: nothing saved, so shown again it is centred on its monitor.
    assert saved["none checked: shown again"] == [D2, 3840 + (1920 - 300) // 2, (1040 - 120) // 2]
    # v108.132: a Display % restart with nothing checked is centred on the monitor it was on.
    assert saved["none checked: Display restart"] == [D2, 3840 + (1920 - 300) // 2, (1040 - 120) // 2]


def test_checking_a_monitor_saves_the_current_position(results):
    assert results["positions saved"]["checking saves now"] == {
        "monitor": D2,
        "saved on D2": {"relative_x": 70, "relative_y": 80, "w": 300, "h": 120},
        "preference": D2,
    }


def test_menus_and_submenus_are_one_point_larger(results):
    assert results["menu fonts"] == {t: [10.0, 10.0] for t in ("Auto-Profiles", "Options", "Display")}


def test_menus_get_the_same_extra_points_at_every_display_size(results):
    # v108.131/132: menus two points larger and the headings three, at 85% only.
    # v108.154: at every size; before, the headings were smaller at 100% and
    # 110% than at 85%, and the menus no larger.
    assert results["menu points"] == [
        {"factor": factor, "menus": [2.0], "headings": [3.0]} for factor in (1.0, 0.85, 1.10)
    ]


def test_only_the_menu_bar_headings_grow(results):
    # v108.133: three points larger.
    assert results["menu-bar headings"] == {"headings": 12.0, "corner title": 9.0, "menu": 9.0}


def test_restarted_copy_comes_to_the_front(results):
    result = results["restart comes to the front"]
    assert result["granted"] == [4321]
    assert result["raised"] == [result["window"]]


def test_comments_scroll_except_while_edited(results):
    assert results["scrolling comments"] == {"painted": ["scrolling", "plain"], "is a line edit": True}


def test_tray_profiles_menu_loads_the_chosen_profile(results):
    # v108.136: tray right-click > Profiles.
    assert results["tray profiles"] == {
        "listed": [["Game", True], ["Notes", False]],
        "loaded": ["Notes.json"],
        "message": ["Active profile: Notes"],
        "after": [["Game", False], ["Notes", True]],
        "none": [["No profiles in the configs folder", False]],
    }


# v108.137: the compact view is removed.
def test_old_compact_records_are_dropped_when_saved(results):
    assert results["old window_state.json"] == {"views": ["full"], "per_monitor": {D2: ["full"]}}


def test_second_launch_asks_the_running_copy_to_show_itself(results):
    # Before v108.137 a second launch called ShowWindow on the running copy's
    # window; hidden in the tray, it then showed unpainted: completely white.
    result = results["second launch"]
    assert result["found"] is True
    # Only the Qt window titled "SpaceNavigator Mapper…", not an Explorer folder
    # of that name; no ShowWindow or SetForegroundWindow from the second copy.
    assert result["calls"] == [["AllowSetForegroundWindow", 777], ["PostMessage", 0x200, 0xC1A5]]
    assert result["handled"] == [True, 0]
    assert result["other message"] == [False, 0]
    assert result["restored"] == ["restored"]  # the tray's own restore path, once
    assert result["visible"] is True
    assert result["minimized comes back"] == [True, False]


def test_version_label_uses_the_comment_size(results):
    assert results["version label"] == {"points": 10.5, "family": "Segoe UI"}


# v108.139: a bind with NoBack has a white line along its bottom.
def test_noback_line_sweeps_toward_its_sides(results):
    assert results["noback glow"] == {
        "sides": ["-", "+-", "+"],
        "resting (pointer away)": [1.0, 170],
        "grows from the middle": True,
        "starts again": True,
        "moving": [True, False],
        "same phase as the title": True,
        "shown": [True, True, False],
    }


# v108.140: v108.139 put the comments one row below their Bind buttons.
def test_comments_share_their_bind_buttons_rows(results):
    assert results["axis panel"]["rows"] == [[i, i] for i in range(6)]


def test_bind_dir_line_along_the_top(results):
    # None: no line; NEG left; POS right; FULL both ways. Green, on top of the
    # button's own style; the NoBack line stays white along the bottom.
    panel = results["axis panel"]
    assert panel["bind dir line"] == ["", "-", "+", "+-"]
    assert panel["line edges"] == ["top", "bottom"]
    assert panel["green"] == [34, 197, 94]
    assert panel["button style kept"] is True


def test_tray_menu_is_two_points_larger(results):
    assert results["tray menu"] == [2.0, 2.0]


# v108.141: macros.
def test_macro_editor_builds_the_steps(results):
    editor = results["macro editor"]
    assert editor["shown"] == ["1. Tap Q", "2. Tap CTRL+S", "3. Delay 250 ms", "4. Down SHIFT", "5. Up SHIFT"]
    # The delay edited to 120 ms and moved up, Q changed to Enter, Shift up deleted.
    assert editor["saved"] == [
        [{"tap": ["enter"]}, {"delay": 120}, {"tap": ["ctrl", "s"]}, {"down": ["shift"]}]
    ]
    assert editor["count"] == "4 of 50 steps"


def test_a_macro_bind_in_the_panel(results):
    bind = results["macro bind"]
    # Mode = Macro shows Play; Repeat also shows "Repeat every".
    assert bind["rows (once, then repeat)"] == [True, False, True, True]
    # Double-click and right-click > Edit macro… open the macro editor.
    assert bind["editor opened"] == ["X Bind #1: macro", "X Bind #1: macro"]
    assert bind["label"] == "Macro (3)"
    assert bind["tip"] == ["Macro, plays repeatedly:", "Tap Q", "Delay 100 ms", "Tap W"]
    steps = [{"tap": ["q"]}, {"delay": 100}, {"tap": ["w"]}]
    assert bind["saved"] == {"mode": "Macro", "macro": steps, "macro_repeat": True}
    assert bind["loaded"] == ["Macro", steps, True, "Macro (3)"]
    # Another Mode uses the key again; the steps are kept for later.
    assert bind["back to Hold"] == ["Bind #1", True, False]


def test_key_picker(results):
    # Ctrl, then S, then Shift: each click reports the combination so far.
    picker = results["key picker"]
    assert picker["with modifiers"] == [["ctrl"], ["ctrl", "s"], ["ctrl", "shift", "s"]]
    # A symbol is its own key combination; the modifier buttons are disabled.
    assert picker["symbol"] == [["shift", "1"], [False, False, False]]
    assert picker["backslash"] == ["backslash"]
    assert picker["symbol unselected"] == [["ctrl", "shift"], [True, True, True]]
    assert picker["key toggled"] == [["ctrl", "shift", "f5"], ["ctrl", "shift"]]
    assert picker["cleared"] is None
    assert picker["preset"] == [["ctrl"], "s"]


def test_device_presence_is_checked_once_a_second(results):
    # Listing HID devices every 16 ms GUI tick was slow; now once a second,
    # and an unplugged device is still noticed within about a second.
    presence = results["device presence"]
    assert presence["opened"] and presence["back"]
    assert presence["checks in 2 s"] <= 3
    assert presence["unplug noticed within"] <= 1.1


def test_editor_and_fonts_fit_smaller_screens(results):
    # v108.151: at 1920x1080 and 125% or 150%, the editor and its fonts are drawn
    # smaller, to the share of the screen they take on 3840x2160 at 225%. Before,
    # 150% drew them 36% larger a share of the screen.
    fits = results["fit to the screen"]
    reference = fits["3840x2160 at 225%"]
    assert reference["fit"] == 1.0 and fits["1920x1080 at 100%"]["fit"] == 1.0
    assert fits["1920x1080 at 125%"]["fit"] == 0.904 and fits["1920x1080 at 150%"]["fit"] == 0.747
    for label in ("1920x1080 at 100%", "1920x1080 at 125%", "1920x1080 at 150%"):
        fit = fits[label]
        assert fit["layout share"] <= reference["layout share"] * 1.03, label
        assert fit["font share"] <= reference["font share"] * 1.05, label
    assert fits["1920x1080 at 150%"]["app font"] == round(9.0 * 0.747, 2)  # the Qt controls' font too


def test_default_font_after_a_windows_scale_change(results):
    # v108.152: Windows' default GUI font is made for the DPI signed in with; Qt 5.15
    # converts it with the monitor's current DPI (QTBUG-101951). After 225% -> 100%
    # without signing out, a new start got an 18 pt default font instead of 8 pt.
    fonts = results["stale default font"]
    assert fonts["unchanged since sign-in"]["app font"] == ["MS Shell Dlg 2", 8.0]
    assert not any("since sign-in" in n for n in fonts["unchanged since sign-in"]["notes"])
    assert fonts["225% to 100%"]["app font"] == ["MS Shell Dlg 2", 8.0]
    assert any("was 18 pt, now 8 pt" in n for n in fonts["225% to 100%"]["notes"])
    # then sized like every other font: Display % x the fit to the screen
    assert fonts["225% to 125%"]["app font"][1] == round(8.0 * fonts["225% to 125%"]["size factor"], 2)
    assert fonts["100% to 225%"]["app font"] == ["MS Shell Dlg 2", 8.25]
    assert fonts["another default font"]["app font"] == ["Segoe UI", 9.0]
    assert fonts["no answer from Windows"]["app font"] == ["MS Shell Dlg 2", 18.0]
    assert fonts["no answer from Windows"]["notes"] == []


def test_editor_grows_to_its_content_once_shown(results):
    # v108.153: the size measured before the window is shown misses the control
    # heights fitted once it is styled; without a saved position, the content
    # stayed slightly larger than the window until Positions Saved was checked.
    settle = results["settle"]
    # D1's work area (Qt pixels): 2560 x 1400, with an 8 px frame each side
    assert settle["centred"]["before"] == [1130, 640, 300, 120]
    assert settle["centred"]["after"] == [1110, 625, 340, 150]  # still centred
    assert settle["saved position"]["after"] == [100, 200, 340, 150]  # same place
    assert settle["never shrinks"]["after"] == settle["never shrinks"]["before"]
    assert settle["never shrinks"]["grown"] == 0
    assert settle["only as far as the monitor"]["after"] == [8, 625, 2544, 150]
    assert all(settle[k]["grown"] == 1 for k in ("centred", "saved position"))


def test_menu_closes_once_the_mouse_has_left(results):
    # v108.160: Auto-Profiles, Options and Display stay open while the mouse is over the
    # drop-down, its submenu or the menu bar, and close 0.4 s after it has left them.
    auto = results["menu autoclose"]
    away = auto["away"]["steps"]
    assert [step[0] for step in away] == [False, False, False, False, False, True]
    assert away[-1][1] == [False, False] and not auto["away"]["watching"]  # the submenu closes too
    # Away for a moment (crossing a gap) and back: stays open.
    assert not any(step[0] for step in auto["back"]["steps"]) and auto["back"]["watching"]
    # Opened from the keyboard, the mouse never over it: stays open.
    assert not any(step[0] for step in auto["keyboard"]["steps"])
    # Moving along the menu bar to another heading: stays open.
    assert not any(step[0] for step in auto["along the bar"]["steps"])
    assert auto["steps"] == [
        [False, True, None],
        [False, False, None],
        [False, True, 1.0],
        [False, True, 1.0],
        [True, True, 1.0],
    ]


def test_settle_keeps_a_strayed_window_on_its_monitor(results):
    # v108.163: Windows moved the just-shown editor to the 150% monitor and the content
    # grew before it was moved back. Before, the growth was placed on that monitor and
    # the editor stayed there ([200, 100, 340, 150] on DISPLAY1).
    strayed = results["settle while strayed"]
    assert strayed["content grows"] == {"windows says": D2, "rect": [3940, 200, 340, 150], "moved back": 1}
    assert strayed["content the same"] == {"windows says": D2, "rect": [3940, 200, 300, 120], "moved back": 1}


def test_monitor_changes_offer_a_restart(results):
    # v108.163: the Qt factors and the layout are fixed at start-up; a monitor connected
    # later, or one whose resolution or scaling changed, needs a restart.
    change = results["monitor change"]
    for label in ("same monitors", "disconnected: nothing to ask", "taskbar moved: nothing to ask"):
        assert change[label]["asked"] == [False] and change[label]["boxes"] == [], label
    added = change["monitor connected later"]
    assert added["asked"] == [True] and added["restarts"] == 1
    assert added["boxes"] == [
        [
            "question",
            "Monitors Changed",
            ["Display 2 — 1920 × 1080, 100% (connected since the Mapper started)"],
        ]
    ]
    assert change["one monitor, connected later"]["boxes"][0][2] == [
        "Display 1 — 3840 × 2160, 150% (connected since the Mapper started)"
    ]
    assert change["scaling changed"]["boxes"][0][2] == [
        "Display 2 — 1920 × 1080, 125% (was 1920 × 1080, 100%)"
    ]
    # No: not asked again for the same monitors; asked again once they change again.
    declined = change["declined: not asked again"]
    assert declined["asked"] == [True, False] and declined["restarts"] == 0 and len(declined["boxes"]) == 1
    assert change["declined: asked for other monitors"] is True
    # Hidden in the tray: asked once the editor is shown.
    hidden = change["hidden: asked once shown"]
    assert hidden["asked"] == [False] and len(hidden["boxes"]) == 1 and hidden["restarts"] == 1
    assert not hidden["pending"]
    # A screen-added signal: checked once the monitors have been quiet for a moment.
    assert change["signal: not yet"] == 0 and change["screen added signal"]["restarts"] == 1
    # QT_SCREEN_SCALE_FACTORS set by the user: never second-guessed.
    assert change["user's own factors"] == []


def test_refit_uses_the_monitor_windows_reports(results):
    # v108.163: Qt named the 150% monitor; the editor stays on DISPLAY2 and fits its work
    # area (1920 wide, an 8 px frame each side). Before, it was fitted into DISPLAY1.
    refit = results["refit after a drag"]
    assert refit["rect"] == [3848, 200, 1904, 150]
    assert refit["note"] == [rf"Re-fitted the editor to {D2} (scale 1.000): 1904x150"]


def test_profile_buttons_end_where_the_profile_box_ends(results):
    # v108.165: a 1000 px row with 8 px gaps and a 200 px Auto Load selector.
    lined = results["profile buttons"]
    target, each = lined["widths"]
    assert target == round(2 * (1000 - 3 * 8) / 5) == 390  # Target as wide as before
    assert each == 126 and target + 3 * (8 + each) == 1000 - 200 - 8  # Load ends with the name box
    assert lined["compact"] == [120, (700 - 150 - 4 * 6 - 120) // 3]  # Target keeps its text width
    # Target, Save/Reload, Save as, Load, then the empty space under Auto Load and its
    # gap: a stretch, with no size or layout gap of its own, so the header is no wider.
    assert lined["stretch"] == [390, 126, 126, 126, 200 + 8] and lined["last item"] == "stretch"


def test_taskbar_restore_and_exit_launches(results):
    # v108.165: the taskbar's Restore SpaceNavigator Mapper (--restore) and a second start
    # bring the running copy forward without a message box; Exit (--exit) asks it to exit
    # and starts nothing, running or not.
    launches = results["taskbar launches"]
    for label in ("restore, running", "second start, running"):
        assert launches[label] == {
            "requests": ["restore"],
            "posted": ["restore"],
            "asked": [],
            "boxes": [],
            "code": 0,
        }, label
    assert launches["second start, window not found"]["boxes"] == ["SpaceNavigator Mapper — already running"]
    for label in ("exit, running", "exit, none running"):
        assert launches[label]["requests"] == ["exit"] and launches[label]["code"] == 0, label
        assert launches[label]["boxes"] == [] and launches[label]["asked"] == [], label
    # The running copy answers the exit message by exiting as Options > Exit does.
    assert launches["exit message"] == [True, 0] and launches["exited"] == [True]
    restore_id, exit_id = launches["message ids"]
    assert restore_id != exit_id


def test_another_version_running_is_not_shown_quietly(results):
    # v108.168: a start of this version found another one running. Since v108.165 it
    # quietly showed the old copy, so the new version seemed to have none of its changes.
    launches = results["taskbar launches"]
    question = "SpaceNavigator Mapper v108.164 is already running (perhaps hidden in the notification area)."
    kept = launches["older running, kept"]  # No: the old copy is shown
    assert kept["asked"] == [question] and kept["posted"] == ["restore"] and kept["code"] == 0
    replaced = launches["older running, replaced"]  # Yes: it exits and this one starts
    assert replaced["posted"] == ["exit"] and replaced["code"] == "started" and replaced["boxes"] == []
    stuck = launches["older running, does not exit"]  # a copy from before v108.165 ignores Exit
    assert stuck["asked"] == [
        "An older SpaceNavigator Mapper is already running (perhaps hidden in the notification area)."
    ]
    assert stuck["boxes"] == ["SpaceNavigator Mapper — another version is running"] and stuck["code"] == 0
    # The taskbar's Restore shows the running copy, whichever version it is.
    assert launches["older running, taskbar restore"]["asked"] == []
    assert launches["version numbers"] == [108168, "v108.164", 0, ""]


def test_button_comments_as_wide_as_an_axis_comment(results):
    # v108.173: Button 1 and 2's comment boxes take an axis bind comment's width when it
    # is laid out (and again whenever it changes size); they still scroll long comments.
    match = results["match width"]
    assert match["after"] == [[263, 263], [263, 263]] and match["again"] is False
    assert match["scrolls"] is True


def test_keys_to_a_program_running_as_administrator(results):
    # v108.174: Windows blocks keys from a program that is not running as administrator to
    # one that is. The Mapper says so when it sends keys to one (the tray once a program a
    # session), asks when one is picked as target, and restarts as administrator.
    e = results["elevation"]
    assert [e["no keys sent"], e["output off"], e["admin program"], e["again"]] == [False, False, True, True]
    assert [e["plain program"], e["cannot tell"]] == [False, False]  # never without reason
    assert e["tray"] == [
        "admin_game.exe runs as administrator, so Windows blocks the Mapper's keys. "
        "Use Options > Restart as Administrator."
    ]
    assert e["status"].startswith("⚠ admin_game.exe runs as administrator")
    assert e["asked"] == ["Program Running as Administrator"] * 2 and e["restarts"] == [True]
    assert e["plain target asks"] is False
    assert e["as administrator"] == [False, False]  # running as administrator: nothing to say
    assert e["menu item"] == ["Restart as Administrator"]
    # Windows' prompt accepted: this copy closes for the new one; declined: nothing changes.
    assert e["restart"]["accepted"][:2] == [True, "runas"] and e["closed"] == ["Restart as Administrator"]
    assert e["restart"]["declined"] == [
        False,
        "runas",
        "Not restarted as administrator: the Windows prompt was declined.",
    ]
