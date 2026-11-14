"""Size the editor to its content and keep every control readable.

* The editor is sized to its six-axis content, limited to the monitor's
  work area (the axis area scrolls when it does not fit).
* fit_controls_to_text re-checks control heights after fonts and QSS are
  applied, for the reduced interface sizes.
* After the window moves to a monitor with a different scale, it is re-fitted
  in place once the drag is finished.
"""

import ctypes

from PyQt5.QtCore import QEvent, QObject, Qt, QTimer
from PyQt5.QtWidgets import QScrollArea, QStyle

from . import scaling as _ui_scaling
from .scaling import restore_readable_height


def prepare_full_scroll(win):
    """Let the editor's scroll areas resize with the window."""
    # Six bind rows per axis make the full editor larger than the available
    # area on some displays. Scroll each axis grid instead of clipping it.
    try:
        from PyQt5.QtWidgets import QScrollArea, QSizePolicy

        full = win.centralWidget()
        if full is None:
            return
        for scroll in full.findChildren(QScrollArea):
            scroll.setWidgetResizable(True)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setMinimumSize(0, 0)
            scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        full.setMinimumSize(0, 0)
    except Exception:
        pass


def editor_needed_size(win):
    """Natural QMainWindow CLIENT width/height needed without axis scrollbars.

    This routine is read-only: it does not resize panes, rearrange binds,
    modify configs, or change the saved geometry.
    """
    full = win.centralWidget()
    if full is None:
        return (1200, 937)
    layout = full.layout()
    if layout is None:
        hint = full.sizeHint()
        return (max(300, hint.width()), max(300, hint.height()))
    full.ensurePolished()
    layout.activate()
    axis_scroll = None
    for scroll in full.findChildren(QScrollArea):
        if scroll.widget() is not None and scroll.widget().layout() is not None:
            # The full editor has one scroll area around all six axes.
            axis_scroll = scroll
            break
    base = layout.sizeHint()
    wanted_w, wanted_h = int(base.width()), int(base.height())
    if axis_scroll is not None:
        axes_widget = axis_scroll.widget()
        axes_widget.ensurePolished()
        axes_layout = axes_widget.layout()
        axes_layout.activate()
        axes_hint = axes_layout.sizeHint().expandedTo(axes_widget.minimumSizeHint())
        # QScrollArea's default sizeHint is deliberately much smaller than
        # the six-axis grid's actual desired viewport size.
        extra = 2 * max(0, axis_scroll.frameWidth()) + 6
        wanted_axes_w = int(axes_hint.width()) + 2 * axis_scroll.frameWidth()
        wanted_axes_h = max(0, int(axes_hint.height())) + extra
        margins = layout.contentsMargins()
        # The three axis columns set the width. Allow flexible toolbar
        # fields to contract to their minimum before widening the editor.
        wanted_w = max(layout.minimumSize().width(), wanted_axes_w + margins.left() + margins.right())
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget() is axis_scroll:
                wanted_h = max(0, wanted_h - int(item.sizeHint().height())) + wanted_axes_h
                break
    # Other QMainWindow client-space elements are outside centralWidget.
    try:
        wanted_h += max(0, int(win.menuBar().sizeHint().height()))
    except Exception:
        pass
    try:
        wanted_h += max(0, int(win.statusBar().sizeHint().height()))
    except Exception:
        pass
    # Small spare room avoids 1-2 px scrollbars due to Qt rounding/DPI.
    return max(350, wanted_w), max(350, wanted_h + 10)


def fit_controls_to_text(win):
    """Measure styled Qt controls after construction.

    Track each button's scaled font + QSS padding; re-apply its height after
    Qt polish (every Display size since v108.154; before, only below 100%). Combos and inputs remain grow-only
    to protect their text and popup display.
    """
    try:
        from PyQt5.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton, QWidget

        roots = [win]
        try:
            roots.extend(getattr(win, "axes", {}).values())
        except (AttributeError, TypeError):
            pass
        seen = set()
        for root in roots:
            if root is None:
                continue
            for w in root.findChildren(QWidget):
                if id(w) in seen:
                    continue
                seen.add(id(w))
                # Labels are only adjusted when they already have a fixed height.
                if isinstance(w, (QPushButton, QComboBox, QLineEdit)) or (
                    isinstance(w, QLabel)
                    and w.minimumHeight() == w.maximumHeight()
                    and w.maximumHeight() < 16777215
                ):
                    restore_readable_height(w)
        # Recompute layouts after increasing widget heights; keep existing
        # editor sizing and monitor-boundary logic in charge of geometry.
        for root in roots:
            try:
                if root is not None and root.layout() is not None:
                    root.layout().invalidate()
            except (RuntimeError, AttributeError):
                pass
    except (RuntimeError, AttributeError, TypeError, ImportError):
        pass


VK_LBUTTON = 0x01


def _mouse_held():
    """True while the left mouse button is down (a window drag)."""
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
    except (AttributeError, OSError):
        return False


def _refit_to_screen(win):
    """Resize the editor to fit its monitor once a drag between monitors ends."""
    timer = getattr(win, "_screen_refit_timer", None)
    if _mouse_held() and timer is not None:
        timer.start()  # still dragging: wait until the window is dropped
        return
    if not win.isVisible() or win.isMinimized() or win.isMaximized() or win.isFullScreen():
        return
    handle = win.windowHandle()
    # v108.163: the monitor Windows has the window on; Qt's screen() can name
    # the other one while the monitors use different scale factors, and the
    # window was then fitted into, and moved onto, that monitor.
    screen = _windows_screen(win)
    if screen is None or handle is None:
        return
    target = getattr(win, "_placement_target", None)
    if target and screen.name() != target[0]:
        return  # a just-restored window strayed: placement will move it back
    area = screen.availableGeometry()
    margins = handle.frameMargins()
    left, top, right, bottom = (
        max(0, n) for n in (margins.left(), margins.top(), margins.right(), margins.bottom())
    )
    room_w = max(200, area.width() - left - right)
    room_h = max(200, area.height() - top - bottom)
    prepare_full_scroll(win)
    width, height = editor_needed_size(win)
    if height > room_h:
        width += win.style().pixelMetric(QStyle.PM_ScrollBarExtent) + 4
    width, height = min(width, room_w), min(height, room_h)
    win.setMinimumSize(200, 200)
    current = win.geometry()
    x = max(area.x() + left, min(current.x(), area.x() + area.width() - right - width))
    y = max(area.y() + top, min(current.y(), area.y() + area.height() - bottom - height))
    win.setGeometry(x, y, width, height)
    win._screen_ratio = screen.devicePixelRatio()
    _note(
        f"Re-fitted the editor to {screen.name()} (scale {screen.devicePixelRatio():.3f}): {width}x{height}"
    )


def _windows_screen(win):
    """The monitor Windows has the window on (Qt's answer when Windows gives none)."""
    from .placement import window_screen  # here: placement imports this module

    return window_screen(win)


def _note(message):
    """Write a line to the start-up log."""
    try:
        from ..bootstrap import note

        note(message)
    except Exception:
        pass


def _screen_changed(win, screen):
    """Schedule a refit when the window reaches a monitor with another scale."""
    if screen is None:
        return
    previous = getattr(win, "_screen_ratio", None)
    if previous is not None and abs(screen.devicePixelRatio() - previous) < 0.001:
        return  # same scale: Qt changed nothing, keep any manual resize
    win._screen_refit_timer.start()


def _watch_window_screen(win):
    """Follow the window's monitor changes."""
    # Reconnect when the native window is (re)created; harmless to repeat.
    handle = win.windowHandle()
    if handle is None or getattr(win, "_watched_handle", None) is handle:
        return
    handle.screenChanged.connect(lambda screen, w=win: _screen_changed(w, screen))
    win._watched_handle = handle
    if handle.screen() is not None:
        win._screen_ratio = handle.screen().devicePixelRatio()


class _ScreenWatchFilter(QObject):
    def eventFilter(self, obj, event):
        """Start following monitor changes once the window has a native handle."""
        if event.type() in (QEvent.Show, QEvent.WinIdChange):
            _watch_window_screen(obj)
        return False


def install_screen_watch(win):
    """Install the monitor-change watch on the main window."""
    try:
        win._screen_refit_timer = QTimer(win)
        win._screen_refit_timer.setSingleShot(True)
        win._screen_refit_timer.setInterval(250)
        win._screen_refit_timer.timeout.connect(lambda w=win: _refit_to_screen(w))
        win._screen_filter = _ScreenWatchFilter(win)
        win.installEventFilter(win._screen_filter)
        _watch_window_screen(win)
    except Exception as exc:
        _note("Per-monitor re-fit unavailable: " + repr(exc))


# v108.151: after start-up the log records whether the editor fits its monitor.
FIT_CHECK_MS = 1500


def log_editor_fit(win):
    """Note in startup.log the editor's natural size, its monitor's room and the fit used.

    Returns (needed, room), or None when the editor is not shown.
    """
    if not win.isVisible() or win.isMinimized():
        return None
    handle = win.windowHandle()
    screen = _windows_screen(win)
    if screen is None or handle is None:
        return None
    area = screen.availableGeometry()
    margins = handle.frameMargins()
    room = (
        area.width() - max(0, margins.left()) - max(0, margins.right()),
        area.height() - max(0, margins.top()) - max(0, margins.bottom()),
    )
    need = editor_needed_size(win)
    info = _ui_scaling.UI_SCALE_INFO
    try:  # Windows' own sizes: too large when the scale changed since sign-in
        scroll = int(win.style().pixelMetric(QStyle.PM_ScrollBarExtent))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        scroll = 0
    _note(
        f"Editor size: needs {need[0]}x{need[1]}, {screen.name()} has {room[0]}x{room[1]} "
        f"(fit {info.get('fit_factor', 1.0)}, layout scale {_ui_scaling.SCALE}, "
        f"font {win.font().pointSizeF():g} pt, scroll bar {scroll} px)"
    )
    return need, room
