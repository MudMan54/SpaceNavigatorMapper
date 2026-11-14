"""The macro editor: a bind's steps (v108.141).

Opened by double-clicking a Bind button whose Mode is Macro, by Edit macro… in
Quick Bind, or from the Bind button's right-click menu. Keys are chosen with
the usual key picker. Save hands the steps back; Cancel changes nothing.
"""

from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..macros import MAX_DELAY_MS, MAX_STEPS, normalize_macro, normalize_step, step_text
from .keyboard_popup import KeyboardPopup
from .scaling import S

DEFAULT_DELAY_MS = 100


def pick_keys(parent, initial=None):
    """The key or combo chosen in the key picker, or None."""
    chosen = [initial]

    def take(tokens):
        chosen[0] = list(tokens) if tokens else None

    KeyboardPopup(parent, take, initial=initial).exec_()
    return chosen[0]


class MacroEditor(QDialog):
    def __init__(self, parent, steps, on_save, title="Macro"):
        """Build the macro editor: step list, add, move, delete, Save and Cancel."""
        super().__init__(parent)
        self.setWindowTitle(title)
        self._steps = normalize_macro(steps)
        self._on_save = on_save
        self.saved = None

        layout = QVBoxLayout(self)
        layout.setSpacing(S(10))
        layout.addWidget(
            QLabel(
                "Steps play from the top. A Tap holds its key for the tap time.\n"
                "Keys still held by a Down step are released when the macro ends."
            )
        )
        self.steps_list = QListWidget()
        self.steps_list.setMinimumHeight(S(260))
        self.steps_list.currentRowChanged.connect(self._row_changed)
        self.steps_list.itemDoubleClicked.connect(lambda _item=None: self.change_selected())
        layout.addWidget(self.steps_list)

        keys = QHBoxLayout()
        self.add_buttons = []
        for kind, label, tip in (
            ("tap", "Add Tap…", "Press and release a key or combo."),
            ("down", "Add Down…", "Press a key and keep holding it."),
            ("up", "Add Up…", "Release a key held by a Down step."),
        ):
            button = QPushButton(label)
            button.setToolTip(tip)
            button.clicked.connect(lambda _checked=False, k=kind: self.add_keys(k))
            keys.addWidget(button)
            self.add_buttons.append(button)
        layout.addLayout(keys)

        delay = QHBoxLayout()
        delay.addWidget(QLabel("Delay:"))
        self.delay_ms = QSpinBox()
        self.delay_ms.setRange(0, MAX_DELAY_MS)
        self.delay_ms.setSingleStep(10)
        self.delay_ms.setSuffix(" ms")
        self.delay_ms.setValue(DEFAULT_DELAY_MS)
        self.delay_ms.setToolTip("The wait for Add Delay; with a Delay step selected, its wait.")
        self.delay_ms.valueChanged.connect(self._delay_changed)
        delay.addWidget(self.delay_ms)
        add_delay = QPushButton("Add Delay")
        add_delay.clicked.connect(lambda _checked=False: self.add_step({"delay": self.delay_ms.value()}))
        delay.addWidget(add_delay)
        self.add_buttons.append(add_delay)
        delay.addStretch(1)
        layout.addLayout(delay)

        order = QHBoxLayout()
        for label, action in (
            ("Move Up", lambda: self.move(-1)),
            ("Move Down", lambda: self.move(+1)),
            ("Change…", self.change_selected),
            ("Delete", self.delete_selected),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, a=action: a())
            order.addWidget(button)
        layout.addLayout(order)

        foot = QHBoxLayout()
        self.count_label = QLabel("")
        foot.addWidget(self.count_label)
        foot.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(lambda _checked=False: self.reject())
        save = QPushButton("Save")
        save.clicked.connect(lambda _checked=False: self.save())
        foot.addWidget(cancel)
        foot.addWidget(save)
        layout.addLayout(foot)

        self.setStyleSheet(
            "QDialog{background-color:#111827;color:#e2e8f0;}"
            "QListWidget{background:#0f172a;color:#e5e7eb;border:1px solid #334155;}"
            "QListWidget::item:selected{background:#374151;}"
        )
        self._show_steps(len(self._steps) - 1)

    # ---------- the steps ----------
    def steps(self):
        """The edited steps, normalized."""
        return [dict(step) for step in self._steps]

    def _show_steps(self, select=-1):
        """Refill the step list and the step counter."""
        self.steps_list.blockSignals(True)
        self.steps_list.clear()
        for number, step in enumerate(self._steps, 1):
            self.steps_list.addItem(f"{number}. {step_text(step)}")
        self.steps_list.blockSignals(False)
        self.steps_list.setCurrentRow(select)
        full = len(self._steps) >= MAX_STEPS
        for button in self.add_buttons:
            button.setEnabled(not full)
        self.count_label.setText(f"{len(self._steps)} of {MAX_STEPS} steps")

    def _row(self):
        """Index of the selected step, or -1."""
        row = self.steps_list.currentRow()
        return row if 0 <= row < len(self._steps) else -1

    def add_step(self, step):
        """Insert `step` after the selected step (at the end with none selected)."""
        step = normalize_step(step)
        if step is None or len(self._steps) >= MAX_STEPS:
            return False
        at = self._row() + 1 if self._row() >= 0 else len(self._steps)
        self._steps.insert(at, step)
        self._show_steps(at)
        return True

    def add_keys(self, kind):
        """Add a Tap, Down or Up step with keys from the key picker."""
        tokens = pick_keys(self)
        if tokens:
            self.add_step({kind: tokens})

    def move(self, delta):
        """Move the selected step up or down."""
        row = self._row()
        to = row + delta
        if row < 0 or not 0 <= to < len(self._steps):
            return
        self._steps[row], self._steps[to] = self._steps[to], self._steps[row]
        self._show_steps(to)

    def delete_selected(self):
        """Delete the selected step."""
        row = self._row()
        if row < 0:
            return
        del self._steps[row]
        self._show_steps(min(row, len(self._steps) - 1))

    def change_selected(self):
        """A key step: pick its keys again. A Delay step: its wait is the Delay box."""
        row = self._row()
        if row < 0:
            return
        step = self._steps[row]
        if "delay" in step:
            step["delay"] = self.delay_ms.value()
            self._show_steps(row)
            return
        kind = next(iter(step))
        tokens = pick_keys(self, initial=step[kind])
        if tokens:
            self._steps[row] = {kind: tokens}
            self._show_steps(row)

    def _row_changed(self, row):
        """Show the selected Delay step's milliseconds."""
        if 0 <= row < len(self._steps) and "delay" in self._steps[row]:
            self.delay_ms.blockSignals(True)
            self.delay_ms.setValue(self._steps[row]["delay"])
            self.delay_ms.blockSignals(False)

    def _delay_changed(self, value):
        """Store a new duration in the selected Delay step."""
        row = self._row()
        if row >= 0 and "delay" in self._steps[row]:
            self._steps[row]["delay"] = int(value)
            self._show_steps(row)

    def save(self):
        """Accept the edited steps and close."""
        self.saved = self.steps()
        self._on_save(self.saved)
        self.accept()
