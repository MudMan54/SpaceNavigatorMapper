"""Header, Bind button and Auto Load / Manual On / Off widgets."""

from PyQt5.QtCore import QEvent, QObject, QPoint, QTimer, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QPushButton, QWidget

from .scaling import S, set_readable_height


class AxisAlignedHeader(QWidget):
    def align_with_axes(self, viewport, panels):
        """Watch the axis panels so the header's right edge follows theirs."""
        self.viewport = viewport
        self.panels = panels
        self.align_timer = QTimer(self)
        self.align_timer.setSingleShot(True)
        self.align_timer.timeout.connect(self._align_right_edge)
        for widget in (viewport, viewport.parentWidget(), panels[0].parentWidget(), *panels):
            widget.installEventFilter(self)
        self.align_timer.start(0)

    def eventFilter(self, watched, event):
        """Re-align after a watched widget moves or resizes."""
        if event.type() in (QEvent.Show, QEvent.Resize, QEvent.Move, QEvent.LayoutRequest):
            self.align_timer.start(0)
        return super().eventFilter(watched, event)

    def _align_right_edge(self):
        """Limit the header's width to the axis panels' right edge."""
        if not self.viewport.isVisible():
            return

        def right_edge(widget):
            return self.mapFromGlobal(widget.mapToGlobal(QPoint(widget.width(), 0))).x()

        width = min(right_edge(self.viewport), max(right_edge(panel) for panel in self.panels))
        if width > 0 and self.maximumWidth() != width:
            self.setMaximumWidth(width)


class MatchWidth(QObject):
    """Keep `targets` as wide as `source` whenever it changes size (v108.173).

    Button 1 and Button 2's comment boxes follow an axis bind's comment box.
    Only the width: a comment box still scrolls a comment longer than it
    (ScrollingLineEdit).
    """

    def __init__(self, source, targets, parent=None):
        """Watch `source`; size `targets` from its next resize on."""
        super().__init__(parent)
        self.source, self.targets = source, tuple(targets)
        source.installEventFilter(self)

    def eventFilter(self, obj, event):
        """The source was resized: the targets take its width."""
        if obj is self.source and event.type() == QEvent.Resize:
            self.apply()
        return False

    def apply(self):
        """Give every target the source's width; True when one changed."""
        try:
            width = int(self.source.width())
        except RuntimeError:  # being destroyed
            return False
        if width <= 0:
            return False
        changed = False
        for target in self.targets:
            if target.minimumWidth() != width or target.maximumWidth() != width:
                target.setFixedWidth(width)
                changed = True
        return changed


class ScaledHeaderButton(QPushButton):
    """Full Editor toolbar button whose preferred width follows its text.

    The native Qt/Windows QPushButton hint imposes relatively wide defaults.
    We retain the original hint from 100% upward and use a text-width hint only
    at reduced interface scaling. As target/key labels change, Qt recomputes
    sizeHint on setText; no static width caps that could truncate key names.
    """

    def sizeHint(self):
        """Size of the button's text at the current font."""
        hint = super().sizeHint()
        from . import scaling

        if scaling.UI_SIZE_FACTOR < 1.0:
            try:
                _, pad_x = scaling.button_padding(vertical=4, horizontal=8)
                text_width = self.fontMetrics().horizontalAdvance(self.text().replace('&', ''))
                hint.setWidth(max(24, text_width + 2 * pad_x + 8))
            except (AttributeError, RuntimeError):
                pass
        return hint


class BindButton(QPushButton):
    MARGIN = 20  # blank space beside the label, both sides together (scaled; at least 14 px)
    _side_space = 0  # v108.180: more blank space at each side, for the Rebound dot

    def sizeHint(self):
        """Size of the Bind button's label at the current font."""
        hint = super().sizeHint()
        # Keep short bindings compact, but still fit multi-key combinations.
        metrics = self.fontMetrics()
        label_width = max(metrics.horizontalAdvance("Bind #6"), metrics.horizontalAdvance(self.text()))
        hint.setWidth(label_width + self.margin() + 2 * self._side_space)
        return hint

    def margin(self):
        """The blank space beside the label without the dot's room, both sides together, in pixels."""
        return max(14, S(self.MARGIN))

    def set_side_space(self, pixels):
        """Keep `pixels` more blank space at each side of the label (v108.180).

        The label stays centred, so a bind with the Rebound dot at an end of
        its button has the same room at both ends and the dot is clear of
        the text. The button grows by twice as much.
        """
        pixels = max(0, int(pixels))
        if pixels != self._side_space:
            self._side_space = pixels
            self.updateGeometry()

    doubleClicked = pyqtSignal()
    rightClicked = pyqtSignal()  # the bind's NoBack menu

    def mouseDoubleClickEvent(self, event):
        """Emit doubleClicked (open the key picker or macro editor)."""
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """Right-click: NoBack (for the way back), Edit macro and Reset axis."""
        if event is not None:
            event.accept()
        self.rightClicked.emit()


class AutoModeCombo(QComboBox):
    """The Auto Load / Manual On / Off selector.

    Auto Load: profiles switch with the program in front, and keys go only
    to the target. Manual On: keys go to whatever is in front (never the
    Mapper). Off: no keys.
    """

    modeChanged = pyqtSignal(str)

    MODE_AUTO_LOAD = "Auto Load"
    MODE_MANUAL_ON = "Manual On"
    MODE_OFF = "Off"
    MODES = (MODE_AUTO_LOAD, MODE_MANUAL_ON, MODE_OFF)

    def __init__(self, parent=None):
        """The Auto Load / Manual On / Off selector."""
        super().__init__(parent)
        self.addItems(list(self.MODES))
        self.setToolTip(
            "Auto Load: program/profile auto-switch; Manual On: mapper active; Off: mapper inactive"
        )
        set_readable_height(self, S(54), "AutoModeCombo")
        self.setMinimumWidth(S(150))
        self.setCurrentText(self.MODE_OFF)
        self.currentIndexChanged.connect(lambda _index: self.modeChanged.emit(self.mode()))

    def mode(self):
        """The selected mode."""
        txt = self.currentText()
        return txt if txt in self.MODES else self.MODE_OFF

    def setMode(self, mode):
        """Select a mode (Off for anything else)."""
        idx = self.findText(mode if mode in self.MODES else self.MODE_OFF)
        if idx >= 0 and idx != self.currentIndex():
            self.setCurrentIndex(idx)

    def isChecked(self):
        """True in Auto Load."""
        return self.mode() == self.MODE_AUTO_LOAD


def _auto_mode_from_config(cfg):
    """The mode a profile stores, accepting the older true/false "auto_mode" field."""
    mode = str(cfg.get("auto_select_mode", "") or "").strip()
    if mode in AutoModeCombo.MODES:
        return mode
    return AutoModeCombo.MODE_AUTO_LOAD if cfg.get("auto_mode") else AutoModeCombo.MODE_MANUAL_ON
