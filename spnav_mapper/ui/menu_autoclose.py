"""Drop-downs close once the mouse has left them (v108.160), not when a setting is clicked (v108.178).

Auto-Profiles, Options and Display (and their submenus) stay open while the
mouse is over the drop-down, its open submenus or the menu bar, and close
LEAVE_MS after the mouse has moved away from all of them. A menu opened from
the keyboard, with the mouse elsewhere, is left alone until the mouse has
been over it once. v108.178: a Bind button's right-click menu closes the same
way (autoclose_popup).

v108.178: a click on a setting (an item with a check mark: NoBack, a Rebound
time, Device LED...) changes it and leaves the drop-down open, so several can
be set and seen in one visit (StayOpen). An item that opens a window or a
dialog, loads a profile, moves or restarts the editor closes the drop-down as
before: those carry the CLOSES_MENU property or have no check mark.
"""

import time

from PyQt5.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer
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

    def __init__(self, bar, clock=time.monotonic, popup=None):
        """Watch the menus of the menu bar `bar`, or (with no bar) the pop-up menu `popup`."""
        super().__init__(bar if bar is not None else popup)
        self.bar = bar
        self.clock = clock
        self.entered = False
        self.away_since = None
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.check)
        for action in bar.actions() if bar is not None else ():
            menu = action.menu()
            if menu is not None:
                menu.aboutToShow.connect(self.start)
        if popup is not None:
            popup.aboutToShow.connect(self.start)

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
        """The menu bar, in screen coordinates (empty for a pop-up menu)."""
        if self.bar is None:
            return QRect()
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


def autoclose_popup(menu):
    """Have a pop-up menu (a Bind button's) close once the mouse has been over it and left."""
    menu._spnav_autoclose = MenuAutoClose(None, popup=menu)
    return menu._spnav_autoclose


def close_open_menus():
    """Close every open drop-down (before a dialog opens: one cannot be used behind an open menu)."""
    try:
        app = QApplication.instance()
        for widget in app.topLevelWidgets() if app is not None else ():
            if isinstance(widget, QMenu) and widget.isVisible():
                widget.hide()
    except (RuntimeError, AttributeError, TypeError):
        pass


# --- v108.178: a click on a setting leaves the drop-down open -----------------
CLOSES_MENU = "spnav_closes_menu"  # an action's property: a click on it closes the drop-down as usual
WATCHED = "spnav_stay_open"  # a menu's property: StayOpen already listens to it


def closes_menu(action):
    """Mark a check-marked item whose click closes the drop-down (it opens, moves or restarts something)."""
    action.setProperty(CLOSES_MENU, True)
    return action


def stays_open(action):
    """True for an item whose click changes a setting and leaves its drop-down open."""
    try:
        return bool(
            action is not None
            and action.isEnabled()
            and not action.isSeparator()
            and action.menu() is None
            and action.isCheckable()
            and not action.property(CLOSES_MENU)
        )
    except (RuntimeError, AttributeError, TypeError):
        return False


class StayOpen(QObject):
    """Keeps a drop-down open when one of its settings is clicked.

    Qt closes a menu on every click. Here the click on a setting is taken
    before the menu sees it: the item is triggered (its check mark changes)
    and the menu, with its parent menus, stays as it is. A menu with a
    `_spnav_refresh` function has it called afterwards, to bring its other
    items up to date.
    """

    def watch(self, menu):
        """Listen to `menu` and its submenus, those it gets later too."""
        pending = [menu]
        while pending:
            current = pending.pop()
            if current is None:
                continue
            try:
                current.installEventFilter(self)  # installing twice keeps one
                if not current.property(WATCHED):
                    current.setProperty(WATCHED, True)
                    current.aboutToShow.connect(lambda m=current: self.watch(m))
                pending.extend(action.menu() for action in current.actions() if action.menu() is not None)
            except (RuntimeError, AttributeError, TypeError):
                pass

    def eventFilter(self, menu, event):
        """Take a left click on a setting: trigger it, keep the menu open."""
        try:
            if event.type() != QEvent.MouseButtonRelease or event.button() != Qt.LeftButton:
                return False
            action = menu.actionAt(event.pos())
            if not stays_open(action):
                return False
            action.trigger()
            self.refresh(menu)
            return True
        except (RuntimeError, AttributeError, TypeError):
            return False

    @staticmethod
    def refresh(menu):
        """Bring `menu` and the menus it hangs from up to date after a click."""
        seen = 0
        while menu is not None and seen < 8:
            refresh = getattr(menu, "_spnav_refresh", None)
            if callable(refresh):
                refresh()
            parent = menu.parentWidget()
            menu = parent if isinstance(parent, QMenu) else None
            seen += 1


def keep_open(owner, menu):
    """Have clicks on `menu`'s settings leave it open; `owner` is a widget of the window (or the window)."""
    try:
        win = owner.window()
    except (RuntimeError, AttributeError, TypeError):
        win = owner
    stay = getattr(win, "_menu_stay_open", None)
    if stay is None:
        stay = StayOpen(menu)  # no menu bar's listener: one of the menu's own
        menu._spnav_stay_open = stay
    stay.watch(menu)
    return stay


def install_menu_autoclose(win):
    """Have the window's menu-bar drop-downs close once the mouse leaves them (None without a menu bar)."""
    menu_bar = getattr(win, "menuBar", None)
    if menu_bar is None:
        return None
    bar = menu_bar()
    win._menu_autoclose = MenuAutoClose(bar)
    # v108.178: and stay open when a setting in them is clicked.
    win._menu_stay_open = StayOpen(bar)
    for action in bar.actions():
        if action.menu() is not None:
            win._menu_stay_open.watch(action.menu())
    return win._menu_autoclose
