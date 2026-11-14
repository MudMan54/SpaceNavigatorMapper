"""The Axis History window and its on/off switch (v108.149).

Options > Axis History turns recording on for all six axes and opens this
window; unchecking it, or closing the window (v108.156), stops recording and
forgets what was recorded. Right-click an axis panel (its border or an empty
spot) > Axis History… opens it again with that axis shown. When the window
was open at the last exit, it opens again with the editor.

v108.157: while the window is open the Target is on for the current profile
(as before once it closes): with the window in front, the binds send their
keys and the window ignores them, so the history shows what they send.

v108.155: any of the six axes can be shown at once, each in its own graph or
all on one graph; the text has a choice of sizes (A− / A+), and the window
opens at most of the screen. The axes, the layout, the time span, the text
size and the window's size are remembered.
"""

import csv
import os
import time

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..axis_history import (
    TEXT_SIZES,
    WINDOWS_S,
    AxisHistory,
    bind_bands,
    csv_rows,
    drawing,
    drawing_together,
    fit_size,
    label_rows,
    load_view,
    summary,
)
from ..display_preferences import read_preferences, update_preference
from ..keyboard_io import combo_to_text
from ..paths import CONFIG_DIR
from ..settings import AXES
from .scaling import S

PREFERENCE = "axis_history"
VIEW_PREFERENCE = "axis_history_view"  # what the window shows (v108.155)
REDRAW_MS = 50  # the graphs redraw 20 times a second while the window is shown
TEXT_POINTS_ABOVE_APP = 2.0  # the window's text at 100%: the app's text + 2 points
LANE_LINES = 9  # each graph is at least nine lines of text tall
REOPEN_MS = 600  # after start-up: reopen the window when it was open at the last exit
ALL_ON_QSS = "QPushButton{background-color:#dc2626;color:#ffffff;font-weight:700;}"
ALL_ON_QSS += "QPushButton:checked{background-color:#16a34a;color:#000000;}"
SEPARATE, TOGETHER = "Separate graphs", "One graph"

COLOURS = {
    "deadzone": (148, 163, 184, 45),
    "grid": (51, 65, 85, 255),
    "label": (148, 163, 184, 255),
    "trace": (255, 255, 255, 255),  # the axis's line (v108.159: white)
    "plus100": (34, 197, 94, 255),  # the +100% line: green
    "zero": (59, 130, 246, 255),  # the 0 line: blue
    "minus100": (239, 68, 68, 255),  # the −100% line: red
    "noback": (226, 232, 240, 255),  # NoBack, light like the NoBack line on the Bind buttons
    # Each bind's basic colour, the same on every axis (v108.159).
    "bind1": (248, 82, 82, 255),  # red
    "bind2": (251, 146, 60, 255),  # orange
    "bind3": (250, 214, 21, 255),  # yellow
    "bind4": (74, 222, 128, 255),  # green
    "bind5": (96, 165, 250, 255),  # blue
    "bind6": (192, 132, 252, 255),  # purple
}
OUTLINE = (11, 18, 32)  # the graph's background: a ring around each filled dot

AXIS_COLOURS = {  # each axis's line, dots and name
    "X": (45, 212, 191),
    "Y": (96, 165, 250),
    "Z": (250, 204, 21),
    "Rx": (244, 114, 182),
    "Ry": (163, 230, 53),
    "Rz": (192, 132, 252),
}


def _colour(name):
    """The QColor of a colour name from axis_history.drawing()."""
    if name in AXIS_COLOURS:
        return QColor(*AXIS_COLOURS[name])
    return QColor(*COLOURS.get(name, COLOURS["label"]))


def noback_note(binds, dead):
    """The summary's NoBack part, such as " · NoBack: Bind #1 −, Bind #3 +" (empty when no bind has it).

    v108.161: named as the Bind button's menu names it, by the way back: "−"
    for NoBack on the + side.
    """
    marks = []
    for index, _sides, _start, _name, noback in bind_bands(binds, dead, _key_text):
        if noback:
            marks.append(f"Bind #{index + 1} {' '.join('+' if side == '-' else '−' for side in noback)}")
    return " · NoBack: " + ", ".join(marks) if marks else ""


def _key_text(bind):
    """The key a bind sends, or "macro"."""
    if bind.get("mode") == "Macro":
        return "macro"
    return combo_to_text(bind.get("combo")) if bind.get("combo") else ""


class HistoryGraph(QWidget):
    """Draws the history of `axes`: one axis in full, or several on one graph."""

    def __init__(self, window, axes):
        """A graph of `axes` for the Axis History window `window`."""
        super().__init__()
        self.history_window = window
        self.axes = list(axes)

    def paintEvent(self, _event):
        """Paint the shapes of the current view."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(QRectF(0, 0, self.width(), self.height()), QColor(*OUTLINE))
        # The window's text size, set here: a style sheet keeps a parent's
        # font from reaching its children (why A− / A+ did nothing in v108.155).
        font = QFont(self.history_window.text_font)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        line, digit = metrics.height(), metrics.horizontalAdvance("0")
        shapes = self.history_window.shapes(
            self.axes, self.width(), self.height(), line, digit, text_w=metrics.horizontalAdvance
        )
        for shape in shapes:
            kind = shape[0]
            if kind == "rect":
                _, x, y, w, h, colour = shape
                painter.fillRect(QRectF(x, y, w, h), _colour(colour))
            elif kind == "line":
                _, x1, y1, x2, y2, colour, width, dashed = shape
                pen = QPen(_colour(colour))
                pen.setWidthF(width)
                if dashed:
                    pen.setStyle(Qt.DotLine if dashed == "dot" else Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            elif kind == "polyline":
                _, points, colour, width = shape
                pen = QPen(_colour(colour))
                pen.setWidthF(width)
                painter.setPen(pen)
                painter.drawPolyline(*(QPointF(x, y) for x, y in points))
            elif kind == "circle":
                _, x, y, r, colour, filled = shape
                pen = QPen(QColor(*OUTLINE) if filled else _colour(colour))
                pen.setWidthF(1.5 if filled else 2.0)
                painter.setPen(pen)
                painter.setBrush(_colour(colour) if filled else Qt.NoBrush)
                painter.drawEllipse(QPointF(x, y), r, r)
                painter.setBrush(Qt.NoBrush)
            elif kind == "text":
                _, x, y, text, colour, align = shape
                painter.setPen(_colour(colour))
                width = metrics.horizontalAdvance(text)
                left = x - width if align == "right" else x - width / 2 if align == "center" else x
                painter.drawText(QPointF(left, y), text)
        painter.end()


class AxisHistoryWindow(QDialog):
    """The last 5, 10 or 30 seconds of any of the axes, with Pause, Clear and Save as CSV."""

    def __init__(self, win):
        """Build the window for the Mapper window `win`."""
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Axis History")
        try:  # no "?" button in the title bar
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        except (AttributeError, TypeError):
            pass
        self.paused_at = None  # the frozen time while paused
        self.view_state = load_view(read_preferences().get(VIEW_PREFERENCE))
        self.lanes = []
        self.text_font = QFont(QApplication.font())
        self._placed = False
        layout = QVBoxLayout(self)

        choose = QHBoxLayout()
        choose.addWidget(QLabel("Axes:"))
        self.axis_checks = {}
        for axis in AXES:
            check = QCheckBox(axis)
            check.setToolTip(f"Show the {axis} axis")
            check.setChecked(axis in self.view_state["axes"])
            check.toggled.connect(lambda on, a=axis: self._axis_toggled(a, on))
            self.axis_checks[axis] = check
            choose.addWidget(check)
        # v108.156: All is green while all six are shown (click: hide them
        # all) and red otherwise (click: show all six).
        self.all_btn = QPushButton("All")
        self.all_btn.setCheckable(True)
        self.all_btn.setToolTip(
            "Green: all six axes shown; click to hide them all. Red: click to show all six."
        )
        self.all_btn.clicked.connect(lambda _checked=False: self.toggle_all())
        choose.addWidget(self.all_btn)
        choose.addSpacing(S(16))
        choose.addWidget(QLabel("Show:"))
        self.layout_box = QComboBox()
        self.layout_box.addItems([SEPARATE, TOGETHER])
        self.layout_box.setToolTip(
            "Separate graphs: each axis with its binds' start lines and dead zone. "
            "One graph: the axes over each other, to compare them."
        )
        self.layout_box.setCurrentText(TOGETHER if self.view_state["together"] else SEPARATE)
        choose.addWidget(self.layout_box)
        choose.addSpacing(S(16))
        choose.addWidget(QLabel("Show the last:"))
        self.span_box = QComboBox()
        self.span_box.addItems([f"{s} s" for s in WINDOWS_S])
        self.span_box.setCurrentText(f"{self.view_state['seconds']} s")
        choose.addWidget(self.span_box)
        choose.addStretch(1)
        layout.addLayout(choose)

        act = QHBoxLayout()
        act.addWidget(QLabel("Text size:"))
        smaller = QPushButton("A−")
        smaller.setToolTip("Smaller text")
        smaller.clicked.connect(lambda _checked=False: self.step_text_size(-1))
        larger = QPushButton("A+")
        larger.setToolTip("Larger text")
        larger.clicked.connect(lambda _checked=False: self.step_text_size(+1))
        act.addWidget(smaller)
        act.addWidget(larger)
        self.size_label = QLabel("")
        act.addWidget(self.size_label)
        act.addStretch(1)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setToolTip("Freeze the graphs to look at them; recording goes on.")
        self.pause_btn.clicked.connect(self.toggle_pause)
        clear = QPushButton("Clear")
        clear.setToolTip("Forget what was recorded on all six axes.")
        clear.clicked.connect(self.clear)
        save = QPushButton("Save as CSV…")
        save.setToolTip("Save the samples and key events of the axes shown, as shown, to a CSV file.")
        save.clicked.connect(self.save_csv)
        for button in (self.pause_btn, clear, save):
            act.addWidget(button)
        layout.addLayout(act)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.lane_box = QWidget()
        self.lane_layout = QVBoxLayout(self.lane_box)
        self.lane_layout.setContentsMargins(0, 0, 0, 0)
        self.lane_layout.setSpacing(S(12))
        self.empty_label = QLabel("No axis is shown: tick one above, or click All.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.lane_layout.addWidget(self.empty_label, 1)
        self.scroll.setWidget(self.lane_box)
        layout.addWidget(self.scroll, 1)
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        hint = QLabel(
            "White line: the axis. Dashed: +100% (green), 0 (blue), −100% (red). Each bind has its "
            "own colour (Bind #1 red, #2 orange, #3 yellow, #4 green, #5 blue, #6 purple), the same "
            "on every axis: a dotted line where it starts, joined to its row on the right, and a dot "
            "for each key it sends, filled when sent (the Target is on while this window is open; "
            "keys sent here are ignored) and hollow when not sent (output off: the Mapper's editor "
            "in front). Shaded grey: the dead zone. NoBack: a thin dashed light line at the highest "
            "band reached while it is in force (lower NoBack binds stay quiet below it until the "
            "axis returns to centre); a hollow light dot is a key it kept from being sent."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.layout_box.currentTextChanged.connect(lambda _text: self._view_changed())
        self.span_box.currentTextChanged.connect(lambda _text: self._view_changed())
        self.timer = QTimer(self)
        self.timer.setInterval(REDRAW_MS)
        self.timer.timeout.connect(self.refresh)
        self.text_size = self.view_state["text_size"]
        self.set_text_size(self.text_size, remember=False)
        self.all_btn.setChecked(len(self.shown_axes()) == len(AXES))
        self._build_lanes()
        self.setFocusPolicy(Qt.StrongFocus)
        self._no_focus()

    # What is shown --------------------------------------------------------
    def shown_axes(self):
        """The axes shown, in the panels' order."""
        return [axis for axis in AXES if self.axis_checks[axis].isChecked()]

    def together(self):
        """True when the axes are drawn on one graph."""
        return self.layout_box.currentText() == TOGETHER

    def seconds(self):
        """How many seconds are shown."""
        return int(self.span_box.currentText().split()[0])

    @property
    def graph(self):
        """The first graph (each axis has its own unless One graph is chosen)."""
        return self.lanes[0] if self.lanes else None

    def set_axes(self, axes):
        """Show exactly `axes` (none is allowed)."""
        wanted = [axis for axis in AXES if axis in axes]
        for axis, check in self.axis_checks.items():
            check.blockSignals(True)
            check.setChecked(axis in wanted)
            check.blockSignals(False)
        self._view_changed()

    def toggle_all(self):
        """All: hide every axis when all six are shown, else show all six."""
        self.set_axes([] if len(self.shown_axes()) == len(AXES) else AXES)

    def _axis_toggled(self, _axis, _on):
        """A check box changed."""
        self._view_changed()

    def _view_changed(self):
        """Rebuild the graphs for the axes and layout chosen, and remember them."""
        self.all_btn.setChecked(len(self.shown_axes()) == len(AXES))
        self._build_lanes()
        self.remember()
        self.refresh()

    def _build_lanes(self):
        """One graph per axis shown, or one for all of them."""
        for lane in self.lanes:
            self.lane_layout.removeWidget(lane)
            lane.setParent(None)
            lane.deleteLater()
        axes = self.shown_axes()
        groups = ([axes] if self.together() else [[axis] for axis in axes]) if axes else []
        self.lanes = [HistoryGraph(self, group) for group in groups]
        for lane in self.lanes:
            lane.setFont(self.text_font)
            self.lane_layout.addWidget(lane, 1)
        self.empty_label.setVisible(not self.lanes)
        self._size_lanes()
        self._no_focus()

    def _no_focus(self):
        """No control takes the keyboard: keys the binds send land on the window, which ignores them."""
        for child in self.findChildren(QWidget):
            child.setFocusPolicy(Qt.NoFocus)

    def keyPressEvent(self, event):
        """Ignore every key (Esc and Enter included): with the Target on, they come from the binds."""
        event.accept()

    def keyReleaseEvent(self, event):
        """Ignore every key release."""
        event.accept()

    def _size_lanes(self):
        """Each graph at least LANE_LINES lines of text tall, and tall enough for a row per bind
        side in its labels (the window scrolls past that)."""
        line = QFontMetrics(self.text_font).height()
        for lane in self.lanes:
            rows = 0
            if len(lane.axes) == 1 and not self.together():
                panel = self.win.axes[lane.axes[0]]
                rows = len(label_rows(bind_bands(panel.binds, panel.dead, _key_text)))
            lane.setMinimumHeight(max(S(160), max(LANE_LINES, rows + 3) * (line + 1)))
            lane.setMinimumWidth(S(400))

    # The view -------------------------------------------------------------
    def now(self):
        """The view's end: the moment Pause was pressed, else now."""
        history = next((p.history for p in self.win.axes.values() if p.history is not None), None)
        clock = history.clock if history is not None else time.perf_counter
        return self.paused_at if self.paused_at is not None else clock()

    def view(self, axis):
        """(samples, events) of `axis` in view."""
        history = self.win.axes[axis].history
        if history is None:
            return [], []
        return history.span(self.now(), self.seconds())

    def shapes(self, axes, width, height, text_px=13, char_px=7, text_w=None):
        """The shapes of a graph of `axes`, `width` × `height` pixels, for text `text_px` tall
        (`text_w(text)`: its width)."""
        now, seconds = self.now(), self.seconds()
        if len(axes) == 1 and not self.together():
            axis = axes[0]
            panel = self.win.axes[axis]
            samples, events = self.view(axis)
            bands = bind_bands(panel.binds, panel.dead, _key_text)
            history = panel.history
            noback = history.noback_span(now, seconds) if history is not None else []
            return drawing(
                samples,
                events,
                bands,
                panel.dead,
                now,
                seconds,
                width,
                height,
                title=axis,
                colour=axis,
                text_px=text_px,
                char_px=char_px,
                noback=noback,
                text_w=text_w,
            )
        series = [(axis, *self.view(axis)) for axis in axes]
        return drawing_together(series, now, seconds, width, height, text_px=text_px, char_px=char_px)

    def refresh(self):
        """Redraw the graphs and the summary lines."""
        lines = []
        for axis in self.shown_axes():
            r, g, b = AXIS_COLOURS[axis]
            lines.append(
                f"<span style='color:rgb({r},{g},{b});font-weight:700'>{axis}</span>: {summary(*self.view(axis))}"
                + noback_note(self.win.axes[axis].binds, self.win.axes[axis].dead)
            )
        self.summary_label.setText("<br>".join(lines))
        for lane in self.lanes:
            lane.update()

    # Text and window size -------------------------------------------------
    def set_text_size(self, size, remember=True):
        """Show the window's text at `size` (one of TEXT_SIZES) × the app's text + 2 points."""
        size = min(TEXT_SIZES, key=lambda choice: abs(choice - float(size)))
        self.text_size = size
        font = QFont(QApplication.font())
        if font.pointSizeF() > 0:
            font.setPointSizeF((font.pointSizeF() + TEXT_POINTS_ABOVE_APP) * size)
        elif font.pixelSize() > 0:
            font.setPixelSize(max(1, round((font.pixelSize() + 3) * size)))
        self.text_font = font
        # A style sheet keeps a parent's font from reaching its children, so
        # each control gets it, and the style sheets carry the size too.
        points = f"{font.pointSizeF():.1f}pt" if font.pointSizeF() > 0 else f"{font.pixelSize()}px"
        self.setFont(font)
        for child in self.findChildren(QWidget):
            child.setFont(font)
        self.setStyleSheet(f"QWidget{{font-size:{points};}}")
        for axis, check in self.axis_checks.items():
            r, g, b = AXIS_COLOURS[axis]
            check.setStyleSheet(f"QCheckBox{{color:rgb({r},{g},{b});font-weight:700;font-size:{points};}}")
        self.all_btn.setStyleSheet(
            ALL_ON_QSS.replace("font-weight:700;", f"font-weight:700;font-size:{points};")
        )
        self.size_label.setText(f"{round(size * 100)}%")
        self._size_lanes()
        if remember:
            self.remember()
        self.refresh()

    def step_text_size(self, steps):
        """The next larger (+1) or smaller (-1) text size."""
        index = TEXT_SIZES.index(self.text_size) + int(steps)
        self.set_text_size(TEXT_SIZES[max(0, min(len(TEXT_SIZES) - 1, index))])

    def _room(self):
        """The available area of the screen the Mapper is on (Qt pixels)."""
        handle = self.win.windowHandle() if hasattr(self.win, "windowHandle") else None
        screen = handle.screen() if handle is not None else None
        screen = screen or QApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else None

    def place(self):
        """Size the window (remembered, else most of the screen) and centre it on the Mapper's screen."""
        area = self._room()
        if area is None:
            self.resize(S(900), S(520))
            return
        width, height = fit_size(self.view_state.get("size"), (area.width(), area.height()))
        self.resize(width, height)
        self.move(area.x() + (area.width() - width) // 2, area.y() + (area.height() - height) // 2)

    def remember(self):
        """Remember the axes, layout, time span, text size and window size for next time."""
        self.view_state = {
            "axes": self.shown_axes(),
            "together": self.together(),
            "seconds": self.seconds(),
            "text_size": self.text_size,
            "size": [self.width(), self.height()] if self._placed else self.view_state.get("size"),
        }
        try:
            update_preference(VIEW_PREFERENCE, self.view_state)
        except OSError:
            pass  # still shown; just not remembered

    # Controls -------------------------------------------------------------
    def show_axis(self, axis=None):
        """Show the window, with `axis` among the axes shown when given."""
        if axis in AXES and not self.axis_checks[axis].isChecked():
            self.axis_checks[axis].setChecked(True)
        if not self._placed:
            self.place()
            self._placed = True
        if hasattr(self.win, "set_history_target"):
            self.win.set_history_target(True)
        self.show()
        self.raise_()
        self.activateWindow()
        self.timer.start()
        self.refresh()

    def toggle_pause(self):
        """Pause (freeze the view) or resume."""
        if self.paused_at is None:
            self.paused_at = self.now()
            self.pause_btn.setText("Resume")
        else:
            self.paused_at = None
            self.pause_btn.setText("Pause")
        self.refresh()

    def clear(self):
        """Forget what was recorded on every axis."""
        for panel in self.win.axes.values():
            if panel.history is not None:
                panel.history.clear()
        self.refresh()

    def save_csv(self):
        """Save the samples and events of the axes shown, in view, to a CSV file the user picks."""
        axes = self.shown_axes()
        if not axes:
            self.win.statusBar().showMessage("Tick an axis to save its history.", 3000)
            return None
        name = "-".join(axes) if len(axes) < len(AXES) else "all"
        default = os.path.join(CONFIG_DIR, f"axis_history_{name}_{time.strftime('%Y%m%d-%H%M%S')}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "Save axis history", default, "CSV files (*.csv)")
        if not path:
            return None
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            with open(path, "w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerows(csv_rows([(axis, *self.view(axis)) for axis in axes]))
        except OSError as exc:
            self.win.statusBar().showMessage(f"✖ Could not save the axis history: {exc}", 5000)
            return None
        self.win.statusBar().showMessage(f"✔ Axis history saved to {os.path.basename(path)}", 3000)
        return path

    def hide_window(self):
        """Hide the window (recording stopped), remembering its size; the Target goes back as it was."""
        self.timer.stop()
        if self._placed:
            self.remember()
        if hasattr(self.win, "set_history_target"):
            self.win.set_history_target(False)
        self.hide()

    def closeEvent(self, event):
        """Closing turns Axis History off (v108.156): recording stops and Options > Axis History is unchecked."""
        self.timer.stop()
        if self.paused_at is not None:
            self.toggle_pause()
        if self._placed:
            self.remember()
        if axis_history_on(self.win):
            set_axis_history(self.win, False)
        if hasattr(self.win, "set_history_target"):
            self.win.set_history_target(False)
        super().closeEvent(event)


# The switch ---------------------------------------------------------------
def axis_history_on(win):
    """True while the axes are being recorded."""
    return any(panel.history is not None for panel in win.axes.values())


def set_axis_history(win, on, show=True):
    """Options > Axis History: record all six axes (and show the window), or stop and forget."""
    on = bool(on)
    for panel in win.axes.values():
        if on and panel.history is None:
            panel.history = AxisHistory()
            panel._dry_states = panel._free_states = None  # the copies start from the binds' own states
        elif not on:
            panel.history = None
    action = getattr(win, "_axis_history_action", None)
    if action is not None and action.isChecked() != on:
        action.blockSignals(True)
        action.setChecked(on)
        action.blockSignals(False)
    try:
        update_preference(PREFERENCE, on)
    except OSError:
        pass  # it still works; it just is not remembered for the next start
    window = getattr(win, "_axis_history_window", None)
    if on:
        if show:
            show_axis_history(win)
        win.statusBar().showMessage("Axis history: recording all six axes", 3000)
    else:
        if window is not None:
            window.hide_window()
        win.statusBar().showMessage("Axis history: off", 2000)


def show_axis_history(win, axis=None):
    """Open the Axis History window (on `axis`), turning recording on when it is off."""
    if not axis_history_on(win):
        set_axis_history(win, True, show=False)
    window = getattr(win, "_axis_history_window", None)
    if window is None:
        window = win._axis_history_window = AxisHistoryWindow(win)
    window.show_axis(axis)
    return window


def add_axis_history_option(win, menu):
    """Add the checkable Options > Axis History; it starts on when it was on at the last exit."""
    from PyQt5.QtWidgets import QAction

    action = QAction("Axis History", win)
    action.setCheckable(True)
    action.setToolTip(
        "Record what each axis does and the keys its binds send, and show it as graphs, "
        "while the Axis History window is open. Right-click an axis to see its history."
    )
    action.toggled.connect(lambda on: set_axis_history(win, on))
    menu.addAction(action)
    win._axis_history_action = action
    if read_preferences().get(PREFERENCE):
        # Open at the last exit: open again once the editor is shown.
        QTimer.singleShot(REOPEN_MS, lambda: reopen_axis_history(win))
    return action


def reopen_axis_history(win):
    """Reopen the window (it was open at the last exit) when the editor is on screen; True when it did."""
    if not win.isVisible() or win.isMinimized() or axis_history_on(win):
        return False  # started in the tray or minimized: it stays off until asked for
    set_axis_history(win, True)
    return True
