"""Save and restore the editor's position: Display > Positions Saved.

Display > Positions Saved lists the connected monitors; at most one is
checked. With a monitor checked, the editor's position on that monitor is
saved (relative to its work area) whenever the window is closed or hidden
while on it, and the editor opens on that monitor at that position: at
start-up and after a Display % restart. If the checked monitor is not
connected, the primary monitor is used, at the same position as far as it
fits.

Wherever no position is saved the editor opens centred. With no monitor
checked the Mapper starts centred on the primary monitor, and a Display %
restart or a return from the tray centres it on the monitor it is on. With a
monitor checked that has no position saved on it yet, it opens centred there.

window_state.json (version 5):
  "monitor"      the checked monitor, else the monitor last used (also read
                 by monitor_scale for the home monitor);
  "views"        {"full": the editor's last record};
  "per_monitor"  {monitor name: {"full": position}}, relative to the work area.
The checked monitor is in ui_preferences.json ("positions_saved_monitor").
Files from before v108.137 also held the removed compact view's records;
they are dropped the next time the file is written.
"""

import json
import os

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QStyle

from ..paths import CONFIG_DIR
from ..settings import ensure_dir
from ..win32 import client_offset_on_monitor, window_monitor_name
from .editor_fit import _mouse_held, _note, editor_needed_size, prepare_full_scroll
from .window_placement import client_rect, read_views, screen_record, select_screen

WINDOW_STATE_FILE = os.path.join(CONFIG_DIR, "window_state.json")
# After a restore, check (once visible) that Windows really put the window on
# the chosen monitor. Showing a window on a monitor with a different scale can
# move it; the later checks catch Windows' own DPI adjustment.
PLACEMENT_CHECKS_MS = (0, 250, 750)
MAX_PLACEMENT_CORRECTIONS = 2
# v108.153: once shown, measure the editor again (see settle_editor_size).
SETTLE_MS = (100, 400)


POSITIONS_PREFERENCE = "positions_saved_monitor"
VIEW = "full"  # the record key in window_state.json (the editor is the only view)


def positions_monitor():
    """The monitor checked in Display > Positions Saved ({screen_name, serial}), or None."""
    from ..display_preferences import read_preferences

    chosen = read_preferences().get(POSITIONS_PREFERENCE)
    return chosen if isinstance(chosen, dict) and chosen.get("screen_name") else None


def connected_screen(record):
    """The connected QScreen for a monitor record, or None (no fallback)."""
    if not record:
        return None
    screens = QGuiApplication.screens()
    serial = record.get("serial") or ""
    if serial:
        same = [s for s in screens if (s.serialNumber() or "") == serial]
        if len(same) == 1:
            return same[0]
    return next((s for s in screens if s.name() == record.get("screen_name")), None)


def set_positions_monitor(win, screen):
    """Check `screen` in Display > Positions Saved (None: uncheck)."""
    from ..display_preferences import update_preference

    record = None
    if screen is not None:
        ident = screen_record(screen)
        record = {"screen_name": ident["screen_name"], "serial": ident["serial"]}
    update_preference(POSITIONS_PREFERENCE, record)
    _view_positions(win)
    if record is not None:
        win._shared_monitor = screen_record(screen)
    current = window_screen(win) if win.isVisible() else None
    if screen is not None and current is not None and current.name() == screen.name():
        save_window_placement(win)  # the current view's position on it, now
    else:
        _write_state(win)
    _note(f"Positions Saved: {record['screen_name'] if record else 'none checked'}")


def load_window_placement():
    """Read window_state.json, or an empty dict."""
    try:
        if not os.path.isfile(WINDOW_STATE_FILE):
            return None
        with open(WINDOW_STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _view_positions(win):
    """The saved editor positions, loaded once per window."""
    if not hasattr(win, "_view_positions"):
        data = load_window_placement()
        win._view_positions = {k: v for k, v in read_views(data).items() if k == VIEW}
        per = data.get("per_monitor") if isinstance(data, dict) else None
        win._monitor_positions = {
            name: {VIEW: saved[VIEW]}
            for name, saved in (per.items() if isinstance(per, dict) else ())
            if isinstance(saved, dict) and isinstance(saved.get(VIEW), dict)
        }
        monitor = data.get("monitor") if isinstance(data, dict) else None
        win._shared_monitor = monitor if isinstance(monitor, dict) else None
    return win._view_positions


def _monitor_positions(win):
    """Saved editor positions, per monitor."""
    _view_positions(win)
    return win._monitor_positions


def _position(record):
    """The position fields of a saved record."""
    keys = ("relative_x", "relative_y", "w", "h")
    return {k: record[k] for k in keys if k in record}


def _screen_named(name):
    """The connected monitor with this name, or None."""
    if not name:
        return None
    return next((s for s in QGuiApplication.screens() if s.name() == name), None)


def _hwnd(win):
    """The window's native handle, or 0."""
    try:
        return int(win.winId())
    except (RuntimeError, TypeError, ValueError):
        return 0


def window_screen(win):
    """The monitor the window is on, as Windows sees it (Qt's view as fallback)."""
    screen = _screen_named(window_monitor_name(_hwnd(win)))
    if screen is None:
        handle = win.windowHandle()
        screen = handle.screen() if handle is not None else None
    return screen


def save_window_placement(win):
    """Save the editor's position on its monitor (Positions Saved)."""
    if not win.isVisible():
        return
    normal = win.isMinimized() or win.isMaximized() or win.isFullScreen()
    g = win.normalGeometry() if normal else win.geometry()
    if not g.isValid():
        return
    frame = g if normal else win.frameGeometry()

    def overlap(screen):
        rect = frame.intersected(screen.geometry())
        return rect.width() * rect.height() if rect.isValid() else 0

    screens = QGuiApplication.screens()
    if not screens:
        return
    # Ask Windows which monitor the window is on and where. Qt's logical
    # coordinates are not enough with per-monitor scale factors: they can
    # land in the gap between monitors (nothing saved, so the next start
    # reopened the view on the monitor of an older record) or name the
    # wrong one.
    hwnd = _hwnd(win)
    screen = _screen_named(window_monitor_name(hwnd))
    relative = None
    if screen is not None and not normal:
        native = client_offset_on_monitor(hwnd)
        if native is not None and native[0] == screen.name():
            ratio = float(screen.devicePixelRatio() or 1.0)
            relative = (round(native[1] / ratio), round(native[2] / ratio))
    if screen is None:
        # Not on Windows: largest overlap; if Qt's geometry misses every
        # monitor, keep the last saved record.
        screen = max(screens, key=overlap)
        if not overlap(screen):
            return
    area = screen.availableGeometry()
    if relative is None:
        relative = (g.x() - area.x(), g.y() - area.y())
    views = _view_positions(win)
    info = dict(
        screen_record(screen),
        relative_x=relative[0],
        relative_y=relative[1],
        x=area.x() + relative[0],
        y=area.y() + relative[1],
        w=g.width(),
        h=g.height(),
    )
    views[VIEW] = info
    _monitor_positions(win).setdefault(screen.name(), {})[VIEW] = _position(info)
    chosen = positions_monitor()
    win._shared_monitor = dict(chosen) if chosen else screen_record(screen)
    _write_state(win)


def _write_state(win):
    """Write window_state.json."""
    data = {
        "version": 5,
        "monitor": getattr(win, "_shared_monitor", None),
        "views": _view_positions(win),
        "per_monitor": _monitor_positions(win),
    }
    try:
        ensure_dir(CONFIG_DIR)
        temporary = WINDOW_STATE_FILE + ".tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
        os.replace(temporary, WINDOW_STATE_FILE)
    except OSError as exc:
        win.statusBar().showMessage(f"Could not save window position: {exc}", 5000)


def _target_screen(win, startup, keep):
    """(screen, saved position record or None for centred) for the editor about to be shown."""
    screens, primary = QGuiApplication.screens(), QGuiApplication.primaryScreen()
    chosen = positions_monitor()
    if chosen:
        # Positions Saved: always that monitor (primary if not connected),
        # at the position saved for it; centred if it has none yet.
        screen = connected_screen(chosen) or primary
        return screen, _saved_on(win, chosen["screen_name"], screen)
    if not startup:
        # Nothing checked: back from the tray, the editor is centred on the
        # monitor Windows has the window on.
        screen = window_screen(win)
        if screen is not None:
            return screen, None
    if keep:
        # Display % restart, no position saved: centred on the monitor it was on.
        wanted = getattr(win, "_shared_monitor", None) or _view_positions(win).get(VIEW)
        if wanted:
            return select_screen(screens, primary, wanted), None
    return primary, None  # no position saved: centred on the primary monitor


def _saved_on(win, name, screen):
    """The editor's saved position on monitor `name`, placed on `screen`; None if not saved."""
    known = _monitor_positions(win).get(name, {}).get(VIEW)
    return dict(screen_record(screen), **known) if known else None


def restore_window_placement(win, startup=False, keep=False):
    """Place the editor on its monitor. False when there is nothing to restore.

    startup: the first placement after launch (remembered monitor, if the
    option is on); keep: always remember (a restart after a Display % change).
    """
    _view_positions(win)
    screen, info = _target_screen(win, startup, keep)
    if screen is None:
        return False
    if info is None:
        info = {"centre": True}
    win.winId()
    handle = win.windowHandle()
    if handle.screen() != screen:
        handle.setScreen(screen)
    area = screen.availableGeometry()
    margins = handle.frameMargins()
    edges = tuple(max(0, n) for n in (margins.left(), margins.top(), margins.right(), margins.bottom()))
    prepare_full_scroll(win)
    size = editor_needed_size(win)
    if size[1] > area.height() - edges[1] - edges[3]:
        size = (size[0] + win.style().pixelMetric(QStyle.PM_ScrollBarExtent) + 4, size[1])
    if info.get("centre"):
        info = dict(
            info,
            relative_x=(area.width() - size[0]) // 2,
            relative_y=max(edges[1], (area.height() - size[1]) // 2),
        )
    rect = client_rect(info, (area.x(), area.y(), area.width(), area.height()), size, edges)
    win.setMinimumSize(200, 200)
    win.setGeometry(*rect)
    win._placement_target = (screen.name(), rect, 0)
    win._placed_centred = bool(info.get("centre"))
    for i, delay in enumerate(PLACEMENT_CHECKS_MS):
        final = i == len(PLACEMENT_CHECKS_MS) - 1
        QTimer.singleShot(delay, lambda w=win, f=final: _keep_on_target_screen(w, f))
    for delay in SETTLE_MS:
        QTimer.singleShot(delay, lambda w=win: settle_editor_size(w))
    how = "centred" if info.get("centre") else "saved position"
    _note(f"Restored the editor on {screen.name()} at {rect[0]},{rect[1]} ({how})")
    return True


def _keep_on_target_screen(win, final=False):
    """Move a just-restored window back if it opened on another monitor."""
    target = getattr(win, "_placement_target", None)
    if not target:
        return
    name, rect, corrections = target
    if win.isVisible() and not win.isMinimized() and not _mouse_held():
        current = window_screen(win)
        wanted = _screen_named(name)
        if current is not None and wanted is not None and current.name() != name:
            if corrections < MAX_PLACEMENT_CORRECTIONS:
                win.windowHandle().setScreen(wanted)
                win.setGeometry(*rect)
                win._placement_target = (name, rect, corrections + 1)
                _note(f"Window opened on {current.name()} instead of {name}; moved it back.")
    if final:
        win._placement_target = None


def settle_editor_size(win):
    """Grow the just-shown editor to hold its content. True when it was resized.

    The size measured before the window is first shown misses what changes
    once it is: control heights fitted to their styled fonts and the bind rows
    lined up with Quick Bind. Before v108.153 that left the content slightly
    larger than the window at start-up until a placement was made again
    (checking a monitor in Positions Saved). The window only grows, within its
    monitor's work area; centred it stays centred, otherwise it keeps its
    position as far as it fits.

    v108.163: the monitor is the one the editor was placed on, and Windows says
    where the window is. When Windows has moved it to another monitor since it
    was shown, only the rect it is moved back to grows. Before, it grew on the
    monitor Qt named, and that rect, on the wrong monitor, became the one it
    was "moved back" to, so it stayed on the wrong monitor.
    """
    if not win.isVisible() or win.isMinimized() or win.isMaximized() or win.isFullScreen():
        return False
    if _mouse_held():
        return False  # being dragged or resized: leave it to the user
    handle = win.windowHandle()
    target = getattr(win, "_placement_target", None)
    on = window_screen(win)
    screen = (_screen_named(target[0]) if target else None) or on
    if screen is None or handle is None:
        return False
    strayed = on is not None and on.name() != screen.name()
    area = screen.availableGeometry()
    margins = handle.frameMargins()
    left, top, right, bottom = (
        max(0, n) for n in (margins.left(), margins.top(), margins.right(), margins.bottom())
    )
    room_w, room_h = area.width() - left - right, area.height() - top - bottom
    prepare_full_scroll(win)
    width, height = editor_needed_size(win)
    if height > room_h:
        width += win.style().pixelMetric(QStyle.PM_ScrollBarExtent) + 4
    g = win.geometry()
    x, y, now_w, now_h = target[1] if strayed else (g.x(), g.y(), g.width(), g.height())
    width = max(now_w, min(width, room_w))
    height = max(now_h, min(height, room_h))
    if (width, height) == (now_w, now_h):
        return False
    if getattr(win, "_placed_centred", False):
        x = area.x() + (area.width() - width) // 2
        y = area.y() + max(top, (area.height() - height) // 2)
    x = max(area.x() + left, min(x, area.x() + area.width() - right - width))
    y = max(area.y() + top, min(y, area.y() + area.height() - bottom - height))
    if target:
        win._placement_target = (target[0], (x, y, width, height), target[2])
    if strayed:
        _note(f"Editor to grow to {width}x{height} once it is back on {screen.name()}")
        return True
    win.setGeometry(x, y, width, height)
    _note(f"Editor grown to hold its content: {now_w}x{now_h} -> {width}x{height}")
    return True
