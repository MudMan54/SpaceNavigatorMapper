"""Auto-Profiles menu, timer and status-bar label (AutoProfilesMixin)."""

import os
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QAction, QLabel, QMenu, QMessageBox

from ..auto_profiles import (
    AUTO_PROFILE_POLL_MS,
    AUTO_PROFILES_FILE,
    AutoProfileManager,
    open_in_os,
)
from ..paths import CONFIG_DIR
from ..win32 import best_program_name, foreground_window, is_own_window, window_exe_path, window_title
from .widgets import AutoModeCombo


def auto_load_status_style(mode):
    """Style sheet for the Auto-Load status badge (loaded, manual, waiting)."""
    base = "QLabel#apStatusLabel {  border-radius: 10px;  padding: 2px 8px;  font-weight: 700;}"
    if mode == "loaded":
        variant = (
            "QLabel#apStatusLabel {  background-color: #16a34a;  color: #ffffff;  border: 1px solid #15803d;}"
        )
    elif mode == "manual":
        variant = (
            "QLabel#apStatusLabel {  background-color: #2563eb;  color: #ffffff;  border: 1px solid #1d4ed8;}"
        )
    elif mode == "off":
        variant = (
            "QLabel#apStatusLabel {  background-color: #374151;  color: #d1d5db;  border: 1px solid #4b5563;}"
        )
    else:
        variant = (
            "QLabel#apStatusLabel {"
            "  background-color: transparent;"
            "  color: #fbbf24;"
            "  border: 1px solid #f59e0b;"
            "}"
        )
    return base + variant


def _same_path(a, b):
    """True when two paths name the same file ("" names none)."""
    if not a or not b:
        return False
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


EDIT_WARNING_TITLE = "Editing in Auto Load"
EDIT_WARNING = (
    "You are changing this profile while Auto Load is on.\n\n"
    "Auto Load loads a profile from its file whenever another program comes in front, "
    "so testing in another game, or a profile picked for it, can replace your changes "
    "before they are saved.\n\n"
    "Switch to Manual On while you edit and test? Choose Auto Load again once you have "
    "saved (Save/Reload)."
)


class AutoProfilesMixin:
    _ap_status_label = None  # the status-bar badge, made by _init_auto_profiles

    def _init_auto_profiles(self):
        """Set up Auto-Profiles: rules, menu, status badge and timer."""
        self._ap_mgr = AutoProfileManager()
        self._ap_mgr.load()
        self._ap_last = {"exe": "", "path": "", "ts": 0.0}
        # v108.165: profiles picked with Switch to…, by program (exe name).
        self._ap_chosen = {}
        # v108.171: the warning about editing in Auto Load, once a profile.
        self._edit_warned = False
        self._ap_enabled = True
        self._ap_timer = QTimer(self)
        self._ap_timer.setInterval(AUTO_PROFILE_POLL_MS)
        self._ap_timer.timeout.connect(self._auto_profiles_tick)
        self._ap_timer.start()
        self._inject_ap_menu()
        self._ap_status_label = QLabel("Auto-Load: Waiting")
        self._ap_status_label.setObjectName("apStatusLabel")
        self._ap_status_label.setMargin(2)
        self.statusBar().addPermanentWidget(self._ap_status_label, 1)
        self._ap_update_status_label()

    def _ap_update_status_label(self, path=None, state=None):
        """Show Auto-Load: Off, Manual On, the loaded profile or Waiting in the badge."""
        lbl = self._ap_status_label
        if lbl is None:  # a profile loaded while the window is being built
            return
        mode = self._get_auto_select_mode()
        if state == "OFF" or mode == AutoModeCombo.MODE_OFF:
            lbl.setText("Auto-Load: Off")
            lbl.setStyleSheet(auto_load_status_style("off"))
            return
        if state == "MANUAL" or mode == AutoModeCombo.MODE_MANUAL_ON:
            lbl.setText("Auto-Load: Manual On")
            lbl.setStyleSheet(auto_load_status_style("manual"))
            return
        if path is None:
            path = self._ap_last.get("path", "")
        if path:
            lbl.setText("Auto-Load: " + os.path.splitext(os.path.basename(path))[0])
            lbl.setStyleSheet(auto_load_status_style("loaded"))
        else:
            lbl.setText("Auto-Load: Waiting")
            lbl.setStyleSheet(auto_load_status_style("waiting"))

    def _ap_program_in_front(self):
        """(window, exe path, exe name, title, product name) of the program the rules look at.

        That is the window in front, or the target's window while the Mapper
        itself (its window, a dialog or a menu) is in front: its own window
        never matches a rule.
        """
        fg = foreground_window()
        if fg and is_own_window(fg):
            fg = self.target_hwnd
            exepath = (window_exe_path(fg) if fg else "") or self.target_exe_path
        else:
            exepath = (window_exe_path(fg) if fg else "") or ""
        title = window_title(fg) if fg else ""
        exe_base = os.path.basename(exepath) if exepath else ""
        product = (best_program_name(exepath) if exepath else "") or ""
        return fg, exepath, exe_base, title, product

    def _inject_ap_menu(self):
        """Build the Auto-Profiles menu in the menu bar."""
        menu = self.menuBar().addMenu("Auto-Profiles")

        # Enable toggle
        self.ap_act_enable = QAction("Enable Auto-Profiles", self)
        self.ap_act_enable.setCheckable(True)
        self.ap_act_enable.setChecked(self._ap_enabled)

        def _on_toggle_ap(enabled):
            self._ap_enabled = bool(enabled)
            self._ap_update_status_label()
            self.statusBar().showMessage("Auto-Profiles: ON" if enabled else "Auto-Profiles: OFF", 1500)

        self.ap_act_enable.toggled.connect(_on_toggle_ap)
        menu.addAction(self.ap_act_enable)

        # "Switch to…": the profiles whose rules match the program in front
        # (the target, while the Mapper's own menu is open).
        self.ap_menu_switch = QMenu("Switch to…", self)

        def _populate_switch_menu():
            self.ap_menu_switch.clear()
            _fg, _exepath, exe_base, title, product = self._ap_program_in_front()
            candidates = self._ap_mgr.candidates_for_current(exe_base, title, product)
            if not candidates:
                act = QAction("(No candidates for current app)", self)
                act.setEnabled(False)
                self.ap_menu_switch.addAction(act)
                return
            for abs_path, priority in candidates:
                act = QAction(f"{os.path.basename(abs_path)}  [priority {priority}]", self)
                act.triggered.connect(lambda _checked=False, p=abs_path: self._ap_manual_switch_to(p))
                self.ap_menu_switch.addAction(act)

        self.ap_menu_switch.aboutToShow.connect(_populate_switch_menu)
        menu.addMenu(self.ap_menu_switch)

        # Reload now
        self.ap_act_reload = QAction("Reload Auto-Profiles", self)

        def _on_reload():
            self._ap_chosen.clear()  # back to what the rules give
            self._ap_mgr.reload_if_changed()
            self._auto_profiles_tick(force=True, fresh=True)
            self.statusBar().showMessage("Auto-Profiles reloaded", 1200)

        self.ap_act_reload.triggered.connect(_on_reload)
        menu.addAction(self.ap_act_reload)

        # v108.165: no Tap dwell (ms)… here; a profile still keeps its tap_down_ms.
        # Open JSON
        self.ap_act_open_json = QAction("Open auto_profiles.json…", self)

        def _on_open_json():
            self._ap_mgr.load()
            open_in_os(AUTO_PROFILES_FILE, select=True)
            self.statusBar().showMessage("Opened auto_profiles.json", 1500)

        self.ap_act_open_json.triggered.connect(_on_open_json)
        menu.addAction(self.ap_act_open_json)

        # Open folder
        self.ap_act_open_folder = QAction("Open Auto-Profiles Folder…", self)

        def _on_open_folder():
            open_in_os(os.path.dirname(AUTO_PROFILES_FILE) or CONFIG_DIR, select=False)
            self.statusBar().showMessage("Opened Auto-Profiles folder", 1500)

        self.ap_act_open_folder.triggered.connect(_on_open_folder)
        menu.addAction(self.ap_act_open_folder)

    def note_profile_edit(self):
        """v108.171: the profile was changed in the editor; in Auto Load, offer Manual On (once)."""
        if self._edit_warned or not self.isVisible():
            return
        if self._get_auto_select_mode() != AutoModeCombo.MODE_AUTO_LOAD:
            return
        self._edit_warned = True
        # After the click or key that made the change has finished.
        QTimer.singleShot(0, self._offer_manual_on)

    def rearm_edit_warning(self):
        """A profile was loaded or saved, or Auto Load chosen: the next change warns again."""
        self._edit_warned = False

    def _offer_manual_on(self):
        """Ask to switch to Manual On while the profile is being edited."""
        if self._get_auto_select_mode() != AutoModeCombo.MODE_AUTO_LOAD:
            return
        answer = QMessageBox.question(
            self, EDIT_WARNING_TITLE, EDIT_WARNING, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if answer == QMessageBox.Yes:
            self._set_auto_select_mode(AutoModeCombo.MODE_MANUAL_ON, emit=True)
            self.statusBar().showMessage(
                "Manual On while you edit: choose Auto Load again after Save/Reload.", 6000
            )
        else:
            self.statusBar().showMessage("Auto Load kept: save your changes before testing.", 5000)

    def _ap_manual_switch_to(self, abs_path):
        """Load a profile picked from Switch to….

        v108.165: the pick stays for that program. Before, Auto Load loaded
        the top-priority profile again as soon as the program was back in
        front, within a second.
        """
        _fg, _exepath, exe_base, _title, _product = self._ap_program_in_front()
        if not self._load_config_from_path(abs_path):
            return  # the status bar says why
        if exe_base:
            self._ap_chosen[exe_base.lower()] = abs_path
        self._ap_last["path"] = abs_path
        self.statusBar().showMessage(f"Switched to: {os.path.basename(abs_path)}", 1500)
        self._ap_update_status_label(abs_path)

    def _auto_profiles_tick(self, force=False, fresh=False):
        """In Auto Load, load the profile that matches the program in front.

        v108.171: a profile that is loaded and already one of that program's
        is never loaded again from its file (unless `fresh`: Reload
        Auto-Profiles). Before, going back to the game with the second of
        two profiles for it loaded (or one opened with Load) loaded the
        first from its file, and the changes not yet saved were gone.
        """
        if not self.auto_chk.isChecked():
            return
        if not self._ap_enabled and not force:
            return
        try:
            self._ap_mgr.reload_if_changed()  # the rules file was edited
        except Exception:
            pass
        fg = foreground_window()
        # The Mapper's own window, dialogs and menus change nothing: editing a
        # profile there and going back to the game must not reload it.
        if not fg or is_own_window(fg):
            return
        exepath = window_exe_path(fg) or ""
        exe_base = os.path.basename(exepath) if exepath else ""
        title = window_title(fg)
        product = (best_program_name(exepath) if exepath else "") or ""

        # Debounce
        now = time.perf_counter()
        if not force:
            if exe_base == self._ap_last.get("exe", "") and now - float(self._ap_last.get("ts", 0.0)) < 1.0:
                return
        pick = self._ap_mgr.pick_profile_for(exe_base, title, product) or ""
        current = getattr(self, "profile_path", None) or ""
        if pick and current and not fresh and not _same_path(pick, current):
            listed = self._ap_mgr.candidates_for_current(exe_base, title, product)
            if any(_same_path(path, current) for path, _priority in listed):
                pick = current  # the loaded profile is one of this program's: keep it
        chosen = "" if pick == current else self._ap_chosen.get(exe_base.lower(), "")
        if chosen and pick:
            # Picked with Switch to… for this program, and its rules still list it.
            listed = self._ap_mgr.candidates_for_current(exe_base, title, product)
            if any(os.path.abspath(path) == os.path.abspath(chosen) for path, _priority in listed):
                pick = chosen
        self._ap_last["exe"] = exe_base
        self._ap_last["ts"] = now
        if not pick:
            self._ap_last["path"] = ""
            self._ap_update_status_label("")
            return
        if _same_path(pick, self._ap_last.get("path", "")) or (
            not fresh and current and _same_path(pick, current)
        ):
            # Loaded already: never again from its file, so edits not yet saved stay.
            self._ap_last["path"] = pick
            self._ap_update_status_label(pick)
            return
        if not self._load_config_from_path(pick):
            self._ap_last["path"] = ""
            self._ap_update_status_label("")
            return
        # The program in front is the target now.
        self.target_exe_path = exepath
        self.target_hwnd = fg
        self._auto_recompute_activation(fg)
        self.statusBar().showMessage(f"Auto-loaded: {os.path.basename(pick)}", 2000)
        self._ap_last["path"] = pick
        self._ap_update_status_label(pick)
