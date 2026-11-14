"""One axis panel: six binds, the Quick Bind editor, NoBack per bind, Tick and Macro modes."""

import time
from functools import partial

from PyQt5 import QtWidgets
from PyQt5.QtCore import QEvent, QPoint, Qt, QTimer
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..axis_history import DOWN, HELD, MACRO, NOBACK_UP, TAP, UP, unsent
from ..keyboard_io import combo_to_text, send_combo
from ..macros import MacroRun, normalize_macro, step_text
from ..settings import BINDS_PER_AXIS
from .keyboard_popup import KeyboardPopup
from .profile_marquee import ScrollingLineEdit
from .scaling import (
    S,
    button_qss,
    fit_axis_combo_width,
    fit_axis_comment_field,
    set_readable_height,
    set_readable_square,
)
from .taps import MIN_UP_MS, TapSender, repeat_interval_ms
from .title_effect import BindDirSweep, NoBackSweep
from .widgets import BindButton

TICK_MODE = "Tick"
MACRO_MODE = "Macro"  # v108.141: the bind plays its macro steps
MODES = ["Hold", "Press/Release", "Release-only", "Press/Repeat", TICK_MODE, MACRO_MODE]


def bind_has_output(bind):
    """True when the bind has something to send: its macro in Macro mode, else its key."""
    if bind.get("mode") == MACRO_MODE:
        return bool(bind.get("macro"))
    return bool(bind.get("combo"))


# Greyed-out Quick Bind controls (the mode does not use them). v108.172: fainter,
# see-through, just readable on the panel (#0f172a): a label's text about 3:1
# against it (was 3.7:1); a button's face only a little lighter than the
# panel (1.5:1, was 2.4:1) and its sign about 2.7:1 against the face (was 3:1).
GHOST_STYLE_LABEL = "color:rgba(148,163,184,0.55);"
GHOST_STYLE_BUTTON = (
    "background-color:rgba(75,85,99,0.5); color:rgba(156,163,175,0.6);"
    " border:1px solid rgba(75,85,99,0.7); border-radius:4px;"
)


def own_style(widget_class, declarations):
    """`declarations` for the widget itself only: ".QPushButton { ... }".

    v108.169: a widget's style sheet without a selector also styles the tip
    shown for it (Qt styles a tip with the style sheet of its widget), so a
    − / + button's tip had its 20 px bold sign size and its white text,
    unreadable on the tip. The class selector (with its dot) matches only
    that exact class, not the tip's label.
    """
    return f".{widget_class} {{ {declarations} }}"


def _tick_dir_ok(value, bind_dir):
    """True when the axis value is on a side the Tick bind's direction allows (not at centre)."""
    if bind_dir == "Full":
        return value != 0
    if bind_dir == "Plus":
        return value > 0
    if bind_dir == "Minus":
        return value < 0
    return False


def _set_ghost(widget, ghost, is_button=False):
    """Grey out (or restore) a Quick Bind control that the mode does not use."""
    if not hasattr(widget, "_tick_ui_orig_style"):  # its own style, kept the first time
        widget._tick_ui_orig_style = widget.styleSheet()
    widget.setEnabled(not ghost)
    if ghost:
        # v108.168: a − / + keeps its sign's size (and no padding) when greyed out;
        # before, the ghost style put back the interface's small text size.
        glyph = getattr(widget, "_spnav_glyph_style", "")
        kind = type(widget).__name__
        widget.setStyleSheet(
            own_style(kind, (GHOST_STYLE_BUTTON + glyph) if is_button else GHOST_STYLE_LABEL)
        )
    else:
        widget.setStyleSheet(widget._tick_ui_orig_style)


# NoBack is set per bind and stored per axis side (right-click a Bind button):
# "noback_plus" for the + side, "noback_minus" for the - side.
NOBACK_KEYS = {"+": "noback_plus", "-": "noback_minus"}
# v108.161: the menu names NoBack by the direction the axis moves on the way
# back, the opposite of the bind's Bind Dir: a POS bind has only "NoBack -"
# (its + side), a NEG bind only "NoBack +" (its - side), a FULL bind both.
RETURN_SIGN = {"+": "-", "-": "+"}  # an axis side -> the direction of the way back from it
NOBACK_TIPS = {
    "+": "On the way back from the + side (the axis moving -): once a higher band was reached, "
    "this bind stays quiet until the axis centres, drops below every band or crosses to the other side.",
    "-": "On the way back from the - side (the axis moving +): once a higher band was reached, "
    "this bind stays quiet until the axis centres, drops below every band or crosses to the other side.",
}


def _covers(direction, side):
    """True when a bind with `direction` works on axis side `side` ("+" or "-")."""
    return direction == "Full" or direction == ("Plus" if side == "+" else "Minus")


def bind_noback_from(source, cfg):
    """A loaded bind's (NoBack +, NoBack -).

    Profiles from v108.137 and older had NoBack + / NoBack - for the whole
    axis side ("suppress_plus" / "suppress_minus"): every bind working on a
    side that had it gets NoBack for that side, so they behave as before.
    """
    source = source if isinstance(source, dict) else {}
    if "noback_plus" in source or "noback_minus" in source:
        return bool(source.get("noback_plus")), bool(source.get("noback_minus"))
    direction = source.get("direction")
    return (
        bool(cfg.get("suppress_plus") and _covers(direction, "+")),
        bool(cfg.get("suppress_minus") and _covers(direction, "-")),
    )


def noback_on(bind, side):
    """True when `bind` has NoBack on axis side `side` and works on that side.

    v108.162: never for a Tick bind. A Tick taps only on its way out, so NoBack
    has next to nothing to hold, and its menu no longer offers it. A NoBack
    set before stays in the profile, and works again if the bind's mode is
    changed back from Tick. A Tick still counts as a band for other binds'
    NoBack.
    """
    if bind.get("mode") == TICK_MODE:
        return False
    return bool(side and bind.get(NOBACK_KEYS[side]) and _covers(bind.get("direction"), side))


def fit_noback_to_direction(bind):
    """Keep NoBack on the side(s) the bind has (v108.161).

    A POS or NEG bind can only have NoBack for the way back from its own
    side. NoBack set for the side it does not have (an older profile's
    "NoBack -" on a POS bind, or a Bind Dir changed from POS to NEG) moves to
    its own side; a FULL bind keeps both; a bind without Bind Dir keeps what
    it has until it gets one.
    """
    direction = bind.get("direction")
    if direction not in ("Plus", "Minus"):
        return bind
    own, other = ("+", "-") if direction == "Plus" else ("-", "+")
    bind[NOBACK_KEYS[own]] = bool(bind.get(NOBACK_KEYS[own]) or bind.get(NOBACK_KEYS[other]))
    bind[NOBACK_KEYS[other]] = False
    return bind


# The Bind Dir line: NEG sweeps left, POS right, FULL both ways; none for None.
DIRECTION_SIDES = {"Minus": "-", "Plus": "+", "Full": "+-"}


def chosen_noback_sides(bind):
    """The axis sides with NoBack on that the bind works on."""
    return "".join(side for side in "+-" if noback_on(bind, side))


def noback_names(bind):
    """The bind's NoBack as its menu names it: the direction of the way back ("-" for a POS bind)."""
    return "".join(RETURN_SIGN[side] for side in chosen_noback_sides(bind))


def _read_dead_value(src, fallback):
    """Per-bind dead zone from profile data, accepting older field names."""
    for k in ("dead", "deadzone", "dzone", "dzone_percent", "dz"):
        if k in src:
            try:
                return int(src[k])
            except (TypeError, ValueError):
                continue
    return int(fallback)


def _status_ignored(_text):
    """Key-sending status messages are not shown."""


# v108.165: hover tips for Quick Bind.
QUICK_BIND_TIPS = {
    "dir": (
        "Bind Dir: the side of the axis the selected bind works on.\n"
        "POS (+) the positive side, NEG (-) the negative side, Full both; [None]: it does nothing."
    ),
    "mode": (
        "Mode: what the selected bind sends in its band.\n"
        "Hold: the key is held while the axis is in the band.\n"
        "Press/Release: one tap on entering the band.\n"
        "Release-only: the key-up only, on entering the band.\n"
        "Press/Repeat: taps again every 'Repeat every' ms while in the band.\n"
        "Tick: one tap each time the axis crosses Tick% going out.\n"
        "Macro: plays the bind's macro."
    ),
    "min": (
        "Min%: where the selected bind's band starts, from 0 to 100% of the axis, after its DZone.\n"
        "Tick%: in Tick mode, where the bind taps."
    ),
    "max": "Max%: where the selected bind's band ends (100: the end of the axis). Not used in Tick mode.",
    "dead": (
        "DZone: the selected bind's own dead zone, in %. Its band starts at DZone + Min% "
        "(at most 100%). Not used in Tick mode."
    ),
    "down": "Lower it by 1. Hold to keep lowering.",
    "up": "Raise it by 1. Hold to keep raising.",
    "tap": (
        "Tap Dwell: how long each tap of the selected bind holds its key down, 0 to 200 ms "
        "(45 by default). Some games miss taps shorter than about 30 ms.\n"
        "Used by Press/Release, Press/Repeat, Tick and a macro's Tap steps; not by Hold or Release-only.\n"
        "Not the same as Repeat every, the time from one tap to the next: after each tap the key "
        "stays up at least 30 ms, so Press/Repeat taps no sooner than Tap Dwell + 30 ms."
    ),
    "repeat": (
        "Repeat every: the time from one tap to the next (start to start) while the axis stays in the band.\n"
        "Never less than the Tap Dwell plus 30 ms: the key must be up long enough for the game to see it released."
    ),
    "tap down": "5 ms shorter. Hold to keep shortening.",
    "tap up": "5 ms longer. Hold to keep lengthening.",
}

# v108.166: Tap Dwell, per bind: how long a tap holds its key down.
TAP_MS_DEFAULT, TAP_MS_MIN, TAP_MS_MAX, TAP_MS_STEP = 45, 0, 200, 5
TAPPING_MODES = ("Press/Release", "Press/Repeat", TICK_MODE, MACRO_MODE)


def clamp_tap_ms(value, default=TAP_MS_DEFAULT):
    """A Tap Dwell in ms, 0 to 200 (`default` for one that is not a number)."""
    try:
        return max(TAP_MS_MIN, min(TAP_MS_MAX, int(value)))
    except (TypeError, ValueError):
        return max(TAP_MS_MIN, min(TAP_MS_MAX, int(default)))


def tap_text(ms):
    """'Tap Dwell:  45ms', the width of three digits."""
    return f"Tap Dwell: {int(ms):>3d}ms"


def give_tip(widget, tip):
    """Set `widget`'s hover tip and keep it to restore after a Tick-mode note."""
    widget._spnav_tip = tip
    widget.setToolTip(tip)


# v108.165: the − / + glyphs of the Min%, Max% and DZone buttons, as a share
# of the button's side, so they grow with the Display size (before, they were
# the interface's text size: small in a large button).
STEP_GLYPH_SHARE = 0.72
STEP_COLOURS = {"−": "#b91c1c", "+": "#16a34a"}


def step_glyph_px(side):
    """The pixel size of a − / + glyph in a button `side` pixels square."""
    return max(12, int(round(side * STEP_GLYPH_SHARE)))


def step_buttons():
    """The red − and green + buttons beside Min%, Max% and DZone."""
    out = []
    for glyph, colour in STEP_COLOURS.items():
        button = QPushButton(glyph)  # U+2212: as wide as + and centred on it
        set_readable_square(button, S(40), S(40))
        side = min(button.minimumWidth(), button.minimumHeight())  # its fixed size
        button._spnav_fixed_height = button.minimumHeight()  # a larger glyph must not grow it
        button._spnav_glyph_style = f"padding:0px;font-weight:700;font-size:{step_glyph_px(side)}px;"
        button.setStyleSheet(
            own_style("QPushButton", f"background-color:{colour};color:#fff;" + button._spnav_glyph_style)
        )
        out.append(button)
    return tuple(out)


class AxisPanel(QGroupBox):
    # The last sample's side ("+", "-" or None) and its distance from centre
    # in percent: a Tick fires when the axis crosses Tick% moving outward.
    _last_side = None
    _last_pct = 0.0
    # Options > Axis History: an AxisHistory recording this axis, else None.
    history = None
    _raw_val = 0.0

    def __init__(self, name, mainwin):
        """Create an axis panel with six binds and its Quick Bind editor."""
        super().__init__("")
        self.axis_name = name
        self.mainwin = mainwin
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        self._status_cb = _status_ignored
        self._reset_noback()
        self.dead = 5
        self.binds = [
            {
                "direction": None,
                "combo": None,
                "mode": "Hold",
                "min": 0,
                "max": 100,
                "comment": "",
                "active": False,
                "last_tap": 0.0,
                "repeat_ms": 60,
                "tap_ms": TAP_MS_DEFAULT,
                "last_on_ts": 0.0,
                "dead": self.dead,
                "noback_plus": False,
                "noback_minus": False,
                "macro": [],
                "macro_repeat": False,
            }
            for _ in range(BINDS_PER_AXIS)
        ]
        self.selected_index = 0
        self._last_labels = [None] * BINDS_PER_AXIS
        self._last_in_range = [False] * BINDS_PER_AXIS
        self._last_selected = -1

        # Motion flash timers
        self._motion_flash_on = False
        self._motion_timer = QTimer(self)
        self._motion_timer.setInterval(120)
        self._motion_timer.timeout.connect(self._toggle_motion_flash)
        self._motion_idle = QTimer(self)
        self._motion_idle.setSingleShot(True)
        self._motion_idle.setInterval(220)
        self._motion_idle.timeout.connect(self._stop_motion_flash)

        self._style_gray = button_qss(
            "QPushButton { background-color:#374151; color:#e5e7eb; border-radius:4px; border:1px solid #1f2937; padding:5px; text-align:center; }"
        )
        self._style_bound_red = button_qss(
            "QPushButton { background-color:#b91c1c; color:#fff; border-radius:4px; border:1px solid #7f1d1d; padding:5px; text-align:center; }"
        )
        self._style_selected = button_qss(
            "QPushButton { background-color:#111827; color:#e5e7eb; border-radius:4px; border:1px solid #4b5563; padding:5px; font-weight:700; text-align:center; }"
        )
        self._build_ui()
        self._load_selected_into_qb()

    def eventFilter(self, watched, event):
        """Re-align the bind rows after the panel is shown, moved or resized."""
        if event.type() in (QEvent.Show, QEvent.Move, QEvent.Resize, QEvent.LayoutRequest):
            if not self._align_pending:
                self._align_pending = True
                QTimer.singleShot(0, self._align_bind_rows)
        return super().eventFilter(watched, event)

    def _align_bind_rows(self):
        """Make the bind rows end where the Quick Bind Mode box ends."""
        self._align_pending = False
        if not self.isVisible() or not self.qb_mode.isVisible():
            return
        # The Mode combo is nested in Quick Bind. Compare both edges in
        # axis-panel coordinates, including the group box's content margins.
        end = self.qb_mode.mapTo(self, QPoint(self.qb_mode.width(), 0)).x()
        start = self.bind_rows.mapTo(self, QPoint(0, 0)).x()
        width = max(1, end - start)
        if self.bind_rows.maximumWidth() != width:
            self.bind_rows.setFixedWidth(width)

    def _build_ui(self):
        """Lay out the Bind buttons, comments and the Quick Bind editor."""
        v = QVBoxLayout(self)
        v.setContentsMargins(S(8), S(20), S(8), S(16))
        v.setSpacing(S(16))
        # The axis and its value are in the border, like Quick Bind's title
        # (v108.139); Reset is in each Bind button's right-click menu.
        self._show_value(0.0)
        # All six comments share one right-hand grid edge.
        self.bind_rows = QWidget(self)
        grid = QtWidgets.QGridLayout(self.bind_rows)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(S(12))
        grid.setVerticalSpacing(S(16))
        group_row = QHBoxLayout()
        group_row.addWidget(self.bind_rows)
        group_row.addStretch(1)
        v.addLayout(group_row)

        self.slot_btns = []
        self.slot_comments = []
        for i in range(BINDS_PER_AXIS):
            btn = BindButton(f"Bind #{i + 1}")
            set_readable_height(btn, S(50))
            btn.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
            btn.setStyleSheet(self._style_gray)
            btn.clicked.connect(partial(self._select_slot, i))
            btn.doubleClicked.connect(partial(self._open_picker_for, i))
            btn.rightClicked.connect(partial(self._show_bind_menu, i))
            grid.addWidget(btn, i, 0, Qt.AlignLeft)
            cmt = ScrollingLineEdit()  # long comments scroll, like the profile name
            cmt.setPlaceholderText(f"comment for bind #{i + 1}")
            cmt.setMaxLength(60)
            cmt.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            cmt.textChanged.connect(lambda txt, ii=i: self._on_comment_change(ii, txt))
            cmt.textEdited.connect(self._edited)  # typed, not set by a load
            # The display field is narrower, but hovering reveals all saved text.
            cmt.textChanged.connect(cmt.setToolTip)

            # All 36 axis comments use a narrower measured column,
            # including Bind #1/#2. Keep the whole string; QLineEdit scrolls.
            fit_axis_comment_field(cmt, S(50), preferred_chars=26, min_chars=1)
            cmt.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            cmt.setMinimumWidth(1)
            cmt.setMaximumWidth(16777215)
            grid.addWidget(cmt, i, 1)  # the same row as its Bind button
            self.slot_btns.append(btn)
            self.slot_comments.append(cmt)
        qb_group = QGroupBox("Quick Bind (edits selected bind)")
        qv = QVBoxLayout(qb_group)
        qv.setContentsMargins(S(8), S(44), S(8), S(16))
        qv.setSpacing(S(14))
        # Quick Bind: Bind Dir and Mode, then Min% [-] [+], then
        # Max% [-] [+] with DZone% [-] [+].

        # Bind Dir dropdown
        self.qb_dir = QComboBox()
        self.qb_dir.addItem("[None]", None)
        self.qb_dir.addItem("POS (+)", "Plus")
        self.qb_dir.addItem("NEG (-)", "Minus")
        self.qb_dir.addItem("Full", "Full")
        set_readable_height(self.qb_dir, S(46))
        self.qb_dir.currentIndexChanged.connect(self._qb_changed)
        self.qb_dir.setStyleSheet("QComboBox { padding-left: 2px; padding-right: 2px; }")
        fit_axis_combo_width(self.qb_dir)
        self.qb_dir.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        # Mode dropdown
        self.qb_mode = QComboBox()
        self.qb_mode.addItems(MODES)
        set_readable_height(self.qb_mode, S(46))
        self.qb_mode.currentTextChanged.connect(self._qb_changed)
        self.qb_mode.setStyleSheet("QComboBox { padding-left: 2px; padding-right: 2px; }")
        fit_axis_combo_width(self.qb_mode)
        self._align_pending = False
        for widget in (self, qb_group, self.qb_mode, self.bind_rows):
            widget.installEventFilter(self)

        self.qb_mode.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # Top line: Bind Dir and Mode.
        qb_row0 = QHBoxLayout()
        qb_row0.setSpacing(S(8))
        qv.insertLayout(0, qb_row0)
        dir_label, mode_label = QLabel("Bind Dir:"), QLabel("Mode:")
        for widget in (dir_label, self.qb_dir):
            give_tip(widget, QUICK_BIND_TIPS["dir"])
        for widget in (mode_label, self.qb_mode):
            give_tip(widget, QUICK_BIND_TIPS["mode"])
        qb_row0.addWidget(dir_label)
        qb_row0.addWidget(self.qb_dir)
        qb_row0.addSpacing(S(2))
        qb_row0.addWidget(mode_label)
        qb_row0.addWidget(self.qb_mode)
        qb_row0.addStretch(1)

        # Deadzone controls
        self.dead_dec, self.dead_inc = step_buttons()
        self.dead_dec.setAutoRepeat(True)
        self.dead_dec.setAutoRepeatDelay(200)
        self.dead_dec.setAutoRepeatInterval(60)
        self.dead_dec.clicked.connect(lambda: self._change_dead(-1))
        self.dead_inc.setAutoRepeat(True)
        self.dead_inc.setAutoRepeatDelay(200)
        self.dead_inc.setAutoRepeatInterval(60)
        self.dead_inc.clicked.connect(lambda: self._change_dead(+1))
        self.dead_lbl = QLabel(f"DZone: {int(self.binds[self.selected_index].get('dead', self.dead)):>3d}%")

        # Tap Dwell controls (v108.166), above DZone: 5 ms a step.
        self.tap_dec, self.tap_inc = step_buttons()
        for button, delta in ((self.tap_dec, -TAP_MS_STEP), (self.tap_inc, TAP_MS_STEP)):
            button.setAutoRepeat(True)
            button.setAutoRepeatDelay(200)
            button.setAutoRepeatInterval(60)
            button.clicked.connect(lambda _checked=False, d=delta: self._change_tap(d))
        self.tap_lbl = QLabel(tap_text(self.binds[self.selected_index].get("tap_ms", TAP_MS_DEFAULT)))

        # Min controls
        self.min_dec, self.min_inc = step_buttons()
        self.min_dec.setAutoRepeat(True)
        self.min_dec.setAutoRepeatDelay(200)
        self.min_dec.setAutoRepeatInterval(60)
        self.min_dec.clicked.connect(lambda: self._change_min(-1))
        self.min_inc.setAutoRepeat(True)
        self.min_inc.setAutoRepeatDelay(200)
        self.min_inc.setAutoRepeatInterval(60)
        self.min_inc.clicked.connect(lambda: self._change_min(+1))
        self.min_text = QLabel("Min%:")
        self.min_text.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.min_val = QLabel("0")
        self.min_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Max controls
        self.max_dec, self.max_inc = step_buttons()
        self.max_dec.setAutoRepeat(True)
        self.max_dec.setAutoRepeatDelay(200)
        self.max_dec.setAutoRepeatInterval(60)
        self.max_dec.clicked.connect(lambda: self._change_max(-1))
        self.max_inc.setAutoRepeat(True)
        self.max_inc.setAutoRepeatDelay(200)
        self.max_inc.setAutoRepeatInterval(60)
        self.max_inc.clicked.connect(lambda: self._change_max(+1))
        self.max_text = QLabel("Max%:")
        self.max_text.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.max_val = QLabel("100")
        self.max_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        for key, widgets in (
            ("min", (self.min_text, self.min_val)),
            ("max", (self.max_text, self.max_val)),
            ("dead", (self.dead_lbl,)),
            ("tap", (self.tap_lbl,)),
        ):
            for widget in widgets:
                give_tip(widget, QUICK_BIND_TIPS[key])
        for down, up in (
            (self.min_dec, self.min_inc),
            (self.max_dec, self.max_inc),
            (self.dead_dec, self.dead_inc),
        ):
            give_tip(down, QUICK_BIND_TIPS["down"])
            give_tip(up, QUICK_BIND_TIPS["up"])
        give_tip(self.tap_dec, QUICK_BIND_TIPS["tap down"])
        give_tip(self.tap_inc, QUICK_BIND_TIPS["tap up"])

        # Min and Max values share a width so their [-]/[+] line up.
        width = max(self.min_val.sizeHint().width(), self.max_val.sizeHint().width())
        self.min_val.setFixedWidth(width)
        self.max_val.setFixedWidth(width)

        # A grid keeps the Min% and Max% columns (label and value) aligned.
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(S(12))
        grid.setVerticalSpacing(S(8))
        grid.setContentsMargins(0, 0, 0, 0)

        # Row 0: Min
        grid.addWidget(self.min_text, 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.min_val, 0, 1, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.min_dec, 0, 2)
        grid.addWidget(self.min_inc, 0, 3)
        grid.addItem(
            QtWidgets.QSpacerItem(S(12), 1, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum),
            0,
            4,
        )
        # Tap Dwell, above DZone (v108.166).
        grid.addWidget(self.tap_lbl, 0, 5, Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(self.tap_dec, 0, 6)
        grid.addWidget(self.tap_inc, 0, 7)
        grid.setColumnStretch(9, 1)

        # Row 1: Max + DZone
        grid.addWidget(self.max_text, 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.max_val, 1, 1, Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(self.max_dec, 1, 2)
        grid.addWidget(self.max_inc, 1, 3)
        grid.addItem(
            QtWidgets.QSpacerItem(S(12), 1, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum),
            1,
            4,
        )
        grid.addWidget(self.dead_lbl, 1, 5, Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(self.dead_dec, 1, 6)
        grid.addWidget(self.dead_inc, 1, 7)
        grid.setColumnStretch(9, 1)

        qv.addLayout(grid)
        # Mode = Macro: play the steps once per band entry, or repeat them.
        self.macro_group = QWidget()
        macro_layout = QHBoxLayout(self.macro_group)
        macro_layout.setSpacing(S(12))
        macro_layout.addWidget(QLabel("Play:"))
        self.qb_play = QComboBox()
        self.qb_play.addItems(["Once", "Repeat"])
        set_readable_height(self.qb_play, S(46))
        self.qb_play.setToolTip(
            "Once: the macro plays each time the axis enters this bind's band.\n"
            "Repeat: it plays again every 'Repeat every' ms while the axis stays there."
        )
        self.qb_play.currentTextChanged.connect(self._on_qb_play_change)
        macro_layout.addWidget(self.qb_play)
        self.macro_edit_btn = QPushButton("Edit macro…")
        set_readable_height(self.macro_edit_btn, S(46))
        self.macro_edit_btn.clicked.connect(lambda: self._open_macro_editor(self.selected_index))
        macro_layout.addWidget(self.macro_edit_btn)
        macro_layout.addStretch(1)
        qv.addWidget(self.macro_group)
        self.macro_group.setVisible(False)
        self.repeat_group = QWidget()
        repeat_layout = QHBoxLayout(self.repeat_group)
        repeat_layout.setSpacing(S(12))
        repeat_label = QLabel("Repeat every:")
        give_tip(repeat_label, QUICK_BIND_TIPS["repeat"])
        repeat_layout.addWidget(repeat_label)
        self.qb_repeat = QComboBox()
        give_tip(self.qb_repeat, QUICK_BIND_TIPS["repeat"])
        self.qb_repeat.addItems([str(i) for i in range(10, 2001, 10)])
        set_readable_height(self.qb_repeat, S(46))
        self.qb_repeat.currentTextChanged.connect(self._on_qb_repeat_change)
        repeat_layout.addWidget(self.qb_repeat)
        repeat_layout.addWidget(QLabel("ms"))
        # v108.167: what Repeat every becomes when the Tap Dwell leaves too little time.
        self.repeat_note = QLabel("")
        self.repeat_note.setStyleSheet(own_style("QLabel", "color:#fbbf24;"))
        repeat_layout.addWidget(self.repeat_note)
        repeat_layout.addStretch(1)
        qv.addWidget(self.repeat_group)
        self.repeat_group.setVisible(False)
        v.addWidget(qb_group)

    def _change_dead(self, delta):
        """Step the selected bind's DZone% up or down."""
        self._edited()
        b = self.binds[self.selected_index]
        b["dead"] = max(0, min(100, int(b.get("dead", self.dead)) + int(delta)))
        self.dead_lbl.setText(f"DZone: {int(b['dead']):>3d}%")
        self._refresh_slot_btn(self.selected_index, force=True)

    def _change_tap(self, delta):
        """Step the selected bind's Tap Dwell (0-200 ms)."""
        self._edited()
        b = self.binds[self.selected_index]
        b["tap_ms"] = clamp_tap_ms(int(b.get("tap_ms", self._profile_tap_ms())) + int(delta))
        self.tap_lbl.setText(tap_text(b["tap_ms"]))
        self._refresh_repeat_note()

    def _bind_tap_ms(self, b):
        """A bind's Tap Dwell (the profile's when it has none)."""
        return clamp_tap_ms(b.get("tap_ms", self._profile_tap_ms()), self._profile_tap_ms())

    def _profile_tap_ms(self):
        """The profile's Tap Dwell: the one a bind without its own gets."""
        return clamp_tap_ms(getattr(self.mainwin, "tap_down_ms", TAP_MS_DEFAULT))

    def _change_max(self, delta):
        """Step the selected bind's Max% (0-100)."""
        self._edited()
        b = self.binds[self.selected_index]
        b["max"] = max(0, min(100, int(b["max"]) + delta))
        if b["max"] < b["min"]:
            b["min"] = b["max"]
        self.min_val.setText(str(int(b['min'])))
        self.max_val.setText(f"{int(b['max']):>3d}")
        self._refresh_slot_btn(self.selected_index, force=True)

    def _refresh_slot_btn(self, idx, in_range=False, force=False):
        """Update a Bind button's label, colours and Bind Dir/NoBack lines."""
        if self._dry:
            return  # a dry run shows nothing; the bind's own pass already did
        b = self.binds[idx]
        is_macro = b.get("mode") == MACRO_MODE
        if is_macro:
            label = f"Macro ({len(b.get('macro') or [])})" if b.get("macro") else f"Bind #{idx + 1}"
        else:
            label = combo_to_text(b["combo"]) if b["combo"] else f"Bind #{idx + 1}"
        selected = idx == self.selected_index
        if not (
            force
            or label != self._last_labels[idx]
            or in_range != self._last_in_range[idx]
            or selected != (self._last_selected == idx)
        ):
            return
        if is_macro:
            steps = [step_text(step) for step in (b.get("macro") or [])]
            if steps:
                shown = steps[:8] + ([f"… {len(steps) - 8} more"] if len(steps) > 8 else [])
                lines = [f"Macro, plays {'repeatedly' if b.get('macro_repeat') else 'once'}:"] + shown
            else:
                lines = ["Double Click to make the macro"]
        else:
            lines = [] if b["combo"] else ["Double Click to Set"]
        for sign in noback_names(b):
            lines.append(f"NoBack {sign} on (quiet on the way back)")
        # v108.162: a Tick bind's menu has no NoBack.
        tick = b.get("mode") == TICK_MODE
        lines.append(
            "Right-click: Edit macro, Reset axis" if tick else "Right-click: NoBack, Edit macro, Reset axis"
        )
        self.slot_btns[idx].setToolTip("\n".join(lines))
        self.slot_btns[idx].setText(label)
        self.slot_btns[idx].setStyleSheet(self._slot_style(idx, selected))
        self._refresh_bind_lines(idx)
        self._last_labels[idx] = label
        self._last_in_range[idx] = in_range
        if selected:
            self._last_selected = idx

    def _slot_style(self, idx, selected=None):
        """The Bind button's stylesheet: selected, bound or empty."""
        if selected is None:
            selected = idx == self.selected_index
        return (
            self._style_selected
            if selected
            else (self._style_bound_red if bind_has_output(self.binds[idx]) else self._style_gray)
        )

    def _on_qb_play_change(self, text):
        """Store the Macro Play choice (Once or Repeat)."""
        self._edited()
        try:
            self.binds[self.selected_index]["macro_repeat"] = text == "Repeat"
        except (IndexError, AttributeError):
            return
        self._sync_mode_groups()

    def _sync_mode_groups(self):
        """Show the Play row for Macro, and the repeat row for Press/Repeat or a repeating macro."""
        try:
            b = self.binds[self.selected_index]
            mode = b.get("mode", "Hold")
            self.macro_group.setVisible(mode == MACRO_MODE)
            self.repeat_group.setVisible(
                mode == "Press/Repeat" or (mode == MACRO_MODE and bool(b.get("macro_repeat")))
            )
        except (IndexError, AttributeError):
            pass

    def _on_qb_repeat_change(self, text):
        """Store the Repeat every (ms) choice."""
        self._edited()
        try:
            self.binds[self.selected_index]["repeat_ms"] = int(text)
        except ValueError:
            pass
        self._refresh_repeat_note()

    def _refresh_repeat_note(self):
        """v108.167: say so when the Tap Dwell makes Press/Repeat tap less often than Repeat every."""
        note = getattr(self, "repeat_note", None)
        if note is None:
            return
        b = self.binds[self.selected_index]
        text = tip = ""
        if b.get("mode") == "Press/Repeat":
            repeat_ms, dwell = int(b.get("repeat_ms", 100)), self._bind_tap_ms(b)
            every = repeat_interval_ms(repeat_ms, dwell)
            if every > repeat_ms:
                text = f"→ {every} ms"
                tip = (
                    f"Taps every {every} ms, not {repeat_ms}: each tap holds its key {dwell} ms (Tap Dwell), "
                    f"then the key stays up at least {MIN_UP_MS} ms so the game sees it released.\n"
                    f"For faster taps, shorten the Tap Dwell."
                )
        note.setText(text)
        note.setToolTip(tip)

    def _open_picker_for(self, idx):
        """Double-click: open the key picker, or the macro editor in Macro mode."""
        if self.binds[idx].get("mode") == MACRO_MODE:
            return self._open_macro_editor(idx)
        self.selected_index = idx
        self._load_selected_into_qb()
        btn = self.slot_btns[idx]
        orig = btn.styleSheet()
        # Green while the picker is open (no selector, so the theme cannot override it).
        btn.setStyleSheet(
            "background-color:#16a34a; color:#ffffff; border:1px solid #14532d; padding:5px; text-align:center;"
        )
        btn.repaint()

        def set_combo(tokens):
            self._edited()
            self.binds[idx]["combo"] = tokens or None
            self._refresh_slot_btn(idx, force=True)

        KeyboardPopup(self, set_combo, initial=self.binds[idx].get("combo")).exec_()
        btn.setStyleSheet(orig)

    def reset_axis(self):
        """Clear every bind of the axis back to the defaults."""
        self.dead = 5
        for i, b in enumerate(self.binds):
            b.update(
                min=0,
                max=100,
                combo=None,
                mode="Hold",
                active=False,
                comment="",
                repeat_ms=100,
                tap_ms=self._profile_tap_ms(),
                last_on_ts=0.0,
                direction="Full",
                noback_plus=False,
                noback_minus=False,
                macro=[],
                macro_repeat=False,
            )
            self.stop_macros(i)
            self.slot_btns[i].setText(f"Bind #{i + 1}")
            self.slot_btns[i].setStyleSheet(self._style_gray)
            self._refresh_bind_lines(i)
            comment = self.slot_comments[i]
            comment.blockSignals(True)
            comment.setText("")
            comment.blockSignals(False)
        self.selected_index = 0
        self._load_selected_into_qb()

    def _on_comment_change(self, idx, text):
        """Store a bind's comment as it is typed."""
        self.binds[idx]["comment"] = text

    def _edited(self, *_args):
        """v108.171: the profile was changed here; in Auto Load the window offers Manual On."""
        note = getattr(self.mainwin, "note_profile_edit", None)
        if note is not None and not self._dry:
            note()

    # Axis history's dry run (v108.156): while output is off (Target off, or
    # the Mapper's own window in front, such as the Axis History window), the
    # binds also run on copies of their state with sending turned off, so the
    # history marks what they would have sent.
    _dry = False
    _dry_states = None
    DRY_STATE = ("active", "last_on_ts", "last_tap")
    # v108.160: "held by NoBack" is marked only where NoBack changed what was
    # sent. A third run, on copies with NoBack left out (sending nothing,
    # recording nothing), shows which binds would have started; a bind that
    # starts there but not in the bind's own run (or its dry run) was held
    # back by NoBack. Before, a bind NoBack ended on the way back was marked
    # held even when, without NoBack, it would have sent nothing more.
    _free = False
    _free_states = None
    _starts = frozenset()
    _free_starts = frozenset()

    def _starts_action(self, idx, kind):
        """True when `kind` starts what bind `idx` does (a press, a tap, a macro; a Release-only release)."""
        if kind in (DOWN, TAP, MACRO):
            return True
        return kind == UP and self.binds[idx].get("mode") == "Release-only"

    def _record(self, idx, kind):
        """Axis history: note what bind `idx` just did (when recording); in a dry run, as not sent."""
        if self.history is None:
            return
        if self._starts_action(idx, kind):
            (self._free_starts if self._free else self._starts).add(idx)
        if self._free:
            return  # the run without NoBack only tells which binds would have started
        b = self.binds[idx]
        key = "macro" if b.get("mode") == MACRO_MODE else combo_to_text(b.get("combo"))
        self.history.add_event(unsent(kind) if self._dry else kind, idx, key, self._raw_val)

    def _send_combo(self, combo, down):
        """Press or release a bind's combo (nothing in a dry run)."""
        if not self._dry:
            send_combo(combo, down, status_callback=self._status_cb)

    def _keep_dry_states(self):
        """Output allowed: the dry run starts from the binds' own states when output goes off."""
        self._dry_states = [{k: b[k] for k in self.DRY_STATE if k in b} for b in self.binds]

    def _copy_run(self, states, value, dir_char, prev_abs_pct, cur_abs_pct, free):
        """Run every bind on copies of `states`, sending nothing; returns the copies' new states."""
        states = states or [{} for _b in self.binds]
        copies = [{**bind, **(states[i] if i < len(states) else {})} for i, bind in enumerate(self.binds)]
        real = self.binds
        self.binds, self._dry, self._free = copies, True, free
        try:
            for i in range(len(copies)):
                self._process_one(i, value, True, dir_char, prev_abs_pct, cur_abs_pct)
        finally:
            self.binds, self._dry, self._free = real, False, False
        return [{k: c[k] for k in self.DRY_STATE if k in c} for c in copies]

    def _dry_run(self, value, dir_char, prev_abs_pct, cur_abs_pct):
        """Output off: run every bind on a copy of its state, sending nothing, recording what it would send."""
        self._dry_states = self._copy_run(self._dry_states, value, dir_char, prev_abs_pct, cur_abs_pct, False)

    def _mark_noback_holds(self, value, dir_char, prev_abs_pct, cur_abs_pct):
        """Run the binds without NoBack (on copies); mark each that would have started but did not."""
        self._free_starts = set()
        self._free_states = self._copy_run(
            self._free_states, value, dir_char, prev_abs_pct, cur_abs_pct, True
        )
        side = dir_char or self._noback_side
        for idx in sorted(self._free_starts - self._starts):
            if noback_on(self.binds[idx], side):
                self._record(idx, HELD)

    def contextMenuEvent(self, event):
        """Right-click the panel (its border or an empty spot): Axis History… for this axis."""
        from .axis_history_window import show_axis_history

        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        action = menu.addAction("Axis History…")
        action.setToolTip(f"A graph of what {self.axis_name} did and the keys its binds sent.")
        action.triggered.connect(lambda _checked=False: show_axis_history(self.mainwin, self.axis_name))
        self._panel_menu = menu  # kept alive while it is open
        if event is not None:
            event.accept()
        menu.exec_(event.globalPos() if event is not None else QCursor.pos())

    def _show_value(self, value):
        """The axis name and its value, in the panel's border."""
        self.setTitle(f"{self.axis_name}: {value:.2f}")

    def _reset_and_blink(self):
        """Flash the panel border amber to confirm, then reset the axis."""
        self._edited()
        self.setStyleSheet("QGroupBox { border: 1px solid #fbbf24; border-radius:5px; }")
        QTimer.singleShot(140, lambda: self.setStyleSheet(""))
        self.reset_axis()

    def _toggle_motion_flash(self):
        """Blink the panel border while the axis moves with output off."""
        if getattr(self.mainwin, "activated", False):
            self._stop_motion_flash()
            return
        self._motion_flash_on = not self._motion_flash_on
        colour = "#60a5fa" if self._motion_flash_on else "#93c5fd"
        self.setStyleSheet(f"QGroupBox {{ border: 1px solid {colour}; border-radius:5px; }}")

    def _stop_motion_flash(self):
        """Stop the motion blink and restore the border."""
        self._motion_timer.stop()
        self._motion_flash_on = False
        self.setStyleSheet("")

    def _show_bind_menu(self, idx):
        """Right-click on a Bind button: NoBack and Edit macro for the bind, Reset for the axis.

        v108.161: NoBack is offered only for the way back, the direction
        opposite the Bind Dir: "NoBack -" for a POS bind, "NoBack +" for a NEG
        bind, both for a FULL bind; none until the bind has a Bind Dir.
        v108.162: no NoBack for a Tick bind; no separator lines; the menu opens
        with its left edge at the button's right edge, so the mouse pointer
        does not cover its check boxes.
        """
        try:
            b = self.binds[idx]
        except IndexError:
            return
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        tick = b.get("mode") == TICK_MODE
        sides = "" if tick else DIRECTION_SIDES.get(b.get("direction"), "")
        if not sides and not tick:
            action = menu.addAction("NoBack")
            action.setEnabled(False)
            action.setToolTip("Choose a Bind Dir first: NoBack is for the way back from it.")
        for side in sides:
            action = menu.addAction(f"NoBack {RETURN_SIGN[side]}")
            action.setCheckable(True)
            action.setChecked(bool(b.get(NOBACK_KEYS[side])))
            action.setToolTip(NOBACK_TIPS[side])
            action.triggered.connect(
                lambda _checked=False, s=side, a=action: self._set_bind_noback(idx, s, a.isChecked())
            )
        edit = menu.addAction("Edit macro…")
        edit.setEnabled(b.get("mode") == MACRO_MODE)
        edit.setToolTip(
            "The steps this bind plays."
            if b.get("mode") == MACRO_MODE
            else "Set this bind's Mode to Macro first."
        )
        edit.triggered.connect(lambda _checked=False: self._open_macro_editor(idx))
        reset = menu.addAction(f"Reset {self.axis_name} axis")
        reset.setToolTip("Clears all six binds of this axis.")
        reset.triggered.connect(lambda _checked=False: self._reset_and_blink())
        self._bind_menu = menu  # kept alive while it is open
        menu.exec_(self._bind_menu_position(idx))

    def _bind_menu_position(self, idx):
        """Where Bind button `idx`'s menu opens: its left edge at the button's right edge, level with its top."""
        try:
            button = self.slot_btns[idx]
            return button.mapToGlobal(QPoint(button.width(), 0))
        except (AttributeError, IndexError, RuntimeError):
            return QCursor.pos()

    def _set_bind_noback(self, idx, side, on):
        """Turn NoBack on or off for one bind, for the way back from axis side `side`."""
        self._edited()
        self.binds[idx][NOBACK_KEYS[side]] = bool(on)
        if not on and self._noback_side == side and not self._side_has_noback(side):
            self._reset_noback()
        self._refresh_slot_btn(idx, force=True)

    def _refresh_bind_lines(self, idx):
        """The Bind button's lines: green along the top for its Bind Dir, white
        along the bottom for its NoBack, toward the way back (v108.161: the
        opposite of the green: left for a POS bind). Each sweeps from the middle."""
        try:
            btn = self.slot_btns[idx]
        except (IndexError, AttributeError):
            return
        b = self.binds[idx]
        win = self.window()
        hovered, phase = getattr(win, "_title_was_hovered", False), getattr(win, "_title_phase", 0.0)
        for attribute, kind, sides in (
            ("_dir_line", BindDirSweep, DIRECTION_SIDES.get(b.get("direction"), "")),
            ("_noback_glow", NoBackSweep, noback_names(b)),
        ):
            line = getattr(btn, attribute, None)
            if line is None:
                if not sides:
                    continue
                line = kind(btn)
                setattr(btn, attribute, line)
            line.set_sides(sides)
            line.set_wanted(bool(sides))
            if sides:
                line.set_hover_phase(hovered, phase)

    def _dir_char(self, value):
        """'+' or '-' for the side of the axis value; None at centre."""
        return '+' if value > 0 else '-' if value < 0 else None

    def _hys(self):
        """Hysteresis percentage used when leaving a band."""
        return int(getattr(self.mainwin, "hys_pct", 3))

    def _min_hold_ms(self):
        """Shortest time a Hold key stays down."""
        return int(getattr(self.mainwin, "min_hold_ms", 60))

    def _hold_ignore_max(self):
        """True when Hold binds keep holding beyond Max%."""
        return bool(getattr(self.mainwin, "hold_ignore_max", True))

    # ------------------------------------------------------------------
    # Macros (v108.141)
    # ------------------------------------------------------------------
    def _macro_runs(self):
        """The macro runs of this panel, keyed by bind index."""
        runs = getattr(self, "_macro_run_by_bind", None)
        if runs is None:
            runs = self._macro_run_by_bind = {}
        return runs

    def _macro_running(self, idx):
        """True while the bind's macro is playing (never in a dry run)."""
        if self._dry:
            return False
        run = self._macro_runs().get(idx)
        return run is not None and run.running

    def _start_macro(self, idx):
        """Play bind `idx`'s macro unless it is still playing. True when it started (a dry run plays nothing)."""
        if self._dry:
            return True
        if self._macro_running(idx):
            return False
        tap_ms = clamp_tap_ms(self.binds[idx].get("tap_ms"), self._profile_tap_ms())  # v108.166: the bind's
        run = MacroRun(
            self.binds[idx].get("macro") or [],
            send=lambda tokens, down: send_combo(tokens, down, status_callback=self._status_cb),
            schedule=lambda ms, callback: QTimer.singleShot(int(ms), callback),
            tap_ms=tap_ms,
            min_up_ms=MIN_UP_MS,  # v108.167: two taps of a key in a row are two presses
        )
        self._macro_runs()[idx] = run
        run.start()
        return True

    def stop_macros(self, idx=None):
        """Stop playing macros (one bind's, or all) and release the keys they hold."""
        if self._dry:
            return
        runs = self._macro_runs()
        for i in [idx] if idx is not None else list(runs):
            run = runs.pop(i, None)
            if run is not None:
                run.stop()

    def set_macro(self, idx, steps):
        """The editor's Save: the bind's new steps."""
        self._edited()
        self.stop_macros(idx)
        self.binds[idx]["macro"] = normalize_macro(steps)
        self._refresh_slot_btn(idx, force=True)

    def _open_macro_editor(self, idx):
        """Open the macro editor for a bind and store the saved steps."""
        from .macro_editor import MacroEditor

        try:
            b = self.binds[idx]
        except IndexError:
            return
        title = f"{self.axis_name} Bind #{idx + 1}: macro"
        MacroEditor(self, b.get("macro") or [], lambda steps: self.set_macro(idx, steps), title=title).exec_()

    def _send_tap(self, combo, dwell=None):
        """Press a combo and release it after its Tap Dwell (0-200 ms).

        Many games ignore zero-length taps. v108.166: the dwell is the bind's
        Tap Dwell (the profile's when it has none). v108.167: the release is
        scheduled, so the Mapper keeps running during the dwell, and a key
        just tapped stays up MIN_UP_MS before it is tapped again (taps.py).
        """
        if self._dry:
            return
        dwell = clamp_tap_ms(dwell, self._profile_tap_ms()) if dwell is not None else self._profile_tap_ms()
        self._taps().tap(combo, dwell)

    def _taps(self):
        """The window's TapSender, shared by its axes (made by the first one that taps)."""
        sender = getattr(self.mainwin, "_tap_sender", None)
        if sender is None:
            sender = TapSender(
                send=lambda combo, down: send_combo(combo, down, status_callback=self._status_cb),
                schedule=lambda ms, callback: QTimer.singleShot(int(ms), callback),
                clock=time.perf_counter,
            )
            self.mainwin._tap_sender = sender
        return sender

    def _dir_ok(self, value, d):
        """True when the axis value is on a side the bind's direction allows."""
        if not d:
            return False
        if d == "Full":
            return True
        return (value > 0) if d == "Plus" else (value < 0)

    def _reset_noback(self):
        """Forget the NoBack side and highest band reached."""
        self._noback_side = None
        self._noback_level = -1
        # Level before the current sample: a band reached on this very sample
        # must not stop a lower bind (or Tick) from starting on the way out.
        self._noback_prior_level = -1

    def _noback_bands(self, side):
        """(start, reached_at(magnitude)) for every mapped bind on this side.

        Tick binds count too: their band starts at Tick% (DZone is not added)
        and has no Max%, matching how a Tick fires.
        """
        direction = 'Plus' if side == '+' else 'Minus'
        bands = []
        for bind in self.binds:
            if not bind_has_output(bind) or bind.get('direction') not in (direction, 'Full'):
                continue
            if bind.get('mode') == 'Tick':
                start = self._tick_threshold(bind)
                bands.append((start, lambda m, s=start: m >= s))
                continue
            start = self._bind_minimum(bind)
            no_top = bind.get('mode') == 'Hold' and self._hold_ignore_max()
            top = int(bind.get('max', 100))
            bands.append((start, lambda m, s=start, t=top, n=no_top: m >= s and (n or m <= t)))
        return bands

    def _advance_noback(self, side, magnitude):
        """Remember the highest mapped band reached during this excursion.

        The memory follows the physical stroke even while output is not
        allowed (target window out of focus), so focus returning during the
        return stroke cannot let a lower bind fire.
        """
        if side != self._noback_side:
            self._reset_noback()
        if not self._side_has_noback(side):
            self._reset_noback()
            return
        bands = self._noback_bands(side)
        if not bands:
            self._reset_noback()
            return
        # Back below every band on this side (less hysteresis) is the same as
        # centring, even when the puck rests just outside the dead zone.
        floor = min(start for start, _reached in bands)
        if self._noback_level >= 0 and magnitude < floor - self._hys():
            self._reset_noback()
        self._noback_side = side
        self._noback_prior_level = self._noback_level
        for start, reached in bands:
            if reached(magnitude):
                self._noback_level = max(self._noback_level, start)

    def _side_has_noback(self, side):
        """True when a mapped bind has NoBack on this side."""
        return any(bind_has_output(b) and noback_on(b, side) for b in self.binds)

    def _noback_blocks(self, start, active, magnitude):
        """True when NoBack must keep a bind starting at ``start`` quiet.

        Asked only for binds that have NoBack. A lower bind may not start once
        a higher band (of any bind on that side) was reached earlier in this
        excursion; one still active is released when the axis comes back below
        the highest band reached.
        """
        if active:
            return self._noback_level > start and magnitude < self._noback_level
        return self._noback_prior_level > start

    def _bind_minimum(self, bind):
        """Where a bind starts: its DZone% plus Min%, capped at 100."""
        return max(0, min(100, int(bind.get('dead', self.dead)) + int(bind['min'])))

    @staticmethod
    def _tick_threshold(bind):
        """The Tick% at which a Tick bind fires."""
        try:
            return max(0, min(100, int(bind.get('min', 0))))
        except (TypeError, ValueError):
            return 0

    def _process_bind(self, idx, value, allow, dir_char, prev_abs_pct, cur_abs_pct):
        """Run one bind's mode (Hold, taps, repeat, macro) for a new axis value."""
        b = self.binds[idx]
        combo, mode, min_val, max_val = b["combo"], b["mode"], int(b["min"]), int(b["max"])
        output = bind_has_output(b)
        d = b.get("direction")
        eff_min = self._bind_minimum(b)
        # A lower band can release its held key, but cannot start again
        # during the same excursion after reaching a higher band.
        # The side of this excursion (still known on the centring sample).
        side = dir_char or self._noback_side
        blocked = (
            not self._free and noback_on(b, side) and self._noback_blocks(eff_min, b["active"], cur_abs_pct)
        )
        if blocked and self._dir_ok(value, d):
            if mode == "Hold" and b["active"]:
                self._send_combo(combo, False)
                self._record(idx, NOBACK_UP)
            b["active"] = False
            self._refresh_slot_btn(idx, in_range=False)
            return
        if mode == "Hold":
            in_range = (
                self._dir_ok(value, d)
                and (cur_abs_pct >= eff_min)
                and (cur_abs_pct <= max_val or self._hold_ignore_max())
                if d
                else False
            )
        else:
            in_band = eff_min <= cur_abs_pct <= max_val
            in_range = (
                (
                    in_band
                    if d == "Full"
                    else (value > 0 and in_band if d == "Plus" else value < 0 and in_band)
                )
                if d
                else False
            )
        if (not getattr(self.mainwin, 'activated', False)) and in_range and output:
            self._pulse_bind_button(idx)
        self._refresh_slot_btn(idx, in_range=in_range)
        if not (allow and output):
            if mode == MACRO_MODE:
                # Not allowed now (Target off, another window in front): stop at once.
                self.stop_macros(idx)
                b["active"] = False
            elif b.get("active") and mode in ("Hold", "Press/Release", "Press/Repeat"):
                self._send_combo(combo, False)
                if mode == "Hold":
                    self._record(idx, UP)
                b["active"] = False
            return
        if mode == "Hold":
            now = time.perf_counter()
            hys = self._hys()
            if in_range and not b["active"]:
                self._send_combo(combo, True)
                self._record(idx, DOWN)
                b["active"] = True
                b["last_on_ts"] = now
            elif b["active"]:
                dir_ok = self._dir_ok(value, d)
                below_min = cur_abs_pct < max(0, eff_min - hys)
                over_max_strict = (cur_abs_pct > max_val) and (not self._hold_ignore_max())
                if (not dir_ok) or below_min or over_max_strict:
                    min_guard_ok = (now - b.get("last_on_ts", now)) * 1000.0 >= self._min_hold_ms()
                    well_below = cur_abs_pct < max(0, min_val - 2 * hys)
                    if min_guard_ok or well_below:
                        self._send_combo(combo, False)
                        self._record(idx, UP)
                        b["active"] = False
        elif mode == "Press/Release":
            if in_range and not b["active"]:
                self._send_tap(combo, b.get("tap_ms"))
                self._record(idx, TAP)
                b["active"] = True
            elif (not in_range) and b["active"]:
                b["active"] = False
        elif mode == "Press/Repeat":
            if in_range:
                now = time.perf_counter()
                if not b["active"]:
                    self._send_tap(combo, b.get("tap_ms"))
                    self._record(idx, TAP)
                    b["last_tap"] = now
                    b["active"] = True
                # v108.167: never sooner than its Tap Dwell plus the time the key must be up.
                elif now - b["last_tap"] >= repeat_interval_ms(b["repeat_ms"], self._bind_tap_ms(b)) / 1000.0:
                    self._send_tap(combo, b.get("tap_ms"))
                    self._record(idx, TAP)
                    b["last_tap"] = now
            elif b["active"]:
                b["active"] = False
        elif mode == "Release-only":
            if in_range and not b["active"]:
                self._send_combo(combo, False)
                self._record(idx, UP)
                b["active"] = True
            elif (not in_range) and b["active"]:
                b["active"] = False
        elif mode == MACRO_MODE:
            # Once: plays on entering the band. Repeat: plays again every
            # repeat_ms (start to start) while in the band, never two at once.
            # Leaving the band lets the run that is playing finish.
            if in_range:
                now = time.perf_counter()
                if not b["active"]:
                    b["active"] = True
                    if self._start_macro(idx):
                        self._record(idx, MACRO)
                        b["last_tap"] = now
                elif (
                    b.get("macro_repeat")
                    and not self._macro_running(idx)
                    and now - b.get("last_tap", 0.0) >= int(b.get("repeat_ms", 100)) / 1000.0
                ):
                    if self._start_macro(idx):
                        self._record(idx, MACRO)
                        b["last_tap"] = now
            elif b["active"]:
                b["active"] = False

    def update_val(self, val, allow):
        """Take a new axis value: update the display, NoBack and every bind."""
        if self.history is not None:  # Options > Axis History
            self._raw_val = val
            self.history.add_sample(val)
        activated = getattr(self.mainwin, "activated", False)
        if activated and self._motion_timer.isActive():
            self._stop_motion_flash()
        dead = self.dead / 100.0
        val_proc = 0.0 if abs(val) < dead else val
        self._show_value(val_proc)
        if not activated and abs(val_proc) >= dead:
            if not self._motion_timer.isActive():
                self._motion_timer.start()
            self._motion_idle.start()
        cur_abs_pct = min(100.0, max(0.0, abs(val_proc) * 100.0))
        dir_char = self._dir_char(val_proc)
        prev_abs_pct = self._last_pct if dir_char and dir_char == self._last_side else 0.0
        # Keep the old level for the center sample so a Full bind with
        # minimum zero cannot fire on the final sample of the return.
        if dir_char:
            self._advance_noback(dir_char, cur_abs_pct)
        else:
            self._noback_prior_level = self._noback_level
        self._starts = set()
        for i in range(len(self.binds)):
            self._process_one(i, val_proc, allow, dir_char, prev_abs_pct, cur_abs_pct)
        if self.history is not None:  # Axis History: what output off and NoBack kept back
            if allow:
                self._keep_dry_states()
            else:
                self._dry_run(val_proc, dir_char, prev_abs_pct, cur_abs_pct)
            self._mark_noback_holds(val_proc, dir_char, prev_abs_pct, cur_abs_pct)
        if dir_char:
            self._last_side, self._last_pct = dir_char, cur_abs_pct
        else:
            # Preserve suppression across repeated neutral samples. The next
            # nonzero sample starts a new excursion on either side.
            self._noback_side = None
            self._last_side, self._last_pct = None, 0.0
        if self.history is not None:  # Axis History draws NoBack while it is in force
            self.history.set_noback(self._noback_side, self._noback_level)

    def clear_keys(self):
        """Release held keys, stop macros and clear active states."""
        self._reset_noback()
        self.stop_macros()
        sender = getattr(self.mainwin, "_tap_sender", None)
        if sender is not None and not self._dry:
            sender.release_all()  # v108.167: taps still in their dwell
        for i, b in enumerate(self.binds):
            if (
                b.get("combo")
                and b.get("mode") in ("Hold", "Press/Release", "Press/Repeat")
                and b.get("active")
            ):
                send_combo(b["combo"], False, status_callback=self._status_cb)
            b["active"] = False
            self._refresh_slot_btn(i, in_range=False, force=True)
        self._last_side, self._last_pct = None, 0.0

    def _pulse_bind_button(self, idx):
        """Briefly grey a Bind button when its band is reached with output off."""
        if self._dry or getattr(self.mainwin, 'activated', False):
            return
        btn = self.slot_btns[idx]
        btn.setStyleSheet(self._style_gray)
        # Back to its own style (selected, NoBack outline) after the flash.
        QTimer.singleShot(120, lambda: btn.setStyleSheet(self._slot_style(idx)))

    # ------------------------------------------------------------------
    # Tick mode: a one-way tap when the axis crosses Tick% moving outward.
    # Tick% is stored in bind["min"]; DZone and Max% do not apply.
    # ------------------------------------------------------------------
    def _process_one(self, idx, value, allow, dir_char, prev_abs_pct, cur_abs_pct):
        """Run one bind for a new axis value: Tick here, every other mode in _process_bind."""
        b = self.binds[idx]
        if b.get("mode") != TICK_MODE:
            return self._process_bind(idx, value, allow, dir_char, prev_abs_pct, cur_abs_pct)
        combo = b.get("combo")
        threshold = self._tick_threshold(b)
        rearm_below = max(0, threshold - max(0, self._hys()))
        dir_ok = _tick_dir_ok(value, b.get("direction"))
        # Crossing Tick% from below means the axis moved outward.
        crossed_tick = dir_ok and prev_abs_pct < threshold <= cur_abs_pct
        # v108.162: no NoBack for a Tick: it taps each time it is crossed going
        # out (it still counts as a band for the NoBack of the binds below it).
        # The Bind button lights while the axis is at or beyond the mark.
        in_range = dir_ok and cur_abs_pct >= threshold
        if not getattr(self.mainwin, "activated", False) and in_range and combo:
            self._pulse_bind_button(idx)
        self._refresh_slot_btn(idx, in_range=in_range)
        if allow and combo and crossed_tick and not b.get("active", False):
            self._send_tap(combo, b.get("tap_ms"))  # fire once, on the outward crossing
            self._record(idx, TAP)
            b["active"] = True
            b["last_on_ts"] = time.perf_counter()
            return
        # Re-arm (sending nothing) once the axis retreats below Tick% less hysteresis.
        if cur_abs_pct < rearm_below:
            b["active"] = False

    def _load_selected_into_qb(self):
        """Show the selected bind in Quick Bind: Bind Dir, Mode, Play, Repeat and values."""
        b = self.binds[self.selected_index]
        for i in range(self.qb_dir.count()):
            if self.qb_dir.itemData(i) == b.get("direction"):
                self.qb_dir.blockSignals(True)
                self.qb_dir.setCurrentIndex(i)
                self.qb_dir.blockSignals(False)
                break
        for combo, text in (
            (self.qb_mode, b.get("mode", "Hold")),
            (self.qb_play, "Repeat" if b.get("macro_repeat") else "Once"),
            (self.qb_repeat, str(b.get("repeat_ms", 100))),
        ):
            combo.blockSignals(True)
            combo.setCurrentText(text)
            combo.blockSignals(False)
        self.min_val.setText(str(int(b.get("min", 0))))
        self.max_val.setText(str(int(b.get("max", 100))))
        self.dead_lbl.setText(f"DZone: {int(b.get('dead', self.dead)):>3d}%")
        for i in range(len(self.binds)):
            self._refresh_slot_btn(i, in_range=self._last_in_range[i], force=True)
        self._apply_selected_mode_ui()

    def _select_slot(self, idx):
        """Select a bind (click on its Bind button) and show it in Quick Bind."""
        if self.selected_index != idx:
            self.selected_index = idx
            self._load_selected_into_qb()
        self.dead_lbl.setText(f"DZone: {int(self.binds[idx].get('dead', self.dead)):>3d}%")
        self._apply_selected_mode_ui()

    def _qb_changed(self, *_args):
        """Store Bind Dir and Mode from Quick Bind into the selected bind."""
        self._edited()
        b = self.binds[self.selected_index]
        b["direction"] = self.qb_dir.currentData()
        fit_noback_to_direction(b)  # NoBack follows the bind to its new side
        mode = self.qb_mode.currentText()
        if b.get("mode") == MACRO_MODE and mode != MACRO_MODE:
            self.stop_macros(self.selected_index)
        b["mode"] = mode
        self._apply_selected_mode_ui()
        # The Bind button shows the key or "Macro (n)", whichever the Mode uses.
        self._refresh_slot_btn(self.selected_index, force=True)

    def _change_min(self, delta):
        """Step the selected bind's Min% (Tick% in Tick mode), 0-100."""
        self._edited()
        b = self.binds[self.selected_index]
        b["min"] = max(0, min(100, int(b["min"]) + int(delta)))
        if b.get("mode") == TICK_MODE:  # Max% is not used by Tick, so it does not follow
            self.min_val.setText(f"{b['min']:>3d}")
            self._refresh_slot_btn(self.selected_index, force=True)
            self._apply_selected_mode_ui()
            return
        if b["min"] > b["max"]:
            b["max"] = b["min"]
        self.min_val.setText(str(b["min"]))
        self.max_val.setText(f"{int(b['max']):>3d}")
        self._refresh_slot_btn(self.selected_index, force=True)

    def _apply_selected_mode_ui(self):
        """Show the Quick Bind controls the selected mode uses (Tick%, Play, Repeat)."""
        b = self.binds[self.selected_index]
        is_tick = b.get("mode") == TICK_MODE
        # Min% becomes Tick% in Tick mode; its [-] [+] step Tick%.
        self.min_text.setText("Tick%:" if is_tick else "Min%:")
        tick_val = max(0, min(100, int(b.get("min", 0))))
        self.min_val.setText(f"{tick_val:>3d}" if is_tick else str(tick_val))
        for widget, is_button in (
            (self.min_text, False),
            (self.min_val, False),
            (self.min_dec, True),
            (self.min_inc, True),
        ):
            _set_ghost(widget, False, is_button)
        # Max% and DZone are not used by Tick: greyed out rather than looking editable.
        for widget, is_button in (
            (self.max_text, False),
            (self.max_val, False),
            (self.max_dec, True),
            (self.max_inc, True),
            (self.dead_lbl, False),
            (self.dead_dec, True),
            (self.dead_inc, True),
        ):
            _set_ghost(widget, is_tick, is_button)
            tip = getattr(widget, "_spnav_tip", "")
            widget.setToolTip("Ignored while Mode = Tick" + (f"\n\n{tip}" if tip else "") if is_tick else tip)
        if not is_tick:
            self.max_val.setText(f"{int(b.get('max', 100)):>3d}")
            self.dead_lbl.setText(f"DZone: {int(b.get('dead', self.dead)):>3d}%")
        # v108.166: Tap Dwell, greyed out for the modes that send no taps.
        mode = b.get("mode", "Hold")
        unused = mode not in TAPPING_MODES
        self.tap_lbl.setText(tap_text(clamp_tap_ms(b.get("tap_ms"), self._profile_tap_ms())))
        for widget, is_button in ((self.tap_lbl, False), (self.tap_dec, True), (self.tap_inc, True)):
            _set_ghost(widget, unused, is_button)
            tip = getattr(widget, "_spnav_tip", "")
            widget.setToolTip(
                f"Not used while Mode = {mode}" + (f"\n\n{tip}" if tip else "") if unused else tip
            )
        # Tick does not use repeat timing; a macro's Play row shows for Macro.
        self._sync_mode_groups()
        self._refresh_repeat_note()
        # NoBack (right-click a Bind button) applies to every mode, Tick
        # included; a Bind Dir change can put it in or out of effect.
        self._refresh_bind_lines(self.selected_index)

    # ------------------------------------------------------------------
    # Profile data (per-bind DZone% and comments included)
    # ------------------------------------------------------------------
    def get_config(self):
        """Profile data for the axis: dead zone, selection and six binds."""
        binds_out = []
        for b, comment in zip(self.binds, self.slot_comments):
            bc = {
                "direction": b.get("direction"),
                "combo": b.get("combo"),
                "mode": b.get("mode"),
                "min": int(b["min"]),
                "max": int(b["max"]),
            }
            if b.get("mode") in ("Press/Repeat", MACRO_MODE):
                bc["repeat_ms"] = int(b.get("repeat_ms", 100))
            if b.get("mode") in TAPPING_MODES:  # v108.166: its Tap Dwell
                bc["tap_ms"] = clamp_tap_ms(b.get("tap_ms"), self._profile_tap_ms())
            if b.get("macro"):
                bc["macro"] = normalize_macro(b["macro"])
                bc["macro_repeat"] = bool(b.get("macro_repeat"))
            bc["comment"] = str(comment.text())  # what the bind's comment field shows
            bc["noback_plus"] = bool(b.get("noback_plus"))
            bc["noback_minus"] = bool(b.get("noback_minus"))
            bc["dead"] = int(b.get("dead", self.dead))
            binds_out.append(bc)
        return {"dead": int(self.dead), "selected": int(self.selected_index), "binds": binds_out}

    def set_config(self, cfg):
        """Load an axis's profile data into its six binds and refresh the panel.

        Older profiles load too: "Press-only" mode, a single "key", other
        dead-zone field names, NoBack for the whole axis, four binds.
        """
        self._reset_noback()
        self.stop_macros()
        try:
            self.dead = int(cfg.get("dead", self.dead))
        except (TypeError, ValueError):
            pass
        src = cfg.get("binds", [])
        for i, b in enumerate(self.binds):
            if i < len(src):
                s = src[i]
                try:
                    mode = s.get("mode", b["mode"])
                    b.update(
                        direction=s.get("direction", "Full"),
                        mode="Press/Release" if mode == "Press-only" else mode,
                        combo=s.get("combo", [s.get("key")] if s.get("key") else None),
                        min=int(s.get("min", b["min"])),
                        max=int(s.get("max", b["max"])),
                        comment=str(s.get("comment", b.get("comment", ""))),
                        repeat_ms=int(s.get("repeat_ms", 100)),
                        # v108.166: older profiles have one Tap Dwell, for every bind.
                        tap_ms=clamp_tap_ms(s.get("tap_ms", self._profile_tap_ms()), self._profile_tap_ms()),
                        macro=normalize_macro(s.get("macro")),
                        macro_repeat=bool(s.get("macro_repeat", False)),
                        dead=_read_dead_value(s, b.get("dead", self.dead)),
                    )
                    b["noback_plus"], b["noback_minus"] = bind_noback_from(s, cfg)
                    fit_noback_to_direction(b)
                except (AttributeError, TypeError, ValueError):
                    pass  # a damaged bind keeps what it had
            else:
                # A four-bind profile must not leave Bind #5/#6 set from the
                # profile loaded before it.
                b.update(
                    direction=None,
                    combo=None,
                    mode="Hold",
                    min=0,
                    max=100,
                    comment="",
                    repeat_ms=100,
                    tap_ms=self._profile_tap_ms(),
                    active=False,
                    last_tap=0.0,
                    last_on_ts=0.0,
                    dead=self.dead,
                    noback_plus=False,
                    noback_minus=False,
                    macro=[],
                    macro_repeat=False,
                )
            comment = self.slot_comments[i]
            comment.blockSignals(True)
            comment.setText(b.get("comment", ""))
            comment.blockSignals(False)
            self._refresh_slot_btn(i, force=True)
        try:
            selected = int(cfg.get("selected", 0))
        except (TypeError, ValueError):
            selected = 0
        self.selected_index = max(0, min(selected, len(self.binds) - 1))
        self._load_selected_into_qb()
