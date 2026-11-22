"""Scroll overflowing text (profile names, comments) inside the existing Qt text rectangle."""

from PyQt5.QtCore import QElapsedTimer, Qt, QTimer
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import (
    QLineEdit,
    QStyle,
    QStyleOptionFrame,
    QStylePainter,
)


def scroll_offset(elapsed_ms, overflow_px):
    """Pixels to scroll a long name after a pause, then pause at the end."""
    if overflow_px <= 0:
        return 0
    travel_ms = overflow_px * 32
    phase = elapsed_ms % (1400 + travel_ms + 1000)
    return min(overflow_px, max(0, phase - 1400) // 32)


class _Marquee:
    def _init_marquee(self, changed):
        """Set up the scrolling clock and timer."""
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(32)
        self._timer.timeout.connect(self.update)
        changed.connect(self._restart)

    def _restart(self, *_):
        """Scroll the text from its start again."""
        self._clock.invalidate()
        self.update()

    def resizeEvent(self, event):
        """Restart scrolling when the field changes size."""
        super().resizeEvent(event)
        self._restart()

    def hideEvent(self, event):
        """Stop scrolling while hidden."""
        self._timer.stop()
        self._clock.invalidate()
        super().hideEvent(event)

    def _overflow(self, text, rect):
        """How many pixels the text is wider than the field."""
        overflow = self.fontMetrics().horizontalAdvance(text) - rect.width()
        if overflow > 0 and rect.width() > 0:
            if not self._clock.isValid():
                self._clock.start()
            if not self._timer.isActive():
                self._timer.start()
            return overflow
        self._timer.stop()
        self._clock.invalidate()
        return 0

    def _draw_name(self, painter, text, rect, overflow, role):
        """Paint the text at its current scroll position."""
        painter.setClipRect(rect)
        colour = getattr(self, "_name_colour", None)  # v108.187: an important note's red or white
        painter.setPen(QColor(colour) if colour else self.palette().color(role))
        offset = scroll_offset(self._clock.elapsed(), overflow)
        rect.setLeft(rect.left() - offset)
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine, text)


NAME_COLOUR_MARK = "/* name colour */"  # what set_name_colour() adds to the field's own style sheet


class ProfileDisplay(_Marquee, QLineEdit):
    _name_colour = None

    def __init__(self, parent=None):
        """The read-only Profile name field, scrolling long names."""
        super().__init__(parent)
        self._init_marquee(self.textChanged)

    def set_name_colour(self, colour):
        """Show the text in `colour` ("#rrggbb"), or in its usual colour for None (v108.187).

        For the profile name while its profile has an important note: red and
        white in turn until the note has been opened, then red. The colour is
        a rule added to the field's own style sheet (for a QLineEdit only, so
        its tip keeps its colours); the rest of that sheet is left as it is.
        """
        if colour == self._name_colour:
            return
        self._name_colour = colour
        own = self.styleSheet().split(NAME_COLOUR_MARK)[0]
        self.setStyleSheet(own + (f"{NAME_COLOUR_MARK} QLineEdit {{ color:{colour}; }}" if colour else ""))
        self.update()

    def paintEvent(self, event):
        """Paint the profile name at its scroll position."""
        option = QStyleOptionFrame()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QStyle.SE_LineEditContents, option, self)
        margins = self.textMargins()
        rect = rect.adjusted(margins.left() + 2, margins.top(), -margins.right() - 2, -margins.bottom())
        text = self.displayText()
        overflow = self._overflow(text, rect)
        if not overflow or self.hasSelectedText():
            return super().paintEvent(event)
        painter = QStylePainter(self)
        painter.drawPrimitive(QStyle.PE_PanelLineEdit, option)
        self._draw_name(painter, text, rect, overflow, QPalette.Text)


class ScrollingLineEdit(ProfileDisplay):
    """Editable field (comments) that scrolls overflowing text like the profile name.

    It scrolls only while it is not being edited: with the keyboard focus it
    behaves as a normal QLineEdit (cursor, selection, typing).
    """

    def paintEvent(self, event):
        """Paint long comment text scrolling while not being edited."""
        if self.hasFocus():
            self._timer.stop()
            self._clock.invalidate()
            return QLineEdit.paintEvent(self, event)
        return super().paintEvent(event)

    def focusInEvent(self, event):
        """Restart scrolling from the start when the field gets focus."""
        super().focusInEvent(event)
        self._restart()

    def focusOutEvent(self, event):
        """Restart scrolling from the start when the field loses focus."""
        super().focusOutEvent(event)
        self._restart()  # scroll from the start again
