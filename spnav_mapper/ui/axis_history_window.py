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
opens at most of the screen. The axes, the layout, the text size and the
window's size are remembered.

v108.187: ten seconds are kept. The graphs show five and a scroll bar under
them goes back over the rest. While the graphs run, the dots have no labels
(text that moves cannot be read): the keys are listed under the graphs, in
rows that stand still, each with how long its key was held; Pause puts the
labels back on the dots. Attach to editor keeps the window joined to the
editor's right side, so a bind can be changed and tried while watching.
Export saves the whole ten seconds: the CSV and, beside it, a chart report
(axis_history_report.py).

v108.188: attached, the window takes the rest of the monitor at full height:
opening it moves the editor aside, unstretched (to the top left of its
monitor, or where it was last put while the window was open, remembered per
monitor), and closing it puts the editor back where and as large as it was.
The puck's Button 1 freezes and resumes the graphs while the window is open.
"""

import csv
import html
import os
import time

from PyQt5.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer
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
    QScrollBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..axis_history import (
    AXIS_COLOURS,
    DOCK_MIN_WIDTH,
    FREEZE_BUTTON,
    KEEP_S,
    OUTLINE,
    TEXT_SIZES,
    VIEW_S,
    AxisHistory,
    bind_bands,
    bind_colour,
    colour_rgba,
    csv_rows,
    drawing,
    drawing_together,
    editor_spot,
    fit_size,
    history_beside,
    key_log,
    key_log_text,
    label_rows,
    load_view,
    ms_text,
    spot_to_remember,
    summary,
)
from ..axis_history_report import report_html
from ..display_preferences import read_preferences, update_preference
from ..keyboard_io import combo_to_text
from ..paths import CONFIG_DIR
from ..settings import AXES, REVISION_DATE, VERSION
from .editor_fit import _note
from .placement import window_screen
from .scaling import S

PREFERENCE = "axis_history"
VIEW_PREFERENCE = "axis_history_view"  # what the window shows (v108.155)
REDRAW_MS = 50  # the graphs redraw 20 times a second while the window is shown
TEXT_POINTS_ABOVE_APP = 2.0  # the window's text at 100%: the app's text + 2 points
LANE_LINES = 9  # each graph is at least nine lines of text tall
REOPEN_MS = 600  # after start-up: reopen the window when it was open at the last exit
REOPEN_AGAIN_MS = 250  # ... looking again while the editor is still being put in its place (v108.189)
REOPEN_TRIES = 8
ALL_ON_QSS = "QPushButton{background-color:#dc2626;color:#ffffff;font-weight:700;}"
ALL_ON_QSS += "QPushButton:checked{background-color:#16a34a;color:#000000;}"
SEPARATE, TOGETHER = "Separate graphs", "One graph"
# v108.187: the scroll bar under the graphs counts tenths of a second back from now.
SCROLL_STEPS_PER_S = 10
KEY_ROWS = 6  # the keys listed under the graphs, the newest on top
DOCK_SETTLE_MS = (0, 250)  # after showing: join the editor again once the window has its frame
NOT_SENT_COLOUR = "#94a3b8"  # a key that was not sent, in the list
# The bar's own look, whatever the style: a dark groove and a blue handle that can be seen on it.
TIME_BAR_QSS = (
    "QScrollBar:horizontal { background:#1f2937; border:1px solid #334155; border-radius:4px; "
    "height:__H__px; margin:0px; }"
    "QScrollBar::handle:horizontal { background:#60a5fa; border-radius:3px; min-width:__W__px; }"
    "QScrollBar::handle:horizontal:hover { background:#93c5fd; }"
    "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0px; height:0px; }"
    "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:transparent; }"
)
LEGEND = (
    "White line: the axis. Dashed: +100% (green), 0 (blue), −100% (red). Each bind has its "
    "own colour (Bind #1 red, #2 orange, #3 yellow, #4 green, #5 blue, #6 purple), the same "
    "on every axis: a dotted line where it starts, joined to its row on the right, and a dot "
    "for each key it sends, filled when sent (the Target is on while this window is open; "
    "keys sent here are ignored) and hollow when not sent (output off: the Mapper's editor "
    "in front). Shaded grey: the dead zone. NoBack: a thin dashed light line at the highest "
    "band reached while it is in force (lower NoBack binds stay quiet below it until the "
    "axis returns to centre); a hollow light dot is a key it kept from being sent. "
    "While the graphs run the dots have no labels: the keys are listed below, the newest "
    "on top. Pause labels the dots."
)


def _colour(name):
    """The QColor of a colour name from axis_history.drawing()."""
    return QColor(*colour_rgba(name))


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


class EditorFollower(QObject):
    """Tells the attached Axis History window when the editor has moved or changed size (v108.187)."""

    def __init__(self, window):
        """Watch the editor of the history window `window`."""
        super().__init__(window)
        self.history_window = window

    def eventFilter(self, _watched, event):
        """The editor moved or was resized: the attached window goes with it."""
        if event.type() in (QEvent.Move, QEvent.Resize):
            self.history_window.follow_editor()
        return False


class AxisHistoryWindow(QDialog):
    """The last 5 of 10 seconds of any of the axes, with Pause, Clear and Export."""

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
        # v108.186: what the graphs showed when Pause was pressed. Recording
        # goes on trimming its rolling KEEP_S window underneath, so a paused
        # view read from the live history drained away from the left once the
        # window caught up with the moment of the pause.
        self._frozen = None  # axis -> a copy of its history at that moment
        self.view_state = load_view(read_preferences().get(VIEW_PREFERENCE))
        self.lanes = []
        self.text_font = QFont(QApplication.font())
        self._placed = False
        # v108.187: attached to the editor's right side. v108.188: opening the
        # window moves the editor aside and closing it puts the editor back.
        self._editor_before = None  # the editor's (x, y, width, height) before the window opened
        self._open_size = None  # the editor's size then: a size other than it is remembered
        self._spot_put = None  # where the editor was last seen while the window is open
        self._spot_live = False  # the editor's moves are followed (and remembered)
        self._keys_html = None
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
        choose.addStretch(1)
        layout.addLayout(choose)

        # v108.187: three short rows, so the window can be narrow beside the editor.
        show = QHBoxLayout()
        show.addWidget(QLabel("Show:"))
        self.layout_box = QComboBox()
        self.layout_box.addItems([SEPARATE, TOGETHER])
        self.layout_box.setToolTip(
            "Separate graphs: each axis with its binds' start lines and dead zone. "
            "One graph: the axes over each other, to compare them."
        )
        self.layout_box.setCurrentText(TOGETHER if self.view_state["together"] else SEPARATE)
        show.addWidget(self.layout_box)
        show.addSpacing(S(16))
        self.attach_check = QCheckBox("Attach to editor")
        self.attach_check.setToolTip(
            "Ticked: opening this window moves the editor to the top left of its monitor (its size "
            "unchanged) and this window takes the rest of the monitor at full height, joined to the "
            "editor's right side, so a bind can be changed and tried while watching the graphs. "
            "Move or resize the editor meanwhile and this window stays beside it; that place is "
            "remembered for the next time. Closing this window puts the editor back where, and as "
            "large as, it was before.\nUnticked: a window of its own, where and as large as you put "
            "it; the editor is left alone."
        )
        self.attach_check.setChecked(bool(self.view_state.get("attached", True)))
        show.addWidget(self.attach_check)
        show.addStretch(1)
        layout.addLayout(show)

        act = QHBoxLayout()
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setToolTip(
            "Freeze the graphs to look at them, for as long as needed; recording goes on underneath.\n"
            "Paused, each dot is labelled with its key and how long it was held, and the scroll bar "
            "goes back over all ten seconds. Export saves what was frozen. Resume returns to live.\n"
            f"Button {FREEZE_BUTTON} on the SpaceNavigator does the same from inside the game: press it "
            "to freeze, press it again to resume. While this window is open it does only that "
            "(its own key is not sent)."
        )
        self.pause_btn.clicked.connect(self.toggle_pause)
        clear = QPushButton("Clear")
        clear.setToolTip("Forget what was recorded on all six axes.")
        clear.clicked.connect(self.clear)
        self.export_btn = QPushButton("Export CSV/HTML")
        self.export_btn.setToolTip(
            f"Save the last {KEEP_S:g} seconds of the axes shown: a CSV file of the samples and keys and, "
            "beside it, a chart report to open in a browser (.html) with each axis's graph, every "
            "setting of its binds and the keys in time order with how long each was held."
        )
        self.export_btn.clicked.connect(lambda _checked=False: self.export())
        self.legend_btn = QPushButton("Legend")
        self.legend_btn.setCheckable(True)
        self.legend_btn.setToolTip("Show or hide the explanation of the graphs' lines and dots.")
        self.legend_btn.setChecked(bool(self.view_state.get("legend", False)))
        self.legend_btn.clicked.connect(lambda _checked=False: self._legend_toggled())
        for button in (self.pause_btn, clear, self.export_btn, self.legend_btn):
            act.addWidget(button)
        act.addStretch(1)
        smaller = QPushButton("A−")
        smaller.setToolTip("Text size: smaller")
        smaller.clicked.connect(lambda _checked=False: self.step_text_size(-1))
        larger = QPushButton("A+")
        larger.setToolTip("Text size: larger")
        larger.clicked.connect(lambda _checked=False: self.step_text_size(+1))
        act.addWidget(smaller)
        act.addWidget(larger)
        self.size_label = QLabel("")
        self.size_label.setToolTip("The text size of this window.")
        act.addWidget(self.size_label)
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

        # v108.187: five seconds are shown; the bar goes back over the ten kept.
        back = QHBoxLayout()
        back.addWidget(QLabel(f"−{KEEP_S:g} s"))
        self.time_bar = QScrollBar(Qt.Horizontal)
        steps = int(round((KEEP_S - VIEW_S) * SCROLL_STEPS_PER_S))
        self.time_bar.setRange(0, max(0, steps))
        self.time_bar.setPageStep(int(VIEW_S * SCROLL_STEPS_PER_S))
        self.time_bar.setSingleStep(max(1, SCROLL_STEPS_PER_S // 2))
        self.time_bar.setValue(self.time_bar.maximum())
        self.time_bar.setStyleSheet(
            TIME_BAR_QSS.replace("__H__", str(max(14, S(20)))).replace("__W__", str(max(30, S(48))))
        )
        self.time_bar.setToolTip(
            f"The graphs show {VIEW_S:g} seconds of the {KEEP_S:g} kept. Drag left to look further back; "
            "all the way right is now. Pause first to hold the picture still."
        )
        self.time_bar.valueChanged.connect(lambda _value: self.refresh())
        back.addWidget(self.time_bar, 1)
        back.addWidget(QLabel("now"))
        layout.addLayout(back)

        self.keys_label = QLabel("")
        self.keys_label.setTextFormat(Qt.RichText)
        self.keys_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # Its rows are one line each and may be wider than a narrow window:
        # they are cut at its edge rather than making the window wider.
        self.keys_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.keys_label.setToolTip(
            "The keys of the axes shown, the newest on top, in rows that stand still while the graphs run.\n"
            "held: how long a Hold bind's key was down (compare with its Min Hold). tap: the tap's Tap Dwell.\n"
            "The last column is the time since the key before it."
        )
        layout.addWidget(self.keys_label)
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.hint_label = QLabel(LEGEND)
        self.hint_label.setWordWrap(True)
        self.hint_label.setVisible(self.legend_btn.isChecked())
        layout.addWidget(self.hint_label)

        self.layout_box.currentTextChanged.connect(lambda _text: self._view_changed())
        self.attach_check.toggled.connect(lambda on: self._attach_toggled(on))
        self.timer = QTimer(self)
        self.timer.setInterval(REDRAW_MS)
        self.timer.timeout.connect(self.refresh)
        self.text_size = self.view_state["text_size"]
        self.set_text_size(self.text_size, remember=False)
        self.all_btn.setChecked(len(self.shown_axes()) == len(AXES))
        self._build_lanes()
        self.setFocusPolicy(Qt.StrongFocus)
        self._no_focus()
        self._follower = EditorFollower(self)
        win.installEventFilter(self._follower)

    # What is shown --------------------------------------------------------
    def shown_axes(self):
        """The axes shown, in the panels' order."""
        return [axis for axis in AXES if self.axis_checks[axis].isChecked()]

    def together(self):
        """True when the axes are drawn on one graph."""
        return self.layout_box.currentText() == TOGETHER

    def seconds(self):
        """How many seconds the graphs show (v108.187: always VIEW_S; the scroll bar goes back)."""
        return VIEW_S

    def ago(self):
        """How many seconds the graphs are scrolled back from the capture's end (0: at now)."""
        return (self.time_bar.maximum() - self.time_bar.value()) / float(SCROLL_STEPS_PER_S)

    def attached(self):
        """True when the window is kept joined to the editor's right side."""
        return self.attach_check.isChecked()

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

    def _legend_toggled(self):
        """Legend: show or hide the explanation under the graphs, and remember it."""
        self.hint_label.setVisible(self.legend_btn.isChecked())
        self.remember()

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
            lane.setMinimumWidth(S(320))
        # The keys' rows keep their room, so the graphs do not jump when a key arrives.
        self.keys_label.setMinimumHeight((KEY_ROWS + 1) * (line + 5))

    # The view -------------------------------------------------------------
    def now(self):
        """The capture's end: the moment Pause was pressed, else now."""
        history = next((p.history for p in self.win.axes.values() if p.history is not None), None)
        clock = history.clock if history is not None else time.perf_counter
        return self.paused_at if self.paused_at is not None else clock()

    def view_end(self):
        """The time at the graphs' right edge: the capture's end, less what the bar is scrolled back."""
        return self.now() - self.ago()

    def _history(self, axis):
        """The history the view reads: the copy frozen at Pause, else the live one."""
        if self._frozen is not None:
            return self._frozen.get(axis)
        return self.win.axes[axis].history

    def view(self, axis):
        """(samples, events) of `axis` in view."""
        history = self._history(axis)
        if history is None:
            return [], []
        return history.span(self.view_end(), self.seconds())

    def capture(self, axis):
        """(samples, events) of `axis` over the whole capture: the last KEEP_S seconds (v108.187)."""
        history = self._history(axis)
        if history is None:
            return [], []
        return history.span(self.now(), KEEP_S)

    def capture_events(self, axis):
        """The events of `axis` over the whole capture (the samples are not gone through)."""
        history = self._history(axis)
        if history is None:
            return []
        now = self.now()
        return [event for event in history.events if now - KEEP_S <= event[0] <= now]

    def labelled(self):
        """None (label the dots, unless too many) while paused; False while the graphs run:
        text that moves cannot be read, and the keys are listed below (v108.187)."""
        return None if self.paused_at is not None else False

    def shapes(self, axes, width, height, text_px=13, char_px=7, text_w=None):
        """The shapes of a graph of `axes`, `width` × `height` pixels, for text `text_px` tall
        (`text_w(text)`: its width)."""
        end, seconds, ago = self.view_end(), self.seconds(), self.ago()
        if len(axes) == 1 and not self.together():
            axis = axes[0]
            panel = self.win.axes[axis]
            samples, events = self.view(axis)
            bands = bind_bands(panel.binds, panel.dead, _key_text)
            history = self._history(axis)
            noback = history.noback_span(end, seconds) if history is not None else []
            return drawing(
                samples,
                events,
                bands,
                panel.dead,
                end,
                seconds,
                width,
                height,
                title=axis,
                colour=axis,
                text_px=text_px,
                char_px=char_px,
                noback=noback,
                text_w=text_w,
                ago=ago,
                labelled=self.labelled(),
            )
        series = [(axis, *self.view(axis)) for axis in axes]
        return drawing_together(
            series,
            end,
            seconds,
            width,
            height,
            text_px=text_px,
            char_px=char_px,
            ago=ago,
            labelled=self.labelled(),
        )

    def key_rows(self):
        """The last KEY_ROWS keys of the axes shown (key_log() rows), the newest first."""
        series = [(axis, [], self.capture_events(axis)) for axis in self.shown_axes()]
        return list(reversed(key_log(series)))[:KEY_ROWS]

    def keys_html(self):
        """The keys' list as a table: rows that stand still while the graphs run (v108.187)."""

        def cell(text, colour="", bold=False):
            text = f"<b>{text}</b>" if bold else text
            return f"<td><span style='color:{colour}'>{text}</span></td>" if colour else f"<td>{text}</td>"

        lines = ["<td colspan='6'><b>Keys</b> (the newest on top)</td>"]
        for row in self.key_rows():
            r, g, b = AXIS_COLOURS[row["axis"]]
            br, bg, bb, _a = colour_rgba(bind_colour(row["bind"]))
            value = f"{row['value']:+.0f}%"
            if row["end_value"] is not None:
                value += f" → {row['end_value']:+.0f}%"
            gap = "" if row["gap_ms"] is None else f"{ms_text(row['gap_ms'])} after the one before"
            dim = "" if row["sent"] else NOT_SENT_COLOUR
            lines.append(
                cell(row["axis"], f"rgb({r},{g},{b})", bold=True)
                + cell(f"Bind&nbsp;#{row['bind'] + 1}", f"rgb({br},{bg},{bb})")
                + cell(html.escape(row["key"]), dim, bold=True)
                + cell(html.escape(key_log_text(row)), dim)
                + cell(value, dim)
                + cell(gap, NOT_SENT_COLOUR)
            )
        while len(lines) < KEY_ROWS + 1:
            lines.append("<td colspan='6'>&nbsp;</td>")
        rows = "".join(f"<tr>{line}</tr>" for line in lines)
        return f"<table cellspacing='0' cellpadding='2'>{rows}</table>"

    def refresh(self):
        """Redraw the graphs, the keys' list and the summary lines."""
        lines = []
        for axis in self.shown_axes():
            r, g, b = AXIS_COLOURS[axis]
            lines.append(
                f"<span style='color:rgb({r},{g},{b});font-weight:700'>{axis}</span>: {summary(*self.view(axis))}"
                + noback_note(self.win.axes[axis].binds, self.win.axes[axis].dead)
            )
        self.summary_label.setText("<br>".join(lines))
        keys = self.keys_html()
        if keys != self._keys_html:  # set only when a key arrived: the rows do not flicker
            self._keys_html = keys
            self.keys_label.setText(keys)
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

    def _screen(self):
        """The screen the Mapper is on, as Windows sees it.

        v108.189: before, Qt was asked. With monitors at different scale
        factors Qt can name the wrong one (see placement.window_screen), and
        the editor was then moved to the top left of that monitor when the
        window opened attached.
        """
        try:
            screen = window_screen(self.win)
        except (AttributeError, RuntimeError, TypeError):
            screen = None
        return screen or QApplication.primaryScreen()

    def _room(self):
        """The available area of the screen the Mapper is on (Qt pixels)."""
        screen = self._screen()
        return screen.availableGeometry() if screen is not None else None

    def _screen_key(self):
        """The name of the screen the Mapper is on: each monitor has its own place for the editor."""
        try:
            return str(self._screen().name() or "")
        except (AttributeError, RuntimeError, TypeError):
            return ""

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
        """Remember the axes, layout, text size, window size, Attach to editor, Legend and where the
        editor goes while the window is open, for next time."""
        floating = self._placed and not self.attached()  # attached, its size is the editor's doing
        self.view_state = {
            "axes": self.shown_axes(),
            "together": self.together(),
            "text_size": self.text_size,
            "size": [self.width(), self.height()] if floating else self.view_state.get("size"),
            "attached": self.attached(),
            "legend": self.legend_btn.isChecked(),
            "editor_spots": dict(self.view_state.get("editor_spots") or {}),
        }
        try:
            update_preference(VIEW_PREFERENCE, self.view_state)
        except OSError:
            pass  # still shown; just not remembered

    # Attached to the editor (v108.187) --------------------------------------
    @staticmethod
    def _rect(rect):
        """A QRect as (x, y, width, height)."""
        return rect.x(), rect.y(), rect.width(), rect.height()

    @staticmethod
    def _frame_margins(widget):
        """(left, top, right, bottom) of a window's frame around its contents; zeros before it is shown."""
        frame, inner = widget.frameGeometry(), widget.geometry()
        return (
            max(0, inner.x() - frame.x()),
            max(0, inner.y() - frame.y()),
            max(0, frame.x() + frame.width() - inner.x() - inner.width()),
            max(0, frame.y() + frame.height() - inner.y() - inner.height()),
        )

    def _dock_margins(self):
        """(this window's frame margins, the pixels of the two frames laid over each other).

        Windows draws a window's left, right and bottom borders invisible but
        for one pixel, so two frames edge to edge look a gap apart; the
        invisible parts are laid over each other. Before this window is first
        shown it has no frame yet: the editor's (the same kind of frame) is
        taken.
        """
        editor = self._frame_margins(self.win)
        own = self._frame_margins(self)
        if not any(own):
            own = editor
        return own, max(0, editor[2] - 1) + max(0, own[0] - 1)

    def _can_dock(self):
        """True when the editor is on screen to be joined to."""
        try:
            return self.win.isVisible() and not self.win.isMinimized()
        except RuntimeError:
            return False

    def _dock_min_width(self):
        """The least width the attached window's frame is given: what its controls need, at least DOCK_MIN_WIDTH."""
        needed = 0
        try:
            self.ensurePolished()
            if self.layout() is not None:
                self.layout().activate()
            needed = int(self.minimumSizeHint().width())
        except (AttributeError, RuntimeError, TypeError):
            pass
        (left, _top, right, _bottom), _overlap = self._dock_margins()
        return max(S(DOCK_MIN_WIDTH), needed + left + right)

    def _editor_geometry(self):
        """The editor's (x, y, width, height): its frame's corner and its own size."""
        return self.win.pos().x(), self.win.pos().y(), self.win.width(), self.win.height()

    def _place_beside(self, area=None):
        """Put the window beside the editor: from its right edge to the screen's right edge,
        over the screen's full height."""
        area = area if area is not None else self._room()
        if area is None:
            return
        (left, top, right, bottom), overlap = self._dock_margins()
        x, y, width, height = history_beside(
            self._rect(self.win.frameGeometry()),
            self._rect(area),
            self._dock_min_width(),
            overlap,
            (max(0, right - 1), max(0, bottom - 1)),
        )
        if (self.pos().x(), self.pos().y()) != (x, y):
            self.move(x, y)
        size = (max(S(200), width - left - right), max(S(150), height - top - bottom))
        if (self.width(), self.height()) != size:
            self.resize(*size)

    def dock(self):
        """Attach the window (v108.188): the editor goes to its place for the time the window is
        open (the top left of its monitor, or where it was last put then), unstretched, and
        the window takes the rest of the monitor at full height. False when it cannot."""
        area = self._room()
        if area is None or not self._can_dock():
            return False
        if self._editor_before is None:
            # Kept, to put the editor back exactly when the window closes.
            self._spot_live = False
            self._editor_before = self._editor_geometry()
            self._open_size = self._editor_before[2:]
            spots = self.view_state.get("editor_spots") or {}
            bleed = max(0, self._frame_margins(self.win)[0] - 1)
            x, y, width, height = editor_spot(
                self._editor_before, self._rect(area), spots.get(self._screen_key()), bleed
            )
            if (width, height) != self._open_size:
                self.win.resize(width, height)
            self.win.move(x, y)
            self._spot_put = (x, y, width, height)
            _note(
                f"Axis History attached on {self._screen_key()}: editor moved from "
                f"{self._editor_before[0]},{self._editor_before[1]} to {x},{y}"
            )
        self._place_beside(area)
        self._spot_live = True
        return True

    def follow_editor(self):
        """The editor moved or changed size while the window is open: stay beside it, and
        remember that place (and a new size) as the editor's for the next time the window opens."""
        if not self._spot_live or not self.attached() or not self.isVisible() or not self._can_dock():
            return
        self._place_beside()
        now = self._editor_geometry()
        if now != self._spot_put:
            self._spot_put = now
            area = self._room()
            if area is not None and self._open_size is not None:
                spots = dict(self.view_state.get("editor_spots") or {})
                spots[self._screen_key()] = spot_to_remember(now, self._rect(area), self._open_size)
                self.view_state["editor_spots"] = spots  # written when the window closes

    def _restore_editor(self):
        """Put the editor back where, and as large as, it was before the window opened."""
        before, self._editor_before = self._editor_before, None
        self._spot_live, self._spot_put = False, None
        if not before:
            return False
        x, y, width, height = before
        try:
            if (self.win.width(), self.win.height()) != (width, height):
                self.win.resize(width, height)
            self.win.move(x, y)
        except RuntimeError:
            return False
        _note(f"Axis History closed: editor back at {x},{y} ({width}x{height})")
        return True

    def _attach_toggled(self, on):
        """Attach to editor was ticked or unticked: join the editor, or become a window of its own."""
        if self.isVisible():
            if on:
                self.dock()
            else:
                self._restore_editor()
                self.place()
                self._placed = True
        self.remember()

    def _settle_dock(self):
        """Once shown, the window has its own frame: put it beside the editor again, exactly."""
        if self.attached() and self.isVisible() and self._spot_live:
            self._place_beside()

    def freeze_from_button(self):
        """The puck's Button 1 was pressed: freeze the graphs, or resume (v108.188)."""
        self.toggle_pause()
        frozen = self.paused_at is not None
        try:
            self.win.statusBar().showMessage(
                f"Axis History frozen by Button {FREEZE_BUTTON}: press it again to resume."
                if frozen
                else f"Axis History resumed by Button {FREEZE_BUTTON}.",
                4000,
            )
        except (AttributeError, RuntimeError):
            pass

    # Controls -------------------------------------------------------------
    def show_axis(self, axis=None):
        """Show the window, with `axis` among the axes shown when given."""
        if axis in AXES and not self.axis_checks[axis].isChecked():
            self.axis_checks[axis].setChecked(True)
        if not self.isVisible():
            if self.attached() and self.dock():
                for delay in DOCK_SETTLE_MS:
                    QTimer.singleShot(delay, self._settle_dock)
            elif not self._placed:
                # Not attached (or the editor is not on screen to join): a window of its own.
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
        """Pause (freeze the view, a copy that outlives the rolling window) or resume."""
        if self.paused_at is None:
            self.paused_at = self.now()
            self._frozen = {}
            for axis, panel in self.win.axes.items():
                live = panel.history
                if live is not None:
                    kept = self._frozen[axis] = AxisHistory(keep_s=live.keep_s, clock=live.clock)
                    kept.samples.extend(live.samples)
                    kept.events.extend(live.events)
                    kept.noback.extend(live.noback)
            self.pause_btn.setText("Resume")
        else:
            self.paused_at = None
            self._frozen = None
            self.pause_btn.setText("Pause")
            self.time_bar.setValue(self.time_bar.maximum())  # back to now
        self.refresh()

    def clear(self):
        """Forget what was recorded on every axis."""
        for panel in self.win.axes.values():
            if panel.history is not None:
                panel.history.clear()
        self.refresh()

    def _export_meta(self, axes, csv_name):
        """What the chart report says about the capture: the profile, the Target, the timing, the note."""
        win = self.win
        profile = getattr(win, "profile_path", None)
        name = os.path.splitext(os.path.basename(str(profile)))[0] if profile else ""
        try:
            name = name or win.profile_display.text().strip()
            mode = str(win.auto_chk.mode())
            state = str(win.target_btn.text())
            target = os.path.basename(str(getattr(win, "target_exe_path", "") or ""))
        except (AttributeError, RuntimeError):
            mode = target = state = ""
        fired_elsewhere = [
            axis for axis in AXES if axis not in axes and any(e[1] != "held" for e in self.capture(axis)[1])
        ]
        return {
            "version": f"{VERSION} ({REVISION_DATE})",
            "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
            "paused": self.paused_at is not None,
            "profile": name,
            "target": target,
            "mode": mode,
            "state": state,
            "timing": (
                f"hysteresis {getattr(win, 'hys_pct', 3)}% · a Hold bind without Min Hold lets go after "
                f"{getattr(win, 'min_hold_ms', 60)} ms, or at once well below its band · "
                f"Hold beyond Max%: {'yes' if getattr(win, 'hold_ignore_max', True) else 'no'} · "
                f"Tap Dwell of a bind without its own: {getattr(win, 'tap_down_ms', 45)} ms · "
                "one sample every 16 ms"
            ),
            "tap_down_ms": getattr(win, "tap_down_ms", 45),
            "note": str(getattr(win, "profile_note", "") or ""),
            "important": bool(getattr(win, "profile_note_important", False)),
            "csv": csv_name,
            "not_shown": ", ".join(fired_elsewhere),
        }

    def export(self):
        """Export the last KEEP_S seconds of the axes shown: a CSV file the user picks and,
        beside it, the chart report (.html). Returns the CSV's path, or None."""
        axes = self.shown_axes()
        if not axes:
            self.win.statusBar().showMessage("Tick an axis to export its history.", 3000)
            return None
        name = "-".join(axes) if len(axes) < len(AXES) else "all"
        default = os.path.join(CONFIG_DIR, f"axis_history_{name}_{time.strftime('%Y%m%d-%H%M%S')}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "Export axis history", default, "CSV files (*.csv)")
        if not path:
            return None
        if not path.lower().endswith(".csv"):
            path += ".csv"
        report_path = path[:-4] + ".html"
        now = self.now()
        series, charts = [], []
        for axis in axes:
            samples, events = self.capture(axis)
            series.append((axis, samples, events))
            panel, history = self.win.axes[axis], self._history(axis)
            charts.append(
                {
                    "axis": axis,
                    "samples": samples,
                    "events": events,
                    "binds": [dict(bind) for bind in panel.binds],
                    "dead": panel.dead,
                    "noback": history.noback_span(now, KEEP_S) if history is not None else [],
                    "now": now,
                    "key_text": _key_text,
                }
            )
        try:
            with open(path, "w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerows(csv_rows(series))
            with open(report_path, "w", encoding="utf-8") as stream:
                stream.write(report_html(self._export_meta(axes, os.path.basename(path)), charts))
        except OSError as exc:
            self.win.statusBar().showMessage(f"✖ Could not export the axis history: {exc}", 5000)
            return None
        self.win.statusBar().showMessage(
            f"✔ Axis history exported: {os.path.basename(path)} and {os.path.basename(report_path)} (the chart)",
            5000,
        )
        return path

    def hide_window(self):
        """Hide the window (recording stopped), remembering its view; the editor and the Target go
        back as they were."""
        self.timer.stop()
        self.remember()
        self._restore_editor()
        if hasattr(self.win, "set_history_target"):
            self.win.set_history_target(False)
        self.hide()

    def closeEvent(self, event):
        """Closing turns Axis History off (v108.156): recording stops and Options > Axis History is unchecked."""
        self.timer.stop()
        if self.paused_at is not None:
            self.toggle_pause()
        self.remember()
        self._restore_editor()
        if axis_history_on(self.win):
            set_axis_history(self.win, False)
        if hasattr(self.win, "set_history_target"):
            self.win.set_history_target(False)
        super().closeEvent(event)


def undock_for_close(win):
    """The editor is closing or hiding: put it back where, and as large as, it was before the
    attached Axis History window moved it aside, so that place is the one saved (v108.187)."""
    window = getattr(win, "_axis_history_window", None)
    if window is not None:
        if window._editor_before is not None:
            window.remember()  # the editor's place beside the window, for next time
        window._restore_editor()


def freeze_button_pressed(win, idx, pressed):
    """True when the puck's button `idx` belongs to Axis History just now (v108.188).

    While the Axis History window is open, Button 1 freezes the graphs
    (press) and resumes them (the next press), whatever key it is bound to,
    and its own key is not sent. With the window closed, False: the button is
    its bind's again.
    """
    if idx != FREEZE_BUTTON:
        return False
    window = getattr(win, "_axis_history_window", None)
    try:
        if window is None or not window.isVisible():
            return False
    except RuntimeError:
        return False
    if pressed:
        window.freeze_from_button()
    return True


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
    from .menu_autoclose import closes_menu

    closes_menu(action)  # v108.178: it opens (or closes) a window
    menu.addAction(action)
    win._axis_history_action = action
    if read_preferences().get(PREFERENCE):
        # Open at the last exit: open again once the editor is shown.
        QTimer.singleShot(REOPEN_MS, lambda: reopen_axis_history(win))
    return action


def reopen_axis_history(win, tries=REOPEN_TRIES):
    """Reopen the window (it was open at the last exit) when the editor is on screen; True when it did.

    v108.189: not before the editor has been put in its place. The start-up
    placement checks that Windows has the editor on its monitor, and moves
    it back when not, up to 750 ms after it is shown; the window, opening
    attached at 600 ms, moved the editor aside in the middle of that. It now
    waits until the placement is done (looking again `tries` times).
    """
    if not win.isVisible() or win.isMinimized() or axis_history_on(win):
        return False  # started in the tray or minimized: it stays off until asked for
    if getattr(win, "_placement_target", None) is not None and tries > 0:
        QTimer.singleShot(REOPEN_AGAIN_MS, lambda: reopen_axis_history(win, tries - 1))
        return False
    set_axis_history(win, True)
    return True
