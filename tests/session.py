"""Drive one scripted Mapper session under tests/fakeqt.py; write checkpoints as JSON.

    python tests/session.py package <repo root>                      out.json [script] [sandbox root]
    python tests/session.py single  <SpaceNavigator_Mapper_..._Complete.py> out.json [script] [sandbox root]

script: full (default), restart, restart_tray, tray_exit, fresh, tray, switch, v187, v189,
v189_again (the next start in the sandbox v189 left).

The whole app starts through bootstrap.launch() with a seeded configs/
folder, then the script clicks, types and moves the axes. Every checkpoint
records what a user could see (widget tree, menus, status bar, tray), the
effects (keys sent, HID reports, dialogs, processes, registry writes), the
configs/ files and any exception that escaped a Qt callback.

Runs in its own interpreter, because the fakes patch PyQt5, ctypes, time and
sys.platform. Sandbox paths and the launcher name are replaced by <SBX> and
<ENTRY> so runs of different builds can be compared.
"""

import json
import os
import re
import shutil
import sys
import traceback

KIND, SRC, OUT = sys.argv[1:4]
SCRIPT = sys.argv[4] if len(sys.argv) > 4 else "full"
import tempfile  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fakeqt  # noqa: E402

SBX_ROOT = sys.argv[5] if len(sys.argv) > 5 else os.path.join(tempfile.gettempdir(), "spnav_sbx")
# "<script>_again": the next start in the sandbox <script> left (its configs/ as it exited).
AGAIN = SCRIPT.endswith("_again")
SBX = os.path.join(SBX_ROOT, f"{KIND}_{SCRIPT[:-6] if AGAIN else SCRIPT}")
if AGAIN:
    shutil.rmtree(SBX + "/spnav_mapper", ignore_errors=True)
else:
    shutil.rmtree(SBX, ignore_errors=True)
    os.makedirs(SBX + "/configs")
    os.makedirs(SBX + "/logs")
os.environ["LOCALAPPDATA"] = SBX + "/logs"
for k in ("QT_SCREEN_SCALE_FACTORS", "SPNAV_AUTO_SCREEN_FACTORS", "SPNAV_UI_SCALE"):
    os.environ.pop(k, None)

if KIND == "single":
    entry = os.path.join(SBX, "SpaceNavigator_Mapper.py")
    shutil.copy(SRC, entry)
else:
    shutil.copytree(os.path.join(SRC, "spnav_mapper"), os.path.join(SBX, "spnav_mapper"))
    entry = os.path.join(SBX, "main.py")
    shutil.copy(os.path.join(SRC, "main.py"), entry)


def bind(direction=None, combo=None, mode="Hold", lo=0, hi=100, comment="", dead=5):
    return {
        "direction": direction,
        "combo": combo,
        "mode": mode,
        "min": lo,
        "max": hi,
        "comment": comment,
        "dead": dead,
    }


EMPTY = bind()


def axis(binds, plus=False, minus=False, selected=0):
    # An old (v108.137 and earlier) profile: NoBack + / NoBack - for the whole
    # axis side; loading gives each bind on that side its own NoBack.
    binds = binds + [EMPTY] * (6 - len(binds))
    return {"dead": 5, "selected": selected, "binds": binds, "suppress_plus": plus, "suppress_minus": minus}


PROFILE = {
    "axes": {
        "X": axis(
            [
                bind("Plus", ["a"], "Press/Release", 10, 40, "A tap"),
                bind("Plus", ["b"], "Press/Release", 40, 100, "B tap"),
                bind("Minus", ["c"], "Hold", 10, 100, "C hold"),
            ],
            plus=True,
        ),
        "Y": axis([bind("Full", ["ctrl", "d"], "Press/Repeat", 20, 100, "repeat")]),
        "Z": axis(
            [
                bind("Plus", ["e"], "Hold", 10, 40, "E"),
                bind("Plus", ["f"], "Tick", 60, 100, "tick"),
                bind("Minus", ["g"], "Release-only", 30, 100, "rel"),
            ],
            plus=True,
            minus=True,
            selected=1,
        ),
        "Rx": axis([]),
        "Ry": axis([bind("Minus", ["space"], "Hold", 15, 100, "jump")]),
        "Rz": axis([]),
    },
    "target": None,
    "quick_key1": ["ctrl", "s"],
    "quick_key2": ["f5"],
    "led_on": False,
    "hys_pct": 3,
    "min_hold_ms": 60,
    "hold_ignore_max": True,
    "tap_down_ms": 45,
    "auto_mode": False,
    "auto_select_mode": "Manual On",
    "version": "v108.117",
    "comment1": "Save game",
    "comment2": "Quick load",
    "target_exe": "",
    "target_file_description": "",
    "target_product_name": "",
    "target_app_name": "",
}


def _seed():
    with open(SBX + "/configs/game.json", "w", encoding="utf-8") as f:
        json.dump(PROFILE, f, indent=2)
    with open(SBX + "/configs/last_path.txt", "w", encoding="utf-8") as f:
        f.write(SBX + "/configs/game.json")
    NOTES = json.loads(json.dumps(PROFILE))
    NOTES["axes"]["X"] = axis([bind("Plus", ["n"], "Hold", 10, 100, "N")])
    NOTES["comment1"] = "Notes profile"
    NOTES["target_exe"] = "C:/Tools/notes.exe"
    with open(SBX + "/configs/notes.json", "w", encoding="utf-8") as f:
        json.dump(NOTES, f, indent=2)
    with open(SBX + "/configs/auto_profiles.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "groups": [
                    {
                        "name": "Game",
                        "enabled": True,
                        "match": {"exe": ["game.exe"]},
                        "profiles": [{"path": "game.json", "priority": 0, "enabled": True}],
                    },
                    {
                        "name": "Notes",
                        "enabled": True,
                        "match": {"exe": ["notes.exe"]},
                        "profiles": [{"path": "notes.json", "priority": 0, "enabled": True}],
                    },
                ]
            },
            f,
            indent=2,
        )
    with open(SBX + "/configs/window_state.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": 5,
                "views": {
                    "full": {
                        "screen_name": r"\\.\DISPLAY1",
                        "serial": "",
                        "screen_geometry": {"x": 0, "y": 0, "w": 2560, "h": 1440},
                        "relative_x": 300,
                        "relative_y": 200,
                        "x": 300,
                        "y": 200,
                        "w": 500,
                        "h": 200,
                    }
                },
            },
            f,
        )


if SCRIPT != "fresh" and not AGAIN:
    _seed()

env = fakeqt.install()
env.win32.windows = [
    (0x5001, "My Game", 777, "C:/Games/MyGame/game.exe"),
    (0x5002, "Notes", 778, "C:/Tools/notes.exe"),
]
env.win32.foreground = 0x5001
CHECKPOINTS = []
_seen = [0]


def configs_listing():
    out = {}
    for root, _dirs, files in os.walk(SBX + "/configs"):
        for name in sorted(files):
            path = os.path.join(root, name)
            rel = os.path.relpath(path, SBX + "/configs")
            rel = re.sub(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d+", "<stamp>", rel)
            try:
                text = open(path, encoding="utf-8").read()
            except UnicodeDecodeError:
                text = "<binary>"
            out[rel] = out.get(rel, []) + [text.replace(SBX, "<SBX>")]
    return out


def checkpoint(label):
    win = env.main_window()
    effects = env.effects[_seen[0] :]
    _seen[0] = len(env.effects)
    CHECKPOINTS.append(
        {
            "label": label,
            "snapshot": fakeqt.snapshot(win),
            "effects": [
                list(map(lambda v: v.replace(SBX, "<SBX>") if isinstance(v, str) else v, e)) for e in effects
            ],
            "errors": list(env.errors),
            "configs": configs_listing(),
            "attrs": probe(win),
        }
    )
    env.errors.clear()


def probe(win):
    """App state that drives behaviour but is not a widget property."""
    if win is None:
        return None
    out = {}
    for k in (
        "activated",
        "target_hwnd",
        "profile_path",
        "hys_pct",
        "min_hold_ms",
        "hold_ignore_max",
        "tap_down_ms",
        "quick_key1",
        "quick_key2",
    ):
        v = getattr(win, k, "<missing>")
        out[k] = v.replace(SBX, "<SBX>") if isinstance(v, str) else repr(v)
    label, axes = getattr(win, "lbl3", None), getattr(win, "axes", {})
    if label is not None and axes:
        comment = next(iter(axes.values())).slot_comments[0]
        out["version_label"] = {
            "points": label.font().pointSizeF(),
            "comment_points": comment.font().pointSizeF(),
            "right_aligned": bool(int(label.alignment()) & 0x2),
        }
    axes = getattr(win, "axes", {})
    out["axes"] = {n: json.loads(json.dumps(p.get_config(), default=repr)) for n, p in axes.items()}
    # The lines on each Bind button, as the side(s) they sweep to: white
    # NoBack along the bottom (v108.139), green Bind Dir along the top (v108.140).
    for key, attribute in (("noback_lines", "_noback_glow"), ("dir_lines", "_dir_line")):
        lines = {}
        for n, p in axes.items():
            row = []
            for btn in getattr(p, "slot_btns", ()):
                line = getattr(btn, attribute, None)
                shown = line is not None and line._wanted and hasattr(line, "sides")
                row.append(line.sides() if shown else "")
            lines[n] = row
        out[key] = lines
    if getattr(win, "_menu_check", None):
        out["menu_check"] = win._menu_check
    if getattr(win, "_edit_probe", None):
        out["edit_probe"] = win._edit_probe
    if getattr(win, "_menu_tips_check", None):
        out["menu_tips_check"] = win._menu_tips_check
    if getattr(win, "_noback_follow", None):
        out["noback_follow"] = win._noback_follow
    # v108.161: the NoBack items of the last Bind button menu opened (text, enabled, checked)
    menu = getattr(axes.get("X"), "_bind_menu", None) if axes else None
    if menu is not None:
        out["bind_menu"] = [
            [a.text(), a.isEnabled(), a.isChecked()] for a in menu.actions() if a.text().startswith("NoBack")
        ]
    pdf = getattr(win, "_readme_pdf", None)
    if pdf:  # v108.145: the README PDF the title's right-click opened
        with open(pdf, "rb") as stream:
            data = stream.read()
        out["readme_pdf"] = {
            "path": pdf.replace(SBX, "<SBX>"),
            "size": len(data),
            "pdf": data[:5] == b"%PDF-",
        }
    # v108.151: no maximize ("full window") button
    out["maximize_button"] = bool(int(win.windowFlags()) & int(fakeqt.Qt.WindowMaximizeButtonHint))
    out["comment1"] = win.comment1.text()
    switch = getattr(win, "_switch_probe", None)
    if switch is not None:  # v108.147: Switch to… opened with the Mapper in front
        out["switch_to"] = switch
    history_window = getattr(win, "_axis_history_window", None)
    out["app_font"] = round(fakeqt.QCoreApplication._app_font.pointSizeF(), 2)
    x_panel = (getattr(win, "axes", None) or {}).get("X")
    if x_panel is not None and (x_panel.history is not None or history_window is not None):
        # v108.149: Options > Axis History
        import re as _re

        window = history_window
        out["axis_history"] = {
            "on": x_panel.history is not None,
            "checked": win._axis_history_action.isChecked(),
            "window": bool(window is not None and window.isVisible()),
            "axes": window.shown_axes() if window else None,
            "together": window.together() if window else None,
            "lanes": [lane.axes for lane in window.lanes] if window else None,
            "summary": [_re.sub(r"<[^>]+>", "", line) for line in window.summary_label.text().split("<br>")]
            if window
            else None,
            "samples": len(x_panel.history.samples) if x_panel.history else 0,
            "events": [[e[1], e[2], e[3]] for e in x_panel.history.events] if x_panel.history else [],
            "shapes": [sorted({s[0] for s in window.shapes(lane.axes, 800, 400)}) for lane in window.lanes]
            if window
            else [],
            # v108.158: NoBack in white (labels in the first graph) and its recorded states
            "noback_labels": [
                s[3]
                for s in window.shapes(window.lanes[0].axes, 800, 400)
                if s[0] == "text" and s[4] == "noback"
            ]
            if window and window.lanes
            else None,
            "noback_states": [[n[1], n[2]] for n in x_panel.history.noback] if x_panel.history else [],
            "dots": [
                [s[4], s[5]]
                for s in window.shapes(window.lanes[0].axes, 800, 400)
                if s[0] == "circle" and s[3] >= 5
            ]
            if window and window.lanes
            else None,
            "text_size": window.text_size if window else None,
            "font": round(window.text_font.pointSizeF(), 2) if window else None,
            "lane_fonts": sorted({round(lane.font().pointSizeF(), 2) for lane in window.lanes})
            if window
            else None,
            "sheet": window.styleSheet() if window else None,
            "all_button": window.all_btn.isChecked() if window else None,
            "empty_label": (not window.empty_label.isHidden()) if window else None,
            # v108.157: the Target is on while the window is open
            "target": [win.target_btn.text(), win.target_btn.isChecked(), win.activated, win.auto_chk.mode()],
            "focusable": sorted(
                {
                    type(c).__name__
                    for c in window.findChildren(fakeqt.QWidget)
                    if c.focusPolicy() != fakeqt.Qt.NoFocus
                }
            )
            if window
            else None,
            "lane_min_height": window.lanes[0].minimumHeight() if window and window.lanes else None,
            "size": [window.width(), window.height()] if window else None,
        }
        if window is not None and hasattr(window, "time_bar"):  # v108.187
            frame = win.frameGeometry()
            texts = (
                [s[3] for s in window.shapes(window.lanes[0].axes, 800, 400) if s[0] == "text"]
                if window.lanes
                else []
            )
            out["axis_history"].update(
                {
                    "attached": window.attached(),
                    "pos": [window.x(), window.y()],
                    "editor_frame": [frame.x(), frame.y(), frame.width(), frame.height()],
                    "editor_pos": [win.x(), win.y()],
                    "editor_size": [win.width(), win.height()],
                    "scroll": [window.time_bar.value(), window.time_bar.maximum(), window.ago()],
                    "paused": window.paused_at is not None,
                    "times": texts[-3:],
                    "dot_labels": [t for t in texts if " tap" in t or " down" in t or " up" in t],
                    "keys": [
                        [row["axis"], row["bind"] + 1, row["key"], row["what"], row["sent"]]
                        for row in window.key_rows()
                    ],
                    "keys_rows": window.keys_label.text().count("<tr>"),
                    "legend": [window.legend_btn.isChecked(), not window.hint_label.isHidden()],
                    "buttons": [b.text() for b in window.findChildren(fakeqt.QPushButton)],
                }
            )
    if getattr(win, "_v187", None):
        out["v187"] = json.loads(json.dumps(win._v187, default=repr))
    if hasattr(win, "profile_note"):  # v108.187: the profile's note and the profile name's colour
        tray = getattr(win, "_tray", None)
        out["note"] = {
            "text": win.profile_note,
            "important": win.profile_note_important,
            "seen": win._note_seen,
            "flashing": win._note_flash_timer.isActive(),
            "colour": win.profile_display._name_colour,
            "sheet": win.profile_display.styleSheet(),
            "tip": win.profile_display.toolTip().splitlines()[0],
            "tray": tray.toolTip() if tray is not None else None,
        }
    prompt = getattr(win, "_save_reload_probe", None)
    if prompt is not None:  # v108.148: the Save/Reload prompt last shown
        out["save_reload"] = prompt
    menu = getattr(win, "_readme_menu", None)
    if menu is not None:  # v108.146: the title's README drop-down
        out["readme_menu"] = [(a.text(), a.isEnabled()) for a in menu.actions() if a.text()]
    viewer = getattr(win, "_readme_viewer", None)
    if viewer is not None:
        out["readme"] = {
            "shown": viewer.isVisible(),
            "title": viewer.windowTitle(),
            "markdown": viewer.browser.isMarkdown(),
            "text": viewer.browser.toPlainText(),
            "text_size": [viewer.size_box.currentText(), viewer.browser.font().pointSizeF()],
        }
    return out


def stroke(axis_index, points, step_ms=16, per=4):
    """Move one axis through device-unit points (-350..350), sampling every step."""
    hid = env.hid
    for a, b in zip(points, points[1:]):
        n = max(1, int(abs(b - a) / (350 * per / 100.0)))
        for i in range(1, n + 1):
            v = a + (b - a) * i / n
            vals = [0] * 6
            vals[axis_index] = v
            hid.push_axes(*vals)
            env.advance(step_ms)
    env.advance(100)


def _try_action(win, *paths):
    from fakeqt import find_action

    for path in paths:
        try:
            find_action(win, *path).trigger()
            return True
        except LookupError:
            continue
    raise LookupError(paths)


def _tray(win):
    return getattr(win, "_tray", None) or win._v10871_tray


def step(label, fn, settle=300):
    try:
        fn()
        env.advance(settle)
        checkpoint(label)
    except Exception:
        env.advance(settle)
        checkpoint(label)
        CHECKPOINTS[-1]["step_failure"] = traceback.format_exc().splitlines()[-1]


ARRIVED_NOTE = "Bind Prone to Ctrl (Hold) in the game.\nRun the Mapper as Administrator."


def v187(W):
    """v108.187: Min Hold, the profile's note, and the Axis History window beside the editor."""
    from fakeqt import QPushButton, find_action, find_widget

    notes = sys.modules["spnav_mapper.ui.profile_note_dialog"]
    game, other = SBX + "/configs/game.json", SBX + "/configs/notes.json"
    W()._v187 = {}

    def save_reload():
        dialogs = sys.modules["spnav_mapper.ui.save_reload_dialog"].SaveReloadDialog
        saved_exec, dialogs.exec_ = dialogs.exec_, lambda dialog: 1
        try:
            find_widget(W().centralWidget(), QPushButton, text="Save/Reload").click()
        finally:
            dialogs.exec_ = saved_exec

    # --- Min Hold: the Tap Dwell line of a Hold bind ---
    def min_hold():
        z = W().axes["Z"]
        z._select_slot(0)  # E: Hold, + side, from 15% (DZone 5 + Min 10) to 40%
        probe = {
            "label": z.tap_lbl.text(),
            "enabled": [z.tap_lbl.isEnabled(), z.tap_dec.isEnabled(), z.tap_inc.isEnabled()],
            "tip": z.tap_lbl.toolTip().split(":")[0],
            "saved at 0": "min_hold_ms" in z.get_config()["binds"][0],
        }
        for _ in range(120):
            z.tap_inc.click()
        probe["at the top"] = [z.tap_lbl.text(), z.binds[0]["min_hold_ms"]]
        for _ in range(65):
            z.tap_dec.click()
        probe["set"] = [
            z.tap_lbl.text(),
            z.binds[0]["min_hold_ms"],
            z.get_config()["binds"][0]["min_hold_ms"],
        ]
        probe["button tip"] = [t for t in z.slot_btns[0].toolTip().splitlines() if t.startswith("Min Hold")]
        z.qb_mode.choose("Tick")
        probe["tick"] = [z.tap_lbl.text(), z.tap_lbl.toolTip().split(":")[0]]
        z.qb_mode.choose("Release-only")
        probe["release-only"] = [z.tap_lbl.isEnabled(), z.tap_lbl.toolTip().splitlines()[0]]
        z.qb_mode.choose("Hold")
        probe["hold again"] = z.tap_lbl.text()
        probe["tap dwell untouched"] = z.binds[0]["tap_ms"]
        probe["others"] = [b.get("min_hold_ms") for b in z.get_config()["binds"][1:]]
        W()._v187["min hold"] = probe

    def flick():
        # Z in E's band for an instant: about 29% for one sample, then back to rest.
        env.hid.push_axes(0, 0, 100, 0, 0, 0)
        env.advance(16)
        env.hid.push_axes(0, 0, 0, 0, 0, 0)
        env.advance(600)

    step("min hold: quick bind", min_hold)
    step("min hold: a flick", flick)
    step("min hold: save/reload", save_reload, 400)

    # --- The profile's note ---
    step("note: none yet", lambda: None)
    step(
        "note: saved, important",
        lambda: notes.save_note(
            W(), "Set Prone to Hold in the game.\r\nRun the Mapper as Administrator.  ", True
        ),
    )

    def load_other_then_game():
        W()._load_config_from_path(other)
        W()._load_config_from_path(game)
        colours = []
        for _ in range(4):
            colours.append(W().profile_display._name_colour)
            env.advance(500)
        W()._v187["flash colours"] = colours

    def note_arrives(text):
        # As a shared profile brings it: the note is in the file, and was never opened on this PC.
        def run():
            pure = sys.modules["spnav_mapper.profile_note"]
            pure.write_note_to_profile(game, text, True, SBX + "/configs/backups")
            load_other_then_game()

        return run

    # v108.189: written here, it is read here, at later loads too.
    step("note: loaded again, still read", load_other_then_game)
    step("note: another arrives with the profile, it flashes", note_arrives(ARRIVED_NOTE))
    step("note: opened from Options", lambda: find_action(W(), "Options", "Profile Note…").trigger())
    step("note: save/reload, still read", save_reload, 400)
    step("note: loaded once more, still read", load_other_then_game)

    def click_the_flashing_name():
        note_arrives(ARRIVED_NOTE + "\nAnd bind Prone to Ctrl.")()
        W().profile_display.mousePressEvent(None)

    step("note: a click on the flashing name opens it", click_the_flashing_name)
    step("note: right-click opens it", lambda: W().profile_display.contextMenuEvent(None))

    def dialog_saves():
        dialog = notes.ProfileNoteDialog(W())
        W()._v187["dialog"] = [
            dialog.windowTitle(),
            dialog.text_edit.toPlainText(),
            dialog.important_chk.isChecked(),
            dialog.where.text(),
        ]
        # v108.188: the whole window in the drop-downs' font.
        menu_font = sys.modules["spnav_mapper.ui.window_chrome"].dropdown_font(W()).pointSizeF()
        W()._v187["dialog fonts"] = {
            "menu": round(menu_font, 2),
            "controls": sorted(
                {round(w.font().pointSizeF(), 2) for w in dialog.findChildren(fakeqt.QWidget)}
            ),
            "text": round(dialog.text_edit.font().pointSizeF(), 2),
            "sheet": dialog.styleSheet(),
            "text sheet": dialog.text_edit.styleSheet().split("padding:4px; ")[1],
        }
        dialog.text_edit.setPlainText("Only a remark.")
        dialog.important_chk.setChecked(False)
        dialog.save()

    step("note: changed in its dialog, not important", dialog_saves)
    step("note: removed", lambda: notes.save_note(W(), "   ", True))

    # --- Axis History beside the editor ---
    def paint():
        window = W()._axis_history_window
        window.refresh()
        for lane in window.lanes:
            lane.paintEvent(None)

    def history_on():
        find_action(W(), "Options", "Axis History").trigger()
        env.advance(300)  # joined again once shown
        stroke(0, [0, 300, 0, -250, 0])
        W()._axis_history_window.set_axes(["X", "Z"])
        flick()
        paint()

    def pause():
        W()._axis_history_window.toggle_pause()
        paint()

    def scroll_back():
        bar = W()._axis_history_window.time_bar
        bar.setValue(bar.minimum())
        paint()

    def editor_moved():
        # Moved by hand while the window is open: the window stays beside it, the place is remembered.
        W().move(200, 60)
        fakeqt.send_event(W(), "Move")

    def editor_resized():
        W().resize(W().width() - 40, W().height() - 100)
        fakeqt.send_event(W(), "Resize")

    def press(mask):
        # A press and release of the puck's Button 1 (mask 1) or Button 2 (mask 2).
        env.hid.push_buttons(mask)
        env.advance(100)
        env.hid.push_buttons(0)
        env.advance(100)

    def export():
        fakeqt.QFileDialog.ANSWERS = [SBX + "/configs/capture"]
        W()._axis_history_window.export()

    def open_history():
        find_action(W(), "Options", "Axis History").trigger()
        env.advance(300)

    step("history: attached to the editor", history_on)
    step("history: paused, the dots labelled", pause)
    step("history: scrolled back", scroll_back)
    step("history: resumed", pause)
    # v108.188: the puck's Button 1 freezes and resumes while the window is open.
    step("history: Button 1 freezes", lambda: press(1))
    step("history: Button 1 again resumes", lambda: press(1))
    step("history: Button 1 a third time freezes", lambda: press(1))  # v108.189: and so on
    step("history: Button 1 a fourth time resumes", lambda: press(1))
    step("history: Button 2 is its bind's", lambda: press(2))
    step("history: exported", export)
    step("history: legend", lambda: W()._axis_history_window.legend_btn.click())
    step("history: the editor moved", editor_moved)
    step("history: closed", lambda: W()._axis_history_window.close())
    step("history: Button 1 is its bind's again", lambda: press(1))
    step("history: opened again", open_history)
    step("history: the editor resized", editor_resized)
    step("history: not attached", lambda: W()._axis_history_window.attach_check.setChecked(False))
    step("history: attached again", lambda: W()._axis_history_window.attach_check.setChecked(True))
    step("history: closed again", lambda: W()._axis_history_window.close())
    step("history: open at exit", open_history)  # the editor is aside; the Mapper exits like that
    step("exit", lambda: find_action(W(), "Options", "Exit SpaceNavigator Mapper").trigger(), 500)


def v189(W):
    """v108.189: an opened note stays read at the next start; Axis History open at exit."""
    from fakeqt import find_action

    pure = sys.modules["spnav_mapper.profile_note"]
    game, other = SBX + "/configs/game.json", SBX + "/configs/notes.json"

    def note_arrives(text):
        def run():
            pure.write_note_to_profile(game, text, True, SBX + "/configs/backups")
            W()._load_config_from_path(other)
            W()._load_config_from_path(game)

        return run

    def open_history():
        find_action(W(), "Options", "Axis History").trigger()
        env.advance(300)

    if SCRIPT == "v189":
        step("note: arrives with the profile, it flashes", note_arrives(ARRIVED_NOTE))
        step("note: opened", lambda: find_action(W(), "Options", "Profile Note…").trigger())

        def positions_saved():
            placement = sys.modules["spnav_mapper.ui.placement"]
            placement.set_positions_monitor(W(), fakeqt.QGuiApplication.primaryScreen())

        step("positions saved: this monitor", positions_saved)
        step("editor: moved", lambda: W().move(300, 31))
        step("history: open at exit", open_history)  # the editor is aside; the Mapper exits like that
    else:
        # The next start: the note opened before the exit is read; Axis History is open again.
        step("history: closed", lambda: W()._axis_history_window.close())
        step("note: another arrives, it flashes", note_arrives(ARRIVED_NOTE + "\nAnd bind Prone to Ctrl."))
    step("exit", lambda: find_action(W(), "Options", "Exit SpaceNavigator Mapper").trigger(), 500)


def session(app):
    from fakeqt import QPushButton, QRect, QScreen, find_action, find_widget

    W = env.main_window
    env.advance(1500)
    checkpoint("startup")
    if SCRIPT == "v187":
        return v187(W)
    if SCRIPT in ("v189", "v189_again"):
        return v189(W)
    if SCRIPT == "tray":
        step(
            "restore from login tray",
            lambda: _tray(W()).activated.emit(fakeqt.QSystemTrayIcon.DoubleClick),
            500,
        )

    step("X strokes", lambda: stroke(0, [0, 280, 0, -280, 0]))

    def yzr():
        stroke(1, [0, 300, 0], per=2)
        stroke(2, [0, 300, 0, -200, 0])
        stroke(4, [0, -200, 0])

    step("Y/Z/Ry strokes", yzr)

    def buttons():
        h = env.hid
        h.push_buttons(1)
        env.advance(100)
        h.push_buttons(0)
        env.advance(100)
        h.push_buttons(2)
        env.advance(100)
        h.push_buttons(0)
        env.advance(100)

    step("hardware buttons", buttons)

    def slots():
        p = W().axes["Z"]
        p._select_slot(0)
        env.advance(50)
        p._select_slot(1)
        env.advance(50)
        p._select_slot(2)

    step("select bind slots", slots)

    def axis_controls():
        p = W().axes["X"]
        # Right-click Bind #3 (C, minus) > NoBack + (the way back from the - side;
        # v108.161), for that bind only (v108.138).
        fakeqt.QMenu.CHOICES = ["NoBack +"]
        p.slot_btns[2].contextMenuEvent(None)
        env.advance(50)
        p.min_inc.click()
        env.advance(30)
        p.max_dec.click()
        env.advance(30)
        p.dead_inc.click()
        env.advance(30)
        p.qb_mode.choose("Tick")
        env.advance(50)
        p.qb_mode.choose("Hold")
        env.advance(50)
        p._select_slot(3)
        env.advance(30)
        p.qb_dir.choose(p.qb_dir.itemText(1))
        env.advance(30)

    step("axis panel controls", axis_controls)

    def noback_on_a_pos_bind():
        # v108.161: a POS bind offers only NoBack - (its way back); turn it off and on.
        fakeqt.QMenu.CHOICES = ["NoBack -"]
        W().axes["X"].slot_btns[0].contextMenuEvent(None)
        fakeqt.QMenu.CHOICES = ["NoBack -"]
        W().axes["X"].slot_btns[0].contextMenuEvent(None)

    step("noback - on a POS bind", noback_on_a_pos_bind)

    def noback_follows_the_bind_dir():
        # v108.161: C (NEG, NoBack on its - side) made POS: NoBack moves to its + side;
        # an older profile's NoBack - on a POS bind (D) counts for its + side.
        p = W().axes["X"]
        p._select_slot(2)
        p.qb_dir.choose("POS (+)")
        moved = [p.binds[2]["noback_plus"], p.binds[2]["noback_minus"]]
        p.qb_dir.choose("NEG (-)")
        back = [p.binds[2]["noback_plus"], p.binds[2]["noback_minus"]]
        cfg = p.get_config()
        cfg["binds"][3].update(direction="Plus", combo=["d"], noback_plus=False, noback_minus=True)
        p.set_config(cfg)
        loaded = [p.binds[3]["noback_plus"], p.binds[3]["noback_minus"]]
        cfg["binds"][3].update(direction=None, combo=None, noback_plus=False, noback_minus=False)
        p.set_config(cfg)
        W()._noback_follow = {"moved": moved, "back": back, "loaded": loaded}

    step("noback follows the bind dir", noback_follows_the_bind_dir)

    def bind_menu_of_a_tick():
        # v108.162: a Tick bind's menu has no NoBack; no separators; it opens with its
        # left edge at the button's right edge.
        out = {}
        for axis, idx in (("Z", 1), ("X", 0)):
            p = W().axes[axis]
            fakeqt.QMenu.CHOICES = []
            p.slot_btns[idx].contextMenuEvent(None)
            menu = p._bind_menu
            button = p.slot_btns[idx]
            corner = button.mapToGlobal(fakeqt.QPoint(button.width(), 0))
            out[f"{axis} #{idx + 1} {p.binds[idx]['mode']}"] = {
                "items": [a.text() for a in menu.actions()],
                "separators": sum(1 for a in menu.actions() if a._sep),
                "at": [menu.exec_pos.x(), menu.exec_pos.y()],
                "button right top": [corner.x(), corner.y()],
            }
        W()._menu_check = out

    # settle=0: no time passes, so the later steps' timers keep their phase.
    step("bind menu of a tick", bind_menu_of_a_tick, settle=0)

    def macro_on_rz():
        # v108.141: Mode = Macro, as the editor's Save leaves it.
        p = W().axes["Rz"]
        p._select_slot(0)
        p.qb_dir.choose("POS (+)")
        p.qb_mode.choose("Macro")
        p.set_macro(0, [{"tap": ["q"]}, {"delay": 100}, {"tap": ["w"]}])

    step("macro bind on Rz", macro_on_rz)
    step("Rz macro stroke", lambda: stroke(5, [0, 200, 200, 200, 0]), 400)
    step("X stroke after edits", lambda: stroke(0, [0, 300, 0, -300, 0]))

    def comments():
        W().comment1.type_text("Quicksave!")
        W().axes["X"].slot_comments[0].type_text("first")

    step("comments", comments)

    def reset_from_bind_menu(name, bind):
        fakeqt.QMenu.CHOICES = [f"Reset {name} axis"]
        W().axes[name].slot_btns[bind].contextMenuEvent(None)

    # v108.139: Reset is only in the Bind buttons' right-click menu.
    step("reset axis", lambda: reset_from_bind_menu("Y", 2))
    step("reset axis from a bind's menu", lambda: reset_from_bind_menu("Ry", 0))

    def save_reload(name=None, answer=1):
        """Click Save/Reload; its prompt (v108.148) is answered with `name` typed, OK (1) or Cancel (0)."""
        dialogs = sys.modules["spnav_mapper.ui.save_reload_dialog"].SaveReloadDialog
        seen = {}

        def exec_(dialog):
            if name is not None:
                dialog.name_edit.setText(name)
            seen.update(
                title=dialog.windowTitle(),
                name=dialog.name_edit.text(),
                note=dialog.note.text(),
                enabled=dialog.save_btn.isEnabled(),
            )
            return answer

        saved_exec = dialogs.exec_
        dialogs.exec_ = exec_
        try:
            # The editor's button: not the prompt's own (it says Save/Reload too).
            find_widget(W().centralWidget(), QPushButton, text="Save/Reload").click()
        finally:
            dialogs.exec_ = saved_exec
        W()._save_reload_probe = seen

    # v108.142: Save/Reload asks first; Cancel saves nothing.
    step("save/reload cancelled", lambda: save_reload(answer=0), 400)
    step("save/reload", lambda: save_reload(), 400)

    def save_as():
        fakeqt.QFileDialog.ANSWERS = [SBX + "/configs/copy.json"]
        find_widget(W(), QPushButton, text="Save as").click()

    step("save as", save_as)

    def load():
        fakeqt.QFileDialog.ANSWERS = [SBX + "/configs/game.json"]
        find_widget(W(), QPushButton, text="Load").click()

    step("load", load)
    # v108.129 has no Refresh button: the list refreshes in the background.
    step("refresh", lambda: W()._maybe_auto_refresh_windows(), 600)
    step("target button", lambda: W().target_btn.click())
    step("target button again", lambda: W().target_btn.click())
    step("LED on", lambda: find_action(W(), "Options", "Device LED").trigger())
    step("LED off", lambda: find_action(W(), "Options", "Device LED").trigger())

    def menus_and_tips():
        # v108.165: Auto-Profiles has no Tap dwell (ms)… and no separator lines;
        # every item of every menu (and the tray menu) has a hover tip.
        win = W()
        menus = {a.text(): a.menu() for a in win.menuBar().actions() if a.menu() is not None}
        menus["tray"] = win._tray_menu
        for menu in list(menus.values()):
            menu.aboutToShow.emit()  # the items a menu fills in as it opens
        untipped, shown = [], []

        def walk(menu, path):
            shown.append([path, bool(getattr(menu, "_tips_visible", False))])
            for action in menu.actions():
                if action.isSeparator():
                    continue
                if not action.toolTip() or action.toolTip() == action.text():
                    untipped.append(f"{path} > {action.text()}")
                if action.menu() is not None:
                    action.menu().aboutToShow.emit()
                    walk(action.menu(), f"{path} > {action.text()}")

        for title, menu in menus.items():
            walk(menu, title)
        auto = menus["Auto-Profiles"]
        x = win.axes["X"]
        controls = {
            "Bind Dir": x.qb_dir,
            "Mode": x.qb_mode,
            "Min%": x.min_text,
            "Max%": x.max_text,
            "DZone": x.dead_lbl,
            "-": x.min_dec,
            "+": x.max_inc,
            "Button 1": win.key1_btn,
            "Button 2": win.key2_btn,
            "Target": win.target_btn,
        }
        for button in win._profile_buttons.buttons:
            controls[button.text()] = button
        controls["Tap Dwell"] = x.tap_lbl
        # v108.166: Tap Dwell, above DZone, greyed out for Hold and Release-only.
        was = x.qb_mode.currentText()
        tap = {}
        for mode in ("Hold", "Release-only", "Press/Release", "Press/Repeat", "Tick", "Macro"):
            x.qb_mode.choose(mode)
            tap[mode] = [x.tap_lbl.isEnabled(), x.tap_dec.isEnabled(), x.tap_inc.isEnabled()]
        x.qb_mode.choose("Press/Release")
        x.tap_inc.click()
        x.tap_inc.click()
        tap["after + +"] = [x.tap_lbl.text(), x.binds[x.selected_index]["tap_ms"]]
        tap["saved"] = x.get_config()["binds"][x.selected_index].get("tap_ms")
        # v108.167: Press/Repeat taps no sooner than the Tap Dwell plus 30 ms (the key up).
        x.qb_mode.choose("Press/Repeat")
        notes = {}
        for every in ("60", "100"):
            x.qb_repeat.setCurrentText(every)
            notes[every] = [x.repeat_note.text(), bool(x.repeat_note.toolTip())]
        tap["repeat notes"] = notes
        x.qb_mode.choose("Press/Release")
        for _ in range(60):
            x.tap_dec.click()
        tap["at the bottom"] = x.tap_lbl.text()
        x.binds[x.selected_index]["tap_ms"] = 45
        x.qb_mode.choose(was)
        tap["hold not saved"] = (
            "tap_ms" in x.get_config()["binds"][x.selected_index] if was == "Hold" else None
        )
        tap["grid"] = [x.tap_lbl.text(), x.dead_lbl.text()]
        # v108.168: greyed out, a − / + keeps its sign's size. (v108.187: in Release-only;
        # in Hold the line is the bind's Min Hold.)
        x.qb_mode.choose("Release-only")
        tap["ghost glyph"] = [
            "font-size:" in x.tap_dec.styleSheet(),
            "rgba(75,85,99,0.5)" in x.tap_dec.styleSheet(),
        ]
        tap["ghost label"] = x.tap_lbl.styleSheet()
        # v108.169: every style of these is for the widget only (".QPushButton { … }"),
        # so it does not reach its tip.
        tap["own styles"] = sorted(
            {
                w.styleSheet().split("{")[0].strip()
                for w in (x.tap_dec, x.tap_lbl, x.min_inc, x.dead_dec, x.repeat_note, win.title_label)
            }
        )
        x.qb_mode.choose(was)
        profile = win.profile_button
        tap["profile button"] = [
            type(profile).__name__,
            profile.objectName(),
            profile.text(),
            profile.font().italic(),
            bool(profile.toolTip()),
        ]
        win._menu_tips_check = {
            "tap dwell": tap,
            "controls without a tip": [name for name, w in controls.items() if not w.toolTip()],
            "step glyphs": [x.min_dec.text(), x.min_inc.text()],
            "step glyph px": x.min_dec.styleSheet().split("font-size:")[-1].split("px")[0],
            "auto-profiles": [a.text() for a in auto.actions()],
            "separators": sum(a.isSeparator() for a in auto.actions()),
            "untipped": untipped,
            "tips shown": [p for p, on in shown if not on],
        }

    step("tap dwell", menus_and_tips)
    step(
        "open auto_profiles.json",
        lambda: find_action(W(), "Auto-Profiles", "Open auto_profiles.json…").trigger(),
    )
    step("open folder", lambda: find_action(W(), "Auto-Profiles", "Open Auto-Profiles Folder…").trigger())
    step("reload auto-profiles", lambda: find_action(W(), "Auto-Profiles", "Reload Auto-Profiles").trigger())

    def switch_menu():
        sub = find_action(W(), "Auto-Profiles", "Switch to…")._submenu
        if sub is not None:
            sub.aboutToShow.emit()
            acts = [a for a in sub._actions if not a._sep]
            if acts:
                acts[0].trigger()

    step("switch to…", switch_menu)

    def pick_target():
        fakeqt.QMenu.CHOICES = ["My Game"]
        W().profile_button.click()  # v108.169: "Profile:" is a button

    step("pick target", pick_target, 1500)

    def auto_load():
        W().auto_chk.choose("Auto Load")
        env.advance(300)
        env.win32.foreground = 0x5002
        env.advance(2500)
        env.win32.foreground = 0x5001
        env.advance(2500)

    step("auto-load switching", auto_load)
    step("auto mode manual", lambda: W().auto_chk.choose("Manual On"))

    MAPPER_WINDOW = (0x5009, "SpaceNavigator Mapper — game", env.win32.my_pid, entry)

    def mapper_in_front():
        # v108.144: Manual On sends nothing while the Mapper itself is in front.
        env.win32.windows.append(MAPPER_WINDOW)
        env.win32.foreground = MAPPER_WINDOW[0]
        stroke(0, [0, 300, 0])

    def game_in_front():
        env.win32.windows.remove(MAPPER_WINDOW)
        env.win32.foreground = 0x5001
        stroke(0, [0, 300, 0])

    step("manual: Mapper in front", mapper_in_front)
    step("manual: game in front", game_in_front)

    # v108.147: Auto Load ignores the Mapper's own window. A profile edited
    # there is not reloaded on going back to the game, and Switch to… lists
    # the target's profiles, not the Mapper's (none).
    RACER = (0x5004, "Racer", 779, "C:/Games/Racer/racer.exe")

    def racer_in_front():
        racer = json.loads(json.dumps(PROFILE))
        racer.update(comment1="Racer", auto_select_mode="Auto Load", auto_mode=True, target_exe=RACER[3])
        with open(SBX + "/configs/racer.json", "w", encoding="utf-8") as f:
            json.dump(racer, f, indent=2)
        rules_path = SBX + "/configs/auto_profiles.json"
        with open(rules_path, encoding="utf-8") as f:
            rules = json.load(f)
        rules["groups"].append(
            {
                "name": "Racer",
                "enabled": True,
                "match": {"exe": ["racer.exe"]},
                "profiles": [{"path": "racer.json", "priority": 0, "enabled": True}],
            }
        )
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=2)
        os.utime(rules_path, (2_000_000_000, 2_000_000_000))  # a new modification time: reloaded
        env.win32.windows.append(RACER)
        W().auto_chk.choose("Auto Load")
        env.win32.foreground = RACER[0]
        env.advance(2500)

    def edit_in_mapper():
        env.win32.windows.append(MAPPER_WINDOW)
        env.win32.foreground = MAPPER_WINDOW[0]
        W().comment1.setText("edited in the Mapper")
        env.advance(2500)

    def back_to_racer():
        env.win32.windows.remove(MAPPER_WINDOW)
        env.win32.foreground = RACER[0]
        env.advance(2500)

    def switch_with_mapper_in_front():
        env.win32.windows.append(MAPPER_WINDOW)
        env.win32.foreground = MAPPER_WINDOW[0]
        sub = find_action(W(), "Auto-Profiles", "Switch to…")._submenu
        sub.aboutToShow.emit()
        W()._switch_probe = [a.text() for a in sub._actions if not a._sep]
        env.win32.windows.remove(MAPPER_WINDOW)
        env.win32.foreground = 0x5001

    step("auto load: racer in front", racer_in_front)
    step("auto load: edit in the Mapper", edit_in_mapper)
    step("auto load: back to the game", back_to_racer)
    step("switch to… with the Mapper in front", switch_with_mapper_in_front)
    step("auto mode manual again", lambda: W().auto_chk.choose("Manual On"))

    # v108.149: Options > Axis History records the axes and shows them as a graph.
    def paint_history():
        window = W()._axis_history_window
        window.refresh()
        for lane in window.lanes:
            lane.paintEvent(None)  # paints without errors

    def history_on():
        find_action(W(), "Options", "Axis History").trigger()
        stroke(0, [0, 300, 0, -250, 0])
        paint_history()

    def history_for_ry():
        fakeqt.QMenu.CHOICES = ["Axis History…"]
        try:
            W().axes["Ry"].contextMenuEvent(None)
        finally:
            fakeqt.QMenu.CHOICES = []

    def history_csv():
        window = W()._axis_history_window
        window.set_axes(["X", "Ry"])
        fakeqt.QFileDialog.ANSWERS = [SBX + "/configs/x_history.csv"]
        window.export()  # v108.187: the CSV and, beside it, the chart report

    def history_together():
        # v108.155: the axes shown on one graph
        W()._axis_history_window.axis_checks["Y"].setChecked(True)
        W()._axis_history_window.layout_box.setCurrentText("One graph")
        paint_history()

    def history_separate_larger():
        W()._axis_history_window.layout_box.setCurrentText("Separate graphs")
        W()._axis_history_window.step_text_size(+1)
        paint_history()

    def history_all():
        W()._axis_history_window.all_btn.click()  # v108.156: all on (green) / all off (red)

    def history_right_click_rx():
        fakeqt.QMenu.CHOICES = ["Axis History…"]
        try:
            W().axes["Rx"].contextMenuEvent(None)
        finally:
            fakeqt.QMenu.CHOICES = []

    def history_reopen():
        from spnav_mapper.ui.axis_history_window import reopen_axis_history

        W()._axis_history_window.close()
        reopen_axis_history(W())  # what start-up does when it was open at the last exit

    def history_mapper_in_front():
        # v108.156: the Mapper (its history window) in front: no keys are sent,
        # and the history marks what the binds would have sent.
        env.win32.windows.append(MAPPER_WINDOW)
        env.win32.foreground = MAPPER_WINDOW[0]
        try:
            stroke(0, [0, 300, 0, -250, 0])
        finally:
            env.win32.windows.remove(MAPPER_WINDOW)
            env.win32.foreground = 0x5001

    def history_nested_binds():
        # v108.160: Bind #1 (A) up to 100%: it is still in its band on the way back,
        # so it would send nothing more without NoBack either: no "held" mark.
        binds = W().axes["X"].binds
        binds[0]["max"] = 100
        try:
            stroke(0, [0, 300, 0])
        finally:
            binds[0]["max"] = 40

    step("axis history on", history_on)
    step("axis history: Mapper in front", history_mapper_in_front)
    step("axis history: nested binds", history_nested_binds)
    step("axis history: right-click Ry", history_for_ry)
    step("axis history: one graph", history_together)
    step("axis history: separate, larger text", history_separate_larger)
    step("axis history: save as CSV", history_csv)
    step("axis history: All, some shown", history_all)
    step("axis history: All, all shown", history_all)
    step("axis history: window closed", lambda: W()._axis_history_window.close())
    step("axis history: stopped", lambda: stroke(0, [0, 200, 0]))
    step("axis history: right-click Rx", history_right_click_rx)
    step("axis history: reopened at start", history_reopen)
    step("axis history off", lambda: find_action(W(), "Options", "Axis History").trigger())

    # v108.157: the Target is on for the current profile while Axis History is open.
    def history_target_stroke():
        env.win32.foreground = int(W()._axis_history_window.winId())
        try:
            stroke(0, [0, 300, 0])
        finally:
            env.win32.foreground = 0x5001

    step("history target: mode Off", lambda: W().auto_chk.choose("Off"))
    step("history target: window opened", lambda: find_action(W(), "Options", "Axis History").trigger())
    step("history target: stroke, window in front", history_target_stroke)
    step("history target: window closed", lambda: W()._axis_history_window.close())
    step("history target: Manual On again", lambda: W().auto_chk.choose("Manual On"))
    step("title click minimizes", lambda: W().title_label.mousePressEvent(None), 100)
    step("taskbar restore", lambda: W().showNormal(), 100)

    def maximize():
        # v108.151: Win+Up or snapping to the top edge maximizes; the Mapper undoes it.
        W().showMaximized()
        W().changeEvent(fakeqt.QEvent(fakeqt.QEvent.WindowStateChange))

    step("maximize is undone", maximize, 100)

    def readme_choice(choice, close_window=False):
        # v108.146: the title's right-click is a drop-down: the README as a PDF or in a window.
        viewer = getattr(W(), "_readme_viewer", None)
        if close_window and viewer is not None:
            viewer.close()
        fakeqt.QMenu.CHOICES = [choice] if choice else []
        try:
            W().title_label.contextMenuEvent(None)
        finally:
            fakeqt.QMenu.CHOICES = []

    step("title right-click: menu closed", lambda: readme_choice(None), 100)
    step("title right-click: README PDF", lambda: readme_choice("Open README (PDF)"), 100)

    def readme_without_pdf_viewer():
        # No program opens PDF files: the README window opens instead.
        import os as os_module

        def refuse(*_args, **_kwargs):
            raise OSError("No application is associated with the specified file")

        opener = os_module.startfile
        os_module.startfile = refuse
        try:
            readme_choice("Open README (PDF)")
            env.advance(100)
        finally:
            os_module.startfile = opener

    step("title right-click: no PDF viewer", readme_without_pdf_viewer)
    step(
        "title right-click: README window",
        lambda: readme_choice("Open README in a window", close_window=True),
        100,
    )

    # v108.150: the README window's Text size, remembered.
    def readme_reopened():
        W()._readme_viewer.close()
        W()._readme_viewer = None
        readme_choice("Open README in a window")

    step("README window: text 150%", lambda: W()._readme_viewer.size_box.setCurrentText("150%"))
    step("README window: A+ twice", lambda: [W()._readme_viewer.step_text_size(+1) for _ in range(2)])
    step("README window: reopened", readme_reopened, 100)
    step("README window: back to 100%", lambda: W()._readme_viewer.set_text_size(1.0))

    def delete_linked_program(answer):
        # v108.145: the Profile drop-down's first entry unlinks the target program.
        fakeqt.QMessageBox.ANSWER = answer
        fakeqt.QMenu.CHOICES = ["Delete Linked Program"]
        try:
            W()._show_target_picker(None)
        finally:
            fakeqt.QMessageBox.ANSWER = None
            fakeqt.QMenu.CHOICES = []

    step("unlink program cancelled", lambda: delete_linked_program(fakeqt.QMessageBox.No), 200)
    step("delete linked program", lambda: delete_linked_program(fakeqt.QMessageBox.Yes), 400)

    # v108.148: Save/Reload's prompt can change the file name.
    def rename_setup():
        W()._load_config_from_path(SBX + "/configs/game.json")
        W().comment2.setText("Renamed copy")

    step("save/reload: load game.json", rename_setup, 200)
    step("save/reload: a settings name is refused", lambda: save_reload("last_config"), 400)
    step("save/reload as a new name", lambda: save_reload("game race.json"), 400)
    step("save/reload: same name again", lambda: save_reload(), 400)

    def second_monitor():
        s2 = QScreen(r"\\.\DISPLAY2", QRect(2560, 0, 1920, 1080), QRect(2560, 0, 1920, 1040), 96.0, 1.25)
        fakeqt.QCoreApplication._screens.append(s2)
        W().windowHandle().setScreen(s2)

    step("moved to second monitor", second_monitor, 800)
    step("minimize", lambda: find_action(W(), "Options", "Minimize to Taskbar").trigger())
    step("restore from tray", lambda: _tray(W()).activated.emit(fakeqt.QSystemTrayIcon.DoubleClick))
    step(
        "autostart on",
        lambda: find_action(W(), "Options", "Auto-start in System Tray with Windows").trigger(),
    )
    step(
        "autostart off",
        lambda: find_action(W(), "Options", "Auto-start in System Tray with Windows").trigger(),
    )
    step("close-to-tray on", lambda: find_action(W(), "Options", "Close to System Tray").trigger())
    step("close (to tray)", lambda: W().close())

    def second_launch():
        # What a second launch posts (single_instance); see v108.137.
        import ctypes
        from ctypes import wintypes

        from spnav_mapper.single_instance import restore_message_id

        msg = wintypes.MSG()
        msg.message = restore_message_id()
        W().nativeEvent(b"windows_generic_MSG", ctypes.addressof(msg))

    step("second launch shows it", second_launch, 500)
    step("close-to-tray off", lambda: find_action(W(), "Options", "Close to System Tray").trigger())
    if SCRIPT == "restart":
        step("display 110%", lambda: find_action(W(), "Display", "110%").trigger(), 500)
    elif SCRIPT == "restart_tray":
        step("close-to-tray on again", lambda: find_action(W(), "Options", "Close to System Tray").trigger())
        step("display 110% with close-to-tray", lambda: find_action(W(), "Display", "110%").trigger(), 500)
    elif SCRIPT == "switch":
        # v108.165: a profile picked with Switch to… stays for that program.
        def two_racer_profiles():
            racer2 = json.loads(json.dumps(PROFILE))
            racer2.update(comment1="Racer two", auto_select_mode="Auto Load", auto_mode=True)
            with open(SBX + "/configs/racer2.json", "w", encoding="utf-8") as f:
                json.dump(racer2, f, indent=2)
            rules_path = SBX + "/configs/auto_profiles.json"
            with open(rules_path, encoding="utf-8") as f:
                rules = json.load(f)
            racer_rule = next(g for g in rules["groups"] if g["name"] == "Racer")
            racer_rule["profiles"] = [
                {"path": "racer.json", "priority": 0, "enabled": True},
                {"path": "racer2.json", "priority": 1, "enabled": True},
            ]
            with open(rules_path, "w", encoding="utf-8") as f:
                json.dump(rules, f, indent=2)
            os.utime(rules_path, (2_000_000_100, 2_000_000_100))
            W().auto_chk.choose("Auto Load")
            env.win32.foreground = 0x5001  # the game, then the racer
            env.advance(2500)
            W().auto_chk.choose("Auto Load")  # game.json is a Manual On profile
            env.win32.foreground = RACER[0]
            env.advance(2500)

        def pick_second():
            env.win32.windows.append(MAPPER_WINDOW)
            env.win32.foreground = MAPPER_WINDOW[0]
            sub = find_action(W(), "Auto-Profiles", "Switch to…")._submenu
            sub.aboutToShow.emit()
            next(a for a in sub._actions if a.text().startswith("racer2.json")).trigger()
            env.advance(1000)

        def racer_again():
            if MAPPER_WINDOW in env.win32.windows:
                env.win32.windows.remove(MAPPER_WINDOW)
            env.win32.foreground = RACER[0]
            env.advance(2500)

        def game_again():
            env.win32.foreground = 0x5001
            env.advance(2500)
            W().auto_chk.choose("Auto Load")  # game.json is a Manual On profile

        def reload_rules():
            find_action(W(), "Auto-Profiles", "Reload Auto-Profiles").trigger()
            env.advance(2500)

        step("switch: racer in front", two_racer_profiles)
        step("switch: racer2 picked", pick_second)
        step("switch: back to the racer", racer_again)
        step("switch: the game", game_again)
        step("switch: the racer again", racer_again)
        step("switch: rules reloaded", reload_rules)

        # v108.170: two profiles saved with the same target are both in Switch to….
        def two_profiles_one_target():
            W().auto_chk.choose("Manual On")
            W()._load_config_from_path(SBX + "/configs/game.json")
            fakeqt.QFileDialog.ANSWERS = [SBX + "/configs/game_two.json"]
            W().save_config()
            env.advance(300)
            env.win32.windows.append(MAPPER_WINDOW)
            env.win32.foreground = MAPPER_WINDOW[0]
            sub = find_action(W(), "Auto-Profiles", "Switch to…")._submenu
            sub.aboutToShow.emit()
            W()._switch_probe = [a.text() for a in sub._actions if not a._sep]
            env.win32.windows.remove(MAPPER_WINDOW)
            env.win32.foreground = 0x5001

        step("switch: two profiles, one target", two_profiles_one_target)

        # v108.171: in Auto Load, the first change warns and offers Manual On; going
        # back to the game keeps a loaded profile of the game (and its changes).
        def boxes_since(first):
            return [e[3] for e in env.effects[first:] if e[1] == "message-box"]

        def edit_in_auto_load(answer):
            def run():
                W().auto_chk.choose("Auto Load")
                env.advance(300)
                env.win32.windows.append(MAPPER_WINDOW)
                env.win32.foreground = MAPPER_WINDOW[0]
                first = len(env.effects)
                fakeqt.QMessageBox.ANSWER = answer
                x = W().axes["X"]
                x.min_inc.click()
                env.advance(50)
                x.min_inc.click()  # a second change: no second warning
                env.advance(50)
                fakeqt.QMessageBox.ANSWER = None
                W()._edit_probe = {"boxes": boxes_since(first), "mode": W().auto_chk.mode()}
                env.win32.windows.remove(MAPPER_WINDOW)
                env.win32.foreground = 0x5001

            return run

        def back_to_the_game_keeps_changes():
            W().auto_chk.choose("Auto Load")
            env.advance(300)
            x = W().axes["X"]
            before = x.binds[x.selected_index]["min"]
            env.win32.windows.append(MAPPER_WINDOW)
            env.win32.foreground = MAPPER_WINDOW[0]
            fakeqt.QMessageBox.ANSWER = fakeqt.QMessageBox.No
            x.min_inc.click()
            env.advance(50)
            fakeqt.QMessageBox.ANSWER = None
            env.win32.windows.remove(MAPPER_WINDOW)
            env.win32.foreground = 0x5001  # the game: game_two.json is one of its profiles
            env.advance(3000)
            W()._edit_probe = {
                "loaded": os.path.basename(W().profile_path or ""),
                "changed min kept": x.binds[x.selected_index]["min"] == before + 1,
            }

        step("edit: Auto Load warns, Manual On chosen", edit_in_auto_load(fakeqt.QMessageBox.Yes))
        step("edit: Auto Load kept", edit_in_auto_load(fakeqt.QMessageBox.No))
        step("edit: back to the game keeps the changes", back_to_the_game_keeps_changes)
        step("exit", lambda: find_action(W(), "Options", "Exit SpaceNavigator Mapper").trigger(), 500)
    elif SCRIPT == "tray_exit":
        step("close-to-tray on again", lambda: find_action(W(), "Options", "Close to System Tray").trigger())
        step(
            "tray menu exit",
            lambda: next(
                a for a in _tray(W()).contextMenu().actions() if a.text() == "Exit SpaceNavigator Mapper"
            ).trigger(),
            500,
        )
    else:
        step("exit", lambda: find_action(W(), "Options", "Exit SpaceNavigator Mapper").trigger(), 500)


env.session = session
sys.argv = [entry] + (["--start-in-tray"] if SCRIPT == "tray" else [])
os.chdir(SBX)
if KIND == "single":
    sys.path.insert(0, SBX)
    g = {"__name__": "spnav_single", "__file__": entry}
    exec(compile(open(entry, encoding="utf-8").read(), entry, "exec"), g)
else:
    sys.path.insert(0, SBX)
try:
    from spnav_mapper.bootstrap import launch

    code = launch()
except SystemExit as exc:
    code = exc.code
except BaseException:
    CHECKPOINTS.append({"label": "LAUNCH FAILURE", "trace": traceback.format_exc()})
    code = None
CHECKPOINTS.append({"label": "exit", "code": code, "errors": list(env.errors)})
text = json.dumps(CHECKPOINTS, indent=1, default=repr)
text = text.replace(SBX, "<SBX>").replace(os.path.basename(entry), "<ENTRY>")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(text)
print("checkpoints:", [c["label"] for c in CHECKPOINTS])
