"""Menu-bar drop-downs close once the mouse has left them (v108.160).

Auto-Profiles, Options and Display (and their submenus) stay open while the
mouse is over the drop-down, its open submenus or the menu bar, and close
LEAVE_MS after the mouse has moved away from all of them. A menu opened from
the keyboard, with the mouse elsewhere, is left alone until the mouse has
been over it once.
"""

import time

from PyQt5.QtCore import QObject, QPoint, QRect, QTimer
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication, QMenu

POLL_MS = 100  # how often the mouse is looked at while a drop-down is open
LEAVE_MS = 400  # how long the mouse may be away (crossing a gap, say) before the menu closes


def leave_step(inside, entered, away_since, now, leave_s=LEAVE_MS / 1000.0):
    """One look at the mouse: (close now, mouse has been over the menu, away since).

    `inside`: the mouse is over an open drop-down or the menu bar. Nothing
    closes until the mouse has been inside once (a menu opened from the
    keyboard), and then only after `leave_s` seconds away without a return.
    """
    if inside:
        return False, True, None
    if not entered:
        return False, False, None
    if away_since is None:
        return False, True, now
    return now - away_since >= leave_s, True, away_since


class MenuAutoClose(QObject):
    """Watches the mouse while one of `bar`'s drop-downs is open, and closes it once the mouse has left."""

    def __init__(self, bar, clock=time.monotonic):
        """Watch the menus of the menu bar `bar`."""
        super().__init__(bar)
        self.bar = bar
        self.clock = clock
        self.entered = False
        self.away_since = None
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.check)
        for action in bar.actions():
            menu = action.menu()
            if menu is not None:
                menu.aboutToShow.connect(self.start)

    def start(self):
        """A drop-down opened: start watching the mouse."""
        if not self.timer.isActive():
            self.entered, self.away_since = False, None
            self.timer.start()

    def open_menus(self):
        """The drop-downs and submenus open now."""
        app = QApplication.instance()
        widgets = app.topLevelWidgets() if app is not None else []
        return [w for w in widgets if isinstance(w, QMenu) and w.isVisible()]

    def _bar_rect(self):
        """The menu bar, in screen coordinates."""
        return QRect(self.bar.mapToGlobal(QPoint(0, 0)), self.bar.size())

    def check(self):
        """Look at the mouse; close the open drop-downs once it has been away long enough. True when closed."""
        shown = self.open_menus()
        if not shown:
            self.timer.stop()
            return False
        pos = QCursor.pos()
        inside = self._bar_rect().contains(pos) or any(menu.geometry().contains(pos) for menu in shown)
        close, self.entered, self.away_since = leave_step(inside, self.entered, self.away_since, self.clock())
        if close:
            for menu in reversed(shown):
                menu.hide()
            self.timer.stop()
        return close


def install_menu_autoclose(win):
    """Have the window's menu-bar drop-downs close once the mouse leaves them (None without a menu bar)."""
    menu_bar = getattr(win, "menuBar", None)
    if menu_bar is None:
        return None
    win._menu_autoclose = MenuAutoClose(menu_bar())
    return win._menu_autoclose
