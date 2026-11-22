"""Hover tips (v108.178): white on black, in the drop-downs' font, beside what they explain.

Qt's own tips came up under the mouse pointer, in a small font and one long
line each. Here every tip of the Mapper (a button, a label, a comment, an
item of a drop-down) is shown in one window of the Mapper's own:

- white text on black, in the font of the Auto-Profiles, Options and Display
  drop-downs;
- wrapped at the width of an axis's comment box;
- at the right or the left edge of the button or text it explains, or below
  or above it, never under the pointer (tip_place.py), and inside the
  Mapper's window while there is room (a drop-down's tip stays off the
  drop-down and its open submenu).

Qt still decides when a tip is due (the pointer has rested on something that
has one) and sends its ToolTip event; Tips answers that event before the
widget does. After a tip has shown, moving to a neighbouring item brings the
next one up quickly, as Qt's did.
"""

import time

from PyQt5.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer
from PyQt5.QtGui import QColor, QCursor, QPalette
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QMenu, QWidget

from ..tip_place import place_tip
from .menu_tips import has_own_tip

TIP_MARGIN = 6  # around the text, inside the tip's border
MIN_WRAP = 200  # the narrowest width a tip is wrapped at
FALLBACK_WRAP = 360  # ... when no comment box can be measured
PROBE_MS = 90  # how often the pointer is looked at for the next tip after one has shown
RECENT_S = 1.5  # how long after a tip the next one comes up quickly
SIZE_MAX = 16777215  # Qt's QWIDGETSIZE_MAX

NOTHING = object()  # a place that must show no tip (a drop-down's item without one)

# Any of these, anywhere in the Mapper, takes the tip away.
HIDE_ON = (
    QEvent.MouseButtonPress,
    QEvent.MouseButtonDblClick,
    QEvent.KeyPress,
    QEvent.Wheel,
    QEvent.WindowDeactivate,
    QEvent.ApplicationDeactivate,
)


def as_tuple(rect):
    """A QRect as (x, y, width, height)."""
    return rect.x(), rect.y(), rect.width(), rect.height()


def show_time_ms(text):
    """How long a tip stays up with the pointer at rest: Qt's own rule."""
    return 10000 + 40 * max(0, len(text) - 100)


class TipLabel(QLabel):
    """The tip's window: white text on black, wrapped at a width."""

    def __init__(self, font=None):
        """A frameless tip window that never takes the focus or the mouse."""
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setMargin(TIP_MARGIN)
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(1)
        palette = QPalette(self.palette())
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            for role in (QPalette.Window, QPalette.Base, QPalette.ToolTipBase):
                palette.setColor(group, role, QColor(0, 0, 0))
            for role in (QPalette.WindowText, QPalette.Text, QPalette.ToolTipText):
                palette.setColor(group, role, QColor(255, 255, 255))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        if font is not None:
            self.setFont(font)

    def fit(self, text, wrap_width):
        """Set the text and size the window: one line if it fits in `wrap_width`, else wrapped. (w, h)."""
        self.setMinimumSize(0, 0)
        self.setMaximumSize(SIZE_MAX, SIZE_MAX)
        self.setWordWrap(False)
        self.setText(text)
        hint = self.sizeHint()
        width, height = int(hint.width()), int(hint.height())
        if width > wrap_width:
            self.setWordWrap(True)
            width = int(wrap_width)
            height = int(self.heightForWidth(width))
            if height <= 0:
                height = int(self.sizeHint().height())
        self.setFixedSize(width, height)
        return width, height


class Tips(QObject):
    """Shows every hover tip of the Mapper in its own window (see the module's text)."""

    def __init__(self, win, font=None, wrap_width=None):
        """`font()`: the tip's font; `wrap_width()`: the width to wrap at (both asked when a tip shows)."""
        super().__init__(win)
        self.win = win
        self._font = font
        self._wrap_width = wrap_width
        self.label = None  # made with the first tip
        self.widget = None  # what the shown tip explains
        self.action = None  # ... and the item, in a drop-down
        self.anchor = None  # its rectangle on the screen; None: no tip shown
        self.text = ""
        self.shown_at = None  # where the tip was put: (x, y)
        self._quick_until = 0.0
        self._rested_at = None
        self.expire = QTimer(self)
        self.expire.setSingleShot(True)
        self.expire.timeout.connect(self.hide_tip)
        self.probe = QTimer(self)
        self.probe.setSingleShot(True)
        self.probe.setInterval(PROBE_MS)
        self.probe.timeout.connect(self.look)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    # -- events ---------------------------------------------------------
    def eventFilter(self, watched, event):
        """Answer Qt's ToolTip events; take the tip away when the pointer leaves or a key or button is pressed."""
        try:
            kind = event.type()
            if kind == QEvent.ToolTip:
                return self.tip_event(watched, event)
            if self.anchor is None:
                return False  # no tip shown: nothing to watch
            if kind == QEvent.MouseMove:
                if not self.anchor.contains(event.globalPos()):
                    self.hide_tip(quick_next=True)
            elif kind in HIDE_ON:
                self.hide_tip()
            elif watched is self.widget:
                if kind == QEvent.Leave:
                    self.hide_tip(quick_next=True)
                elif kind in (QEvent.Hide, QEvent.Close):
                    self.hide_tip()
        except (RuntimeError, AttributeError, TypeError):
            pass  # a tip must never get in the way of the event
        return False

    def tip_event(self, widget, event):
        """Qt says a tip is due at `event.pos()` of `widget`. True when it was handled here."""
        if not isinstance(widget, QWidget) or widget is self.label:
            return False
        target = self.target(widget, event.pos())
        if target is None:
            return False  # nothing of ours: Qt goes on to the parent widget
        if target is NOTHING:
            self.hide_tip()
            return True
        self.show_tip(widget, *target)
        return True

    def target(self, widget, pos):
        """What a tip at `pos` of `widget` is for: (text, rectangle on the screen, drop-down item), NOTHING or None."""
        if isinstance(widget, QMenu):
            if not widget.toolTipsVisible():
                return None
            action = widget.actionAt(pos)
            if action is None or action.isSeparator() or not has_own_tip(action):
                return NOTHING
            return self.item_target(widget, action)
        text = widget.toolTip()
        if not text:
            return None
        return text, QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size()), None

    @staticmethod
    def item_target(menu, action):
        """(text, rectangle on the screen, item) for the tip of a drop-down's item."""
        row = menu.actionGeometry(action)
        corner = menu.mapToGlobal(QPoint(0, row.y()))
        # The whole row, the drop-down's width: the tip goes beside the drop-down.
        return action.toolTip(), QRect(corner.x(), corner.y(), menu.width(), row.height()), action

    def look(self):
        """Soon after a tip: once the pointer rests on something else with a tip, show it."""
        if self.anchor is not None or time.monotonic() > self._quick_until:
            return
        try:
            pos = QCursor.pos()
            point = (pos.x(), pos.y())
            if point != self._rested_at:
                self._rested_at = point  # still moving: look again
                self.probe.start()
                return
            widget = QApplication.widgetAt(pos)
            while widget is not None and widget is not self.label:
                target = self.target(widget, widget.mapFromGlobal(pos))
                if target is NOTHING:
                    return
                if target is not None:
                    self.show_tip(widget, *target)
                    return
                if widget.isWindow():
                    return
                widget = widget.parentWidget()
        except (RuntimeError, AttributeError, TypeError):
            pass

    # -- showing --------------------------------------------------------
    def wrap_width(self, outer):
        """The width tips are wrapped at: an axis's comment box, within reason."""
        try:
            width = int(self._wrap_width()) if self._wrap_width is not None else 0
        except (RuntimeError, AttributeError, TypeError, ValueError):
            width = 0
        if width <= 0:
            width = FALLBACK_WRAP
        return max(MIN_WRAP, min(width, int(outer[2]) - 2 * TIP_MARGIN))

    def areas(self, widget, anchor):
        """(the Mapper window the tip belongs in, the screen) as rectangles; the window is None when hidden."""
        screen = QApplication.screenAt(anchor.center()) or QApplication.primaryScreen()
        outer = screen.availableGeometry()
        owner = widget
        while isinstance(owner, QMenu) and owner.parentWidget() is not None:
            owner = owner.parentWidget()  # a drop-down belongs to the window it was opened from
        owner = owner.window()
        if isinstance(owner, QMenu) or not owner.isVisible() or owner.isMinimized():
            return None, as_tuple(outer)  # the tray icon's menu: no window to stay in
        inside = QRect(owner.mapToGlobal(QPoint(0, 0)), owner.size()).intersected(outer)
        if inside.width() <= 0 or inside.height() <= 0:
            return None, as_tuple(outer)
        return as_tuple(inside), as_tuple(outer)

    def show_tip(self, widget, text, anchor, action=None):
        """Show `text` for `widget` (its `action`, in a drop-down), whose rectangle on the screen is `anchor`."""
        if (
            self.anchor is not None
            and widget is self.widget
            and action is self.action
            and text == self.text
            and as_tuple(anchor) == as_tuple(self.anchor)
        ):
            return  # this tip is up already
        if self.label is None:
            font = self._font() if callable(self._font) else self._font
            self.label = TipLabel(font)
        bounds, outer = self.areas(widget, anchor)
        size = self.label.fit(text, self.wrap_width(outer))
        cursor = QCursor.pos()
        avoid = []
        around = as_tuple(anchor)
        if isinstance(widget, QMenu):  # keep the open drop-downs readable
            app = QApplication.instance()
            avoid = [
                as_tuple(menu.geometry())
                for menu in (app.topLevelWidgets() if app is not None else ())
                if isinstance(menu, QMenu) and menu.isVisible()
            ]
            submenu = action.menu() if action is not None else None
            if submenu is not None and not submenu.isVisible():
                # v108.179: the item's submenu is about to open beside it: keep its place free too.
                hint = submenu.sizeHint()
                edge = anchor.x() + anchor.width()
                avoid.append((edge, anchor.y(), int(hint.width()), int(hint.height())))
            if avoid:
                # Beside the open drop-downs taken together (a submenu stands
                # next to its menu), level with the item.
                left = min(rect[0] for rect in avoid + [around])
                right = max(rect[0] + rect[2] for rect in avoid + [around])
                around = (left, around[1], right - left, around[3])
        x, y = place_tip(
            around,
            size,
            bounds or outer,
            (cursor.x(), cursor.y()),
            avoid=avoid,
            outer=outer if bounds else None,
        )
        self.label.move(int(x), int(y))
        self.label.show()
        self.label.raise_()
        self.widget, self.action, self.anchor, self.text = widget, action, anchor, text
        self.shown_at = (int(x), int(y))
        self.probe.stop()
        self.expire.start(show_time_ms(text))

    def hide_tip(self, quick_next=False):
        """Take the tip away; `quick_next`: the pointer moved on, so the next tip may come up quickly."""
        if self.anchor is None:
            return
        self.widget = self.action = self.anchor = None
        self.text = ""
        self.expire.stop()
        if self.label is not None:
            self.label.hide()
        if quick_next:
            self._quick_until = time.monotonic() + RECENT_S
            self._rested_at = None
            self.probe.start()


def show_tip_now(menu, action):
    """Show the tip of a drop-down's item at once, without the hover wait (v108.179). True when shown.

    It leaves like any tip: when the pointer moves off the item (to its
    submenu, say), or a key or button is pressed.
    """
    try:
        owner = menu
        while isinstance(owner, QMenu) and owner.parentWidget() is not None:
            owner = owner.parentWidget()
        tips = getattr(owner.window(), "_tips", None)
        if tips is None or not has_own_tip(action):
            return False
        tips.show_tip(menu, *tips.item_target(menu, action))
        return True
    except (RuntimeError, AttributeError, TypeError):
        return False


def _comment_width(win):
    """The width of an axis's comment box (0 when there is none yet)."""
    try:
        panel = next(iter(win.axes.values()))
        return int(panel.slot_comments[0].width())
    except (AttributeError, IndexError, StopIteration, RuntimeError, TypeError):
        return 0


def install_tips(win):
    """Show the Mapper's hover tips in its own tip window from now on."""
    from .window_chrome import dropdown_font

    if getattr(win, "menuBar", None) is None:
        return None  # not a window
    win._tips = Tips(win, font=lambda: dropdown_font(win), wrap_width=lambda: _comment_width(win))
    return win._tips
