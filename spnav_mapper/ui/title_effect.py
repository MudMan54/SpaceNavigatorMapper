"""Hover shimmer on the "SpaceNavigator Mapper" title.

A rainbow outline and an orbiting spark are painted over the title while the
pointer is over the window. The overlay is mouse-transparent, so clicks reach
the title (a click minimizes the window).

Bind buttons have two lines driven by the same timer: white along the bottom
for NoBack (NoBackSweep) and green along the top for the Bind Dir
(BindDirSweep). Each sweeps from the middle while the pointer is over the
window and rests at full length otherwise. v108.178: a bind with Rebound has
an amber dot at its end (ReboundBounce) that falls from the top and bounces on
the bottom like a ball let go, each bounce lower, and comes to rest there.
"""

import math

from PyQt5.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt5.QtWidgets import QApplication, QWidget


class RainbowOverlay(QWidget):
    """Hover-only animated rainbow outline and orbiting spark."""

    def __init__(self, target):
        """Overlay that draws the title's rainbow border."""
        super().__init__(target)
        self._title_target = target
        self._phase = 0.0
        self._hover_on = False
        self._wanted = True
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setGeometry(target.rect())
        target.installEventFilter(self)
        self.show()
        self.raise_()

    def eventFilter(self, watched, event):
        """Keep the overlay the size of its widget."""
        if watched is self._title_target and event.type() in (
            QEvent.Resize,
            QEvent.Show,
            QEvent.FontChange,
            QEvent.StyleChange,
        ):
            try:
                self.setGeometry(watched.rect())
                if event.type() == QEvent.Show and self._wanted:
                    self.show()
                self.raise_()
            except RuntimeError:
                pass
        return False

    def set_wanted(self, on):
        """Show or hide the overlay for good (not just between hovers)."""
        self._wanted = bool(on)
        self.setVisible(self._wanted)
        if self._wanted:
            self.setGeometry(self._title_target.rect())
            self.raise_()
        else:
            self._hover_on = False

    def set_hover_phase(self, active, phase):
        """Set the animation phase and repaint."""
        active = bool(active)
        changed = active != self._hover_on
        self._hover_on = active
        self._phase = float(phase) % 1.0
        if active or changed:
            self.update()

    @staticmethod
    def _rainbow(hue, alpha):
        """A rainbow colour for a hue and opacity."""
        # HSV hue wraps naturally at 360 degrees; alpha controls glow.
        return QColor.fromHsv(int(hue) % 360, 245, 255, int(alpha))

    def _orbit_gradient(self, cx, cy, opacity):
        """The rotating conical gradient of the border."""
        # A ~78-degree highlight consisting of a complete rainbow, with
        # transparent leading and trailing edges.  Rotating the angular
        # gradient is the Qt equivalent of the example's conic spark.
        grad = QConicalGradient(cx, cy, -360.0 * self._phase)
        grad.setColorAt(0.000, self._rainbow(0, 0))
        grad.setColorAt(0.010, self._rainbow(0, opacity))
        grad.setColorAt(0.041, self._rainbow(35, opacity))
        grad.setColorAt(0.072, self._rainbow(60, opacity))
        grad.setColorAt(0.103, self._rainbow(120, opacity))
        grad.setColorAt(0.134, self._rainbow(185, opacity))
        grad.setColorAt(0.165, self._rainbow(240, opacity))
        grad.setColorAt(0.196, self._rainbow(290, opacity))
        grad.setColorAt(0.217, self._rainbow(325, 0))
        grad.setColorAt(1.000, self._rainbow(0, 0))
        return grad

    def paintEvent(self, event):
        """Paint the animated border."""
        if not self._hover_on or self.width() < 18 or self.height() < 14:
            return
        painter = None
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            # The inset keeps the glow inside the title's box; the radius
            # is clamped to the title's height.
            bounds = QRectF(3.5, 3.5, self.width() - 7.0, self.height() - 7.0)
            r = min(9.0, max(3.0, (bounds.height() - 2.0) * 0.45))
            path = QPainterPath()
            path.addRoundedRect(bounds, r, r)
            cx, cy = bounds.center().x(), bounds.center().y()

            # Faint full rainbow perimeter (only visible on hover).
            halo = QConicalGradient(cx, cy, -360.0 * self._phase)
            for i in range(7):
                hue = (i % 6) * 60
                halo.setColorAt(i / 6.0, self._rainbow(hue, 75))
            pen = QPen(QBrush(halo), 1.6)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

            # Transparent glow + bright multicolor band orbit the border.
            for thickness, alpha in ((6.2, 28), (3.9, 72), (2.1, 240)):
                spark = self._orbit_gradient(cx, cy, alpha)
                edge_pen = QPen(QBrush(spark), thickness)
                edge_pen.setCapStyle(Qt.RoundCap)
                edge_pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(edge_pen)
                painter.drawPath(path)
        except (RuntimeError, AttributeError, TypeError, ValueError):
            pass  # Decorative painting must not interrupt HID mapping.
        finally:
            if painter is not None and painter.isActive():
                painter.end()


class SweepLine(RainbowOverlay):
    """A thin line along one edge of a Bind button, from the middle outward.

    Side "-": sweeping left; "+": sweeping right; "+-": both ways. It sweeps
    while the pointer is over the window (the title's timer, about 1.3 s a
    sweep) and rests at full length otherwise. The button's own style is
    unchanged; the line is painted over it.
    """

    SWEEP_SHARE = 0.6  # of each cycle spent growing; the rest fades
    EDGE = "bottom"
    RGB = (255, 255, 255)

    def __init__(self, target):
        """Thin line on a Bind button (white NoBack, green Bind Dir)."""
        self._sides = ""
        super().__init__(target)

    def set_sides(self, sides):
        """Which way the line runs from the middle: left, right or both."""
        sides = "".join(side for side in "+-" if side in (sides or ""))
        if sides != self._sides:
            self._sides = sides
            self.update()

    def sides(self):
        """The sides the line covers."""
        return self._sides

    def sweep(self):
        """(share of the half-width reached, alpha) for the current phase."""
        if not self._hover_on:
            return 1.0, 170
        t = (self._phase * 2.0) % 1.0
        if t < self.SWEEP_SHARE:
            grow = t / self.SWEEP_SHARE
            return 1.0 - (1.0 - grow) ** 3, 255  # ease out
        fade = (t - self.SWEEP_SHARE) / (1.0 - self.SWEEP_SHARE)
        return 1.0, int(255 - 215 * fade)

    def paintEvent(self, _event):
        """Paint the line from the middle out to its current reach."""
        if not self._sides:
            return
        w, h = float(self.width()), float(self.height())
        if w < 18 or h < 10:
            return
        reach, alpha = self.sweep()
        thick = max(2.0, h * 0.05)
        inset = max(4.0, h * 0.12)  # inside the border and its rounding
        y = h - inset if self.EDGE == "bottom" else inset
        middle = w / 2.0
        length = (middle - max(5.0, w * 0.06)) * reach
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(*self.RGB, alpha))
        pen.setWidthF(thick)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        for side in self._sides:
            end = middle + length if side == "+" else middle - length
            painter.drawLine(QPointF(middle, y), QPointF(end, y))
        painter.end()


class NoBackSweep(SweepLine):
    """White, along the bottom: the bind's NoBack - / NoBack + / both."""


class BindDirSweep(SweepLine):
    """Green, along the top: the bind's Bind Dir (NEG left, POS right, FULL both)."""

    EDGE = "top"
    RGB = (34, 197, 94)  # #22c55e


class ReboundBounce(SweepLine):
    """An amber dot at the end of a Bind button on its Rebound side(s), bouncing like a ball let go.

    "+": the right end; "-": the left end (the beginning); "+-": both. While
    the pointer is over the window the dot starts at the top, by the Bind Dir
    line, falls to the bottom and bounces off it, each bounce lower, like the
    puck's spring after it is let go; then it rests at the bottom, fades, and
    starts again (one round with each lap of the title's timer, about 2.7 s).
    Otherwise it rests at the bottom. v108.179: a dot bouncing up and down (in
    the v108.178 test an upright line moved sideways).
    """

    RGB = (245, 158, 11)  # #f59e0b
    BOUNCES = 4
    BOUNCE_SHARE = 0.72  # of each lap spent bouncing; the rest it stays at the bottom, fading

    def bounce(self):
        """(height above the bottom as a share of the drop, alpha) for the current phase."""
        if not self._hover_on:
            return 0.0, 170
        t = self._phase % 1.0
        if t < self.BOUNCE_SHARE:
            u = t / self.BOUNCE_SHARE
            # A ball let go: down to the bottom and up again, BOUNCES times, lower each time.
            return abs(math.cos(math.pi * self.BOUNCES * u)) * (1.0 - u) ** 1.5, 255
        fade = (t - self.BOUNCE_SHARE) / (1.0 - self.BOUNCE_SHARE)
        return 0.0, int(255 - 195 * fade)

    GAP = 3.0  # between the dot and the button's label

    @staticmethod
    def radius(height):
        """The dot's radius on a button `height` pixels high."""
        return max(2.5, float(height) * 0.09)

    @staticmethod
    def edge(height):
        """How far the dot stays from the end of the button."""
        return max(5.0, float(height) * 0.12)

    @classmethod
    def room(cls, height):
        """The width the dot takes at an end of a button `height` high, its gap to the label included."""
        return cls.edge(height) + 2.0 * cls.radius(height) + cls.GAP

    def spots(self):
        """Where the dot is now: [(x, y, radius)] for each side, in the button's pixels."""
        w, h = float(self.width()), float(self.height())
        if not self._sides or w < 18 or h < 10:
            return []
        height, _alpha = self.bounce()
        radius = self.radius(h)
        edge = self.edge(h)
        top, bottom = h * 0.27, h * 0.73  # between the Bind Dir line and the NoBack line
        y = bottom - (bottom - top) * height
        return [((w - edge - radius) if side == "+" else (edge + radius), y, radius) for side in self._sides]

    def paintEvent(self, _event):
        """Paint the dot at its current height at each end."""
        spots = self.spots()
        if not spots:
            return
        _height, alpha = self.bounce()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(*self.RGB, alpha)))
        for x, y, radius in spots:
            painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.end()


# Bind button attributes holding its lines (axis_panel._refresh_bind_lines).
LINE_ATTRIBUTES = ("_noback_glow", "_dir_line", "_rebound_dot")


def _noback_glows(win):
    """Every shown line (NoBack and Bind Dir) on every Bind button."""
    out = []
    for panel in (getattr(win, "axes", None) or {}).values():
        for button in getattr(panel, "slot_btns", ()):
            for attribute in LINE_ATTRIBUTES:
                line = getattr(button, attribute, None)
                if line is not None and line._wanted:
                    out.append(line)
    return out


def _cursor_over_app(win):
    """True when the mouse pointer is over the Mapper's window."""
    if not win.isVisible():
        return False
    point = QCursor.pos()
    widget = QApplication.widgetAt(point)
    while widget is not None:
        if widget is win:
            return True
        widget = widget.parentWidget()
    # Window decorations are native rather than Qt widgets.  Only accept
    # them if this app has focus, to avoid animating behind another window.
    return bool(win.isActiveWindow() and win.frameGeometry().contains(point))


def _title_controls(win):
    """The widgets that get the title effect."""
    title = getattr(win, "title_label", None)
    return [title] if title is not None else []


def wire_title_effect(win):
    """Attach the border overlay to the title."""
    try:
        for target in _title_controls(win):
            effect = getattr(target, '_container_overlay', None)
            if effect is None:
                target._container_overlay = RainbowOverlay(target)
            else:
                effect.setGeometry(target.rect())
                effect.raise_()
    except (RuntimeError, AttributeError, TypeError):
        pass


def _tick_title_effect(win):
    """Advance the title and Bind-line animation while hovering."""
    try:
        active = _cursor_over_app(win)
        was_active = getattr(win, '_title_was_hovered', False)
        if active:
            # One lap in ~2.7 s at 40ms/tick; pause off-hover.
            win._title_phase = (getattr(win, '_title_phase', 0.0) + 0.015) % 1.0
        else:
            win._title_phase = 0.0
        win._title_was_hovered = active
        if active or was_active:
            wire_title_effect(win)
            for control in _title_controls(win):
                overlay = getattr(control, '_container_overlay', None)
                if overlay is not None:
                    overlay.set_hover_phase(active, win._title_phase)
            for glow in _noback_glows(win):
                glow.set_hover_phase(active, win._title_phase)
    except (RuntimeError, AttributeError, TypeError):
        pass


def install_title_effect(win):
    """Start the title animation timer."""
    win._title_phase = 0.0
    win._title_was_hovered = False
    wire_title_effect(win)
    win._title_effect_timer = QTimer(win)
    win._title_effect_timer.setInterval(40)
    win._title_effect_timer.timeout.connect(lambda w=win: _tick_title_effect(w))
    win._title_effect_timer.start()
