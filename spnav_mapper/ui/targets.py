"""Target window list, picker and resolution for MainWindow (TargetsMixin)."""

import json

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QMenu, QMessageBox

from ..paths import LAST_CONFIG_FILE
from ..win32 import (
    best_program_name,
    current_process_id,
    format_target_item,
    is_omitted_target,
    list_windows,
    normalized_path,
    process_image_path,
    visible_windows,
    window_class,
    window_exe_path,
    window_pid,
)
from .widgets import AutoModeCombo

# The target picker's "Delete Linked Program" entry (its data; window handles are ints).
UNLINK_PROGRAM = "delete-linked-program"


class TargetsMixin:
    """Which program receives the keys: list, pick, remember, re-find."""

    _window_scan_pending = False  # True until the first window is shown
    _last_target_keys = ()  # the list's window handles after the last refresh

    def _target_program_path(self):
        """Executable path of the target window, or empty."""
        return window_exe_path(self.target_hwnd) if self.target_hwnd else ""

    def _target_program_name(self):
        """Readable name of the target program."""
        exe = self._target_program_path()
        return best_program_name(exe) if exe else ""

    def refresh_windows(self):
        """Refill the list of windows that can be targets (most recently used first)."""
        # Skip the EnumWindows / per-process lookups while the first window
        # is being constructed and painted (_after_show_window_scan runs it).
        if self._window_scan_pending:
            return
        before_keys = self._last_target_keys
        own_pid = current_process_id()
        exe_of = {}  # each window's EXE, looked up once
        filtered = []
        for hwnd, title in list_windows():
            if own_pid and window_pid(hwnd) == own_pid:
                continue  # the Mapper's own windows
            exe_of[hwnd] = window_exe_path(hwnd)
            if is_omitted_target(title, exe_of[hwnd], window_class(hwnd)):
                continue
            filtered.append((hwnd, title))
        titles = dict(filtered)
        recent = [(h, titles[h]) for h in self._recent_targets if h in titles]
        others = sorted(
            ((h, t) for h, t in filtered if h not in self._recent_targets),
            key=lambda x: (x[1] or "").lower(),
        )
        current = self.target_hwnd
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("[None]", None)
        for h, t in recent + others:
            self.combo.addItem(format_target_item(h, t), h)
        if current:
            for i in range(self.combo.count()):
                if self.combo.itemData(i) == current:
                    self.combo.setCurrentIndex(i)
                    break
        self.combo.blockSignals(False)
        if current:
            # The window may be gone: re-find the target by its saved EXE.
            want = normalized_path(self.target_exe_path)
            if want:
                for i in range(1, self.combo.count()):
                    hwnd_i = self.combo.itemData(i)
                    exe_i = exe_of.get(hwnd_i)
                    if exe_i and normalized_path(exe_i) == want:
                        self.combo.setCurrentIndex(i)
                        self.target_hwnd = hwnd_i
                        break
        after_keys = [self.combo.itemData(i) for i in range(self.combo.count())]
        self._last_target_keys = after_keys
        if after_keys != before_keys:
            self.statusBar().showMessage("Targets refreshed", 1200)

    def _refresh_windows_quietly(self):
        """refresh_windows for timers and events: an error is logged, never shown."""
        try:
            self.refresh_windows()
        except Exception as exc:
            from ..bootstrap import note

            note("Target list refresh failed: " + repr(exc))

    def _resolve_target_if_running(self) -> bool:
        """If the target program is running, make its window the target. True when found."""
        want = normalized_path(self.target_exe_path)
        if not want:
            return False
        try:
            windows = visible_windows()
        except (OSError, AttributeError):
            return False
        for hwnd in windows:
            exe = process_image_path(window_pid(hwnd))
            if exe and normalized_path(exe) == want:
                self.target_hwnd = hwnd
                self.target_exe_path = exe  # the path as Windows reports it
                self._target_rechecker.stop()  # found: no need to keep looking
                return True
        return False

    def _on_app_state_changed(self, state):
        """Refresh targets when the Mapper becomes active."""
        if int(state) == int(Qt.ApplicationActive):
            self._refresh_windows_quietly()

    def _maybe_auto_refresh_windows(self):
        """Background auto-refresh of window list to catch newly opened apps."""
        self._refresh_windows_quietly()

    def _remember_recent_target(self, hwnd):
        """Put a target window first in the list's most-recently-used order."""
        if hwnd in self._recent_targets:
            self._recent_targets.remove(hwnd)
        if hwnd:
            self._recent_targets.insert(0, hwnd)

    def set_target(self):
        """Make the window chosen in the list the target and recompute output."""
        self.target_hwnd = self.combo.currentData()
        self.statusBar().showMessage(f"Target: {self.combo.currentText()}", 2000)
        if self.auto_chk.isChecked():
            self._auto_recompute_activation()
        elif self._get_auto_select_mode() == AutoModeCombo.MODE_MANUAL_ON:
            self._set_activation(True, auto=False)
        self._remember_recent_target(self.target_hwnd)

    def _show_target_picker(self, _evt=None):
        """Click on the Profile name: the target list, with Delete Linked Program first.

        The profile's saved target is checked."""
        if not self.profile_path:
            self.statusBar().showMessage("Load a profile first (Load).", 2500)
            return
        try:
            with open(self.profile_path, encoding="utf-8") as stream:
                saved_target = json.load(stream).get("target")
        except (OSError, ValueError, AttributeError):
            saved_target = None
        self._refresh_windows_quietly()
        menu = QMenu(self)
        # v108.145: above [None], remove the program linked to the loaded
        # profile, then save and reload it (it asks first).
        unlink = menu.addAction("Delete Linked Program")
        unlink.setData(UNLINK_PROGRAM)
        linked = self.linked_program()
        unlink.setEnabled(linked is not None)
        unlink.setToolTip(
            f"Remove {linked[0]} from this profile, then save and reload it."
            if linked
            else "No program is linked to this profile."
        )
        menu.setToolTipsVisible(True)
        menu.addSeparator()
        preselect = None
        for i in range(self.combo.count()):
            hwnd = self.combo.itemData(i)
            act = menu.addAction(self.combo.itemText(i))
            act.setData(hwnd)
            if saved_target is not None and hwnd == saved_target and preselect is None:
                act.setCheckable(True)
                act.setChecked(True)
                preselect = act
        self._target_menu = menu  # kept alive while it is open
        chosen = menu.exec_(QCursor.pos(), preselect) if preselect is not None else menu.exec_(QCursor.pos())
        if chosen is None:
            return
        if chosen.data() == UNLINK_PROGRAM:
            self.remove_linked_program()
            return
        self._apply_target_from_menu(chosen.data(), chosen.text())

    def _apply_target_from_menu(self, hwnd, label):
        """Make the chosen window the target, offer to save it in the loaded profile, then
        (v108.174) offer to restart as administrator when the target runs as administrator."""
        try:
            self._apply_target_and_save(hwnd, label)
        finally:
            guard = getattr(self, "_elevation", None)
            if guard is not None:
                guard.check_target(hwnd)

    def _apply_target_and_save(self, hwnd, label):
        """Make the chosen window the target and offer to save it in the loaded profile."""
        self.target_hwnd = hwnd
        exe = self._target_program_path()
        if exe:
            self.target_exe_path = exe
        self.statusBar().showMessage(f"Target: {label}", 2000)
        self._remember_recent_target(hwnd)
        if self.auto_chk.isChecked():
            self._auto_recompute_activation()
        path = self.profile_path
        if not path:
            return
        answer = QMessageBox.question(
            self,
            "Save target to profile?",
            "Save this target to the currently loaded profile?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            try:
                with open(path, encoding="utf-8") as stream:
                    profile = json.load(stream)
            except (OSError, ValueError):
                profile = {}
            # The window and its program, so the target is found again next time
            # and Auto-Profiles can link the profile to the program.
            profile["target"] = hwnd
            profile.update(self._target_fields())
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(profile, stream, indent=2, ensure_ascii=False)
            with open(LAST_CONFIG_FILE, "w", encoding="utf-8") as stream:
                json.dump(profile, stream, indent=2, ensure_ascii=False)
            self.statusBar().showMessage("✔ Target saved to profile", 2000)
            self._link_to_its_program(path, profile, quiet=True)  # v108.170: and in its Auto-Profiles group
        except (OSError, TypeError, ValueError):
            self.statusBar().showMessage("✖ Failed to save target to profile", 3000)

    def restore_target(self, hwnd):
        """Re-select a saved target window, or clear the target."""
        if not hwnd:
            self.target_hwnd = None
            return
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == hwnd:
                self.combo.setCurrentIndex(i)
                break
        self.target_hwnd = hwnd
