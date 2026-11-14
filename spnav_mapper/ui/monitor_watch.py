"""Offer a restart when the monitors changed after start-up (v108.163).

The per-monitor Qt factors (monitor_scale) and the editor's layout are fixed
when the Mapper starts, for the monitors connected then. When a monitor is
connected later (at a Windows sign-in the Mapper can start before every
monitor is ready), or a monitor's resolution or Windows scaling changes, the
editor is drawn at the wrong size on it until the Mapper restarts.

This module notices such a change once Windows has finished re-arranging the
monitors, and, while the editor is shown, asks whether to restart (the same
restart a Display size change uses: the editor comes back where it was). It
never restarts by itself, and does not ask again for the same monitors. A
monitor that was disconnected changes nothing, so nothing is asked.
"""

from PyQt5.QtCore import QEvent, QObject, QTimer
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QMessageBox

# After a monitor change: wait until Windows has stopped re-arranging them.
QUIET_MS = 2000
# After the editor is shown: once its placement has settled.
SHOWN_MS = 1000
TITLE = "Monitors Changed"


def _note(message):
    """Write a line to the start-up log."""
    try:
        from ..bootstrap import note

        note(message)
    except Exception:
        pass


class _ShownFilter(QObject):
    def eventFilter(self, obj, event):
        """A check that waited for the editor to be shown runs once it is."""
        if event.type() == QEvent.Show and getattr(obj, "_monitor_check_pending", False):
            check_monitors_soon(obj, SHOWN_MS)
        return False


def install_monitor_watch(win):
    """Follow monitors being connected, disconnected, resized or rescaled."""
    try:
        timer = QTimer(win)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda w=win: check_monitors(w))
        win._monitor_check_timer = timer
        win._monitor_declined = set()
        win._monitor_check_pending = False
        win._monitor_filter = _ShownFilter(win)
        win.installEventFilter(win._monitor_filter)
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(lambda screen, w=win: _changed(w, screen))
            app.screenRemoved.connect(lambda _screen, w=win: _changed(w))
        for screen in QGuiApplication.screens():
            _watch_screen(win, screen)
    except Exception as exc:
        _note("Monitor change watch unavailable: " + repr(exc))


def _watch_screen(win, screen):
    """Follow one monitor's resolution and scaling."""
    for name in ("geometryChanged", "logicalDotsPerInchChanged"):
        signal = getattr(screen, name, None)
        if signal is not None:
            signal.connect(lambda *_args, w=win: _changed(w))


def _changed(win, screen=None):
    """A monitor came, went or changed: check once things are quiet."""
    if screen is not None:
        _watch_screen(win, screen)
    check_monitors_soon(win, QUIET_MS)


def check_monitors_soon(win, delay=SHOWN_MS):
    """Check the monitors after `delay` ms (restarted by every new change)."""
    timer = getattr(win, "_monitor_check_timer", None)
    if timer is not None:
        timer.start(int(delay))


def check_monitors(win):
    """Ask to restart when the editor is drawn at the wrong size on a monitor now. True when asked."""
    from . import monitor_scale

    try:
        monitors = monitor_scale.native_monitors()
    except (OSError, AttributeError, ValueError, TypeError):
        return False
    stale = monitor_scale.stale_monitors(monitor_scale.INFO, monitors)
    if not stale:
        win._monitor_check_pending = False
        return False
    if not win.isVisible() or win.isMinimized():
        win._monitor_check_pending = True  # asked when the editor is shown
        return False
    win._monitor_check_pending = False
    key = tuple(sorted(monitor_scale.monitor_shape(m) for m in monitors))
    declined = getattr(win, "_monitor_declined", set())
    if key in declined:
        return False
    lines = [f"{monitor_scale.describe_monitor(m)} ({why})" for m, why in stale]
    _note("Monitors changed since start-up, editor sized wrong on: " + "; ".join(lines))
    text = (
        "The monitors changed since the Mapper started, so the editor is drawn at the "
        "wrong size on:\n\n" + "\n".join(lines) + "\n\nRestart the Mapper now to size it "
        "for them? It comes back where it is."
    )
    answer = QMessageBox.question(win, TITLE, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
    if answer == QMessageBox.Yes:
        from ..restart import restart_after_display_change

        _note("Monitors changed: restarting.")
        restart_after_display_change(win)
    else:
        declined.add(key)
        win._monitor_declined = declined
        win.statusBar().showMessage(
            "Monitors changed: the editor is sized for them after the Mapper restarts.", 8000
        )
    return True
