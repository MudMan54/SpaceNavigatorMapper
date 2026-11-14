"""Save and restore the editor across two monitors with different scale factors; print JSON.

Started by test_placement.py in its own interpreter (fakeqt patches globals).

Layout used by every case, as Qt 5 sees it with per-monitor factors: the
primary 4K monitor at 150 % is 2560 logical pixels wide but the second
monitor starts at native x=3840, so Qt leaves a logical gap from 2560 to 3840.
"""

import json
import os
import pathlib
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import fakeqt  # noqa: E402
from fakeqt import CLOCK, W32, QMainWindow, QRect, QScreen  # noqa: E402

D1, D2 = r"\\.\DISPLAY1", r"\\.\DISPLAY2"
SCREENS = [
    QScreen(D1, QRect(0, 0, 2560, 1440), QRect(0, 0, 2560, 1400), dpr=1.5),
    QScreen(D2, QRect(3840, 0, 1920, 1080), QRect(3840, 0, 1920, 1040), dpr=1.0),
]
fakeqt.install(SCREENS)
W32.monitors = [  # physical pixels
    (D1, 0, 0, 3840, 2160, 2100, 144, True),
    (D2, 3840, 0, 1920, 1080, 1040, 96, False),
]

from spnav_mapper.ui import placement  # noqa: E402

EDITOR_SIZE = (300, 120)  # the editor's content size, kept small for readable numbers
placement.editor_needed_size = lambda win: EDITOR_SIZE
SANDBOX = tempfile.mkdtemp(prefix="spnav-placement-")
placement.CONFIG_DIR = SANDBOX
placement.WINDOW_STATE_FILE = os.path.join(SANDBOX, "window_state.json")
NOTES = []
placement._note = NOTES.append
from spnav_mapper import bootstrap  # noqa: E402

bootstrap.note = NOTES.append  # never write to the real startup.log
from spnav_mapper import display_preferences  # noqa: E402

display_preferences.PREFERENCES_PATH = pathlib.Path(SANDBOX) / "ui_preferences.json"


def check_monitor(name):
    """Display > Positions Saved: check monitor `name` (None: none checked)."""
    value = {"screen_name": name, "serial": ""} if name else None
    display_preferences.update_preference(placement.POSITIONS_PREFERENCE, value)


class Window(QMainWindow):
    pass


def saved():
    with open(placement.WINDOW_STATE_FILE, encoding="utf-8") as stream:
        return json.load(stream)["views"]


def write_state(views):
    """A version 5 state with each record also as its position on that monitor."""
    per = {}
    for view, record in views.items():
        per.setdefault(record["screen_name"], {})[view] = {
            k: record[k] for k in ("relative_x", "relative_y", "w", "h") if k in record
        }
    with open(placement.WINDOW_STATE_FILE, "w", encoding="utf-8") as stream:
        json.dump({"version": 5, "views": views, "per_monitor": per}, stream)


def reset():
    W32.window_monitor = None
    W32.client_origin = None
    NOTES.clear()
    if os.path.exists(placement.WINDOW_STATE_FILE):
        os.remove(placement.WINDOW_STATE_FILE)


def record_on(name, dx, dy):
    return {"screen_name": name, "serial": "", "relative_x": dx, "relative_y": dy}


def save_case(geometry, monitor, origin):
    """Save a visible editor whose Qt geometry is `geometry`."""
    reset()
    W32.window_monitor, W32.client_origin = monitor, origin
    win = Window()
    win.show()
    win.setGeometry(*geometry)
    placement.save_window_placement(win)
    if not os.path.exists(placement.WINDOW_STATE_FILE):
        return None
    record = saved()["full"]
    return [record["screen_name"], record["relative_x"], record["relative_y"]]


def restore_case(record, monitor_answers):
    """Restore, show and let the post-show checks run.

    monitor_answers: what MonitorFromWindow reports on each call (the last
    answer repeats), simulating Windows putting the window somewhere else.
    """
    reset()
    write_state({"full": record})
    check_monitor(record["screen_name"])
    answers = list(monitor_answers)

    def monitor(_hwnd):
        return answers.pop(0) if len(answers) > 1 else answers[0]

    W32.window_monitor = monitor
    win = Window()
    placement.restore_window_placement(win, startup=True)
    win.show()
    CLOCK.advance(1000)
    g = win.geometry()
    return {
        "screen": win.windowHandle().screen().name(),
        "rect": [g.x(), g.y(), g.width(), g.height()],
        "moved_back": sum("moved it back" in n for n in NOTES),
        "checking": getattr(win, "_placement_target", None) is not None,
    }


def write_v5(per_monitor, monitor=None):
    with open(placement.WINDOW_STATE_FILE, "w", encoding="utf-8") as stream:
        json.dump({"version": 5, "monitor": monitor, "views": {}, "per_monitor": per_monitor}, stream)


def place(windows_says, checked, startup=False, keep=False, geometry=None):
    """Restore the editor; `windows_says`: the monitor the window is on now."""
    check_monitor(checked)
    W32.window_monitor = windows_says
    win = Window()
    if geometry:
        win.setGeometry(*geometry)
    placement.restore_window_placement(win, startup=startup, keep=keep)
    win.show()
    CLOCK.advance(1000)
    g = win.geometry()
    return [win.windowHandle().screen().name(), g.x(), g.y()]


def positions_saved_cases():
    pos = lambda x, y: {"relative_x": x, "relative_y": y, "w": 300, "h": 120}  # noqa: E731
    out = {}
    # D2 checked: the editor always opens on D2 at the position saved for D2,
    # at start-up and when shown again, wherever the window is now.
    reset()
    write_v5({D1: {"full": pos(40, 60)}, D2: {"full": pos(500, 300)}})
    out["checked: start-up"] = place(D1, D2, startup=True)
    out["checked: shown again"] = place(D1, D2, geometry=(40, 60, 300, 120))
    # v108.137: an old compact-view position is not the editor's: centred there.
    reset()
    write_v5({D2: {"compact": pos(250, 150)}})
    out["checked: not saved yet"] = place(D2, D2, startup=True)
    # Checked monitor not connected: the primary one, same position if it fits.
    reset()
    write_v5({r"\\.\DISPLAY9": {"full": pos(700, 500)}})
    out["checked monitor missing"] = place(D1, r"\\.\DISPLAY9", startup=True)
    # Nothing checked: start-up centred on the primary monitor...
    reset()
    write_v5({D2: {"full": pos(500, 300)}})
    out["none checked: start-up"] = place(D2, None, startup=True)
    # ...shown again, it is centred on the monitor the window is on...
    out["none checked: shown again"] = place(D2, None, geometry=(3840 + 200, 100, 300, 120))
    # ...and a Display % restart keeps the monitor it was on, centred.
    reset()
    write_v5({D2: {"full": pos(500, 300)}}, monitor={"screen_name": D2, "serial": ""})
    out["none checked: Display restart"] = place(D1, None, startup=True, keep=True)
    # Checking a monitor saves the editor's position on it right away.
    reset()
    check_monitor(None)
    W32.window_monitor, W32.client_origin = D2, (3840 + 70, 80)
    win = Window()
    win.show()
    win.setGeometry(3910, 80, 300, 120)
    placement.set_positions_monitor(win, SCREENS[1])
    with open(placement.WINDOW_STATE_FILE, encoding="utf-8") as stream:
        data = json.load(stream)
    out["checking saves now"] = {
        "monitor": data["monitor"]["screen_name"],
        "saved on D2": data["per_monitor"][D2]["full"],
        "preference": display_preferences.read_preferences()[placement.POSITIONS_PREFERENCE]["screen_name"],
    }
    W32.client_origin = None
    check_monitor(None)
    return out


def menu_font_case():
    from fakeqt import QFont, QMenu

    from spnav_mapper.ui import window_chrome

    win = QMainWindow()
    sizes = {}
    for title in ("Auto-Profiles", "Options", "Display"):
        menu = win.menuBar().addMenu(title)
        font = QFont()
        font.setPointSizeF(9.0)
        menu.setFont(font)
        sub = QMenu("Sub", menu)
        sub.setFont(font)
        menu.addMenu(sub)
        sizes[title] = (menu, sub)
    window_chrome.enlarge_menu_fonts(win)
    return {t: [m.font().pointSizeF(), s.font().pointSizeF()] for t, (m, s) in sizes.items()}


def menu_points_case():
    """The points added to the menus and the menu-bar headings at each Display size."""
    from spnav_mapper.ui import scaling, window_chrome

    calls = []
    original = (
        window_chrome._add_display_menu,
        window_chrome.enlarge_menu_fonts,
        window_chrome.enlarge_menu_bar_headings,
        scaling.UI_SIZE_FACTOR,
    )
    window_chrome._add_display_menu = lambda win: None
    try:
        for factor in (1.0, 0.85, 1.10):
            menus, headings = [], []
            window_chrome.enlarge_menu_fonts = lambda win, points=1.0, out=menus: out.append(points)
            window_chrome.enlarge_menu_bar_headings = lambda win, points=1.0, out=headings: out.append(points)
            scaling.UI_SIZE_FACTOR = factor
            window_chrome.WindowChromeMixin._init_display_menu(object())
            calls.append({"factor": factor, "menus": menus, "headings": headings})
    finally:
        (
            window_chrome._add_display_menu,
            window_chrome.enlarge_menu_fonts,
            window_chrome.enlarge_menu_bar_headings,
            scaling.UI_SIZE_FACTOR,
        ) = original
    return calls


def menu_heading_case():
    """The menu-bar headings grow; corner title and menus keep their size."""
    from fakeqt import QFont, QLabel

    from spnav_mapper.ui import window_chrome

    win = QMainWindow()
    bar = win.menuBar()
    base = QFont()
    base.setPointSizeF(9.0)
    bar.setFont(base)
    menu = bar.addMenu("Display")
    menu.setFont(base)
    corner = QLabel("SpaceNavigator Mapper")
    bar.setCornerWidget(corner)
    corner.setFont(base)
    window_chrome.enlarge_menu_bar_headings(win, window_chrome.MENU_BAR_HEADING_POINTS)
    return {
        "headings": bar.font().pointSizeF(),
        "corner title": corner.font().pointSizeF(),
        "menu": menu.font().pointSizeF(),
    }


def restart_front_case():
    """The old copy lets the restarted one take the front; the new one raises itself."""
    import subprocess

    from spnav_mapper import app, restart, win32

    granted, raised = [], []

    class Successor:
        pid = 4321

    class Closing:
        _force_exit = False

        def close(self):
            return True

    saved = (subprocess.Popen, win32.allow_foreground, win32.bring_to_front)
    subprocess.Popen = lambda *a, **k: Successor()
    win32.allow_foreground = granted.append
    win32.bring_to_front = lambda hwnd: raised.append(hwnd) or True
    try:
        restart.restart_after_display_change(Closing())
        win = Window()
        win.show()
        app._bring_to_front(win)
        hidden = Window()
        app._bring_to_front(hidden)  # not shown: left alone
    finally:
        subprocess.Popen, win32.allow_foreground, win32.bring_to_front = saved
    return {"granted": granted, "raised": [hex(h) for h in raised], "window": hex(int(win.winId()))}


def scrolling_comment_case():
    """Comments scroll like the profile name, but not while being edited."""
    from fakeqt import QLineEdit

    from spnav_mapper.ui import profile_marquee

    painted = []
    saved = (QLineEdit.paintEvent, profile_marquee.ProfileDisplay.paintEvent)
    QLineEdit.paintEvent = lambda self, e: painted.append("plain")
    profile_marquee.ProfileDisplay.paintEvent = lambda self, e: painted.append("scrolling")
    try:
        field = profile_marquee.ScrollingLineEdit()
        field.hasFocus = lambda: False
        field.paintEvent(None)
        field.hasFocus = lambda: True
        field.paintEvent(None)
    finally:
        QLineEdit.paintEvent, profile_marquee.ProfileDisplay.paintEvent = saved
    return {"painted": painted, "is a line edit": isinstance(field, QLineEdit)}


def tray_profiles_case():
    """Tray > Profiles lists the profiles, the active one checked; choosing one loads it."""
    from fakeqt import QMenu

    from spnav_mapper.ui import window_chrome

    folder = os.path.join(SANDBOX, "profiles")
    os.makedirs(folder, exist_ok=True)
    for name in ("Game", "Notes", "last_config", "window_state", "ui_preferences", "auto_profiles"):
        with open(os.path.join(folder, name + ".json"), "w", encoding="utf-8") as stream:
            stream.write("{}")
    loaded, messages = [], []

    class Tray:
        def showMessage(self, title, text, *rest):
            messages.append(text)

    class Win:
        profile_path = os.path.join(folder, "Game.json")
        _tray = Tray()

        def _load_config_from_path(self, path):
            loaded.append(os.path.basename(path))
            self.profile_path = path
            return True

        def _refresh_windows_quietly(self):
            pass

        def statusBar(self):
            return self

        def showMessage(self, *a):
            pass

    saved = window_chrome.CONFIG_DIR
    window_chrome.CONFIG_DIR = folder
    try:
        win, menu = Win(), QMenu()
        window_chrome.fill_tray_profiles(win, menu)
        listed = [(a.text(), a.isChecked()) for a in menu.actions()]
        next(a for a in menu.actions() if a.text() == "Notes").trigger()
        window_chrome.fill_tray_profiles(win, menu)  # rebuilt when opened again
        after = [(a.text(), a.isChecked()) for a in menu.actions()]
        empty = QMenu()
        window_chrome.CONFIG_DIR = os.path.join(SANDBOX, "no-profiles")
        os.makedirs(window_chrome.CONFIG_DIR, exist_ok=True)
        window_chrome.fill_tray_profiles(win, empty)
        none = [(a.text(), a.isEnabled()) for a in empty.actions()]
    finally:
        window_chrome.CONFIG_DIR = saved
    return {"listed": listed, "loaded": loaded, "message": messages, "after": after, "none": none}


def old_state_case():
    """A window_state.json from before v108.137 still holds compact-view records."""
    reset()
    check_monitor(None)
    with open(placement.WINDOW_STATE_FILE, "w", encoding="utf-8") as stream:
        json.dump(
            {
                "version": 5,
                "monitor": {"screen_name": D2, "serial": ""},
                "views": {"compact": record_on(D2, 5, 5), "full": record_on(D2, 100, 200)},
                "per_monitor": {
                    D1: {"compact": {"relative_x": 1, "relative_y": 2}},
                    D2: {"compact": {"relative_x": 5, "relative_y": 5}, "full": {"relative_x": 100}},
                },
            },
            stream,
        )
    W32.window_monitor, W32.client_origin = D2, (3840 + 100, 200)
    win = Window()
    win.show()
    win.setGeometry(3940, 200, 300, 120)
    placement.save_window_placement(win)
    with open(placement.WINDOW_STATE_FILE, encoding="utf-8") as stream:
        data = json.load(stream)
    return {
        "views": sorted(data["views"]),
        "per_monitor": {k: sorted(v) for k, v in data["per_monitor"].items()},
    }


def second_launch_case():
    """A second launch posts "show yourself" to the running copy; it never calls ShowWindow."""
    import ctypes
    from ctypes import wintypes

    from fakeqt import EFFECTS

    from spnav_mapper import single_instance
    from spnav_mapper.ui import window_chrome

    W32.windows = [
        (0x100, "SpaceNavigator Mapper", 0, "explorer.exe"),  # a folder of that name
        (0x200, "SpaceNavigator Mapper — game", 777, "mapper.exe"),
        (0x300, "Notepad", 888, "notepad.exe"),
    ]
    W32.classes = {0x100: "CabinetWClass", 0x200: "Qt5152QWindowIcon", 0x300: "Notepad"}
    del EFFECTS[:]
    found = single_instance._restore_existing_window()
    posted = [list(e[1:]) for e in EFFECTS]
    W32.windows, W32.classes = [], {}

    class Shown(window_chrome.WindowChromeMixin, Window):
        pass

    restored = []
    saved = (window_chrome.restore_from_taskbar,)
    window_chrome.restore_from_taskbar = lambda w: restored.append("restored") or w.showNormal()
    try:
        win = Shown()
        win.hide()  # closed to the tray
        msg = wintypes.MSG()
        msg.message = single_instance.restore_message_id()
        handled = win.nativeEvent(b"windows_generic_MSG", ctypes.addressof(msg))
        other = wintypes.MSG()
        other.message = 0x0200  # WM_MOUSEMOVE: not ours
        passed_on = win.nativeEvent(b"windows_generic_MSG", ctypes.addressof(other))
        CLOCK.advance(50)
        visible = win.isVisible()
        minimized = Shown()
        minimized.show()
        minimized.showMinimized()  # on the taskbar, not in the tray
        minimized.nativeEvent(b"windows_generic_MSG", ctypes.addressof(msg))
        CLOCK.advance(50)
    finally:
        (window_chrome.restore_from_taskbar,) = saved
    return {
        "found": found,
        "calls": posted,
        "handled": list(handled),
        "other message": list(passed_on),
        "restored": restored,
        "visible": visible,
        "minimized comes back": [minimized.isVisible(), minimized.isMinimized()],
    }


def version_label_case():
    """The version and date use the comment lines' point size, family unchanged."""
    from fakeqt import QFont, QLabel, QLineEdit

    from spnav_mapper.ui.main_window import match_comment_font

    label, comment = QLabel("v108.137  11/08/2026"), QLineEdit()
    big = QFont("Segoe UI")
    big.setPointSizeF(14.0)
    label.setFont(big)
    small = QFont("Consolas")
    small.setPointSizeF(10.5)
    comment.setFont(small)
    match_comment_font(label, comment)
    return {"points": label.font().pointSizeF(), "family": label.font().family()}


def noback_glow_case():
    """The NoBack line sweeps with the title's timer: left for -, right for +, both for both."""
    from fakeqt import QPushButton

    from spnav_mapper.ui import title_effect

    win = Window()
    minus, both, off = QPushButton("Bind #1", win), QPushButton("Bind #2", win), QPushButton("Bind #3", win)
    for button, sides in ((minus, "-"), (both, "+-"), (off, "+")):
        button.resize(120, 50)
        button._noback_glow = title_effect.NoBackSweep(button)
        button._noback_glow.set_sides(sides)
    off._noback_glow.set_wanted(False)  # NoBack switched off again
    win.axes = {"X": type("Panel", (), {"slot_btns": [minus, both, off]})()}
    win.show()
    resting = minus._noback_glow.sweep()
    saved = title_effect._cursor_over_app
    title_effect._cursor_over_app = lambda w: True
    reach = []
    try:
        for _ in range(45):  # 1.8 s: a whole sweep, its fade and the next start
            title_effect._tick_title_effect(win)
            reach.append(round(minus._noback_glow.sweep()[0], 2))
        minus._noback_glow.paintEvent(None)  # draws without errors
    finally:
        title_effect._cursor_over_app = saved
    grow = reach[: reach.index(1.0) + 1]
    return {
        "sides": [b._noback_glow.sides() for b in (minus, both, off)],
        "resting (pointer away)": list(resting),
        "grows from the middle": grow == sorted(grow) and grow[0] < 0.2,
        "starts again": min(reach[reach.index(1.0) :]) < 0.2,
        "moving": [minus._noback_glow._hover_on, off._noback_glow._hover_on],
        "same phase as the title": minus._noback_glow._phase == win._title_phase > 0,
        "shown": [b._noback_glow.isVisible() for b in (minus, both, off)],
    }


def axis_panel_case():
    """Each Bind button and its comment share a grid row; the lines show Bind Dir and NoBack."""
    from spnav_mapper.ui.axis_panel import AxisPanel

    win = Window()
    panel = AxisPanel("X", win)
    rows = {"buttons": {}, "comments": {}}
    for item in panel.bind_rows.layout()._items:
        widget = item.widget()
        if widget in panel.slot_btns:
            rows["buttons"][panel.slot_btns.index(widget)] = item.extra[0]
        elif widget in panel.slot_comments:
            rows["comments"][panel.slot_comments.index(widget)] = item.extra[0]
    lines = []
    for direction in (None, "Minus", "Plus", "Full"):
        panel.binds[0]["direction"] = direction
        panel._refresh_slot_btn(0, force=True)
        line = getattr(panel.slot_btns[0], "_dir_line", None)
        lines.append(line.sides() if line is not None and line._wanted else "")
    panel.binds[0]["noback_minus"] = True
    panel._refresh_slot_btn(0, force=True)
    both = panel.slot_btns[0]
    return {
        "rows": [[rows["buttons"].get(i), rows["comments"].get(i)] for i in range(6)],
        "bind dir line": lines,
        "line edges": [both._dir_line.EDGE, both._noback_glow.EDGE],
        "green": list(both._dir_line.RGB),
        "button style kept": both.styleSheet() == panel._slot_style(0),
    }


def tray_menu_case():
    """The tray icon's menu and its Profiles submenu are 2 points larger."""
    from fakeqt import QMenu

    from spnav_mapper.ui import window_chrome

    menu = QMenu()
    base = menu.font().pointSizeF()
    profiles = menu.addMenu("Profiles")
    window_chrome.grow_menu_fonts(menu, window_chrome.TRAY_MENU_EXTRA_POINTS)
    return [menu.font().pointSizeF() - base, profiles.font().pointSizeF() - base]


def macro_editor_case():
    """The macro editor's steps: add, move, change, delete, save (v108.141)."""
    from spnav_mapper.ui import macro_editor

    picks = [["ctrl", "s"], ["shift"], ["shift"], ["enter"]]
    saved_pick = macro_editor.pick_keys
    macro_editor.pick_keys = lambda parent, initial=None: picks.pop(0) if picks else None
    got = []
    try:
        editor = macro_editor.MacroEditor(None, [{"tap": ["q"]}], got.append, title="X Bind #1: macro")
        editor.add_keys("tap")  # after Q (the last step is selected)
        editor.delay_ms.setValue(250)
        editor.add_step({"delay": editor.delay_ms.value()})
        editor.add_keys("down")
        editor.add_keys("up")
        shown = editor.steps_list.texts()
        editor.steps_list.setCurrentRow(2)  # the delay step: the box edits it
        editor.delay_ms.setValue(120)
        editor.move(-1)  # the delay before Ctrl+S
        editor.steps_list.setCurrentRow(0)
        editor.change_selected()  # Q becomes Enter
        editor.steps_list.setCurrentRow(4)
        editor.delete_selected()  # Shift up
        editor.save()
    finally:
        macro_editor.pick_keys = saved_pick
    return {"shown": shown, "saved": got, "count": editor.count_label.text()}


def macro_bind_case():
    """A bind in Macro mode: Quick Bind rows, label, tooltip, menu and profile data."""
    from fakeqt import QMenu

    from spnav_mapper.ui import macro_editor
    from spnav_mapper.ui.axis_panel import AxisPanel

    win = Window()
    panel = AxisPanel("X", win)
    panel._select_slot(0)
    panel.qb_mode.setCurrentText("Macro")
    rows = [not panel.macro_group.isHidden(), not panel.repeat_group.isHidden()]
    panel.qb_play.setCurrentText("Repeat")
    rows += [not panel.macro_group.isHidden(), not panel.repeat_group.isHidden()]
    opened = []
    saved_exec = macro_editor.MacroEditor.exec_
    macro_editor.MacroEditor.exec_ = lambda self: opened.append(self.windowTitle()) or 0
    try:
        panel._open_picker_for(0)  # double-click: the macro editor, not the key picker
        QMenu.CHOICES = ["Edit macro…"]
        panel.slot_btns[0].contextMenuEvent(None)
    finally:
        macro_editor.MacroEditor.exec_ = saved_exec
    panel.set_macro(0, [{"tap": ["q"]}, {"delay": 100}, {"tap": ["w"]}])
    button = panel.slot_btns[0]
    label, tip = button.text(), button.toolTip().splitlines()[:4]
    config = panel.get_config()["binds"][0]
    other = AxisPanel("Y", Window())
    other.set_config(panel.get_config())
    loaded = other.binds[0]
    panel.qb_mode.setCurrentText("Hold")  # the key again; the steps are kept
    return {
        "rows (once, then repeat)": rows,
        "editor opened": opened,
        "label": label,
        "tip": tip,
        "saved": {k: config.get(k) for k in ("mode", "macro", "macro_repeat")},
        "loaded": [loaded["mode"], loaded["macro"], loaded["macro_repeat"], other.slot_btns[0].text()],
        "back to Hold": [button.text(), panel.binds[0]["macro"] != [], not panel.macro_group.isHidden()],
    }


def key_picker_case():
    """The key picker: keys with modifiers, symbols (modifiers off), toggling, Clear, a preset combo."""
    from spnav_mapper.ui.keyboard_popup import KeyboardPopup

    picked = []
    popup = KeyboardPopup(None, picked.append)
    keys = dict(popup.key_buttons)
    popup.mod_buttons["ctrl"].click()
    keys["s"].click()
    popup.mod_buttons["shift"].click()
    with_mods = list(picked)
    symbols = {b.text(): b for b in popup.findChildren(type(keys["s"])) if b.text() in popup._SYMBOL_LABELS}
    symbols["!"].click()
    symbol = [picked[-1], [b.isEnabled() for b in popup.mod_buttons.values()]]
    symbols["\\"].click()
    backslash = picked[-1]
    symbols["\\"].click()  # the same symbol again: unselected
    unselected = [picked[-1], [b.isEnabled() for b in popup.mod_buttons.values()]]
    keys["f5"].click()
    keys["f5"].click()  # the same key again: unselected
    toggled = picked[-2:]
    keys["space"].click()
    popup._clear_selection()
    cleared = picked[-1]
    preset = KeyboardPopup(None, picked.append, initial=["ctrl", "S"])
    shown = sorted(t for t, b in preset.mod_buttons.items() if b.isChecked()), preset.selected_key_token
    return {
        "with modifiers": with_mods,
        "symbol": symbol,
        "backslash": backslash,
        "symbol unselected": unselected,
        "key toggled": toggled,
        "cleared": cleared,
        "preset": list(shown),
    }


def device_presence_case():
    """The device's presence is checked once a second, not every 16 ms tick; unplugging is noticed."""
    from spnav_mapper import devices

    hid = devices.hid
    calls = []
    real = hid.enumerate
    hid.enumerate = lambda *a: calls.append(a) or real(*a)
    try:
        nav = devices.SpaceNavigator()
        opened = nav.open()
        before = len(calls)
        for _ in range(125):  # two seconds of GUI ticks
            nav.tick()
            CLOCK.sleep(0.016)
        checks = len(calls) - before
        hid.present = False
        start = CLOCK.perf_counter()
        while nav.dev is not None and CLOCK.perf_counter() - start < 5:
            nav.tick()
            CLOCK.sleep(0.016)
        noticed = round(CLOCK.perf_counter() - start, 1)
        hid.present = True
        for _ in range(100):
            nav.tick()
            CLOCK.sleep(0.016)
        return {
            "opened": opened,
            "checks in 2 s": checks,
            "unplug noticed within": noticed,
            "back": nav.dev is not None,
        }
    finally:
        hid.enumerate = real
        hid.present = True


def fit_to_screen_case():
    """v108.151: the editor and its fonts take the same share of a 1080p screen as of 4K at 225%."""
    from fakeqt import QApplication, QCoreApplication, QFont

    from spnav_mapper.ui import monitor_scale, scaling

    saved = (
        list(QCoreApplication._screens),
        QFont(QCoreApplication._app_font),
        monitor_scale.HOME_NAME,
        scaling.SCALE,
        scaling.BASE_UI_SCALE,
        scaling.UI_SIZE_FACTOR,
        dict(scaling.UI_SCALE_INFO),
    )
    screens = {  # Qt logical pixels: the screen / its Windows scale, less the taskbar
        "3840x2160 at 225%": QScreen(D1, QRect(0, 0, 1707, 960), QRect(0, 0, 1707, 912), dpr=2.25),
        "1920x1080 at 100%": QScreen(D1, QRect(0, 0, 1920, 1080), QRect(0, 0, 1920, 1032), dpr=1.0),
        "1920x1080 at 125%": QScreen(D1, QRect(0, 0, 1536, 864), QRect(0, 0, 1536, 816), dpr=1.25),
        "1920x1080 at 150%": QScreen(D1, QRect(0, 0, 1280, 720), QRect(0, 0, 1280, 672), dpr=1.5),
    }
    out = {}
    try:
        monitor_scale.HOME_NAME = ""
        for label, screen in screens.items():
            QCoreApplication._screens = [screen]
            font = QFont("Segoe UI")
            font.setPointSizeF(9.0)
            QApplication.setFont(font)
            scaling._apply_dynamic_scale(QApplication)
            rows = screen.availableGeometry().height() * screen.devicePixelRatio()  # physical pixels
            out[label] = {
                "fit": scaling.UI_SCALE_INFO.get("fit_factor"),
                "scale": scaling.SCALE,
                # a 1000-unit tall layout, and a 12-pt label, as a share of the screen's height
                "layout share": round(scaling.S(1000) * screen.devicePixelRatio() / rows, 4),
                "font share": round(scaling.Sf(12) * 96 / 72 * screen.devicePixelRatio() / rows, 5),
                "app font": QApplication.font().pointSizeF(),
            }
    finally:
        QCoreApplication._screens, QCoreApplication._app_font = saved[0], saved[1]
        monitor_scale.HOME_NAME = saved[2]
        scaling.SCALE, scaling.BASE_UI_SCALE, scaling.UI_SIZE_FACTOR = saved[3:6]
        scaling.UI_SCALE_INFO = saved[6]
    return out


def stale_font_case():
    """v108.152: after the Windows scale changed since sign-in, Qt's default font is given the size Windows meant."""
    from fakeqt import QApplication, QCoreApplication, QFont

    from spnav_mapper.ui import monitor_scale, scaling

    saved = (
        list(QCoreApplication._screens),
        QFont(QCoreApplication._app_font),
        monitor_scale.HOME_NAME,
        scaling.SCALE,
        scaling.BASE_UI_SCALE,
        scaling.UI_SIZE_FACTOR,
        dict(scaling.UI_SCALE_INFO),
    )
    four_k = QScreen(D1, QRect(0, 0, 1707, 960), QRect(0, 0, 1707, 912), dpr=2.25)
    full_hd = QScreen(D1, QRect(0, 0, 1920, 1080), QRect(0, 0, 1920, 1032), dpr=1.0)
    full_hd_125 = QScreen(D1, QRect(0, 0, 1536, 864), QRect(0, 0, 1536, 816), dpr=1.25)
    signed_in_225 = (216, (-24, "MS Shell Dlg"))  # Windows' GUI font: 8 pt at 225%
    signed_in_100 = (96, (-11, "MS Shell Dlg"))  # 8.25 pt at 100%
    cases = {
        # (screen now, sign-in DPI and GUI font, Qt's default font family and size)
        "unchanged since sign-in": (four_k, signed_in_225, ("MS Shell Dlg 2", 8.0)),
        "225% to 100%": (full_hd, signed_in_225, ("MS Shell Dlg 2", 18.0)),
        "225% to 125%": (full_hd_125, signed_in_225, ("MS Shell Dlg 2", 14.4)),
        "100% to 225%": (four_k, signed_in_100, ("MS Shell Dlg 2", 3.67)),
        "another default font": (full_hd, signed_in_225, ("Segoe UI", 9.0)),
        "no answer from Windows": (full_hd, (0, None), ("MS Shell Dlg 2", 18.0)),
    }
    out = {}
    try:
        monitor_scale.HOME_NAME = ""
        for label, (screen, (dpi, gui_font), (family, points)) in cases.items():
            QCoreApplication._screens = [screen]
            W32.system_dpi, W32.gui_font = dpi, gui_font
            font = QFont(family)
            font.setPointSizeF(points)
            QApplication.setFont(font)
            del NOTES[:]
            scaling._apply_dynamic_scale(QApplication)
            out[label] = {
                "app font": [QApplication.font().family(), QApplication.font().pointSizeF()],
                "size factor": scaling.UI_SIZE_FACTOR,
                "notes": [n for n in NOTES if "font" in n],
            }
    finally:
        W32.system_dpi, W32.gui_font = 0, None
        QCoreApplication._screens, QCoreApplication._app_font = saved[0], saved[1]
        monitor_scale.HOME_NAME = saved[2]
        scaling.SCALE, scaling.BASE_UI_SCALE, scaling.UI_SIZE_FACTOR = saved[3:6]
        scaling.UI_SCALE_INFO = saved[6]
    return out


def settle_case():
    """v108.153: the content grows once the window is shown; the window grows with it."""
    out = {}
    cases = {
        # (monitor checked, saved record, size the content needs once shown)
        "centred": (None, None, (340, 150)),
        "saved position": (D1, record_on(D1, 100, 200), (340, 150)),
        "never shrinks": (None, None, (280, 100)),
        "only as far as the monitor": (None, None, (5000, 150)),
    }
    for label, (checked, record, shown_size) in cases.items():
        reset()
        if record:
            write_state({"full": record})
        check_monitor(checked)
        W32.window_monitor = D1
        win = Window()
        placement.editor_needed_size = lambda w: EDITOR_SIZE  # measured before it is shown
        placement.restore_window_placement(win, startup=True)
        before = win.geometry()
        win.show()
        placement.editor_needed_size = lambda w, size=shown_size: size  # styled and aligned
        CLOCK.advance(1000)
        g = win.geometry()
        out[label] = {
            "before": [before.x(), before.y(), before.width(), before.height()],
            "after": [g.x(), g.y(), g.width(), g.height()],
            "grown": sum("grown to hold its content" in n for n in NOTES),
        }
    placement.editor_needed_size = lambda w: EDITOR_SIZE
    check_monitor(None)
    return out


def settle_strayed_case():
    """v108.163: Windows moves the just-shown editor to the other monitor before the content grows.

    The window must still end on its monitor (D2), at the grown size. Before
    v108.163 the growth was placed on the monitor Qt named (D1), and that
    rect became the target the window was "moved back" to.
    """
    out = {}
    for label, shown_size in {"content grows": (340, 150), "content the same": EDITOR_SIZE}.items():
        reset()
        write_state({"full": record_on(D2, 100, 200)})
        check_monitor(D2)
        win = Window()

        def windows_says(_hwnd, w=win):
            centre = w.geometry().center()
            return next((s.name() for s in SCREENS if s.geometry().contains(centre)), D1)

        W32.window_monitor = windows_says
        placement.editor_needed_size = lambda w: EDITOR_SIZE
        placement.restore_window_placement(win, startup=True)
        win.show()
        CLOCK.advance(50)
        # Windows' DPI adjustment after show puts it on the 150% monitor; Qt follows.
        win.windowHandle().setScreen(SCREENS[0])
        win.setGeometry(200, 100, 300, 120)
        placement.editor_needed_size = lambda w, size=shown_size: size
        CLOCK.advance(1000)
        g = win.geometry()
        out[label] = {
            "windows says": windows_says(0),
            "rect": [g.x(), g.y(), g.width(), g.height()],
            "moved back": sum("moved it back" in n for n in NOTES),
        }
    placement.editor_needed_size = lambda w: EDITOR_SIZE
    check_monitor(None)
    return out


def monitor_change_case():
    """v108.163: monitors connected or changed after start-up: a restart is offered while the editor is shown."""
    from spnav_mapper import restart
    from spnav_mapper.ui import monitor_scale, monitor_watch

    big = (D1, 0, 0, 3840, 2160, 2100, 144, True)
    small = (D2, 3840, 0, 1920, 1080, 1040, 96, False)
    small_125 = (D2, 3840, 0, 1920, 1080, 1040, 120, False)
    saved = (list(W32.monitors), dict(monitor_scale.INFO), monitor_scale.HOME_NAME, dict(os.environ))
    restarts = []
    real_restart = restart.restart_after_display_change
    restart.restart_after_display_change = lambda win: restarts.append(1)
    out = {}

    def run(label, at_start, now, answer=fakeqt.QMessageBox.Yes, shown=True, checks=1, then=None):
        os.environ.pop(monitor_scale.QT_ENV, None)
        W32.monitors = list(at_start)
        monitor_scale.configure_before_qapplication(SANDBOX, 1.0, note=NOTES.append)
        W32.monitors = list(now)
        win = Window()
        monitor_watch.install_monitor_watch(win)
        if shown:
            win.show()
        fakeqt.QMessageBox.ANSWER = answer
        first = len(fakeqt.EFFECTS)
        restarts.clear()
        asked = [monitor_watch.check_monitors(win) for _ in range(checks)]
        if then:
            then(win)
        boxes = [e for e in fakeqt.EFFECTS[first:] if e[1] == "message-box"]
        out[label] = {
            "asked": asked,
            "boxes": [[b[2], b[3], b[4].splitlines()[2:-2]] for b in boxes],
            "restarts": len(restarts),
            "pending": win._monitor_check_pending,
        }
        fakeqt.QMessageBox.ANSWER = None

    run("same monitors", [big, small], [big, small])
    run("monitor connected later", [big], [big, small])
    run("one monitor, connected later", [small], [small, big])
    run("disconnected: nothing to ask", [big, small], [big])
    run("taskbar moved: nothing to ask", [big, small], [big, (D2, 3840, 0, 1920, 1080, 1080, 96, False)])
    run("scaling changed", [big, small], [big, small_125])
    run("declined: not asked again", [big], [big, small], answer=fakeqt.QMessageBox.No, checks=2)

    def change_again(win):
        W32.monitors = [big, small_125]
        out["declined: asked for other monitors"] = monitor_watch.check_monitors(win)

    run("declined, then changed again", [big], [big, small], answer=fakeqt.QMessageBox.No, then=change_again)

    def show_later(win):
        win.show()
        CLOCK.advance(monitor_watch.SHOWN_MS + 100)

    run("hidden: asked once shown", [big], [big, small], shown=False, then=show_later)

    def signal(win):
        fakeqt.QApplication.instance().screenAdded.emit(SCREENS[1])
        CLOCK.advance(monitor_watch.QUIET_MS - 100)
        out["signal: not yet"] = len(restarts)
        CLOCK.advance(200)

    had_app = fakeqt.QApplication.instance()
    if had_app is None:
        fakeqt.QApplication([])  # the watch connects to the application's screenAdded
    run("screen added signal", [big], [big, small], checks=0, then=signal)
    fakeqt.QCoreApplication._app = had_app
    os.environ[monitor_scale.QT_ENV] = "1.5;1"  # set by the user: kept, and never second-guessed
    W32.monitors = [big]
    monitor_scale.configure_before_qapplication(SANDBOX, 1.0, note=NOTES.append)
    W32.monitors = [big, small]
    out["user's own factors"] = monitor_scale.stale_monitors(
        monitor_scale.INFO, monitor_scale.native_monitors()
    )
    restart.restart_after_display_change = real_restart
    W32.monitors, monitor_scale.HOME_NAME = saved[0], saved[2]
    monitor_scale.INFO.clear()
    monitor_scale.INFO.update(saved[1])
    os.environ.clear()
    os.environ.update(saved[3])
    return out


def refit_case():
    """v108.163: after a drag the editor is fitted to the monitor Windows has it on, not the one Qt names."""
    from spnav_mapper.ui import editor_fit

    reset()
    W32.window_monitor = D2
    win = Window()
    win.show()
    win.windowHandle().setScreen(SCREENS[0])  # Qt names the 150% monitor
    win.setGeometry(3940, 200, 300, 120)
    real = editor_fit.editor_needed_size
    editor_fit.editor_needed_size = lambda w: (5000, 150)
    editor_fit._refit_to_screen(win)
    editor_fit.editor_needed_size = real
    g = win.geometry()
    return {"rect": [g.x(), g.y(), g.width(), g.height()], "note": [n for n in NOTES if "Re-fitted" in n]}


def profile_buttons_case():
    """v108.165: Save/Reload, Save as and Load end where the profile name box ends; Target keeps its width."""
    from spnav_mapper.ui.profile_buttons import ProfileButtonRow, profile_button_widths

    out = {"widths": profile_button_widths(1000, 8, 200), "compact": profile_button_widths(700, 6, 150, 120)}
    column = fakeqt.QWidget()
    layout = fakeqt.QVBoxLayout(column)
    layout.setContentsMargins(0, 0, 0, 0)
    row = fakeqt.QHBoxLayout()
    row.setSpacing(8)
    layout.addLayout(row)
    beside = fakeqt.QComboBox()
    beside.setFixedWidth(200)
    buttons = [fakeqt.QPushButton(t) for t in ("Target", "Save/Reload", "Save as", "Load")]
    lined = ProfileButtonRow(column, row, buttons[0], buttons[1:], beside)
    column.setGeometry(0, 0, 1000, 120)
    lined.apply()
    out["stretch"] = [row.itemAt(i).stretch for i in range(row.count())]
    out["last item"] = row.itemAt(row.count() - 1).kind
    return out


def taskbar_launch_case():
    """v108.165: the taskbar's Restore / Exit SpaceNavigator Mapper, as launches with --restore / --exit."""
    import ctypes
    from ctypes import wintypes

    from spnav_mapper import bootstrap, single_instance
    from spnav_mapper.ui import window_chrome

    out = {}
    names = (
        "acquire_single_instance",
        "find_running_windows",
        "post_to_windows",
    )
    saved_si = {name: getattr(single_instance, name) for name in names}
    saved = (bootstrap._message_box, bootstrap._ask, bootstrap._start_ui, bootstrap.OTHER_VERSION_EXIT_S)
    saved_sys = (list(sys.argv), sys.excepthook)
    mine = single_instance.version_number(bootstrap.VERSION)
    restore, exit_ = single_instance.restore_message_id(), single_instance.exit_message_id()
    try:
        # label, arguments, the running copy's version (None: none running,
        # "hidden": its window not found), Yes to "exit it?", whether it exits
        for label, argv, running, yes, exits in (
            ("restore, running", ["mapper.exe", "--restore"], mine, None, False),
            ("second start, running", ["mapper.exe"], mine, None, False),
            ("second start, window not found", ["mapper.exe"], "hidden", None, False),
            ("exit, running", ["mapper.exe", "--exit"], mine, None, False),
            ("exit, none running", ["mapper.exe", "--exit"], None, None, False),
            # v108.168: another version running.
            ("older running, kept", ["mapper.exe"], 108164, False, False),
            ("older running, replaced", ["mapper.exe"], 108164, True, True),
            ("older running, does not exit", ["mapper.exe"], 0, True, False),
            ("older running, taskbar restore", ["mapper.exe", "--restore"], 108164, None, False),
        ):
            log = {"requests": [], "posted": [], "asked": [], "boxes": []}
            state = {"exited": False}

            def acquire(*, restore_existing=True, request="restore", running=running, state=state, log=log):
                log["requests"].append(request)
                single_instance.restored_existing = running not in (None, "hidden")
                return running is None or state["exited"]

            def windows(running=running):
                return [] if running in (None, "hidden") else [(0x200, 777, running)]

            def post(found, message, state=state, log=log, exits=exits):
                log["posted"].append({restore: "restore", exit_: "exit"}.get(message, message))
                if message == exit_ and exits:
                    state["exited"] = True
                return bool(found)

            def ask(title, text, log=log, yes=yes):
                log["asked"].append(text.split("\n")[0])
                return bool(yes)

            single_instance.acquire_single_instance = acquire
            single_instance.find_running_windows = windows
            single_instance.post_to_windows = post
            bootstrap._ask = ask
            bootstrap._start_ui = lambda: "started"
            bootstrap.OTHER_VERSION_EXIT_S = 0.5
            bootstrap._message_box = lambda title, *a, log=log, **k: log["boxes"].append(title)
            sys.argv = argv
            log["code"] = bootstrap.launch()
            out[label] = log
    finally:
        for name, value in saved_si.items():
            setattr(single_instance, name, value)
        bootstrap._message_box, bootstrap._ask, bootstrap._start_ui, bootstrap.OTHER_VERSION_EXIT_S = saved
        sys.argv[:], sys.excepthook = saved_sys
    out["version numbers"] = [
        single_instance.version_number("v108.168"),
        single_instance.version_text(108164),
        single_instance.version_number("garbage"),
        single_instance.version_text(0),
    ]

    # The running copy, asked to exit: it exits as Options > Exit does.
    class Shown(window_chrome.WindowChromeMixin, Window):
        pass

    exits = []
    real_exit = window_chrome.exit_application
    window_chrome.exit_application = exits.append
    try:
        win = Shown()
        msg = wintypes.MSG()
        msg.message = single_instance.exit_message_id()
        out["exit message"] = list(win.nativeEvent(b"windows_generic_MSG", ctypes.addressof(msg)))
        CLOCK.advance(50)
        out["exited"] = [w is win for w in exits]
        out["message ids"] = [single_instance.restore_message_id(), single_instance.exit_message_id()]
    finally:
        window_chrome.exit_application = real_exit
    return out


def match_width_case():
    """v108.173: Button 1 and 2's comments follow an axis bind comment's width."""
    from spnav_mapper.ui.profile_marquee import ScrollingLineEdit
    from spnav_mapper.ui.widgets import MatchWidth

    source = fakeqt.QLineEdit()
    targets = [ScrollingLineEdit(), ScrollingLineEdit()]
    matcher = MatchWidth(source, targets)
    before = [t.maximumWidth() for t in targets]
    source.setGeometry(0, 0, 263, 30)
    matcher.eventFilter(source, fakeqt.QEvent(fakeqt.QEvent.Resize))
    after = [[t.minimumWidth(), t.maximumWidth()] for t in targets]
    again = matcher.apply()  # nothing left to change
    return {
        "before": before,
        "after": after,
        "again": again,
        "scrolls": isinstance(targets[0], ScrollingLineEdit),
    }


def elevation_case():
    """v108.174: keys to a program running as administrator are blocked; the Mapper says so."""
    import ctypes

    from spnav_mapper import keyboard_io, restart, win32
    from spnav_mapper.ui import elevation

    saved = (
        win32.window_pid,
        win32.process_elevated,
        win32.window_exe_path,
        restart.restart_as_administrator,
    )
    elevated = {11: True, 22: False, 33: None}  # by pid: admin, not, cannot tell
    win32.window_pid = lambda hwnd: hwnd // 100
    win32.process_elevated = lambda pid: elevated.get(pid)
    win32.window_exe_path = lambda hwnd: {1100: r"C:\Games\Admin\admin_game.exe"}.get(hwnd, r"C:\x\plain.exe")
    restarts = []
    restart.restart_as_administrator = restarts.append
    out = {}
    try:

        class Tray:
            def __init__(self):
                self.messages = []

            def showMessage(self, title, text, *args):
                self.messages.append(text)

        win = Window()
        win._tray = Tray()
        guard = elevation.ElevationGuard(win, mapper_admin=False)

        def tick(hwnd, allow=True, send=True):
            if send:
                keyboard_io.SENT_EVENTS += 1
            return guard.tick(hwnd, allow)

        out["no keys sent"] = tick(1100, send=False)
        out["output off"] = tick(1100, allow=False)
        out["admin program"] = tick(1100)
        out["again"] = tick(1100)
        out["plain program"] = tick(2200)
        out["cannot tell"] = tick(3300)
        out["tray"] = win._tray.messages
        out["status"] = win.statusBar().currentMessage()
        first = len(fakeqt.EFFECTS)
        for answer in (fakeqt.QMessageBox.No, fakeqt.QMessageBox.Yes):
            fakeqt.QMessageBox.ANSWER = answer
            guard.check_target(1100)
        fakeqt.QMessageBox.ANSWER = None
        out["asked"] = [e[3] for e in fakeqt.EFFECTS[first:] if e[1] == "message-box"]
        out["restarts"] = [w is win for w in restarts]
        out["plain target asks"] = guard.check_target(2200)
        admin = elevation.ElevationGuard(win, mapper_admin=True)
        keyboard_io.SENT_EVENTS += 1
        out["as administrator"] = [admin.tick(1100, True), admin.check_target(1100)]

        menu = fakeqt.QMenu()
        win2 = Window()
        elevation.install_elevation_guard(win2, menu)
        out["menu item"] = [a.text() for a in menu.actions()]
    finally:
        win32.window_pid, win32.process_elevated, win32.window_exe_path, restart.restart_as_administrator = (
            saved
        )

    # Restart as administrator: Windows asks; declined, nothing changes.
    closes = []
    real_close = restart.close_for_successor
    restart.close_for_successor = lambda window, title: closes.append(title) or True
    shell = ctypes.windll.shell32
    results = {}
    try:
        for label, answer in (("accepted", 42), ("declined", 5)):
            calls = []
            shell.ShellExecuteW = lambda *a, calls=calls, answer=answer: calls.append(a[1:3]) or answer
            win3 = Window()
            results[label] = [
                restart.restart_as_administrator(win3),
                calls[0][0],
                win3.statusBar().currentMessage(),
            ]
    finally:
        restart.close_for_successor = real_close
    out["restart"] = results
    out["closed"] = closes
    return out


def menu_autoclose_case():
    """v108.160: a menu-bar drop-down closes once the mouse has been away from it for a moment."""
    from fakeqt import QCursor, QMenu, QPoint, QRect, QSize

    from spnav_mapper.ui import menu_autoclose

    class Popup:  # an open drop-down, in screen coordinates
        def __init__(self, rect):
            self.rect, self.shown = rect, True

        def geometry(self):
            return self.rect

        def isVisible(self):
            return self.shown

        def hide(self):
            self.shown = False

    menu = QMenu("Options")

    class Bar:  # the menu bar: 0..400 x 0..24
        def actions(self):
            return [menu.menuAction()]

        def mapToGlobal(self, p):
            return QPoint(p.x(), p.y())

        def size(self):
            return QSize(400, 24)

    now = [0.0]
    out = {}
    saved_pos = QCursor._pos

    def run(path, popups):
        """Open Options, then move the mouse along `path` [(x, y, seconds later)]; what happened."""
        watcher = menu_autoclose.MenuAutoClose(Bar(), clock=lambda: now[0])
        watcher.open_menus = lambda: [p for p in popups if p.shown]
        menu.aboutToShow.emit()
        steps = []
        for x, y, later in path:
            now[0] += later
            QCursor._pos = QPoint(x, y)
            closed = watcher.check()
            steps.append([closed, [p.shown for p in popups]])
        return {"steps": steps, "watching": watcher.timer.isActive()}

    try:
        drop = QRect(40, 24, 200, 160)  # Options' drop-down, under its heading
        sub = QRect(240, 60, 180, 100)  # a submenu beside it
        # From the heading into the drop-down and its submenu, then away: closes 0.4 s later.
        out["away"] = run(
            [
                (60, 10, 0.1),
                (100, 80, 0.1),
                (300, 90, 0.1),
                (600, 400, 0.1),
                (600, 400, 0.2),
                (600, 400, 0.2),
            ],
            [Popup(drop), Popup(sub)],
        )
        # Away for a moment (a gap, a slip) and back: stays open.
        out["back"] = run(
            [(100, 80, 0.1), (100, 300, 0.1), (100, 300, 0.2), (100, 80, 0.1), (100, 80, 0.5)], [Popup(drop)]
        )
        # Opened from the keyboard with the mouse elsewhere: stays open.
        out["keyboard"] = run([(900, 700, 0.1), (900, 700, 1.0), (900, 700, 1.0)], [Popup(drop)])
        # The mouse moves along the menu bar to another heading: stays open.
        out["along the bar"] = run([(60, 10, 0.1), (350, 12, 0.5), (350, 12, 0.5)], [Popup(drop)])
    finally:
        QCursor._pos = saved_pos
    out["steps"] = [
        menu_autoclose.leave_step(True, False, None, 1.0),
        menu_autoclose.leave_step(False, False, None, 1.0),
        menu_autoclose.leave_step(False, True, None, 1.0),
        menu_autoclose.leave_step(False, True, 1.0, 1.3),
        menu_autoclose.leave_step(False, True, 1.0, 1.5),
    ]
    return out


results = {
    # Qt mis-maps the window into the gap: Windows' answer is used.
    "save in the logical gap": save_case((2700, 200, 300, 120), D2, (3840 + 100, 200)),
    # Native offsets are divided by the monitor's scale factor.
    "save on the 150% monitor": save_case((200, 100, 300, 120), D1, (300, 150)),
    # Without Windows' answer the Qt geometry is used, as before.
    "save without Windows' answer": save_case((3940, 200, 300, 120), None, None),
    "gap without Windows' answer saves nothing": save_case((2700, 200, 300, 120), None, None),
    "restore on the saved monitor": restore_case(record_on(D2, 100, 200), [D2]),
    "restore that strays is moved back": restore_case(record_on(D2, 100, 200), [D1, D2]),
    "restore keeps straying": restore_case(record_on(D2, 100, 200), [D1]),
    "restore on the primary monitor": restore_case(record_on(D1, 40, 60), [D1]),
    "positions saved": positions_saved_cases(),
    "menu fonts": menu_font_case(),
    "menu points": menu_points_case(),
    "menu-bar headings": menu_heading_case(),
    "restart comes to the front": restart_front_case(),
    "scrolling comments": scrolling_comment_case(),
    "tray profiles": tray_profiles_case(),
    "old window_state.json": old_state_case(),
    "second launch": second_launch_case(),
    "version label": version_label_case(),
    "noback glow": noback_glow_case(),
    "axis panel": axis_panel_case(),
    "tray menu": tray_menu_case(),
    "macro editor": macro_editor_case(),
    "macro bind": macro_bind_case(),
    "key picker": key_picker_case(),
    "device presence": device_presence_case(),
    "fit to the screen": fit_to_screen_case(),
    "stale default font": stale_font_case(),
    "settle": settle_case(),
    "settle while strayed": settle_strayed_case(),
    "monitor change": monitor_change_case(),
    "refit after a drag": refit_case(),
    "profile buttons": profile_buttons_case(),
    "taskbar launches": taskbar_launch_case(),
    "match width": match_width_case(),
    "elevation": elevation_case(),
    "menu autoclose": menu_autoclose_case(),
}
print(json.dumps(results))
