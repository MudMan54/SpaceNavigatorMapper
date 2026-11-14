"""Keyboard assignment picker dialog."""

from PyQt5 import QtWidgets
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .scaling import S

_MODIFIERS = ("ctrl", "shift", "alt")


class KeyboardPopup(QDialog):
    """Pick a key, or a key with Ctrl / Shift / Alt, or a symbol."""

    # Color palette
    _CLR_BLUE = "#3b82f6"  # default blue for Ctrl/Shift/Alt/Clear, Save & Close
    _CLR_RED = "#ef4444"  # selected red
    _CLR_YELLOW = "#f59e0b"  # default yellow (F-keys)
    _CLR_FLASH = "#fbbf24"  # flash on click
    _CLR_DARK = "#1f2937"
    _CLR_DARK_BORDER = "#334155"
    _CLR_TEXT_LIGHT = "#e5e7eb"
    _CLR_TEXT_DARK = "#111827"
    _CLR_GRAY_BORDER = "#6b7280"
    _CLR_GRAY_MED = "#4b5563"  # symbol rows

    # Symbol label → the keys that type it (so '!' becomes ['shift','1'], etc.)
    _SYMBOL_COMBOS = {
        # shifted number-row
        "~": ["shift", "`"],
        "!": ["shift", "1"],
        "@": ["shift", "2"],
        "#": ["shift", "3"],
        "$": ["shift", "4"],
        "%": ["shift", "5"],
        "^": ["shift", "6"],
        "&": ["shift", "7"],
        "*": ["shift", "8"],
        "(": ["shift", "9"],
        ")": ["shift", "0"],
        "_": ["shift", "-"],
        "+": ["shift", "="],
        # unshifted punctuation rows
        "`": ["`"],
        "-": ["-"],
        "=": ["="],
        "[": ["["],
        "]": ["]"],
        "\\": ["\\"],
        ";": [";"],
        "'": ["'"],
        ",": [","],
        ".": ["."],
        "/": ["/"],
    }
    _SYMBOL_LABELS = set(_SYMBOL_COMBOS)

    # Visible label → the key token keyboard_io knows it by
    _VISIBLE_TO_TOKEN = {
        "`": "backtick",
        "-": "minus",
        "=": "equals",
        "[": "lbracket",
        "]": "rbracket",
        "\\": "backslash",
        ";": "semicolon",
        "'": "apostrophe",
        ",": "comma",
        ".": "period",
        "/": "slash",
    }

    def __init__(self, parent, cb, initial=None):
        """Build the key picker: keys, modifiers, symbols and its buttons."""
        super().__init__(parent)
        self.cb = cb
        self.mod_buttons = {}
        self.key_buttons = []
        self.selected_key_btn = None
        self.selected_key_token = None
        self.selected_symbol_combo = None  # when a symbol is chosen we store its baked combo

        init_mods = set()
        init_key = None
        if isinstance(initial, list) and initial:
            lows = [str(x).lower() for x in initial]
            init_mods = {m for m in lows if m in _MODIFIERS}
            mains = [m for m in lows if m not in _MODIFIERS]
            init_key = mains[0] if mains else None
        elif isinstance(initial, str):
            t = initial.lower().strip()
            if t in _MODIFIERS:
                init_mods = {t}
            else:
                init_key = t

        self.setWindowTitle("Pick Key / Combo")
        self.resize(980, 740)
        # Ctrl / Shift / Alt get a 12 pt font once the dialog is built.
        QTimer.singleShot(0, self._apply_modifier_font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(S(16), S(16), S(16), S(16))
        layout.setSpacing(S(10))
        layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

        # --- Modifiers strip (Ctrl/Shift/Alt) ---
        mods_row = QHBoxLayout()
        mods_row.setContentsMargins(0, 0, 0, 0)
        mods_row.setSpacing(5)
        for mod in ("Ctrl", "Shift", "Alt"):
            btn = QPushButton(mod)
            btn.setCheckable(True)
            btn.setFixedHeight(S(88))
            btn.setMinimumWidth(S(146))
            btn.setStyleSheet(
                f"background-color:{self._CLR_BLUE}; color:#ffffff; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px; font-weight:600; "
            )
            token = mod.lower()
            if token in init_mods:
                btn.setChecked(True)
                self._apply_red(btn)
            btn.clicked.connect(lambda _, t=token, b=btn: self._toggle_modifier(t, b))
            self.mod_buttons[token] = btn
            mods_row.addWidget(btn)
        mods_row.addStretch(1)
        layout.addLayout(mods_row)

        # --- Keys area: one tab, its tab bar hidden ---
        tabs = QTabWidget(self)
        layout.addWidget(tabs)
        tabs.setTabBarAutoHide(True)
        tabs.tabBar().hide()
        tabs.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        tabs.setStyleSheet("QTabWidget::pane { padding:0px; margin:0px } QWidget { margin:0px; padding:0px }")
        keys_tab = QWidget()
        tabs.addTab(keys_tab, "Keys")
        vbox = QVBoxLayout(keys_tab)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)
        keys_tab.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)

        def key_row(labels, size, style=None):
            """A row of key buttons; the initial key starts selected (red)."""
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(5)
            row.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
            for label in labels:
                b = QPushButton(label)
                b.setFixedSize(*size(label))
                if style:
                    b.setStyleSheet(style)
                token = label.lower()
                if token == (init_key or ""):
                    self.selected_key_btn = b
                    self.selected_key_token = token
                    self._apply_red(b)
                b.clicked.connect(lambda _, tok=token, bb=b: self._pick_key(tok, bb))
                row.addWidget(b)
                self.key_buttons.append((token, b))
            row.addStretch(1)
            vbox.addLayout(row)

        # F-keys (yellow), numbers, three letter rows, then specials.
        key_row(
            [f"F{i}" for i in range(1, 13)],
            lambda _label: (S(116), S(70)),
            f"background-color:{self._CLR_YELLOW}; color:{self._CLR_TEXT_DARK}; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px; font-weight:600;",
        )
        for labels in ("1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"):
            key_row(list(labels), lambda _label: (S(116), S(54)))
        specials = [
            "ESC",
            "TAB",
            "ENTER",
            "BACKSPACE",
            "SPACE",
            "PAGEUP",
            "PAGEDOWN",
            "UP",
            "DOWN",
            "LEFT",
            "RIGHT",
        ]
        key_row(specials, lambda label: (S(116) if len(label) <= 3 else S(136), S(80)))

        # Symbols rows (lighter gray default)
        def symbol_row(symbols):
            row = QHBoxLayout()
            row.setSpacing(S(10))
            for label in symbols:
                b = QPushButton(label)
                b.setFixedSize(S(96), S(54))
                b.setStyleSheet(
                    f"background-color:{self._CLR_GRAY_MED}; color:#ffffff; border:1px solid {self._CLR_GRAY_BORDER}; border-radius:4px;"
                )
                b.clicked.connect(lambda _, lab=label, bb=b: self._pick_symbol(lab, bb))
                row.addWidget(b)
            row.addStretch(1)
            vbox.addLayout(row)

        symbol_row(["~", "!", "@", "#", "$", "%", "^", "&", "*", "(", ")", "_", "+"])
        symbol_row(["`", "-", "=", "[", "]", "\\", ";", "'", ",", ".", "/"])

        # Footer: Clear, Close, Save & Close (blue, flash on click)
        foot = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        close_btn = QPushButton("Save && Close")
        cancel_btn = QPushButton("Close")
        for b in (clear_btn, cancel_btn, close_btn):
            b.setFixedHeight(S(26))
            b.setMinimumWidth(S(166))
            b.setStyleSheet(
                f"background-color:{self._CLR_BLUE}; color:#ffffff; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px; font-weight:600; min-height:26px; max-height:82px;"
            )
        clear_btn.clicked.connect(lambda: (self._flash_button(clear_btn), self._clear_selection()))
        cancel_btn.clicked.connect(
            lambda: (self._flash_button(cancel_btn), QTimer.singleShot(120, self.close))
        )
        close_btn.clicked.connect(
            lambda: (
                self._flash_button(close_btn),
                self._reset_mods_no_cb(),
                QTimer.singleShot(120, self.close),
            )
        )
        foot.addStretch(1)
        foot.addWidget(clear_btn)
        foot.addWidget(cancel_btn)
        foot.addWidget(close_btn)
        layout.addLayout(foot)

        self.setStyleSheet(
            "QDialog{background-color:#111827;color:#e2e8f0;} "
            "QTabWidget::pane{border:1px solid #334155;} "
            "QTabBar::tab{background:#1f2937;color:#e5e7eb;padding:4px 8px;border:1px solid #334155;border-bottom:none;} "
            "QTabBar::tab:selected{background:#374151;}"
        )

    # ---------- helpers ----------
    def _apply_modifier_font(self):
        """Ctrl / Shift / Alt in 12 pt."""
        for btn in self.mod_buttons.values():
            font = btn.font()
            font.setPointSize(12)
            btn.setFont(font)
            btn.setStyleSheet((btn.styleSheet() + "; font-size: 12pt;").strip("; "))

    def _flash_button(self, btn, flash=_CLR_FLASH, flash_text=_CLR_TEXT_DARK, ms=140):
        """Briefly highlight a button that was clicked."""
        orig = btn.styleSheet()
        btn.setStyleSheet(
            f"background-color:{flash}; color:{flash_text}; border:1px solid {self._CLR_GRAY_BORDER}; border-radius:4px;"
        )
        QTimer.singleShot(ms, lambda: btn.setStyleSheet(orig))

    def _gmods(self):
        """The modifier tokens currently selected."""
        return [name for name, b in self.mod_buttons.items() if b.isChecked()]

    def _capture_inline_default(self, btn):
        """Remember the button's look before it is first shown selected, to restore it later.

        A button with no style sheet of its own gets one made from its palette.
        """
        if getattr(btn, "_orig_style", "").strip():
            return
        style = (btn.styleSheet() or "").strip()
        if not style:
            palette = btn.palette()
            style = (
                f"background-color:{palette.color(QPalette.Button).name()}; "
                f"color:{palette.color(QPalette.ButtonText).name()}; "
                f"border:1px solid {self._CLR_GRAY_BORDER}; border-radius:4px;"
            )
        btn._orig_style = style

    def _apply_red(self, btn):
        """Show a key or modifier as selected (red)."""
        self._capture_inline_default(btn)
        btn.setStyleSheet(
            f"background-color:{self._CLR_RED}; color:#ffffff; border:1px solid #7f1d1d; border-radius:4px; font-weight:700;"
        )

    def _apply_default(self, btn, token_or_label):
        """Restore a key button's normal look."""
        tok = (token_or_label or "").lower()
        # If it's a single alphanumeric key (0–9, a–z), use BLUE when unselected
        if tok and len(tok) == 1 and (tok.isalpha() or tok.isdigit()):
            btn.setStyleSheet(
                f"background-color:{self._CLR_BLUE}; color:#ffffff; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px; font-weight:600;"
            )
            return

        # Otherwise, restore the remembered original style
        orig = getattr(btn, "_orig_style", "")
        if orig:
            btn.setStyleSheet(orig)
            return

        # Fallback: a default by category
        if token_or_label in self._SYMBOL_LABELS:
            btn.setStyleSheet(
                f"background-color:{self._CLR_GRAY_MED}; color:#ffffff; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px;"
            )
        elif tok in (
            'tab',
            'enter',
            'esc',
            'backspace',
            'delete',
            'home',
            'end',
            'pageup',
            'pagedown',
            'space',
            'up',
            'down',
            'left',
            'right',
        ):
            btn.setStyleSheet(
                f"background-color:{self._CLR_GRAY_MED}; color:#ffffff; border:1px solid {self._CLR_GRAY_BORDER}; border-radius:4px;"
            )
        elif tok.startswith('f') and tok[1:].isdigit():
            btn.setStyleSheet(
                f"background-color:{self._CLR_YELLOW}; color:{self._CLR_TEXT_DARK}; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px; font-weight:600;"
            )
        else:
            btn.setStyleSheet(
                f"background-color:{self._CLR_DARK}; color:{self._CLR_TEXT_LIGHT}; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px;"
            )
        return

    def _set_mods_enabled(self, enabled: bool):
        """Enable or disable the modifier buttons."""
        for b in self.mod_buttons.values():
            b.setEnabled(enabled)
            if enabled:
                if b.isChecked():
                    self._apply_red(b)
                else:
                    b.setStyleSheet(
                        f"background-color:{self._CLR_BLUE}; color:#ffffff; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px; font-weight:600;"
                    )
            else:
                b.setStyleSheet(
                    f"background-color:#6b7280; color:{self._CLR_TEXT_DARK}; border:1px solid #4b5563; border-radius:4px;"
                )

    def _reset_mods_no_cb(self):
        """Clear the modifiers without triggering their handlers."""
        for b in self.mod_buttons.values():
            b.setChecked(False)
            b.setStyleSheet(
                f"background-color:{self._CLR_BLUE}; color:#ffffff; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px; font-weight:600;"
            )
        self._set_mods_enabled(True)

    @staticmethod
    def _dedupe_mods(mods):
        """The selected modifiers, each once, in Ctrl, Shift, Alt order."""
        return [m for m in _MODIFIERS if m in mods]

    def _toggle_modifier(self, token, btn):
        """Add or remove a modifier from the combo."""
        if btn.isChecked():
            self._apply_red(btn)
        else:
            btn.setStyleSheet(
                f"background-color:{self._CLR_BLUE}; color:#ffffff; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px; font-weight:600;"
            )
        combo = self._compose_combo()
        self.cb(combo if combo else None)

    def _compose_combo(self):
        """Combine current mods with selected key OR symbol combo.
        IMPORTANT: When a symbol is selected, DO NOT apply any extra modifiers from the UI.
        """
        if self.selected_symbol_combo:
            # Return only the baked symbol combo (e.g., ['shift','1'] for '!') — ignore UI modifiers.
            return list(self.selected_symbol_combo)
        mods = self._dedupe_mods(self._gmods())
        if self.selected_key_token:
            return mods + [self.selected_key_token]
        return mods or None

    def _pick_key(self, token, btn):
        """Choose the main key of the combo."""
        # Clear any active symbol selection
        if self.selected_key_btn and self.selected_key_btn is not btn:
            self._apply_default(self.selected_key_btn, self.selected_key_token)
        if self.selected_key_btn is btn and self.selected_symbol_combo is None:
            self._apply_default(btn, token)
            self.selected_key_btn = None
            self.selected_key_token = None
            self.selected_symbol_combo = None
            self._set_mods_enabled(True)
            self.cb(self._compose_combo())
            return
        self.selected_key_btn = btn
        self.selected_key_token = token
        self.selected_symbol_combo = None
        self._set_mods_enabled(True)
        self._apply_red(btn)
        self.cb(self._compose_combo())

    def _pick_symbol(self, label, btn):
        """Choose a symbol, as its key plus Shift when needed (the modifiers are disabled)."""
        if self.selected_key_btn and self.selected_key_btn is not btn:
            self._apply_default(self.selected_key_btn, self.selected_key_token)

        # Toggle if same symbol pressed
        if self.selected_key_btn is btn and self.selected_symbol_combo is not None:
            self._apply_default(btn, label)
            self.selected_key_btn = None
            self.selected_key_token = None
            self.selected_symbol_combo = None
            self._set_mods_enabled(True)
            self.cb(self._compose_combo())
            return

        self.selected_key_btn = btn
        self.selected_key_token = label
        self._apply_red(btn)
        self._set_mods_enabled(False)
        self.selected_symbol_combo = [
            t if t in _MODIFIERS or t.isalnum() else self._VISIBLE_TO_TOKEN.get(t, t)
            for t in self._SYMBOL_COMBOS.get(label, [])
        ]
        self.cb(self._compose_combo())

    def _clear_selection(self):
        """Clear the key and modifiers (Clear button)."""
        for mb in self.mod_buttons.values():
            mb.setChecked(False)
            mb.setStyleSheet(
                f"background-color:{self._CLR_BLUE}; color:#ffffff; border:1px solid {self._CLR_DARK_BORDER}; border-radius:4px; font-weight:600;"
            )
        if self.selected_key_btn:
            self._apply_default(self.selected_key_btn, self.selected_key_token)
        self.selected_key_btn = None
        self.selected_key_token = None
        self.selected_symbol_combo = None
        self._set_mods_enabled(True)
        self.cb(None)
