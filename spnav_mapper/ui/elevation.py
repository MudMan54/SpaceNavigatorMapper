"""Programs running as administrator (v108.174).

Windows does not let a program that is not running as administrator send keys
to one that is (User Interface Privilege Isolation). The Mapper's SendInput
calls then succeed and do nothing, so a game or tool started "as
administrator" (some launchers and games ask for it) seemed to ignore the
Mapper. Running the Mapper as administrator too lets its keys through.

ElevationGuard notices it, and says so:
- when a target is picked that runs as administrator, it asks at once
  whether to restart the Mapper as administrator;
- when the Mapper sends keys while such a program is in front, the status
  bar says that they are blocked, and the tray icon says so once for that
  program in a session;
- Options > Restart as Administrator restarts it (Windows asks first) and it
  comes back where it was, with the same profile. When it already runs as
  administrator the item says so instead.

A program that cannot be told (None) is taken as not running as administrator:
the Mapper never warns without reason.
"""

import os

from PyQt5.QtWidgets import QAction, QMessageBox, QSystemTrayIcon

from .. import keyboard_io, win32

TITLE = "Program Running as Administrator"
RESTART_TEXT = "Restart as Administrator"
RUNNING_TEXT = "Running as Administrator"


def _note(message):
    """Write a line to the start-up log."""
    try:
        from ..bootstrap import note

        note(message)
    except Exception:
        pass


def _program_name(hwnd):
    """The program's file name (its window's title when that cannot be read)."""
    path = win32.window_exe_path(hwnd)
    if path:
        return os.path.basename(path.replace("\\", "/"))
    try:
        return win32.window_title(hwnd) or "This program"
    except Exception:
        return "This program"


class ElevationGuard:
    """Tells when the Mapper's keys cannot reach a program running as administrator."""

    def __init__(self, win, mapper_admin=None):
        """For window `win`; `mapper_admin` overrides asking Windows (tests)."""
        self.win = win
        self.mapper_admin = (win32.mapper_elevated() is True) if mapper_admin is None else bool(mapper_admin)
        self._cache = {}  # pid -> elevated (True / False / None)
        self._told = set()  # programs the tray has told about this session
        self._sent = keyboard_io.SENT_EVENTS
        _note("Running as administrator." if self.mapper_admin else "Not running as administrator.")

    def blocked(self, hwnd):
        """True when keys to window `hwnd` are blocked: it runs as administrator and the Mapper does not."""
        if self.mapper_admin or not hwnd:
            return False
        pid = win32.window_pid(hwnd)
        if pid not in self._cache:
            self._cache[pid] = win32.process_elevated(pid)
        return self._cache[pid] is True

    def tick(self, fg, allow):
        """Each GUI tick: keys sent to `fg` (output allowed) while it runs as administrator?"""
        sent, self._sent = keyboard_io.SENT_EVENTS - self._sent, keyboard_io.SENT_EVENTS
        if not sent or not allow or not self.blocked(fg):
            return False
        name = _program_name(fg)
        self.win.statusBar().showMessage(
            f"⚠ {name} runs as administrator: Windows blocks the Mapper's keys. Options > {RESTART_TEXT}.",
            6000,
        )
        if name not in self._told:
            self._told.add(name)
            _note(f"Keys blocked: {name} runs as administrator.")
            tray = getattr(self.win, "_tray", None)
            if tray is not None:
                tray.showMessage(
                    "SpaceNavigator Mapper",
                    f"{name} runs as administrator, so Windows blocks the Mapper's keys. "
                    f"Use Options > {RESTART_TEXT}.",
                    QSystemTrayIcon.Warning,
                    6000,
                )
        return True

    def check_target(self, hwnd):
        """A target was picked: when it runs as administrator, offer the restart now. True when asked."""
        if not self.blocked(hwnd):
            return False
        name = _program_name(hwnd)
        self._told.add(name)
        _note(f"Target {name} runs as administrator.")
        answer = QMessageBox.question(
            self.win,
            TITLE,
            f"{name} runs as administrator.\n\n"
            "Windows does not let a program that is not running as administrator send it keys, "
            "so the Mapper's keys would not reach it.\n\n"
            "Restart the Mapper as administrator now? Windows asks first; the Mapper comes back "
            "where it is, with the same profile.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            from ..restart import restart_as_administrator

            restart_as_administrator(self.win)
        return True


def install_elevation_guard(win, menu=None):
    """Make the window's guard, and its Options item (Restart as / Running as Administrator)."""
    win._elevation = ElevationGuard(win)
    if menu is None:
        return win._elevation
    if win._elevation.mapper_admin:
        item = QAction(RUNNING_TEXT, win)
        item.setCheckable(True)
        item.setChecked(True)
        item.setEnabled(False)
        item.setToolTip("The Mapper runs as administrator: its keys reach programs that do too.")
    else:
        item = QAction(RESTART_TEXT, win)
        item.setToolTip(
            "Start the Mapper again as administrator (Windows asks first), so its keys reach programs "
            "running as administrator. It comes back where it is, with the same profile."
        )

        def restart(*_args):
            from ..restart import restart_as_administrator

            restart_as_administrator(win)

        item.triggered.connect(restart)
    menu.addAction(item)
    win._elevation_action = item
    return win._elevation
