"""The profile's note in the Mapper window (v108.187): its dialog, and the profile name's flash.

Options > Profile Note… or a right-click on the profile name opens the note.
A note marked Important makes the profile name flash red and white when the
profile is loaded, until the note has been opened once (a click on the
flashing name opens it); after that the name stays red. That it has been
opened is remembered on this PC (v108.189): the name does not flash again at
the next load or the next start, until the note's text changes.

Save Note writes the note, and only the note, into the loaded profile's
file at once; the profile's other unsaved changes stay unsaved.
"""

import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..paths import CONFIG_DIR
from ..profile_note import (
    FLASH_MS,
    READ_PREFERENCE,
    UNREAD,
    clean_note,
    clean_read,
    flash_colour,
    name_state,
    name_tip,
    note_from_config,
    note_read,
    with_note_read,
    write_note_to_profile,
)
from .scaling import S

IMPORTANT_TIP = (
    "Ticked: the profile needs what the note says to work. Its name flashes red and white when the "
    "profile is loaded, until the note has been opened once; after that the name stays red.\n"
    "For a profile you share: it reminds its user that the game, or the Mapper, needs setting up too."
)
MENU_TIP = (
    "A note kept with the loaded profile: what the game or the Mapper needs set for it to work. "
    "Marked Important, it makes the profile name flash until it has been opened. "
    "Also a right-click on the profile name."
)


def profile_name(win):
    """The loaded profile's file name, or "" when none is loaded."""
    path = getattr(win, "profile_path", None)
    return os.path.basename(str(path)) if path else ""


NOTE_POINTS = 2.0  # without the drop-downs' font: the app's text size and this, as theirs is


def note_font(win):
    """The Profile Note window's font (v108.188): the font of the menu bar's drop-downs
    (Auto-Profiles, Options, Display), which is the app's text 2 points larger."""
    from .window_chrome import dropdown_font

    font = dropdown_font(win)
    if font is None:
        font = QFont(QApplication.font())
        if font.pointSizeF() > 0:
            font.setPointSizeF(font.pointSizeF() + NOTE_POINTS)
        elif font.pixelSize() > 0:
            font.setPixelSize(font.pixelSize() + 3)
    return font


def font_css_size(font):
    """A font's size for a style sheet: "12.0pt", or "16px" for a font sized in pixels."""
    return f"{font.pointSizeF():.1f}pt" if font.pointSizeF() > 0 else f"{font.pixelSize()}px"


class ProfileNoteDialog(QDialog):
    """The loaded profile's note: its text, Important, then Save Note or Close."""

    def __init__(self, win):
        """Build the dialog for the Mapper window `win`, showing the note it has now."""
        super().__init__(win)
        self.win = win
        name = profile_name(win)
        self.setWindowTitle(f"Profile Note — {os.path.splitext(name)[0]}" if name else "Profile Note")
        try:  # no "?" button in the title bar
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        except (AttributeError, TypeError):
            pass
        layout = QVBoxLayout(self)
        layout.setSpacing(S(10))
        intro = QLabel(
            "A note kept with this profile: what the game or the Mapper needs set for it to work "
            "(in-game key binds and settings, Run as Administrator, anything the profile cannot hold)."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(win.profile_note)
        self.text_edit.setPlaceholderText("Type the note here.")
        self.text_edit.setTabChangesFocus(True)
        self.text_edit.setMinimumSize(S(700), S(300))
        layout.addWidget(self.text_edit, 1)
        self.important_chk = QCheckBox("Important: the profile needs this to work (its name flashes)")
        self.important_chk.setChecked(bool(win.profile_note_important))
        self.important_chk.setToolTip(IMPORTANT_TIP)
        layout.addWidget(self.important_chk)
        self.where = QLabel(
            f"Save Note writes the note into {name} at once, and nothing else of the profile."
            if name
            else "No profile file is loaded: the note is kept with the settings. Save as writes it to a profile."
        )
        self.where.setWordWrap(True)
        layout.addWidget(self.where)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.save_btn = QPushButton("Save Note")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        # v108.188: the whole window, the note's text included, in the font of
        # the Auto-Profiles drop-down. A style sheet keeps a parent's font from
        # reaching its children, so each control gets it and the style sheets
        # carry the size too.
        self.note_font = note_font(win)
        size = font_css_size(self.note_font)
        self.setFont(self.note_font)
        for child in self.findChildren(QWidget):
            child.setFont(self.note_font)
        self.setStyleSheet(f"QWidget{{font-size:{size};}}")
        # A box like the comment fields', so it is seen on the dark window.
        self.text_edit.setStyleSheet(
            "QPlainTextEdit { background:#1f2937; color:#e5e7eb; border:1px solid #334155; "
            f"border-radius:4px; padding:4px; font-size:{size}; }}"
        )

    def save(self):
        """Save Note: keep the text and Important, write them to the profile file, and close."""
        save_note(self.win, self.text_edit.toPlainText(), self.important_chk.isChecked())
        self.accept()


def save_note(win, text, important):
    """Give the loaded profile this note, and write it into the profile's file. True when written.

    Only the note is written: the file's other contents stay as they are, so
    changes made in the editor and not yet saved are not saved by this. With
    no profile file loaded the note is kept with the settings, like any
    other change.
    """
    text = clean_note(text)
    win.profile_note, win.profile_note_important = text, bool(text and important)
    win._note_seen = True  # whoever writes it has read it
    remember_note_read(win)  # v108.189: at the next starts too
    path = getattr(win, "profile_path", None)
    written = False
    if path and os.path.isfile(str(path)):
        name = os.path.basename(str(path))
        try:
            write_note_to_profile(str(path), text, important, os.path.join(CONFIG_DIR, "backups"))
            written = True
            message = f"✔ Note saved in {name}" if text else f"✔ Note removed from {name}"
        except (OSError, ValueError) as exc:
            message = f"✖ The note could not be saved in {name}: {exc}"
    else:
        win.note_profile_edit()
        message = "Note kept with the settings: Save as writes it to a profile."
    refresh_note(win)
    win.statusBar().showMessage(message, 5000)
    return written


def note_read_here(win):
    """True when the loaded profile's note has been opened on this PC before (v108.189)."""
    from ..display_preferences import read_preferences

    known = clean_read(read_preferences().get(READ_PREFERENCE)) + list(getattr(win, "_notes_read", ()))
    return note_read(known, win.profile_note)


def remember_note_read(win):
    """Remember on this PC that the loaded profile's note has been opened (v108.189).

    Kept in ui_preferences.json by what the note says, so the profile name
    does not flash again at the next start; it does when the note's text has
    changed since. False when it could not be written: it is then remembered
    until the Mapper exits, and the name flashes once more at the next start.
    """
    from ..display_preferences import read_preferences, update_preference

    if not win.profile_note:
        return True  # no note: nothing to remember
    win._notes_read = with_note_read(getattr(win, "_notes_read", ()) or [], win.profile_note)
    stored = read_preferences().get(READ_PREFERENCE)
    if note_read(stored, win.profile_note):
        return True  # remembered already
    try:
        update_preference(READ_PREFERENCE, with_note_read(stored, win.profile_note))
    except OSError:
        return False
    return True


def open_profile_note(win):
    """Open the note's dialog; opening it counts as having read the note (the flash ends),
    here and at the next starts on this PC."""
    remember_note_read(win)
    if not win._note_seen:
        win._note_seen = True
        refresh_note(win)
    dialog = win._profile_note_dialog = ProfileNoteDialog(win)  # kept: the last one opened
    return dialog.exec_()


def take_note_from_profile(win, cfg):
    """A profile is being put into the window: take its note (not yet shown; see note_loaded())."""
    win.profile_note, win.profile_note_important = note_from_config(cfg)


def note_loaded(win):
    """After a load: the note counts as read when it has been opened on this PC before (v108.189).

    Before, it was unread at every load, so the name flashed again at every
    start, though the note had been opened.
    """
    win._note_seen = note_read_here(win)
    refresh_note(win)


def refresh_note(win):
    """Show the note's state on the profile name: its flash or colour, its tip, and the tray's tip."""
    state = name_state(win.profile_note, win.profile_note_important, win._note_seen)
    timer = win._note_flash_timer
    if state == UNREAD:
        if not timer.isActive():
            win._note_flash_phase = True  # red first
            timer.start()
    else:
        timer.stop()
    win.profile_display.set_name_colour(flash_colour(state, win._note_flash_phase))
    win.profile_display.setToolTip(name_tip(win.profile_note, win.profile_note_important, win._note_seen))
    from .window_chrome import refresh_title

    refresh_title(win)


def _flash_tick(win):
    """Twice a second while an important note is unread: the profile name's other colour."""
    win._note_flash_phase = not win._note_flash_phase
    state = name_state(win.profile_note, win.profile_note_important, win._note_seen)
    win.profile_display.set_name_colour(flash_colour(state, win._note_flash_phase))


def _name_pressed(win, event=None):
    """A click on the profile name: the note while it flashes, else the target list (a right-click: neither)."""
    try:
        if event is not None and event.button() == Qt.RightButton:
            return  # the context-menu event that follows opens the note
    except AttributeError:
        pass
    if name_state(win.profile_note, win.profile_note_important, win._note_seen) == UNREAD:
        open_profile_note(win)
        return
    win._show_target_picker(event)


def _name_right_clicked(win, event=None):
    """A right-click on the profile name opens the note."""
    try:
        if event is not None:
            event.accept()
    except AttributeError:
        pass
    open_profile_note(win)


def install_profile_note(win):
    """Give the Mapper window its note: no note yet, the flash timer, and the profile name's clicks."""
    win.profile_note, win.profile_note_important = "", False
    win._note_seen = True
    win._notes_read = []  # opened since the start, should the preferences not take it
    win._note_flash_phase = True
    win._note_flash_timer = QTimer(win)
    win._note_flash_timer.setInterval(FLASH_MS)
    win._note_flash_timer.timeout.connect(lambda: _flash_tick(win))
    win.profile_display.mousePressEvent = lambda event=None: _name_pressed(win, event)
    win.profile_display.contextMenuEvent = lambda event=None: _name_right_clicked(win, event)
    win.profile_display.setToolTip(name_tip("", False, True))


def add_profile_note_option(win, menu):
    """Add Options > Profile Note…"""
    from PyQt5.QtWidgets import QAction

    action = QAction("Profile Note…", win)
    action.setToolTip(MENU_TIP)
    action.triggered.connect(lambda _checked=False: open_profile_note(win))
    menu.addAction(action)
    win._profile_note_action = action
    return action
