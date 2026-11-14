"""Save/Reload's prompt, with the file name editable (v108.148).

Keeping the name saves over the loaded profile and reloads it, as before.
A new name saves the settings as a new profile in the same folder and loads
that one; the file loaded before stays as it is.
"""

import os
import re

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from .scaling import S

# configs/ files that hold the Mapper's own settings, never a profile.
SETTINGS_STEMS = {"last_config", "auto_profiles", "ui_preferences", "window_state"}
_DEVICE_NAMES = {"con", "prn", "aux", "nul"} | {f"{port}{n}" for port in ("com", "lpt") for n in range(1, 10)}
_BAD_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def profile_stem(text):
    """The typed name without the spaces around it or a ".json" ending."""
    name = (text or "").strip()
    if name.lower().endswith(".json"):
        name = name[:-5].rstrip()
    return name


def name_problem(stem):
    """Why `stem` cannot name a profile file, or "" when it can."""
    if not stem:
        return "Type a file name."
    if _BAD_CHARACTERS.search(stem):
        return 'A file name cannot contain \\ / : * ? " < > |'
    if stem.endswith((".", " ")):
        return "A file name cannot end with a dot or a space."
    if stem.lower() in _DEVICE_NAMES:
        return f"{stem} is a name Windows keeps for itself."
    if stem.lower() in SETTINGS_STEMS or stem.lower().startswith("window_"):
        return f"{stem}.json holds the Mapper's own settings; choose another name."
    return ""


class SaveReloadDialog(QDialog):
    """The file to save and reload: its name, editable, then Save/Reload or Cancel."""

    def __init__(self, parent, path):
        """Build the prompt for saving to `path` (the name can be changed)."""
        super().__init__(parent)
        self.setWindowTitle("Save/Reload")
        try:  # no "?" button in the title bar
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        except (AttributeError, TypeError):
            pass
        self.folder = os.path.dirname(path)
        self.current = os.path.splitext(os.path.basename(path))[0]
        self.current_exists = os.path.isfile(path)

        layout = QVBoxLayout(self)
        layout.setSpacing(S(10))
        layout.addWidget(QLabel("Save the current settings to this file, then reload it:"))
        row = QHBoxLayout()
        row.addWidget(QLabel("File name:"))
        self.name_edit = QLineEdit(self.current)
        self.name_edit.setToolTip(
            "Keep the name to save over this profile, or type a new one for a new profile."
        )
        self.name_edit.selectAll()
        row.addWidget(self.name_edit, 1)
        row.addWidget(QLabel(".json"))
        layout.addLayout(row)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.save_btn = QPushButton("Save/Reload")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        self.name_edit.textChanged.connect(self._update)
        self._update()
        self.setMinimumWidth(S(560))

    def chosen_path(self):
        """The file to save and reload, or None while the name cannot be used."""
        stem = profile_stem(self.name_edit.text())
        if name_problem(stem):
            return None
        return os.path.join(self.folder, stem + ".json")

    def is_new_name(self):
        """True when the name differs from the loaded profile's."""
        return os.path.normcase(profile_stem(self.name_edit.text())) != os.path.normcase(self.current)

    def _update(self, *_args):
        """Say what Save/Reload will do with the name typed; disable it for a name that cannot be used."""
        stem = profile_stem(self.name_edit.text())
        problem = name_problem(stem)
        self.save_btn.setEnabled(not problem)
        if problem:
            note = problem
        elif not self.is_new_name():
            note = (
                "The file's previous contents are kept in the backups folder."
                if self.current_exists
                else f"A new profile, {stem}.json, is saved."
            )
        else:
            if os.path.isfile(os.path.join(self.folder, stem + ".json")):
                note = (
                    f"{stem}.json already exists: it is replaced, and its previous contents "
                    "are kept in the backups folder."
                )
            else:
                note = f"A new profile, {stem}.json, is saved and loaded."
            if self.current_exists:
                note += f" {self.current}.json stays as it is."
        self.note.setText(note)


def ask_save_reload_path(parent, path):
    """Show the prompt for `path`; the file to save and reload, or None when cancelled."""
    dialog = SaveReloadDialog(parent, path)
    try:
        return dialog.chosen_path() if dialog.exec_() else None
    finally:
        dialog.deleteLater()
