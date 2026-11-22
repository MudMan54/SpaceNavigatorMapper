"""Start the whole app under tests/fakeqt.py and drive a user session.

These catch import errors, broken wiring between modules and exceptions in Qt
callbacks, without Windows, a SpaceNavigator or a display.
"""

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SESSION = ROOT / "tests" / "session.py"
sys.path.insert(0, str(ROOT))
from spnav_mapper.keyboard_io import SC  # noqa: E402

KEY_NAMES = {code: name for name, code in SC.items()}


def run_session(tmp_path, script, kind="package", source=ROOT):
    out = tmp_path / f"{script}.json"
    subprocess.run(
        [sys.executable, "-I", str(SESSION), kind, str(source), str(out), script, str(tmp_path / "sbx")],
        check=True,
        timeout=600,
        capture_output=True,
    )
    checkpoints = json.loads(out.read_text(encoding="utf-8"))
    return {c["label"]: c for c in checkpoints if "snapshot" in c or "trace" in c}


def keys(checkpoint):
    out = []
    for effect in checkpoint["effects"]:
        if effect[1] == "keys":
            out.append("+".join(KEY_NAMES.get(k[0], str(k[0])) for k in effect[2]) + " " + effect[2][0][1])
    return out


def kinds(checkpoint):
    return [effect[1] for effect in checkpoint["effects"]]


@pytest.fixture(scope="module")
def full(tmp_path_factory):
    return run_session(tmp_path_factory.mktemp("full"), "full")


def test_no_errors_or_failed_steps(full):
    assert "LAUNCH FAILURE" not in full
    assert "DRIVER FAILURE" not in full
    for label, checkpoint in full.items():
        assert not checkpoint.get("errors"), (label, checkpoint["errors"])
        assert not checkpoint.get("step_failure"), (label, checkpoint["step_failure"])


def test_starts_in_the_editor_with_profile(full):
    # v108.137: the editor is the only view (the compact view is removed).
    start = full["startup"]
    assert "compact_mode" not in start["attrs"]
    assert start["snapshot"]["visible"] is True
    assert start["attrs"]["profile_path"].endswith("game.json")
    menu = [entry["text"] for entry in start["snapshot"]["menu"] if entry != "---"]
    assert menu == ["Auto-Profiles", "Options", "Display"]


def test_version_label_matches_the_comments_and_is_right_aligned(full):
    label = full["startup"]["attrs"]["version_label"]
    assert label["points"] == label["comment_points"] > 0
    assert label["right_aligned"] is True


def test_axis_strokes_send_keys(full):
    # X: the old profile's NoBack+ gives A and B NoBack, so A is not tapped
    # again on the way back.
    assert keys(full["X strokes"]) == ["a down", "a up", "b down", "b up", "c down", "c up"]
    z = keys(full["Y/Z/Ry strokes"])
    assert z[:2] == ["ctrl+d down", "d+ctrl up"]  # Y: Press/Repeat
    assert z[-7:] == ["e down", "f down", "f up", "e up", "g up", "space down", "space up"]  # Z Hold/Tick, Ry


def test_macro_bind_plays_its_steps(full):
    # v108.141: Rz Bind #1 in Macro mode (Play: Once) plays Tap Q, Delay, Tap W once.
    assert full["macro bind on Rz"]["attrs"]["axes"]["Rz"]["binds"][0]["mode"] == "Macro"
    assert keys(full["Rz macro stroke"]) == ["q down", "q up", "w down", "w up"]
    sent = [e[0] for e in full["Rz macro stroke"]["effects"] if e[1] == "keys"]
    assert sent[2] - sent[1] >= 100  # the Delay step
    labels = [w.get("text") for w in _widgets(full["Rz macro stroke"]["snapshot"]["central"])]
    assert "Macro (3)" in labels


def test_hardware_buttons(full):
    assert keys(full["hardware buttons"]) == ["ctrl+s down", "s+ctrl up", "f5 down", "f5 up"]


def test_save_reload_asks_first(full):
    # v108.142: a confirm prompt; Cancel changes no file and reloads nothing.
    # v108.148: the prompt shows the file name, editable.
    cancelled, done = full["save/reload cancelled"], full["save/reload"]
    for checkpoint in (cancelled, done):
        prompt = checkpoint["attrs"]["save_reload"]
        assert prompt["title"] == "Save/Reload" and prompt["name"] == "game" and prompt["enabled"]
        assert "previous contents are kept in the backups folder" in prompt["note"]
        assert not [e for e in checkpoint["effects"] if e[1] == "message-box"]
    assert cancelled["configs"] == full["reset axis from a bind's menu"]["configs"]
    assert cancelled["snapshot"]["status"] == "Save/Reload cancelled"
    assert done["configs"]["game.json"] != cancelled["configs"]["game.json"]
    assert done["snapshot"]["status"] == "✔ Saved and reloaded game.json"


def test_save_reload_with_a_new_name(full):
    # v108.148: a new name saves a new profile and loads it; the old file stays.
    before = full["save/reload: load game.json"]
    refused = full["save/reload: a settings name is refused"]
    assert refused["attrs"]["save_reload"]["enabled"] is False
    assert "Mapper's own settings" in refused["attrs"]["save_reload"]["note"]
    assert refused["configs"] == before["configs"]  # nothing saved
    assert refused["snapshot"]["status"] == "Save/Reload cancelled"
    renamed = full["save/reload as a new name"]
    prompt = renamed["attrs"]["save_reload"]
    assert prompt["enabled"] and prompt["note"] == (
        "A new profile, game race.json, is saved and loaded. game.json stays as it is."
    )
    assert renamed["attrs"]["profile_path"] == "<SBX>/configs/game race.json"
    assert renamed["configs"]["game.json"] == before["configs"]["game.json"]
    saved = json.loads(renamed["configs"]["game race.json"][-1])
    assert saved["comment2"] == "Renamed copy"
    assert renamed["configs"]["last_path.txt"] == ["<SBX>/configs/game race.json"]
    assert renamed["snapshot"]["status"] == "✔ Saved as game race.json and reloaded"
    assert "game race" in renamed["snapshot"]["title"]
    # The next Save/Reload offers the new name.
    again = full["save/reload: same name again"]["attrs"]["save_reload"]
    assert again["name"] == "game race"


def test_profile_files_and_auto_load(full):
    assert "game.json" in full["save/reload"]["configs"]
    assert "copy.json" in full["save as"]["configs"]
    saved = json.loads(full["save as"]["configs"]["copy.json"][-1])
    assert saved["comment1"] == "Quicksave!"
    # v108.138: NoBack + / NoBack - are saved per bind; the old per-side keys
    # are not written.
    x = saved["axes"]["X"]
    assert "suppress_plus" not in x and "suppress_minus" not in x
    # A and B (Plus) get NoBack on their + side from the old profile's NoBack+;
    # C (Minus) got it on its - side from its right-click menu (NoBack +).
    assert [b["noback_plus"] for b in x["binds"]] == [True, True, False, False, False, False]
    # v108.161: a POS bind has no NoBack on the - side, which it does not have.
    assert [b["noback_minus"] for b in x["binds"]] == [False, False, True, False, False, False]
    z = saved["axes"]["Z"]  # NoBack+ and NoBack- were both on: E, F (Plus), G (Minus)
    assert [(b["noback_plus"], b["noback_minus"]) for b in z["binds"]][:3] == [
        (True, False),
        (True, False),
        (False, True),
    ]
    assert saved["axes"]["Ry"]["binds"][0]["combo"] is None  # reset from a bind's menu
    assert full["auto-load switching"]["attrs"]["profile_path"].endswith("notes.json")


def test_device_led_and_autostart(full):
    assert kinds(full["LED on"]) == ["hid-feature"]
    assert full["autostart on"]["effects"][0][1] == "registry-set"
    assert full["autostart off"]["effects"][0][1] == "registry-delete"


def test_manual_on_sends_nothing_to_the_mapper_itself(full):
    # v108.144: with the Mapper (or its dialog or menu) in front, Manual On is quiet.
    assert keys(full["manual: Mapper in front"]) == []
    assert keys(full["manual: game in front"]) != []


def test_title_right_click_shows_the_readme_menu(full):
    # v108.146: a drop-down with the README as a PDF or in a window; closing it opens nothing.
    closed = full["title right-click: menu closed"]
    assert closed["attrs"]["readme_menu"] == [
        ["Open README (PDF)", True],
        ["Open README in a window", True],
    ]
    assert closed["effects"] == [] and "readme" not in closed["attrs"] and "readme_pdf" not in closed["attrs"]


def test_readme_menu_opens_the_pdf(full):
    # v108.145: the PDF is copied to the log folder and opened in the PDF viewer.
    from spnav_mapper.version import VERSION

    checkpoint = full["title right-click: README PDF"]
    copy = f"<SBX>/logs/SpaceNavigatorMapper/SpaceNavigator_Mapper_README_{VERSION}.pdf"
    assert ["startfile", copy] in [effect[1:] for effect in checkpoint["effects"]]
    pdf = checkpoint["attrs"]["readme_pdf"]
    assert pdf["path"] == copy and pdf["pdf"]
    shipped = ROOT / "spnav_mapper" / "resources" / "SpaceNavigator_Mapper_README.pdf"
    assert pdf["size"] == shipped.stat().st_size
    assert "readme" not in checkpoint["attrs"]  # no window when the PDF opens


def _readme_window_text(checkpoint):
    readme = checkpoint["attrs"]["readme"]
    assert readme["shown"] and readme["markdown"]
    assert readme["title"] == "SpaceNavigator Mapper — README"
    return readme["text"]


def test_readme_menu_opens_the_window(full):
    # v108.146: the README in a window of the Mapper, from the PDF's Markdown.
    checkpoint = full["title right-click: README window"]
    text = _readme_window_text(checkpoint)
    assert text.startswith("# SpaceNavigator Mapper — Full Editor README")
    assert "## 8. Function reference" in text and "Delete Linked Program" in text
    assert "<!--" not in text and "<div" not in text  # PDF-only HTML is left out
    assert not [e for e in checkpoint["effects"] if e[1] == "startfile"]


def test_readme_window_text_sizes(full):
    # v108.150: Text size 100%-250%, A- / A+, remembered for the next time.
    base = full["title right-click: README window"]["attrs"]["readme"]["text_size"]
    assert base[0] == "100%"
    points = base[1]
    sizes = [
        full[label]["attrs"]["readme"]["text_size"]
        for label in (
            "README window: text 150%",
            "README window: A+ twice",
            "README window: reopened",
            "README window: back to 100%",
        )
    ]
    assert sizes == [
        ["150%", points * 1.5],
        ["200%", points * 2.0],
        ["200%", points * 2.0],  # reopened: remembered
        ["100%", points],
    ]
    prefs = full["README window: back to 100%"]["configs"]["ui_preferences.json"][-1]
    assert '"readme_text_size": 1.0' in prefs
    assert (
        "**Code by:** Don Muddiman, ChatGPT and Claude"
        in full["title right-click: README window"]["attrs"]["readme"]["text"]
    )


def test_readme_window_when_no_pdf_viewer(full):
    # v108.145: with no program for PDF files, the PDF choice opens the README window.
    text = _readme_window_text(full["title right-click: no PDF viewer"])
    assert text.startswith("# SpaceNavigator Mapper — Full Editor README")


def test_delete_linked_program(full):
    # v108.145: removes the program linked to the profile, then saves and reloads it.
    cancelled, done = full["unlink program cancelled"], full["delete linked program"]
    name = full["taskbar restore"]["attrs"]["profile_path"].replace("<SBX>/configs/", "")
    for checkpoint in (cancelled, done):
        prompts = [e for e in checkpoint["effects"] if e[1] == "message-box"]
        assert len(prompts) == 1 and prompts[0][2:4] == ["question", "Delete Linked Program"]
        assert f"from {name}, then save and reload {name}?" in prompts[0][4]
    # No: nothing changes.
    assert cancelled["snapshot"]["status"] == "Delete Linked Program cancelled"
    before = json.loads(cancelled["configs"][name][-1])
    assert before["target_exe"]
    groups = json.loads(cancelled["configs"]["auto_profiles.json"][-1])["groups"]
    assert any(p["path"] == name for g in groups for p in g["profiles"])
    # Yes: the profile stays (binds kept) without its program; saved with a backup and reloaded.
    after = json.loads(done["configs"][name][-1])
    assert after["target_exe"] == "" and after["target"] is None and after["target_app_name"] == ""
    assert after["axes"] == cancelled["attrs"]["axes"]  # the binds as they were in the editor
    assert done["attrs"]["profile_path"].endswith(name)
    stem = name[: -len(".json")]
    assert sum(f.startswith(f"backups/{stem}_") for f in done["configs"]) > sum(
        f.startswith(f"backups/{stem}_") for f in cancelled["configs"]
    )
    # Auto-Profiles no longer loads it for that program.
    groups = json.loads(done["configs"]["auto_profiles.json"][-1])["groups"]
    assert not any(p["path"] == name for g in groups for p in g["profiles"])
    assert done["snapshot"]["status"].startswith("✔") and "saved and reloaded" in done["snapshot"]["status"]


def test_options_menu_has_no_separator_lines(full):
    options = [m for m in full["startup"]["snapshot"]["menu"] if m != "---" and m["text"] == "Options"][0]
    assert "---" not in options["menu"]
    assert [m["text"] for m in options["menu"]] == [
        "Minimize to Taskbar",
        "Close to System Tray",
        "Auto-start in System Tray with Windows",
        "Device LED",
        "Axis History",
        "Profile Note…",  # v108.187
        "Load Backup",
        "Restart as Administrator",  # v108.174 (Running as Administrator when it is)
        "Exit SpaceNavigator Mapper",
    ]


def test_display_menu_has_no_separator_line(full):
    # v108.178: the line before Positions Saved showed as a blank line.
    display = [m for m in full["startup"]["snapshot"]["menu"] if m != "---" and m["text"] == "Display"][0]
    assert "---" not in display["menu"]
    assert display["menu"][-1]["text"] == "Positions Saved"
    assert display["menu"][0]["text"].endswith("%")


def test_auto_load_ignores_the_mapper_itself(full):
    # v108.147: Auto Load loaded racer.json for the racer. Editing in the Mapper
    # (in front) and going back to the racer keeps the edit: no reload.
    assert full["auto load: racer in front"]["attrs"]["profile_path"] == "<SBX>/configs/racer.json"
    assert full["auto load: racer in front"]["attrs"]["comment1"] == "Racer"
    back = full["auto load: back to the game"]["attrs"]
    assert back["profile_path"] == "<SBX>/configs/racer.json"
    assert back["comment1"] == "edited in the Mapper"


def test_switch_to_lists_the_target_profiles_with_the_mapper_in_front(full):
    # v108.147: opening the menu puts the Mapper in front; the list is the racer's.
    assert full["switch to… with the Mapper in front"]["attrs"]["switch_to"] == ["racer.json  [priority 0]"]


def test_axis_history(full):
    # v108.149: Options > Axis History records the axes and opens the graph window.
    on = full["axis history on"]["attrs"]["axis_history"]
    assert on["on"] and on["checked"] and on["window"] and on["axes"] == ["X"]
    assert on["samples"] > 20
    # X: Bind #1 (A, Press/Release) taps, Bind #2 (B) taps further out, then
    # NoBack keeps A quiet on the way back; Bind #3 (C, Hold) on the - side.
    assert on["events"] == [
        ["tap", 0, "A"],
        ["tap", 1, "B"],
        ["held", 0, "A"],
        ["down", 2, "C"],
        ["up", 2, "C"],
    ]
    assert on["summary"][0].startswith("X: Peak +86%, −71%")
    assert "Bind #1 tapped 1×" in on["summary"][0] and "NoBack held 1×" in on["summary"][0]
    assert on["shapes"] == [["circle", "line", "polyline", "rect", "text"]]
    assert '"axis_history": true' in full["axis history on"]["configs"]["ui_preferences.json"][-1]
    # v108.158: NoBack shows in white. X's Bind #1 (A, 15%) and Bind #2 (B, 45%)
    # have NoBack +: in force from 15% (reached), up to 45%, off at centre.
    assert on["noback_states"] == [["+", 15], ["+", 45], [None, -1]]
    # v108.159: in the labels' column, top to bottom: Bind #2 (45%, nothing higher), Bind #1.
    assert on["noback_labels"] == ["NoBack 15%", "NoBack 45%", "NoBack: nothing to hold", "NoBack"]
    # v108.159: each bind's dots in its own colour; NoBack's hold a hollow light dot.
    assert on["dots"] == [
        ["bind1", True],
        ["bind2", True],
        ["noback", False],
        ["bind3", True],
        ["bind3", True],
    ]
    assert on["summary"][0].endswith(" · NoBack held 1× · NoBack: Bind #1 −, Bind #2 −")  # by the way back
    # v108.156: the Mapper in front sends nothing; the same stroke is marked as not sent.
    front = full["axis history: Mapper in front"]
    assert keys(front) == []
    assert front["attrs"]["axis_history"]["events"][len(on["events"]) :] == [
        ["unsent-tap", 0, "A"],
        ["unsent-tap", 1, "B"],
        ["held", 0, "A"],
        ["unsent-down", 2, "C"],
        ["unsent-up", 2, "C"],
    ]
    assert "Bind #1 tapped 1× (not sent)" in front["attrs"]["axis_history"]["summary"][0]
    # v108.160: "held by NoBack" only where NoBack changed what was sent. With Bind #1
    # up to 100% it never starts again on the way back, NoBack or not: no mark.
    nested = full["axis history: nested binds"]["attrs"]["axis_history"]["events"]
    assert nested[len(front["attrs"]["axis_history"]["events"]) :] == [["tap", 0, "A"], ["tap", 1, "B"]]
    # Right-click an axis panel: that axis is shown too, in its own graph.
    ry = full["axis history: right-click Ry"]["attrs"]["axis_history"]
    assert ry["axes"] == ["X", "Ry"] and ry["lanes"] == [["X"], ["Ry"]]
    assert [line.split(":")[0] for line in ry["summary"]] == ["X", "Ry"]
    # Export (v108.187; Save as CSV before): the samples and events of the axes shown, with
    # their axis; a tap with its Tap Dwell and a key-up with how long its key was held.
    exported = full["axis history: save as CSV"]["configs"]
    csv_text = exported["x_history.csv"][-1].splitlines()
    assert csv_text[0] == "axis,time_s,value_percent,event,bind,key,held_ms"
    assert any(line.startswith("X,") and line.endswith(",tap,Bind #1,A,45.0") for line in csv_text)
    assert any(line.startswith("X,") and line.endswith(",down,Bind #3,C,") for line in csv_text)
    assert any(line.startswith("X,") and ",up,Bind #3,C," in line and line[-1].isdigit() for line in csv_text)
    assert any(line.startswith("Ry,") for line in csv_text)
    # ... and beside it the chart report: a graph for each axis shown, and its binds.
    report = exported["x_history.html"][-1]
    assert report.count("<svg") == 2 and "<h2>X axis</h2>" in report and "<h2>Ry axis</h2>" in report
    assert "Binds of this axis" in report and "Keys, in time order" in report
    assert full["axis history: save as CSV"]["snapshot"]["status"] == (
        "✔ Axis history exported: x_history.csv and x_history.html (the chart)"
    )
    # v108.156: closing the window turns Axis History off: unchecked, stopped, forgotten.
    closed = full["axis history: window closed"]["attrs"]["axis_history"]
    assert not closed["on"] and not closed["checked"] and not closed["window"] and closed["samples"] == 0
    assert (
        '"axis_history": false' in full["axis history: window closed"]["configs"]["ui_preferences.json"][-1]
    )
    assert full["axis history: stopped"]["attrs"]["axis_history"]["samples"] == 0
    # Right-click an axis: on again, with that axis.
    rx = full["axis history: right-click Rx"]["attrs"]["axis_history"]
    assert rx["on"] and rx["checked"] and rx["window"] and rx["axes"] == ["Rx"]
    # Open at the last exit: opened again at start with the editor.
    reopened = full["axis history: reopened at start"]["attrs"]["axis_history"]
    assert reopened["on"] and reopened["checked"] and reopened["window"]
    # Unchecking stops recording and forgets.
    off = full["axis history off"]["attrs"]["axis_history"]
    assert not off["on"] and not off["checked"] and not off["window"] and off["samples"] == 0
    assert '"axis_history": false' in full["axis history off"]["configs"]["ui_preferences.json"][-1]


def test_axis_history_several_axes_text_and_size(full):
    # v108.155: any of the axes at once, on one graph or each in its own;
    # larger text (A+), a window at 80% of the screen, all remembered.
    on = full["axis history on"]["attrs"]["axis_history"]
    # The text: the app's + 2 points, at 125%. v108.187: the window is attached to the
    # editor: at its frame's right edge (their invisible borders laid over each other),
    # as tall as it, up to the screen's right edge. (Not attached: 80% of the screen;
    # see test_axis_history_beside_the_editor.)
    app_points = full["axis history on"]["attrs"]["app_font"]
    assert on["text_size"] == 1.25 and on["font"] == round((app_points + 2) * 1.25, 2)
    # v108.188: the editor is at the top left of its monitor meanwhile, and the window takes
    # the rest of the monitor at full height (see test_axis_history_beside_the_editor).
    x, y, width, _height = on["editor_frame"]
    assert on["attached"] and on["pos"] == [x + width - 14, 0]
    assert on["size"] == [2560 + 7 - on["pos"][0] - 16, 1400 + 7 - 39]
    together = full["axis history: one graph"]["attrs"]["axis_history"]
    assert together["axes"] == ["X", "Y", "Ry"] and together["together"]
    assert together["lanes"] == [["X", "Y", "Ry"]]
    assert together["shapes"] == [["circle", "line", "polyline", "text"]]  # no bands or dead zone
    larger = full["axis history: separate, larger text"]["attrs"]["axis_history"]
    assert larger["lanes"] == [["X"], ["Y"], ["Ry"]] and larger["text_size"] == 1.5
    assert larger["font"] == round((app_points + 2) * 1.5, 2) and larger["font"] > on["font"]
    assert larger["lane_min_height"] > on["lane_min_height"]
    # v108.156: A− / A+ reach the graphs and the controls, through the style sheet too
    # (a style sheet keeps a parent's font from reaching its children).
    assert larger["lane_fonts"] == [larger["font"]] and on["lane_fonts"] == [on["font"]]
    assert larger["sheet"] == f"QWidget{{font-size:{larger['font']:.1f}pt;}}"
    remembered = json.loads(full["axis history: window closed"]["configs"]["ui_preferences.json"][-1])
    assert remembered["axis_history_view"] == {
        "axes": [],
        "together": False,
        "text_size": 1.5,
        "size": None,  # attached: its size is the editor's doing, not remembered
        "attached": True,
        "legend": False,
        "editor_spots": {},  # v108.188: the editor was not moved by hand while the window was open
    }


def test_axis_history_all_button(full):
    # v108.156: All is green (checked) while all six are shown; a click hides them all
    # (red). Red: a click shows all six.
    some = full["axis history: All, some shown"]["attrs"]["axis_history"]
    assert some["axes"] == ["X", "Y", "Z", "Rx", "Ry", "Rz"] and some["all_button"] is True
    assert len(some["lanes"]) == 6 and not some["empty_label"]
    none = full["axis history: All, all shown"]["attrs"]["axis_history"]
    assert none["axes"] == [] and none["all_button"] is False
    assert none["lanes"] == [] and none["empty_label"] and none["summary"] == [""]
    assert full["axis history: save as CSV"]["attrs"]["axis_history"]["all_button"] is False


def test_axis_history_holds_the_target_on(full):
    # v108.157: opening Axis History turns the Target on for the current profile
    # (the mode stays Off); with its window in front the binds send their keys
    # (the window ignores them: no control takes the keyboard), and the history
    # marks them as sent. Closing the window puts the Target back.
    assert full["history target: mode Off"]["attrs"]["axis_history"]["target"] == [
        "Target: OFF",
        False,
        False,
        "Off",
    ]
    opened = full["history target: window opened"]["attrs"]["axis_history"]
    assert opened["target"] == ["Target: ON (History)", True, True, "Off"]
    assert opened["focusable"] == []
    stroke = full["history target: stroke, window in front"]
    assert keys(stroke)[:2] == ["a down", "a up"]
    events = stroke["attrs"]["axis_history"]["events"]
    assert events[0] == ["tap", 0, "A"] and not [e for e in events if e[0].startswith("unsent-")]
    closed = full["history target: window closed"]["attrs"]["axis_history"]
    assert closed["target"] == ["Target: OFF", False, False, "Off"] and not closed["on"]
    # While Axis History was open in Manual On, the Mapper's editor in front still sent nothing.
    assert full["axis history on"]["attrs"]["axis_history"]["target"][0] == "Target: ON (History)"
    assert full["axis history off"]["attrs"]["axis_history"]["target"][0] == "Target: MANUAL ON"
    again = full["history target: Manual On again"]["attrs"]["axis_history"]["target"]
    assert again == ["Target: MANUAL ON", True, True, "Manual On"]


def test_title_click_minimizes(full):
    # v108.138: a click on the title sends the window to the taskbar.
    assert full["title click minimizes"]["snapshot"]["state"] == "min"
    assert full["taskbar restore"]["snapshot"]["state"] == "normal"


def test_no_maximize_button(full):
    # v108.151: the title bar has no maximize ("full window") button, and a
    # maximize from the keyboard or by snapping is undone.
    assert full["taskbar restore"]["attrs"]["maximize_button"] is False
    assert full["maximize is undone"]["snapshot"]["state"] == "normal"


def _widgets(tree):
    """Every widget description in a snapshot tree."""
    if isinstance(tree, dict):
        if "cls" in tree:
            yield tree
        for value in tree.values():
            yield from _widgets(value)
    elif isinstance(tree, (list, tuple)):
        for value in tree:
            yield from _widgets(value)


def test_noback_is_set_per_bind_from_its_menu(full):
    texts = [w.get("text") for w in _widgets(full["startup"]["snapshot"]["central"])]
    assert "NoBack +" not in texts and "NoBack -" not in texts and "NoBack" not in texts
    # v108.139: a bind with NoBack has a white line along its bottom, sweeping
    # from the middle toward its NoBack side(s); the others have none.
    after = list(_widgets(full["axis panel controls"]["snapshot"]["central"]))
    lines = [w for w in after if w["cls"] == "NoBackSweep" and w.get("shown")]
    assert len(lines) == 5  # X: A, B, C; Z: E, G (v108.162: F, a Tick, has no NoBack)
    binds = [w for w in after if w["cls"] == "BindButton"]
    with_noback = [w for w in binds if "NoBack + on" in w.get("tip", "") or "NoBack - on" in w.get("tip", "")]
    # v108.161: named by the way back: NoBack - for the POS binds, NoBack + for the NEG ones
    # (v108.162: Z's Bind #2, a Tick, has none)
    assert sum("NoBack - on (quiet on the way back)" in w.get("tip", "") for w in binds) == 3
    assert sum("NoBack + on (quiet on the way back)" in w.get("tip", "") for w in binds) == 2
    assert len(with_noback) == 5
    assert all(
        any(c["cls"] == "NoBackSweep" and c.get("shown") for c in w.get("children", [])) for w in with_noback
    )
    assert all("Right-click" in w.get("tip", "") for w in binds)
    # v108.162: a Tick bind's tip leaves NoBack out of its right-click menu (v108.177: Rebound in it).
    tips = [w.get("tip", "") for w in binds]
    assert (
        sum("Right-click: Bind Enabled, Rebound, Copy, Paste, Edit macro, Reset axis" in t for t in tips) >= 1
    )
    # v108.161: the white line sweeps toward the way back, opposite the green Bind Dir line:
    # A, B (POS): left; C (NEG): right.
    sides = full["axis panel controls"]["attrs"]["noback_lines"]
    assert sides["X"] == ["-", "-", "+", "", "", ""]
    assert sides["Z"][:3] == ["-", "", "+"]  # v108.162: Z's Bind #2 is a Tick: no NoBack


def test_noback_only_for_the_way_back(full):
    # v108.161: a POS bind offers only NoBack - (the way back from its + side); its
    # NoBack stays on the + side (toggled off and on again here).
    after = full["noback - on a POS bind"]
    assert after["attrs"]["noback_lines"]["X"][0] == "-"
    bind = after["attrs"]["axes"]["X"]["binds"][0]
    assert bind["direction"] == "Plus" and bind["noback_plus"] and not bind["noback_minus"]
    assert after["attrs"]["bind_menu"] == [["NoBack -", True, True]]
    # A NEG bind made POS takes its NoBack along; an older profile's NoBack - on a POS
    # bind (which did nothing) now counts, as NoBack for its way back.
    follow = full["noback follows the bind dir"]["attrs"]["noback_follow"]
    assert follow == {"moved": [True, False], "back": [False, True], "loaded": [True, False]}


def test_bind_menu_no_noback_for_tick_and_beside_the_button(full):
    # v108.162: a Tick bind's menu offers no NoBack; the menu has no separator lines and
    # opens with its left edge at the Bind button's right edge (the pointer stays off it).
    menus = full["bind menu of a tick"]["attrs"]["menu_check"]
    # v108.177: the rebound settle guard, a submenu, for both (v108.178: named Rebound).
    # v108.179: off until a time is chosen.
    # v108.181: Copy and Paste.
    # v108.182: Undo Paste.
    # v108.183: Bind Enabled, first.
    common = ["Rebound: Off", "Copy", "Paste", "Undo Paste", "Edit macro…"]
    assert menus["Z #2 Tick"]["items"] == ["Bind Enabled", *common, "Reset Z axis"]
    assert menus["X #1 Hold"]["items"] == ["Bind Enabled", "NoBack -", *common, "Reset X axis"]
    for menu in menus.values():
        assert menu["separators"] == 0
        assert menu["at"] == menu["button right top"] and menu["at"][0] > 0


def test_bind_dir_lines_match_the_profile(full):
    # v108.140: green along the top: POS right, NEG left, FULL both, None none.
    start = full["startup"]["attrs"]
    for name, axis in start["axes"].items():
        expected = [{"Plus": "+", "Minus": "-", "Full": "+-"}.get(b["direction"], "") for b in axis["binds"]]
        assert start["dir_lines"][name] == expected, name
    assert start["dir_lines"]["X"][:3] == ["+", "+", "-"]
    after_reset = full["reset axis"]["attrs"]  # Reset makes every bind FULL
    assert after_reset["dir_lines"]["Y"] == ["+-"] * 6


def test_axis_name_and_value_are_in_the_border(full):
    # v108.139: no header row and no Reset button; "X: 0.00" is the panel's title.
    start = list(_widgets(full["startup"]["snapshot"]["central"]))
    assert "Reset" not in [w.get("text") for w in start]
    titles = [w.get("title") for w in start if w["cls"] == "AxisPanel"]
    assert sorted(titles) == sorted(f"{name}: 0.00" for name in ("X", "Y", "Z", "Rx", "Ry", "Rz"))
    moved = [
        w.get("title") for w in _widgets(full["X strokes"]["snapshot"]["central"]) if w["cls"] == "AxisPanel"
    ]
    assert "X: 0.00" in moved  # back at the centre after the strokes


def test_reset_from_a_bind_menu(full):
    for label, name in (("reset axis", "Y"), ("reset axis from a bind's menu", "Ry")):
        assert "menu-choice-missing" not in kinds(full[label])
        assert all(b["combo"] is None for b in full[label]["attrs"]["axes"][name]["binds"])


def test_close_to_tray_keeps_running(full):
    assert "window-closed" not in kinds(full["close (to tray)"])
    assert full["close (to tray)"]["snapshot"]["visible"] is False


def test_second_launch_shows_the_window_from_the_tray(full):
    # v108.137: shown by Qt (painted), not by ShowWindow from the other process.
    shown = full["second launch shows it"]
    assert shown["snapshot"]["visible"] is True
    assert "ShowWindow" not in kinds(shown)


def test_display_restart_exits_even_with_close_to_tray(tmp_path):
    session = run_session(tmp_path, "restart_tray")
    effects = kinds(session["display 110% with close-to-tray"])
    assert "process" in effects
    assert "window-closed" in effects


def test_tray_exit_quits(tmp_path):
    assert "window-closed" in kinds(run_session(tmp_path, "tray_exit")["tray menu exit"])


def test_first_run_without_configs(tmp_path):
    session = run_session(tmp_path, "fresh")
    for label, checkpoint in session.items():
        assert not checkpoint.get("errors"), (label, checkpoint["errors"])


def test_windows_login_start_hidden_in_tray(tmp_path):
    session = run_session(tmp_path, "tray")
    assert session["startup"]["snapshot"]["visible"] in (None, False)
    assert session["restore from login tray"]["snapshot"]["visible"] is True


def test_menus_and_controls_have_tips(full):
    # v108.165: no Tap dwell (ms)… in Auto-Profiles and no separator lines there;
    # a hover tip on every menu item (the tray menu too), Quick Bind and the header buttons.
    check = full["tap dwell"]["attrs"]["menu_tips_check"]
    assert check["auto-profiles"] == [
        "Enable Auto-Profiles",
        "Switch to…",
        "Reload Auto-Profiles",
        "Open auto_profiles.json…",
        "Open Auto-Profiles Folder…",
    ]
    assert check["separators"] == 0
    assert check["untipped"] == [] and check["tips shown"] == []
    assert check["controls without a tip"] == []
    # The − / + buttons: a real minus sign, its glyph sized from the button.
    assert check["step glyphs"] == ["−", "+"] and int(check["step glyph px"]) >= 20


def test_switch_to_pick_stays_for_its_program(tmp_path):
    # v108.165: a profile picked with Auto-Profiles > Switch to… stays for that program in
    # Auto Load. Before, the top-priority profile was loaded again once it was back in front.
    out = run_session(tmp_path, "switch")

    def loaded(label):
        return out[label]["attrs"]["profile_path"].rsplit("/", 1)[-1]

    assert loaded("switch: racer in front") == "racer.json"  # priority 0
    assert loaded("switch: racer2 picked") == "racer2.json"  # priority 1, picked
    assert loaded("switch: back to the racer") == "racer2.json"  # kept
    assert loaded("switch: the game") == "game.json"
    assert loaded("switch: the racer again") == "racer2.json"  # remembered for the racer
    assert loaded("switch: rules reloaded") == "racer.json"  # Reload Auto-Profiles forgets it
    # v108.170: profiles saved with the game as target are all listed for it (before,
    # only game.json, which was in the rules from the start).
    assert out["switch: two profiles, one target"]["attrs"]["switch_to"] == [
        "game.json  [priority 0]",
        "game race.json  [priority 1]",
        "game_two.json  [priority 2]",
    ]
    # v108.171: the first change in Auto Load warns once; Yes switches to Manual On.
    warned = out["edit: Auto Load warns, Manual On chosen"]["attrs"]["edit_probe"]
    assert warned == {"boxes": ["Editing in Auto Load"], "mode": "Manual On"}
    kept = out["edit: Auto Load kept"]["attrs"]["edit_probe"]
    assert kept == {"boxes": ["Editing in Auto Load"], "mode": "Auto Load"}
    # Back in the game, the loaded game_two.json (one of the game's profiles) stays, with
    # its change not yet saved; before, game.json was loaded from its file in its place.
    back = out["edit: back to the game keeps the changes"]["attrs"]["edit_probe"]
    assert back == {"loaded": "game_two.json", "changed min kept": True}
    assert all(not c.get("step_failure") for c in out.values() if isinstance(c, dict))


def test_tap_dwell_above_dzone(full):
    # v108.166: Tap Dwell, per bind, above DZone: 5 ms a step, 0 to 200 ms; greyed out
    # for the mode that sends no taps (Release-only); saved with tapping binds only.
    # v108.187: in Hold the line is the bind's Min Hold, so it is not greyed out there.
    tap = full["tap dwell"]["attrs"]["menu_tips_check"]["tap dwell"]
    assert tap["Release-only"] == [False, False, False]
    for mode in ("Hold", "Press/Release", "Press/Repeat", "Tick", "Macro"):
        assert tap[mode] == [True, True, True], mode
    assert tap["after + +"] == ["Tap Dwell:  55ms", 55] and tap["saved"] == 55
    # v108.167: with a 55 ms Tap Dwell, Repeat every 60 ms taps every 85 ms (55 down, 30 up).
    assert tap["repeat notes"] == {"60": ["→ 85 ms", True], "100": ["", False]}
    assert tap["at the bottom"] == "Tap Dwell:   0ms"
    assert tap["hold not saved"] is False
    # Back in Hold (the bind's own mode), the line above DZone is its Min Hold (v108.187).
    assert tap["grid"] == ["Min Hold:   0ms", "DZone:   5%"]
    # v108.168: the greyed-out − / + keep their large signs (and the grey look).
    assert tap["ghost glyph"] == [True, True]
    # v108.172: greyed out, fainter and see-through, just readable.
    assert tap["ghost label"] == ".QLabel { color:rgba(148,163,184,0.55); }"
    # v108.169: their styles are for the widget only, not its tip (before, a − / + tip had
    # the 20 px bold sign size, and white letters).
    assert tap["own styles"] == [".QLabel", ".QPushButton"]
    # "Profile:" is a dark gray button in its italic font; a click opens the target list.
    assert tap["profile button"] == ["QPushButton", "ProfileButton", "Profile:", True, True]


# --- v108.187: Min Hold, the profile's note, Axis History beside the editor -----------------------
@pytest.fixture(scope="module")
def v187(tmp_path_factory):
    return run_session(tmp_path_factory.mktemp("v187"), "v187")


def test_v187_session_has_no_errors(v187):
    assert "LAUNCH FAILURE" not in v187 and "DRIVER FAILURE" not in v187
    for label, checkpoint in v187.items():
        assert not checkpoint.get("errors"), (label, checkpoint["errors"])
        assert not checkpoint.get("step_failure"), (label, checkpoint["step_failure"])


def test_min_hold_on_the_tap_dwell_line_of_a_hold_bind(v187):
    # In Hold mode the Tap Dwell line and its − / + are the bind's Min Hold: 0 to 500 ms, 5 ms a step.
    probe = v187["min hold: quick bind"]["attrs"]["v187"]["min hold"]
    assert probe["label"] == "Min Hold:   0ms" and probe["enabled"] == [True, True, True]
    assert probe["tip"] == "Min Hold" and probe["saved at 0"] is False  # left out of the profile at 0
    assert probe["at the top"] == ["Min Hold: 500ms", 500]
    assert probe["set"] == ["Min Hold: 175ms", 175, 175]
    assert probe["button tip"] == ["Min Hold: 175 ms (the key stays down at least this long)"]
    # Another mode shows the Tap Dwell again (greyed out in Release-only); both are kept.
    assert probe["tick"] == ["Tap Dwell:  45ms", "Tap Dwell"]
    assert probe["release-only"] == [False, "Not used while Mode = Release-only"]
    assert probe["hold again"] == "Min Hold: 175ms" and probe["tap dwell untouched"] == 45
    assert probe["others"] == [None] * 5  # the other binds have none
    # A flick through the band, in it for an instant: the key stays down for its Min Hold.
    presses = [e for e in v187["min hold: a flick"]["effects"] if e[1] == "keys"]
    assert [(KEY_NAMES[e[2][0][0]], e[2][0][1]) for e in presses] == [("e", "down"), ("e", "up")]
    assert 175 <= presses[1][0] - presses[0][0] < 175 + 16
    # Saved with the profile, per bind, and there again after the reload.
    saved = json.loads(v187["min hold: save/reload"]["configs"]["game.json"][-1])
    binds = saved["axes"]["Z"]["binds"]
    assert binds[0]["min_hold_ms"] == 175 and all("min_hold_ms" not in b for b in binds[1:])
    assert saved["min_hold_ms"] == 60  # the profile's own short guard, as before
    assert v187["min hold: save/reload"]["attrs"]["axes"]["Z"]["binds"][0]["min_hold_ms"] == 175


def test_profile_note_flashes_the_name_until_it_is_opened(v187):
    red, white = "#ff4040", "#ffffff"
    none = v187["note: none yet"]["attrs"]["note"]
    assert (none["text"], none["colour"], none["flashing"], none["sheet"]) == ("", None, False, "")
    assert "note" not in json.loads(v187["note: none yet"]["configs"]["game.json"][-1])
    # Save Note writes the note into the profile's file at once. Whoever wrote it has read it:
    # the name is red, not flashing.
    saved = v187["note: saved, important"]
    text = "Set Prone to Hold in the game.\nRun the Mapper as Administrator."
    assert json.loads(saved["configs"]["game.json"][-1])["note"] == {"text": text, "important": True}
    assert saved["snapshot"]["status"] == "✔ Note saved in game.json"
    note = saved["attrs"]["note"]
    assert (note["text"], note["important"], note["seen"], note["flashing"]) == (text, True, True, False)
    assert note["colour"] == red and note["sheet"] == f"/* name colour */ QLineEdit {{ color:{red}; }}"
    # v108.189: written on this PC, it is read on this PC: loaded again (another profile was
    # loaded meanwhile), the name stays red. Before, it flashed again at every load.
    again = v187["note: loaded again, still read"]["attrs"]["note"]
    assert (again["seen"], again["flashing"], again["colour"]) == (True, False, red)
    marks = json.loads(v187["note: saved, important"]["configs"]["ui_preferences.json"][-1])
    assert len(marks["profile_notes_read"]) == 1 and len(marks["profile_notes_read"][0]) == 16
    # A note that arrives with the profile (never opened on this PC): the name flashes red and
    # white, one flash a second, and the tray icon's tip says so.
    arrived = "Bind Prone to Ctrl (Hold) in the game.\nRun the Mapper as Administrator."
    loaded = v187["note: another arrives with the profile, it flashes"]["attrs"]
    assert loaded["note"]["text"] == arrived
    assert loaded["note"]["seen"] is False and loaded["note"]["flashing"] is True
    assert loaded["v187"]["flash colours"] == [red, white, red, white]  # every 500 ms
    assert loaded["note"]["tip"] == "⚠ Important note, not opened yet: click the name to read it."
    assert loaded["note"]["tray"].endswith("\n⚠ Important profile note: open it")
    # Opened once (Options > Profile Note…): steady red from then on, and remembered on this PC.
    opened = v187["note: opened from Options"]
    assert ["dialog", "ProfileNoteDialog", "Profile Note — game"] in [e[1:] for e in opened["effects"]]
    note = opened["attrs"]["note"]
    assert (note["seen"], note["flashing"], note["colour"]) == (True, False, red)
    assert "⚠" not in note["tray"]
    assert len(json.loads(opened["configs"]["ui_preferences.json"][-1])["profile_notes_read"]) == 2
    # Save/Reload, and another profile loaded in between: no flash again.
    for label in ("note: save/reload, still read", "note: loaded once more, still read"):
        again = v187[label]["attrs"]["note"]
        assert (again["seen"], again["flashing"], again["colour"]) == (True, False, red), label
    assert (
        json.loads(v187["note: save/reload, still read"]["configs"]["game.json"][-1])["note"]["text"]
        == arrived
    )
    # The note's text changed (the profile came again, with more in it): it flashes again. A
    # click on the flashing name opens the note (not the target list); a right-click always does.
    text = arrived + "\nAnd bind Prone to Ctrl."
    for label in ("note: a click on the flashing name opens it", "note: right-click opens it"):
        effects = [e[1:] for e in v187[label]["effects"]]
        assert ["dialog", "ProfileNoteDialog", "Profile Note — game"] in effects, label
        assert not [e for e in effects if e[0] == "menu"], label
        assert v187[label]["attrs"]["note"]["flashing"] is False
    assert v187["note: a click on the flashing name opens it"]["attrs"]["note"]["text"] == text
    # The dialog shows the note; saved without Important, the name is as always.
    changed = v187["note: changed in its dialog, not important"]
    assert changed["attrs"]["v187"]["dialog"][:3] == ["Profile Note — game", text, True]
    # v108.188: the window's text, the note's included, is in the font of the Auto-Profiles
    # drop-down: the app's text 2 points larger.
    fonts = changed["attrs"]["v187"]["dialog fonts"]
    assert fonts["menu"] == round(changed["attrs"]["app_font"] + 2, 2)
    assert fonts["controls"] == [fonts["menu"]] and fonts["text"] == fonts["menu"]
    assert fonts["sheet"] == f"QWidget{{font-size:{fonts['menu']:.1f}pt;}}"
    assert fonts["text sheet"] == f"font-size:{fonts['menu']:.1f}pt; }}"
    assert json.loads(changed["configs"]["game.json"][-1])["note"] == {
        "text": "Only a remark.",
        "important": False,
    }
    assert (changed["attrs"]["note"]["colour"], changed["attrs"]["note"]["sheet"]) == (None, "")
    assert changed["attrs"]["note"]["tip"].startswith("Note (right-click to open it")
    # Saved empty, the note is gone from the file.
    removed = v187["note: removed"]
    assert "note" not in json.loads(removed["configs"]["game.json"][-1])
    assert removed["snapshot"]["status"] == "✔ Note removed from game.json"


def test_axis_history_beside_the_editor(v187):
    start = v187["startup"]["snapshot"]["geometry"]  # the editor: x, y, width, height
    on = v187["history: attached to the editor"]["attrs"]["axis_history"]
    # v108.188: opening the window moves the editor to the top left of its monitor, its size
    # unchanged (7 pixels of its frame's invisible left border are past the screen's edge) ...
    assert on["editor_pos"] == [-7, 0] and on["editor_size"] == start[2:]
    # ... and the window takes the rest of the monitor: from the editor's right edge to the
    # screen's right edge, over the full height of the work area (2560 x 1400 here).
    x, _y, width, _height = on["editor_frame"]
    assert on["attached"] and on["pos"] == [x + width - 14, 0]
    assert on["pos"][0] + on["size"][0] + 16 == 2560 + 7 and on["size"][1] + 39 == 1400 + 7
    assert on["buttons"] == ["All", "Pause", "Clear", "Export CSV/HTML", "Legend", "A−", "A+"]
    # Five of the ten seconds are shown; the bar is at now.
    assert on["times"] == ["−5 s", "−2.5 s", "now"] and on["scroll"] == [50, 50, 0.0]
    # Running: no labels on the dots; the keys are listed, the newest on top, in rows that stay.
    assert on["dot_labels"] == [] and on["keys_rows"] == 7  # the heading and six rows, always
    assert on["keys"] == [
        ["Z", 1, "E", "held", True],  # the flick: held for its Min Hold
        ["X", 3, "C", "held", True],
        ["X", 1, "A", "held by NoBack", True],
        ["X", 2, "B", "tap", True],
        ["X", 1, "A", "tap", True],
    ]
    # Paused: the dots are labelled, with the times.
    paused = v187["history: paused, the dots labelled"]["attrs"]["axis_history"]
    assert paused["paused"] and paused["dot_labels"][:3] == ["A tap · 45 ms", "B tap · 45 ms", "C down"]
    assert paused["dot_labels"][3].startswith("C up · held ") and paused["keys"] == on["keys"]
    # Scrolled all the way back: the five seconds before; Resume returns to now.
    back = v187["history: scrolled back"]["attrs"]["axis_history"]
    assert back["scroll"] == [0, 50, 5.0] and back["times"] == ["−10 s", "−7.5 s", "−5 s"]
    resumed = v187["history: resumed"]["attrs"]["axis_history"]
    assert not resumed["paused"] and resumed["scroll"] == [50, 50, 0.0] and resumed["dot_labels"] == []
    # Export: the CSV and the chart report beside it, the whole ten seconds of the axes shown.
    exported = v187["history: exported"]
    assert (
        exported["snapshot"]["status"] == "✔ Axis history exported: capture.csv and capture.html (the chart)"
    )
    csv_text = exported["configs"]["capture.csv"][-1].splitlines()
    assert csv_text[0].endswith(",held_ms")
    held = [line.split(",") for line in csv_text if ",up,Bind #1,E," in line]
    assert len(held) == 1 and held[0][0] == "Z" and 175 <= float(held[0][-1]) < 191
    report = exported["configs"]["capture.html"][-1]
    assert report.count("<svg") == 2 and "E up · held 176 ms" in report and "<td>175 ms</td>" in report
    assert "game" in report and "the last 10 seconds" in report
    # Legend shows the explanation; remembered.
    assert v187["history: legend"]["attrs"]["axis_history"]["legend"] == [True, True]
    assert on["legend"] == [False, False]


def test_button_1_freezes_axis_history(v187):
    # v108.188: while the Axis History window is open, the puck's Button 1 freezes the graphs
    # and, pressed again, resumes them, whatever it is bound to (Ctrl+S here); its own key is
    # not sent. Button 2 is its bind's as always.
    def keys(label):
        return [[KEY_NAMES[k[0]] for k in e[2]] for e in v187[label]["effects"] if e[1] == "keys"]

    frozen = v187["history: Button 1 freezes"]
    assert frozen["attrs"]["axis_history"]["paused"] is True and keys("history: Button 1 freezes") == []
    assert frozen["snapshot"]["status"] == "Axis History frozen by Button 1: press it again to resume."
    assert frozen["attrs"]["axis_history"]["dot_labels"]  # frozen: the dots are labelled
    again = v187["history: Button 1 again resumes"]
    assert again["attrs"]["axis_history"]["paused"] is False
    assert keys("history: Button 1 again resumes") == []
    assert again["snapshot"]["status"] == "Axis History resumed by Button 1."
    # v108.189: and so on, press after press: pause, resume, pause, resume.
    third, fourth = (
        v187["history: Button 1 a third time freezes"],
        v187["history: Button 1 a fourth time resumes"],
    )
    assert third["attrs"]["axis_history"]["paused"] is True
    assert third["snapshot"]["status"] == "Axis History frozen by Button 1: press it again to resume."
    assert fourth["attrs"]["axis_history"]["paused"] is False
    assert fourth["snapshot"]["status"] == "Axis History resumed by Button 1."
    assert (
        keys("history: Button 1 a third time freezes")
        == keys("history: Button 1 a fourth time resumes")
        == []
    )
    assert keys("history: Button 2 is its bind's") == [["f5"], ["f5"]]
    assert v187["history: Button 2 is its bind's"]["attrs"]["axis_history"]["paused"] is False
    # With the window closed, Button 1 sends its own key again.
    assert keys("history: Button 1 is its bind's again") == [["ctrl", "s"], ["s", "ctrl"]]


def test_editor_goes_aside_for_axis_history_and_comes_back(v187):
    start = v187["startup"]["snapshot"]["geometry"]
    # Moved by hand while the window is open: the window stays beside it, still at full height.
    moved = v187["history: the editor moved"]["attrs"]["axis_history"]
    x, _y, width, _height = moved["editor_frame"]
    assert moved["editor_pos"] == [200, 60] and moved["pos"] == [x + width - 14, 0]
    assert moved["pos"][0] + moved["size"][0] + 16 == 2560 + 7 and moved["size"][1] + 39 == 1400 + 7
    # Closing the window puts the editor back where, and as large as, it was before it opened.
    closed = v187["history: closed"]
    assert closed["snapshot"]["geometry"] == start
    # Its place beside the window is remembered, apart from its own, per monitor.
    view = json.loads(closed["configs"]["ui_preferences.json"][-1])["axis_history_view"]
    assert view["editor_spots"] == {"\\\\.\\DISPLAY1": [200, 60, None, None]}
    again = v187["history: opened again"]["attrs"]["axis_history"]
    assert again["editor_pos"] == [200, 60] and again["editor_size"] == start[2:]
    assert again["pos"] == moved["pos"] and again["size"] == moved["size"]
    # Resized by hand while the window is open: that size is remembered with the place.
    resized = v187["history: the editor resized"]["attrs"]["axis_history"]
    assert resized["editor_size"] == [start[2] - 40, start[3] - 100]
    assert resized["pos"][0] == moved["pos"][0] - 40 and resized["size"][1] == moved["size"][1]
    # Not attached: the editor goes back, and the window is one of its own (80% of the screen).
    free = v187["history: not attached"]
    assert free["snapshot"]["geometry"] == start
    assert free["attrs"]["axis_history"]["attached"] is False
    assert free["attrs"]["axis_history"]["size"] == [round(2560 * 0.8), round(1400 * 0.8)]
    assert free["attrs"]["axis_history"]["pos"] == [256, 140]
    view = json.loads(free["configs"]["ui_preferences.json"][-1])["axis_history_view"]
    assert view["attached"] is False and view["editor_spots"] == {
        "\\\\.\\DISPLAY1": [200, 60, start[2] - 40, start[3] - 100]
    }
    # Attached again: the editor goes to its remembered place and size, the window beside it.
    back_on = v187["history: attached again"]["attrs"]["axis_history"]
    assert back_on["editor_pos"] == [200, 60] and back_on["editor_size"] == resized["editor_size"]
    assert back_on["pos"] == resized["pos"] and back_on["size"] == resized["size"]
    assert v187["history: closed again"]["snapshot"]["geometry"] == start
    # Exit with the window open and the editor aside: the position and size saved are the
    # editor's own.
    assert v187["history: open at exit"]["attrs"]["axis_history"]["editor_pos"] == [200, 60]
    state = json.loads(v187["exit"]["configs"]["window_state.json"][-1])["views"]["full"]
    assert [state["x"], state["y"], state["w"], state["h"]] == start


# v108.189 -------------------------------------------------------------------
@pytest.fixture(scope="module")
def v189(tmp_path_factory):
    """Two starts in one folder: (the first start, the next start)."""
    folder = tmp_path_factory.mktemp("v189")
    return run_session(folder, "v189"), run_session(folder, "v189_again")


def test_v189_sessions_have_no_errors(v189):
    for session in v189:
        assert "LAUNCH FAILURE" not in session and "DRIVER FAILURE" not in session
        for label, checkpoint in session.items():
            assert not checkpoint.get("trace"), label
            assert not checkpoint["errors"], (label, checkpoint["errors"])


def test_an_opened_note_is_still_read_at_the_next_start(v189):
    first, second = v189
    red = "#ff4040"
    # Never opened on this PC: it flashes. Opened: steady red.
    arrived = first["note: arrives with the profile, it flashes"]["attrs"]["note"]
    assert (arrived["seen"], arrived["flashing"]) == (False, True)
    opened = first["note: opened"]
    assert (opened["attrs"]["note"]["seen"], opened["attrs"]["note"]["flashing"]) == (True, False)
    marks = json.loads(opened["configs"]["ui_preferences.json"][-1])["profile_notes_read"]
    assert len(marks) == 1
    # The next start loads the last configuration, the note with it: read, not flashing. Before
    # v108.189 the name flashed again at every start.
    start = second["startup"]["attrs"]["note"]
    assert start["text"] == arrived["text"] and start["important"] is True
    assert (start["seen"], start["flashing"], start["colour"]) == (True, False, red)
    assert "⚠" not in start["tip"]
    # Another text is another note: it flashes until it is opened.
    changed = second["note: another arrives, it flashes"]["attrs"]["note"]
    assert changed["text"] != arrived["text"] and (changed["seen"], changed["flashing"]) == (False, True)
    assert json.loads(second["exit"]["configs"]["ui_preferences.json"][-1])["profile_notes_read"] == marks


def test_exit_with_axis_history_open_saves_the_editors_own_place(v189):
    first, second = v189
    moved = first["editor: moved"]["snapshot"]["geometry"]
    assert moved[:2] == [300, 31]
    # Axis History, attached, has the editor aside at the top left when the Mapper exits ...
    aside = first["history: open at exit"]
    assert aside["snapshot"]["geometry"][:2] == [-7, 0]
    # ... and the place saved for the next start is the editor's own, on the checked monitor.
    state = json.loads(first["exit"]["configs"]["window_state.json"][-1])
    saved = state["per_monitor"]["\\\\.\\DISPLAY1"]["full"]
    assert (saved["relative_x"], saved["relative_y"], saved["w"], saved["h"]) == tuple(moved)
    # The next start: Axis History opens again (it was open at the exit), only once the editor
    # has been put in its saved place, and closing it puts the editor back there.
    start = second["startup"]
    assert start["attrs"]["axis_history"]["checked"] is True
    assert start["snapshot"]["geometry"][:2] == [-7, 0]
    assert second["history: closed"]["snapshot"]["geometry"] == moved
    state = json.loads(second["exit"]["configs"]["window_state.json"][-1])
    assert state["per_monitor"]["\\\\.\\DISPLAY1"]["full"]["relative_x"] == 300
