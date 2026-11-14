"""The Mapper window: the editor, input loop, hardware buttons and activation.

MainWindow is assembled from feature mixins; each lives in its own module:

* ui.targets            target window list, picker and resolution
* ui.profiles           new / load / save / backups of profile files
* ui.auto_profiles_menu Auto-Profiles menu, timer and status label
* ui.window_chrome      icon, title, tray, close-to-tray, Options and Display menus

``__init__`` runs their setup steps in a fixed order (the order matters:
later steps add menu entries after earlier ones).
"""

import ctypes
import os
from ctypes import wintypes

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from ..devices import SpaceNavigator
from ..keyboard_io import send_combo
from ..paths import CONFIG_DIR, LAST_PATH_FILE
from ..settings import (
    AXES,
    GUI_MS,
    POLL_MS,
    REVISION_DATE,
    TITLE_LINE1,
    TITLE_LINE2,
    VERSION,
    ensure_dir,
)
from ..win32 import foreground_window, is_own_window, same_process
from . import scaling as _ui_scaling
from .auto_profiles_menu import AutoProfilesMixin
from .axis_panel import AxisPanel
from .editor_fit import fit_controls_to_text
from .keyboard_popup import KeyboardPopup
from .profile_buttons import ProfileButtonRow
from .profile_marquee import ProfileDisplay, ScrollingLineEdit
from .profiles import ProfilesMixin
from .scaling import (
    S,
    Sf,
    fit_scaled_comment_field,
    fit_scaled_input_height,
    restore_readable_height,
    set_readable_height,
)
from .targets import TargetsMixin
from .title_controls import fit_full_editor_title_label
from .title_effect import install_title_effect
from .widgets import (
    AutoModeCombo,
    AxisAlignedHeader,
    MatchWidth,
    ScaledHeaderButton,
)
from .window_chrome import WindowChromeMixin


def _give_refresh_space_to_credit(header, row, button, labels, most=1.6, step=0.025):
    """Remove the Refresh button and enlarge `labels` into its space.

    The header's width with the button is the limit: the labels grow while
    the header is no wider than that, so the editor does not get wider.
    Returns the factor applied.
    """
    header.ensurePolished()
    limit = header.sizeHint().width()
    row.removeWidget(button)
    button.hide()
    button.deleteLater()
    base = [QFont(label.font()) for label in labels]

    def apply(factor):
        for label, font in zip(labels, base):
            grown = QFont(font)
            if font.pointSizeF() > 0:
                grown.setPointSizeF(font.pointSizeF() * factor)
            label.setFont(grown)
        header.layout().invalidate()

    best = 1.0
    factor = 1.0 + step
    while factor <= most + 1e-9:
        apply(factor)
        if header.sizeHint().width() > limit:
            break
        best = factor
        factor += step
    apply(best)
    return best


TARGET_TIP = (
    "Turns key output on or off. In Auto Load it follows the target program: on while it is in "
    "front.\nIt flashes while the Mapper itself, not its target, is in front."
)
BUTTON_TIPS = {
    side: (
        f"The key combination the device's {name} button sends while it is held. "
        "Click to pick it; the button lights while the device's button is pressed."
    )
    for side, name in ((1, "left"), (2, "right"))
}


def match_comment_font(label, comment):
    """Give `label` the point size of the comment field `comment` (family unchanged)."""
    font = QFont(label.font())
    source = comment.font()
    if source.pointSizeF() > 0:
        font.setPointSizeF(source.pointSizeF())
    elif source.pixelSize() > 0:
        font.setPixelSize(source.pixelSize())
    label.setFont(font)
    return font


class MainWindow(ProfilesMixin, TargetsMixin, AutoProfilesMixin, WindowChromeMixin, QMainWindow):
    def __init__(self):
        """Build the window, load the last profile and start the timers."""
        super().__init__()
        self._build_full_editor()
        self._init_auto_profiles()
        self._init_window_chrome()
        self._init_close_to_tray()
        install_title_effect(self)
        self._init_display_menu()
        # Once QSS and fonts are polished, make every control fit its text.
        QTimer.singleShot(0, lambda: fit_controls_to_text(self))

    # ------------------------------------------------------------------
    # Full editor
    # ------------------------------------------------------------------
    def _build_full_editor(self):
        """Lay out the header, button row, six axis panels and status bar."""
        ensure_dir(CONFIG_DIR)
        self.version_str = VERSION
        self.setWindowTitle(f"SPNav Key Mapper — {self.version_str}")
        # v108.151: no maximize (full window) button; the editor is sized to its content.
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        self._apply_custom_titlebar_color()
        self.profile_path = None
        self.spnav = SpaceNavigator()
        self.activated = False
        self._history_target = False  # v108.157: Target on while Axis History is open
        self.target_hwnd = None
        self.target_exe_path = ""  # the target program, to find its window again
        self._recent_targets = []  # target windows, most recently used first
        self._target_rechecker = QTimer(self)  # started by app.run once the window shows
        self._target_rechecker.setInterval(1000)
        self._target_rechecker.timeout.connect(self._resolve_target_if_running)
        self._buttons_prev = 0
        self._hw_btn_active = {1: False, 2: False}
        self.quick_key1 = self.quick_key2 = None  # Button 1 / Button 2 combos
        self.hys_pct = 3
        self.min_hold_ms = 60
        self.hold_ignore_max = True
        self.tap_down_ms = 45

        cw = QWidget()
        root = QVBoxLayout(cw)
        root.setContentsMargins(S(12), S(12), S(12), S(12))
        root.setSpacing(S(12))

        top_area = AxisAlignedHeader()
        top_area.setObjectName("TopArea")
        top_h = QHBoxLayout(top_area)
        top_h.setContentsMargins(S(12), S(8), S(12), S(20))
        top_h.setSpacing(S(12))

        left_col = QWidget()
        left_v = QVBoxLayout(left_col)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(S(8))

        # ----- Target / Focus rows WITHOUT a QGroupBox -----
        row_combo = QHBoxLayout()
        row_combo.setSpacing(S(8))
        # v108.169: "Profile:" is a dark gray button, in its own italic font;
        # a click opens the target list, as the label did.
        lbl_profile = QtWidgets.QPushButton("Profile:")
        lbl_profile.setObjectName("ProfileButton")
        profile_font = QFont("Segoe UI")
        profile_font.setPointSize(Sf(26))
        profile_font.setItalic(True)
        lbl_profile.setFont(profile_font)
        lbl_profile.setCursor(Qt.PointingHandCursor)
        lbl_profile.setToolTip(
            "The target program: click to choose its window from the list (with Delete Linked Program)."
        )
        self.profile_button = lbl_profile
        # Read-only display for the loaded profile/json filename
        self.profile_display = ProfileDisplay()
        self.profile_display.setReadOnly(True)
        self.profile_display.setPlaceholderText("[None]")
        self.profile_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.profile_display.textChanged.connect(lambda *_: self.profile_display.setCursorPosition(0))
        set_readable_height(self.profile_display, S(54))
        self.profile_display.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.profile_display.setMinimumWidth(
            self.profile_display.fontMetrics().horizontalAdvance("[None]") + S(20)
        )
        # The profile name is about a third larger than the interface font.
        name_font = self.profile_display.font()
        base_pt = name_font.pointSize()
        if base_pt <= 0:  # a pixel-sized font: the window's point size, else 12
            base_pt = self.font().pointSize()
            if base_pt <= 0:
                base_pt = 12
        name_font.setPointSize(int(round(base_pt * 1.32)))
        self.profile_display.setFont(name_font)
        fit_scaled_input_height(self.profile_display, S(54))
        # Level with the name box (and never too short for its own text); the
        # height is kept when the editor's control heights are checked again.
        lbl_profile._spnav_fixed_height = max(
            self.profile_display.minimumHeight(), lbl_profile.fontMetrics().height() + 4
        )
        lbl_profile.setFixedHeight(lbl_profile._spnav_fixed_height)
        # Keep internal target combo (for window list) but HIDE it
        self.combo = QComboBox()
        set_readable_height(self.combo, S(54))
        self.combo.setMinimumWidth(S(466))
        self.combo.setMinimumContentsLength(65)
        self.combo.setVisible(False)
        self.auto_chk = AutoModeCombo(self)
        self.auto_chk.modeChanged.connect(self._apply_auto_mode_selection)
        # No Refresh button (v108.129): the target list refreshes when the
        # target picker opens, when the Mapper becomes active and in the
        # background. It is laid out only to measure the header, then
        # removed; its width goes to the credit and version text.
        _refresh_probe = ScaledHeaderButton("Refresh")
        set_readable_height(_refresh_probe, S(54))
        row_combo.addWidget(lbl_profile)
        row_combo.addWidget(self.profile_display, 1)
        row_combo.addWidget(self.auto_chk)
        row_combo.addWidget(_refresh_probe)
        # Clicking "Profile:" or the profile name opens the target list.
        lbl_profile.clicked.connect(lambda _checked=False: self._show_target_picker())
        self.profile_display.mousePressEvent = self._show_target_picker
        left_v.addLayout(row_combo)

        row_actions = QHBoxLayout()
        row_actions.setSpacing(S(8))
        self.target_btn = ScaledHeaderButton("Target: OFF")
        self.target_btn.setObjectName("TargetButton")
        self.target_btn.setCheckable(True)
        self.target_btn.toggled.connect(self._on_target_button_toggled)
        set_readable_height(self.target_btn, S(52))
        save_btn = ScaledHeaderButton("Save/Reload")
        set_readable_height(save_btn, S(48))
        save_btn.clicked.connect(self.save_reload_config)
        save_btn.setObjectName("QuickYellow")
        save_btn.setToolTip(
            "Save the current settings, then reload the saved file.\n"
            "Its prompt lets you change the file name: a new name saves a new profile."
        )
        save_btn.clicked.connect(lambda: self._flash_button_main(save_btn))
        saveb = ScaledHeaderButton("Save as")
        saveb.setObjectName("SaveAsButton")  # white with black letters (QSS)
        set_readable_height(saveb, S(48))
        saveb.clicked.connect(self.save_config)
        loadb = ScaledHeaderButton("Load")
        set_readable_height(loadb, S(48))
        loadb.clicked.connect(self.load_config)
        # v108.165: hover tips.
        self.target_btn.setToolTip(TARGET_TIP)
        saveb.setToolTip(
            "Save the profile under a new .json name (a file dialog), and make it the loaded one."
        )
        loadb.setToolTip("Load a profile (.json) from a file dialog.")
        if _ui_scaling.UI_SIZE_FACTOR < 1.0:
            # Positive layout stretch otherwise turns tiny text into a wide
            # rectangular button. Maximum follows the styled text-size hint
            # and adjusts whenever Target/Save/Load changes its label.
            for button in (self.target_btn, save_btn, saveb, loadb):
                button.setMinimumWidth(0)
                button.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        # v108.165: Save/Reload, Save as and Load share, equally, the room from
        # Target to where the profile name box ends; Target keeps its width.
        left_v.addLayout(row_actions)
        self._profile_buttons = ProfileButtonRow(
            left_col,
            row_actions,
            self.target_btn,
            (save_btn, saveb, loadb),
            self.auto_chk,
            compact=_ui_scaling.UI_SIZE_FACTOR < 1.0,
        )
        # -----------------------------------------------

        right_col = QWidget()
        right_v = QVBoxLayout(right_col)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(S(4))
        title_box = QWidget()
        tb_layout = QVBoxLayout(title_box)
        tb_layout.setContentsMargins(S(8), S(4), S(8), S(4))
        tb_layout.setSpacing(0)
        lbl1 = QLabel(TITLE_LINE1)
        f1 = QFont("Segoe UI")
        f1.setPointSize(Sf(16))
        f1.setItalic(True)
        lbl1.setFont(f1)
        lbl2 = QLabel(TITLE_LINE2)
        f2 = QFont("Segoe Script")
        f2.setPointSize(Sf(16))
        f2.setItalic(True)
        lbl2.setFont(f2)
        # Version and date: the size of the bind comment lines (set below,
        # once those are enlarged), right-justified under the credit.
        self.lbl3 = QLabel(f"{self.version_str}  {REVISION_DATE}")
        self.lbl3.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # The title sits in the menu bar's top-left corner; a click on it
        # sends the window to the taskbar.
        self.title_label = lbl1
        lbl1.setStyleSheet(  # v108.169: for the label only, not its tip
            ".QLabel { color:#FFFFFF; background-color:rgba(255,255,255,0.10);"
            "border:1px solid rgba(255,255,255,0.25); border-radius:6px;"
            "padding:2px 6px; }"
        )
        lbl1.setCursor(Qt.PointingHandCursor)
        lbl1.setToolTip(
            "Click to minimize to the taskbar\nRight-click to open the README (PDF or in a window)"
        )
        lbl1.setAccessibleDescription(
            "Click to minimize to the taskbar; right-click to open the README as a PDF or in a window"
        )
        lbl1.mousePressEvent = self._title_clicked
        lbl1.contextMenuEvent = self._title_right_clicked
        self.menuBar().setCornerWidget(lbl1, Qt.TopLeftCorner)
        for label in (lbl2, self.lbl3):
            label.setStyleSheet(".QLabel { color:#FFFFFF; }")
            tb_layout.addWidget(label)
        right_v.addWidget(title_box, 0, Qt.AlignTop)
        right_v.addStretch(1)

        top_h.addWidget(left_col, 1)
        top_h.addWidget(right_col, 0)
        header_row = QHBoxLayout()
        header_row.addWidget(top_area, 1)
        header_row.addStretch(0)
        root.addLayout(header_row)

        btnrow = QHBoxLayout()
        btnrow.setSpacing(S(12))
        self.led_chk = QtWidgets.QAction("Device LED", self)
        self.led_chk.setCheckable(True)
        self.led_chk.toggled.connect(self._toggle_led)
        self.key1_btn = ScaledHeaderButton("Button 1:")
        self.key1_btn.pressed.connect(lambda: self._handle_quick_button_press(self.key1_btn, 1))
        self.key1_btn.released.connect(lambda: self._handle_quick_button_release(self.key1_btn, 1))
        set_readable_height(self.key1_btn, S(54))
        btnrow.addWidget(self.key1_btn)
        self.comment1 = ScrollingLineEdit()  # long comments scroll, like the profile name
        self.comment1.textEdited.connect(lambda *_: self.note_profile_edit())  # v108.171
        self.comment1.setMaxLength(28)
        set_readable_height(self.comment1, S(54))
        if _ui_scaling.UI_SIZE_FACTOR < 1.0:
            fit_scaled_comment_field(self.comment1, S(54), max_chars=28, min_chars=8)
            self.comment1.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            btnrow.addWidget(self.comment1)
        else:
            self.comment1.setMinimumWidth(S(186))
            btnrow.addWidget(self.comment1, 1)
        self.key1_btn.setToolTip(BUTTON_TIPS[1])
        self.key2_btn = ScaledHeaderButton("Button 2:")
        self.key2_btn.setToolTip(BUTTON_TIPS[2])
        self.key2_btn.pressed.connect(lambda: self._handle_quick_button_press(self.key2_btn, 2))
        self.key2_btn.released.connect(lambda: self._handle_quick_button_release(self.key2_btn, 2))
        set_readable_height(self.key2_btn, S(54))
        btnrow.addWidget(self.key2_btn)
        self.comment2 = ScrollingLineEdit()  # long comments scroll, like the profile name
        self.comment2.textEdited.connect(lambda *_: self.note_profile_edit())
        self.comment2.setMaxLength(28)
        set_readable_height(self.comment2, S(54))
        if _ui_scaling.UI_SIZE_FACTOR < 1.0:
            fit_scaled_comment_field(self.comment2, S(54), max_chars=28, min_chars=8)
            self.comment2.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            btnrow.addWidget(self.comment2)
        else:
            self.comment2.setMinimumWidth(S(186))
            btnrow.addWidget(self.comment2, 1)
        if _ui_scaling.UI_SIZE_FACTOR < 1.0:
            for button in (self.key1_btn, self.key2_btn):
                button.setMinimumWidth(0)
                button.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        btnrow.addStretch(1)
        root.addLayout(btnrow)
        root.addSpacing(S(24))

        axes_container = QWidget()
        grid = QtWidgets.QGridLayout(axes_container)
        grid.setHorizontalSpacing(S(12))
        grid.setVerticalSpacing(S(12))
        grid.setContentsMargins(0, 0, 0, 0)
        self.axes = {name: AxisPanel(name, self) for idx, name in enumerate(AXES)}
        for idx, name in enumerate(AXES):
            grid.addWidget(self.axes[name], idx // 3, idx % 3)
        grid.setColumnStretch(3, 1)  # Keep spare editor width beyond the three axis columns.
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(axes_container)
        top_area.align_with_axes(scroll.viewport(), list(self.axes.values()))
        root.addWidget(scroll, 1)

        self.setCentralWidget(cw)
        self.setStyleSheet(self._dark_stylesheet())
        fit_full_editor_title_label(lbl1)
        for panel in self.axes.values():
            for comment in panel.slot_comments:
                self._enlarge_axis_comment_text(comment)
        match_comment_font(self.lbl3, self.axes[AXES[0]].slot_comments[0])
        # v108.173: Button 1 and 2's comments as wide as an axis bind's comment.
        self._button_comment_width = MatchWidth(
            self.axes[AXES[0]].slot_comments[0], (self.comment1, self.comment2), self
        )
        # The credit alone grows into the Refresh button's space.
        _give_refresh_space_to_credit(top_area, row_combo, _refresh_probe, (lbl2,))

        # Game time meter: accumulated active time (hours:minutes)
        self.game_seconds_total = 0
        self.game_time_label = QLabel("Game Time: 0:00", self)
        self.game_time_label.setToolTip("Double-click to reset game time")
        self.game_time_label.mouseDoubleClickEvent = self._on_game_time_label_double_click
        self.statusBar().addPermanentWidget(self.game_time_label)
        self._game_timer = QTimer(self)
        self._game_timer.setInterval(1000)
        self._game_timer.timeout.connect(self._on_game_timer_tick)
        self._game_timer.start()

        # Display the window before potentially slow HID enumeration.
        # The same device initialization executes once after the first paint.
        self._device_scan_pending = True
        self._window_scan_pending = True
        self.statusBar().showMessage("Connecting to 3Dconnexion device...")
        self.combo.currentIndexChanged.connect(self.set_target)
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.spnav.read)
        self.poll_timer.start(POLL_MS)
        self.gui_timer = QTimer()
        self.gui_timer.timeout.connect(self.refresh_gui)
        self.gui_timer.start(GUI_MS)

        # Auto-refresh window list periodically to detect newly opened apps
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.setInterval(2000)  # 2 seconds
        self.auto_refresh_timer.timeout.connect(self._maybe_auto_refresh_windows)
        self.auto_refresh_timer.start()
        # Open the profile used last (last_path.txt), else last_config.json.
        try:
            with open(LAST_PATH_FILE, encoding="utf-8") as lf:
                last_path = lf.read().strip()
        except OSError:
            last_path = ""
        if last_path and os.path.exists(last_path):
            self._load_config_from_path(last_path)
        else:
            self.load_last_config()
        # Also refresh the targets when the app becomes active.
        QApplication.instance().applicationStateChanged.connect(self._on_app_state_changed)
        self._target_flash_timer = QTimer(self)
        self._target_flash_timer.setInterval(400)
        self._target_flash_timer.timeout.connect(self._on_target_flash_tick)
        self._target_flash_on = False

    def _dark_stylesheet(self):
        """The application's dark style sheet."""
        return (
            """
            QWidget { background-color: #0f172a; color: #e2e8f0; }
            QWidget#TopArea { background-color: #1f2937; }
            QWidget#TopArea QLabel { color: #ffffff; }
            QLabel { color: #e2e8f0; }
            QGroupBox { border: 1px solid #334155; border-radius: 5px; margin-top: 4px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 1px 4px; background-color: #1f2937; border-radius: 4px; color: #e5e7eb; font-weight: 600; }
            QPushButton { background-color: #2563eb; color: #e2e7eb; border: none; padding: __BUTTON_PAD_Y__px __BUTTON_PAD_X__px; border-radius: 4px; }
            QPushButton#TargetButton { background-color: #374151; color: #e5e7eb; }
            /* Profile: (v108.169): dark gray, as Target is when off; its italic font is its own. */
            QPushButton#ProfileButton { background-color: #374151; color: #ffffff; padding: 0px 12px; }
            QPushButton#ProfileButton:hover { background-color: #4b5563; }
            QPushButton#ProfileButton:pressed { background-color: #1f2937; }
            QPushButton#TargetButton:checked { background-color: #16a34a; color: #000000; }
            /* Save/Reload (object name kept): red with white letters. */
            QPushButton#QuickYellow { background-color: #dc2626; color: #ffffff; font-weight: 700; }
            QPushButton#QuickYellow:hover { background-color: #b91c1c; color: #ffffff; }
            QPushButton#QuickYellow[hwpress="true"] { background-color: #7f1d1d; color: #ffffff; }
            /* Save as: white with black letters (v108.135). */
            QPushButton#SaveAsButton { background-color: #ffffff; color: #000000; }
            QPushButton#SaveAsButton:hover { background-color: #e5e7eb; color: #000000; }
            QPushButton#SaveAsButton:pressed { background-color: #d1d5db; color: #000000; }
            /* Menu-bar headings (Auto-Profiles, Options, Display): medium-gray
               highlight with white letters (v108.134). */
            QMenuBar { background-color:#0f172a; color:#e2e8f0; }
            QMenuBar::item {
                background-color:transparent;
                color:#e2e8f0;
                padding:4px 10px;
                border-radius:4px;
            }
            QMenuBar::item:selected {
                background-color:#6b7280;
                color:#ffffff;
            }
            QMenuBar::item:hover {
                background-color:#6b7280;
                color:#ffffff;
            }
            QMenuBar::item:pressed {
                background-color:#6b7280;
                color:#ffffff;
            }
            QComboBox { background:#1f2937; color:#e5e7eb; border:1px solid #334155; border-radius:4px; padding:4px 6px; }
            QMenu, QComboBox QAbstractItemView {
                border:1px solid palette(highlight);
                selection-background-color:palette(highlight);
                selection-color:palette(highlighted-text);
            }
            QMenu::item:selected:enabled,
            QComboBox QAbstractItemView::item:selected,
            QComboBox QAbstractItemView::item:hover:enabled {
                background-color:palette(highlight);
                color:palette(highlighted-text);
            }
            QLineEdit { background:#1f2937; color:#e5e7eb; border:1px solid #334155; border-radius:4px; padding:__INPUT_PAD_Y__px __INPUT_PAD_X__px; }
            QCheckBox { color:#e2e8eb; }
        """.replace("__BUTTON_PAD_Y__", str(_ui_scaling.button_padding(vertical=4, horizontal=8)[0]))
            .replace("__BUTTON_PAD_X__", str(_ui_scaling.button_padding(vertical=4, horizontal=8)[1]))
            .replace("__INPUT_PAD_Y__", str(_ui_scaling.input_padding()[0]))
            .replace("__INPUT_PAD_X__", str(_ui_scaling.input_padding()[1]))
        )

    def _title_clicked(self, event=None):
        """A left click on the title sends the window to the taskbar."""
        try:
            if event is not None:
                if event.button() != Qt.LeftButton:
                    return
                event.accept()
        except AttributeError:
            pass
        # After the click is delivered, not from inside it.
        QTimer.singleShot(0, self.showMinimized)

    def _title_right_clicked(self, event=None):
        """Right-click on the title: a drop-down to open the README as a PDF or in a window."""
        pos = None
        try:
            if event is not None:
                event.accept()
                pos = event.globalPos()
        except AttributeError:
            pass
        from .readme_viewer import show_readme_menu

        show_readme_menu(self, pos)

    @staticmethod
    def _enlarge_axis_comment_text(comment):
        """Use the existing field height and reclaim padding for larger type."""
        comment.ensurePolished()
        restore_readable_height(comment)
        if comment.minimumHeight() == comment.maximumHeight():
            height = comment.minimumHeight()
        else:
            height = comment.sizeHint().height()
        original = comment.font()
        font = QFont(original)
        points = original.pointSizeF()
        # Reserve room for the frame and QLineEdit's own text margins.
        for increase in (2.0, 1.5, 1.0, 0.5):
            if points > 0:
                font.setPointSizeF(points + increase)
            else:
                font.setPixelSize(original.pixelSize() + max(1, round(increase)))
            if QFontMetrics(font, comment).height() <= height - 4:
                comment.setFont(font)
                break
        comment.setStyleSheet("QLineEdit { padding-top:0px; padding-bottom:0px; }")
        comment.setFixedHeight(height)
        comment._spnav_fixed_height = height

    def _apply_custom_titlebar_color(self):
        """Apply a custom Windows 10/11 title bar color using DWM APIs.

        This keeps the standard Windows title bar (caption buttons, drag behavior)
        but changes its background and text color so the app is visually distinct.
        """
        try:
            hwnd = int(self.winId())
            DWMWA_CAPTION_COLOR = 35
            DWMWA_TEXT_COLOR = 36

            # Dark gray caption with white text
            r, g, b = 40, 40, 40
            color_bgr = (b & 0xFF) | ((g & 0xFF) << 8) | ((r & 0xFF) << 16)
            val = ctypes.c_int(color_bgr)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), ctypes.c_int(DWMWA_CAPTION_COLOR), ctypes.byref(val), ctypes.sizeof(val)
            )

            text_color = 0x00FFFFFF  # white
            val2 = ctypes.c_int(text_color)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), ctypes.c_int(DWMWA_TEXT_COLOR), ctypes.byref(val2), ctypes.sizeof(val2)
            )
        except Exception:
            # If DWM is unavailable (older Windows, classic theme, etc), just ignore.
            pass

    # ------------------------------------------------------------------
    # Input loop and hardware buttons
    # ------------------------------------------------------------------
    def _allow_output_now(self, fg):
        """True when keys may be sent now, with window `fg` in front (mode, target, foreground)."""
        if self._history_window_in_front(fg):
            return True  # v108.157: the keys land in the Axis History window, which ignores them
        if not self.activated:
            return False
        mode = self._get_auto_select_mode()
        if mode == AutoModeCombo.MODE_OFF:
            return False
        # v108.144: never type into the Mapper itself (its window, a dialog
        # or a menu in front), in Manual On above all.
        if fg and is_own_window(fg):
            return False
        if mode == AutoModeCombo.MODE_MANUAL_ON:
            return True
        return bool(fg and self.target_hwnd and same_process(fg, self.target_hwnd))

    def refresh_gui(self):
        """Each GUI tick: feed axis values and button changes to the binds."""
        fg = foreground_window()  # one look per tick
        if self.auto_chk.isChecked():
            self._auto_recompute_activation(fg)
        self.spnav.tick()
        allow = self._allow_output_now(fg)
        cur = self.spnav.buttons & 0x03
        for i, name in enumerate(AXES):
            self.axes[name].update_val(self.spnav.axes[i], allow)
        guard = getattr(self, "_elevation", None)
        if guard is not None:
            guard.tick(fg, allow)  # v108.174: keys sent to a program running as administrator?
        changed = cur ^ self._buttons_prev
        if changed:
            for idx in (1, 2):  # bit 0: Button 1, bit 1: Button 2
                bit = 1 << (idx - 1)
                if changed & bit:
                    self._on_hw_button_event(idx, bool(cur & bit), allow)
            self._buttons_prev = cur

    def _on_hw_button_event(self, idx, pressed, allow):
        """Press or release Button 1/2's combo when the device button changes."""
        combo = self.quick_key1 if idx == 1 else self.quick_key2
        btn_widget = self.key1_btn if idx == 1 else self.key2_btn
        btn_widget.setProperty("hwpress", bool(pressed))
        self._repolish(btn_widget)
        if pressed:
            self._flash_hw_button_label(idx)  # red pulse on Button 1 / 2

        if not combo or not allow:
            self._hw_btn_active[idx] = False
            return

        if pressed and not self._hw_btn_active[idx]:
            send_combo(combo, True)
            self._hw_btn_active[idx] = True
        elif (not pressed) and self._hw_btn_active[idx]:
            send_combo(combo, False)
            self._hw_btn_active[idx] = False

    def release_all_keys(self):
        """Release every held key, Button 1/2 and binds alike, and stop macros."""
        for idx, combo in ((1, self.quick_key1), (2, self.quick_key2)):
            if self._hw_btn_active[idx]:
                if combo:
                    send_combo(combo, False)
                self._hw_btn_active[idx] = False
        for panel in self.axes.values():
            panel.clear_keys()

    def clear_all(self):
        """Release every held key and say so in the status bar."""
        self.release_all_keys()
        self.statusBar().showMessage("✔ All keys released", 2000)

    def _after_show_device_scan(self):
        """Connect hardware after first paint; never block the initial window show."""
        if not getattr(self, "_device_scan_pending", False):
            return
        self._device_scan_pending = False
        from ..bootstrap import note

        note("Starting deferred HID device scan...")
        try:
            ok = bool(self.spnav.dev) or self.spnav.open()
            self.statusBar().showMessage(
                ("✔ " + str(self.spnav.device_name) + " connected")
                if ok
                else "⚠ No supported 3Dconnexion device found"
            )
        except Exception as exc:
            note("HID device scan error: " + repr(exc))
            self.statusBar().showMessage("Device connection failed: " + str(exc), 5000)
        note("Deferred HID device scan finished.")

    def _after_show_window_scan(self):
        """Build the target list once visible, preserving initial combo semantics."""
        if not getattr(self, "_window_scan_pending", False):
            return
        self._window_scan_pending = False
        from ..bootstrap import note

        note("Starting deferred running-window scan...")
        try:
            was_blocked = self.combo.blockSignals(True)
            try:
                self.refresh_windows()
            finally:
                self.combo.blockSignals(was_blocked)
            self._resolve_target_if_running()
        except Exception as exc:
            note("Target window scan error: " + repr(exc))
        note("Deferred running-window scan finished.")

    # ------------------------------------------------------------------
    # Activation and the Off / Manual On / Auto Load selector
    # ------------------------------------------------------------------
    def _fg_matches_target(self, fg=None):
        """True when the program in front (`fg`, looked up when not given) is the target program."""
        if not self.target_hwnd:
            return False
        if fg is None:
            fg = foreground_window()
        return bool(fg and same_process(fg, self.target_hwnd))

    def _set_activation(self, st: bool, auto: bool = False):
        """Turn output on or off and update the Target button."""
        if st and self._get_auto_select_mode() == AutoModeCombo.MODE_MANUAL_ON:
            self.activated = True
            self.target_btn.blockSignals(True)
            self.target_btn.setChecked(True)
            self.target_btn.blockSignals(False)
            self.target_btn.setText("Target: MANUAL ON")
            self.combo.setEnabled(False)
            return
        self._apply_activation(st, auto=auto)

    def _apply_activation(self, st: bool, auto: bool = False):
        """Apply Target ON/OFF, asking for a target when none is set."""
        if st and not self.target_hwnd:
            if not auto:
                self.statusBar().showMessage("Pick a target (click the Profile label) first.", 3000)
            self.target_btn.blockSignals(True)
            self.target_btn.setChecked(False)
            self.target_btn.blockSignals(False)
            return
        if self.activated == st:
            self.target_btn.blockSignals(True)
            self.target_btn.setChecked(st)
            self.target_btn.blockSignals(False)
            self.combo.setEnabled(not st)
            return
        self.activated = st
        self.target_btn.blockSignals(True)
        self.target_btn.setChecked(st)
        self.target_btn.blockSignals(False)
        self.target_btn.setText("Target: ON" if st else "Target: OFF")
        self.combo.setEnabled(not st)
        if not st:
            self.clear_all()
        self.statusBar().showMessage(
            ("Auto: " if auto else "") + ("✔ Target ON" if st else "Target OFF"), 2000
        )

    def _get_auto_select_mode(self):
        """The current mode: Auto Load, Manual On or Off."""
        return self.auto_chk.mode()

    def _set_auto_select_mode(self, mode, emit=False):
        """Select Auto Load, Manual On or Off (without signalling unless `emit`)."""
        was_blocked = self.auto_chk.blockSignals(not emit)
        try:
            self.auto_chk.setMode(mode)
        finally:
            self.auto_chk.blockSignals(was_blocked)

    def _apply_auto_mode_selection(self, mode=None):
        """Apply the selected mode to activation and Auto-Profiles."""
        self._history_target = False  # the user's choice ends Axis History's temporary Target
        mode = mode or self._get_auto_select_mode()
        try:
            self._auto_mode_internal_change = True
            if mode == AutoModeCombo.MODE_AUTO_LOAD:
                self.rearm_edit_warning()  # v108.171: Auto Load again: the next change warns
                self.target_btn.setEnabled(False)
                self._auto_recompute_activation()
                self._ap_update_status_label()
            elif mode == AutoModeCombo.MODE_MANUAL_ON:
                self.target_btn.setEnabled(True)
                self._set_activation(True, auto=False)
                self._ap_update_status_label(state="MANUAL")
                self.statusBar().showMessage(
                    "Manual On — SPNav output active; Auto-Load switching disabled.", 2500
                )
            else:
                self.target_btn.setEnabled(False)
                self._set_activation(False, auto=False)
                self._ap_update_status_label(state="OFF")
                self.statusBar().showMessage("Off — mapper inactive; Auto-Load disabled.", 2500)
        finally:
            self._auto_mode_internal_change = False

    def _on_target_button_toggled(self, st: bool):
        """Target button clicked: turn output on or off."""
        self._history_target = False  # the user's choice ends Axis History's temporary Target
        if not getattr(self, "_auto_mode_internal_change", False):
            self._set_auto_select_mode(AutoModeCombo.MODE_MANUAL_ON if st else AutoModeCombo.MODE_OFF)
        self._set_activation(st, auto=False)

    def _auto_recompute_activation(self, fg=None):
        """In Auto Load, activate output only while the target is in front (`fg`: the window in front)."""
        if self._get_auto_select_mode() != AutoModeCombo.MODE_AUTO_LOAD or self._history_target:
            return
        if not self.target_hwnd:
            self._set_activation(False, auto=True)
            self.statusBar().showMessage("Auto Load is selected but no target is selected.", 2500)
            return
        self._set_activation(self._fg_matches_target(fg), auto=True)

    # ------------------------------------------------------------------
    # Axis History's temporary Target (v108.157)
    # ------------------------------------------------------------------
    def _history_window_in_front(self, fg):
        """True when Axis History holds the Target on and its window (`fg`) is in front."""
        if not self._history_target or not fg:
            return False
        window = getattr(self, "_axis_history_window", None)
        try:
            return window is not None and window.isVisible() and int(window.winId()) == int(fg)
        except (RuntimeError, TypeError, ValueError):
            return False

    def set_history_target(self, on):
        """Target on for the current profile while the Axis History window is open; as before after.

        While it is on, the binds send their keys when the Axis History
        window is in front (the window ignores them), so the history shows
        what they send. The mode (Auto Load, Manual On, Off) is not changed
        or saved; closing the window puts the Target back as the mode has it.
        """
        on = bool(on)
        if on == self._history_target:
            return
        if on:
            self._history_target = True
            self.activated = True
            self.target_btn.blockSignals(True)
            self.target_btn.setChecked(True)
            self.target_btn.blockSignals(False)
            self.target_btn.setText("Target: ON (History)")
            self.target_btn.setToolTip(
                "On for the current profile while the Axis History window is open.\n\n" + TARGET_TIP
            )
            self.combo.setEnabled(False)
            self.statusBar().showMessage("Target on while the Axis History window is open", 3000)
            return
        self._history_target = False
        self.release_all_keys()
        mode = self._get_auto_select_mode()
        if mode == AutoModeCombo.MODE_MANUAL_ON:
            st, text = True, "Target: MANUAL ON"
        elif mode == AutoModeCombo.MODE_AUTO_LOAD:
            st = self._fg_matches_target()
            text = "Target: ON" if st else "Target: OFF"
        else:
            st, text = False, "Target: OFF"
        self.activated = st
        self.target_btn.blockSignals(True)
        self.target_btn.setChecked(st)
        self.target_btn.blockSignals(False)
        self.target_btn.setText(text)
        self.target_btn.setToolTip(TARGET_TIP)
        self.combo.setEnabled(not st)

    # ------------------------------------------------------------------
    # Button 1 / Button 2 quick keys, LED, visual feedback
    # ------------------------------------------------------------------
    def _handle_quick_button_press(self, btn, which):
        """Button 1/2 pressed on screen: open its key picker."""
        btn.setProperty("hwpress", True)
        self._repolish(btn)
        QTimer.singleShot(100, lambda: self._open_quick_picker(which))

    def _handle_quick_button_release(self, btn, which):
        """Button 1/2 released on screen: restore its look."""
        btn.setProperty("hwpress", False)
        self._repolish(btn)

    @staticmethod
    def _repolish(w):
        """Re-apply the style sheet after a dynamic property changed."""
        w.style().unpolish(w)
        w.style().polish(w)
        w.update()

    def _open_quick_picker(self, which):
        """Open the key picker for Button 1 or Button 2."""
        btn_widget = self.key1_btn if which == 1 else self.key2_btn
        attribute = f"quick_key{which}"
        btn_widget.setProperty("selected", True)
        self._repolish(btn_widget)

        def set_combo(tokens):
            self.note_profile_edit()  # v108.171
            setattr(self, attribute, tokens or None)
            btn_widget.setText(self._button_key_label(which))

        try:
            KeyboardPopup(self, set_combo, initial=getattr(self, attribute)).exec_()
        finally:
            btn_widget.setProperty("selected", False)
            self._repolish(btn_widget)

    def _toggle_led(self, st):
        """Options > Device LED: switch the device LED."""
        try:
            self.spnav.set_led(st, None)
        except Exception:  # the device boundary: the menu never fails
            pass

    def _flash_button_main(self, btn, ms=140):
        """Flash a header button amber for a moment (Save/Reload)."""
        orig = btn.styleSheet()
        btn.setStyleSheet(
            "background-color:#fbbf24; color:#111827; border:1px solid #9ca3af; border-radius:4px;"
        )
        QTimer.singleShot(ms, lambda: btn.setStyleSheet(orig))

    def _flash_hw_button_label(self, idx: int, ms: int = 180):
        """Pulse Button 1 / Button 2 deep red when the device's button is pressed."""
        btn_widget = self.key1_btn if idx == 1 else self.key2_btn
        orig = btn_widget.styleSheet()
        btn_widget.setStyleSheet((orig + "; background-color:#7f1d1d; color:#ffffff;").strip("; "))
        QTimer.singleShot(ms, lambda: btn_widget.setStyleSheet(orig))

    def _on_target_flash_tick(self):
        """Flash the Target button while the Mapper, not its target, is in front."""
        if not (self.isActiveWindow() and not self._fg_matches_target()):
            self._target_flash_on = False
            self.target_btn.setStyleSheet("")
            self._target_flash_timer.stop()
            return
        self._target_flash_on = not self._target_flash_on
        self.target_btn.setStyleSheet(
            "background-color:#fbbf24; color:#111827; border:1px solid #6b7280; border-radius:4px;"
            if self._target_flash_on
            else ""
        )

    def focusInEvent(self, event):
        """Window focused: start the Target button flash check and refresh the targets."""
        super().focusInEvent(event)
        if not self._target_flash_timer.isActive():
            self._on_target_flash_tick()
            self._target_flash_timer.start()
        self.refresh_windows()

    def focusOutEvent(self, event):
        """Window unfocused: stop flashing the Target button."""
        super().focusOutEvent(event)
        self._target_flash_timer.stop()
        self._target_flash_on = False
        self.target_btn.setStyleSheet("")

    # ------------------------------------------------------------------
    # Game time meter (status bar)
    # ------------------------------------------------------------------
    def _on_game_timer_tick(self):
        """Count a second of game time while output is on (not Axis History's temporary Target)."""
        if self.activated and not self._history_target:
            self.game_seconds_total += 1
            hours, mins = self.game_seconds_total // 3600, (self.game_seconds_total // 60) % 60
            self.game_time_label.setText(f"Game Time: {hours:d}:{mins:02d}")

    def _on_game_time_label_double_click(self, event):
        """Reset the game time when the label is double-clicked."""
        self.game_seconds_total = 0
        self.game_time_label.setText("Game Time: 0:00")
        if event is not None:
            event.accept()
