"""Profile files: new, load, save, save-as, backups (ProfilesMixin).

Every public action refreshes the window title and tray tooltip afterwards,
whichever way the action ends; the work itself is in the ``_..._impl``
methods.
"""

import json
import os

from PyQt5.QtWidgets import QFileDialog, QMessageBox

from ..auto_profiles import link_profile_to_program, unlink_profile_from_program
from ..backups import restore_backup, save_with_backup
from ..keyboard_io import combo_to_text
from ..paths import CONFIG_DIR, LAST_CONFIG_FILE, LAST_PATH_FILE
from ..settings import AXES, REVISION_DATE, VERSION, ensure_dir
from ..win32 import best_program_name, version_info_strings
from .save_reload_dialog import ask_save_reload_path
from .widgets import _auto_mode_from_config
from .window_chrome import refresh_title


class ProfilesMixin:
    # Public actions --------------------------------------------------------
    def load_config(self):
        """Load button: choose a profile file and load it."""
        result = self._load_config_impl()
        refresh_title(self)
        return result

    def load_last_config(self):
        """Load the profile used last (start-up)."""
        result = self._load_last_config_impl()
        self._shadow_loaded = os.path.isfile(LAST_CONFIG_FILE)
        refresh_title(self)
        return result

    def _load_config_from_path(self, path):
        """Load a profile file and refresh the title."""
        result = self._load_config_from_path_impl(path)
        refresh_title(self)
        return result

    def save_config(self):
        """Save as button: choose a file and save the profile."""
        result = self._save_config_impl()
        refresh_title(self)
        return result

    def save_config_quick(self, path=None):
        """Save the profile to `path`, else its current file; returns the path."""
        result = self._save_config_quick_impl(path)
        refresh_title(self)
        return result

    def save_reload_config(self):
        """Save/Reload: ask first, with the file name editable, then reload exactly the file written.

        v108.142: nothing is saved or reloaded unless confirmed. v108.148: a
        new name saves a new profile and loads it; the old file is kept.
        """
        current, _fallback = self._quick_save_destination()
        path = ask_save_reload_path(self, current)
        if not path:
            self.statusBar().showMessage("Save/Reload cancelled", 2000)
            return False
        try:
            saved = self.save_config_quick(path)
            if not saved:
                return False
            if not self._load_config_from_path(saved):
                return False
            name = os.path.basename(saved)
            renamed = os.path.normcase(os.path.abspath(saved)) != os.path.normcase(os.path.abspath(current))
            self.statusBar().showMessage(
                f"✔ Saved as {name} and reloaded" if renamed else f"✔ Saved and reloaded {name}", 3000
            )
            return True
        except Exception as exc:
            self.statusBar().showMessage(f"✖ Save/Reload failed: {exc}", 5000)
            return False

    def remove_linked_program(self):
        """Remove the program linked to the loaded profile, then save and reload it (v108.145).

        The profile keeps its binds; it just no longer names a target program,
        and Auto-Profiles stops loading it for that program.
        """
        try:
            return self._remove_linked_program_impl()
        finally:
            refresh_title(self)

    def linked_program(self):
        """(display name, exe path) of the program linked to the loaded profile, or None."""
        exe = self._target_program_path() or self.target_exe_path
        if not exe and not self.target_hwnd:
            return None
        name = (best_program_name(exe) if exe else "") or (
            os.path.basename(exe) if exe else "the target window"
        )
        return name, exe

    def _remove_linked_program_impl(self):
        """Confirm, then unlink the program, save and reload the profile."""
        path = self.profile_path
        if not path or not os.path.isfile(path):
            self.statusBar().showMessage("Load a profile first.", 3000)
            return False
        linked = self.linked_program()
        if linked is None:
            self.statusBar().showMessage("No program is linked to this profile.", 3000)
            return False
        program, exe = linked
        name = os.path.basename(path)
        shown = (
            f"{program} ({os.path.basename(exe)})" if exe and os.path.basename(exe) != program else program
        )
        text = f"Remove the linked program {shown} from {name}, then save and reload {name}?\n\n"
        if exe:
            text += f"Auto-Profiles will no longer load {name} for {os.path.basename(exe)}. "
        text += "The profile's previous contents are kept in the backups folder."
        try:
            answer = QMessageBox.question(
                self, "Delete Linked Program", text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
        except Exception:
            return False
        if answer != QMessageBox.Yes:
            self.statusBar().showMessage("Delete Linked Program cancelled", 2000)
            return False
        self.restore_target(None)
        self.target_exe_path = ""
        saved = self.save_config_quick()
        if not saved:
            self.statusBar().showMessage(
                "✖ The profile could not be saved; the link is unchanged on disk.", 6000
            )
            return False
        removed = unlink_profile_from_program(saved, exe) if exe else 0
        if not self._load_config_from_path(saved):
            return False
        note = f"; removed from {removed} Auto-Profiles group(s)" if removed else ""
        self.statusBar().showMessage(f"✔ {program} unlinked from {name}; saved and reloaded{note}", 6000)
        return True

    def load_backup_config(self, path):
        """Load a recovery copy without making the backup itself editable."""
        try:
            restored = restore_backup(path, CONFIG_DIR)
            if self._load_config_from_path(str(restored)):
                with open(LAST_PATH_FILE, "w", encoding="utf-8") as stream:
                    stream.write(str(restored))
                self.statusBar().showMessage(f"✔ Backup loaded as {restored.name}", 5000)
                return True
        except Exception as exc:
            self.statusBar().showMessage(f"✖ Load backup failed: {exc}", 5000)
        return False

    # Implementations -------------------------------------------------------
    def _save_config_impl(self):
        """Save as: ask for a .json path and write the profile there."""
        ensure_dir(CONFIG_DIR)
        cfg = self._profile_data()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Config", self._suggest_save_path(), "JSON Files (*.json)"
        )
        if not path:
            return None
        if not path.lower().endswith(".json"):
            path = path.rstrip(".") + ".json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            with open(LAST_PATH_FILE, "w", encoding="utf-8") as lf:  # Save/Reload writes here next
                lf.write(path)
            with open(LAST_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            self.profile_path = path
            self.profile_display.setText(os.path.splitext(os.path.basename(path))[0])
            self.statusBar().showMessage(f"✔ Config saved to {path}", 3000)
            self._link_to_its_program(path, cfg)
            self.rearm_edit_warning()
            return path
        except OSError as e:
            self.statusBar().showMessage(f"✖ Save failed: {e}", 5000)
            return None

    def _quick_save_destination(self):
        """(path, fallback) where Save/Reload writes: the active profile, else the
        last-used path, else (fallback True) a suggested one under CONFIG_DIR."""
        path = self.profile_path
        if not path:
            try:
                with open(LAST_PATH_FILE, encoding="utf-8") as lf:
                    path = lf.read().strip()
            except OSError:
                path = None
        if path:
            return path, False
        return self._suggest_save_path(), True

    def _save_config_quick_impl(self, path=None):
        """Save without a file dialog to `path`, else the active profile, else the
        last-used path, else a suggested path under CONFIG_DIR; also refresh last_config.json."""
        ensure_dir(CONFIG_DIR)
        cfg = self._profile_data()
        if path is None:
            path, _fallback = self._quick_save_destination()
        try:
            save_with_backup(path, cfg, os.path.join(CONFIG_DIR, "backups"))
            with open(LAST_PATH_FILE, "w", encoding="utf-8") as lf:
                lf.write(str(path))
            with open(LAST_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            self.statusBar().showMessage(f"✔ Saved to {path}", 3000)
            self._link_to_its_program(path, cfg)
            self.rearm_edit_warning()  # v108.171: saved; the next change warns again
            return path
        except Exception as e:
            self.statusBar().showMessage(f"✖ Save failed: {e}", 5000)
            return None

    def _link_to_its_program(self, path, cfg, quiet=False):
        """v108.170: list a profile with a target program in that program's Auto-Profiles group.

        Then Switch to… lists it, and Auto Load knows it. Before, only the
        profiles there when auto_profiles.json was first made were listed, so
        a profile made since, even with the same target, was in no rule.
        """
        exe = (cfg or {}).get("target_exe") or ""
        if not exe or not path:
            return ""
        try:
            result = link_profile_to_program(path, exe, (cfg or {}).get("target_app_name") or "")
        except (OSError, TypeError, ValueError):
            return ""
        if result == "added":
            manager = getattr(self, "_ap_mgr", None)
            if manager is not None:
                manager.reload()
            if not quiet:
                self.statusBar().showMessage(
                    f"✔ Saved to {path}; Auto-Profiles lists it for {os.path.basename(exe)}", 4000
                )
        return result

    def _read_profile(self, path):
        """(profile, migrated) read from a JSON file."""
        with open(path, encoding="utf-8") as f:
            return self._sanitize_config(json.load(f))

    def _apply_profile(self, cfg):
        """Put a profile's settings into every panel and control."""
        # First: a bind without its own Tap Dwell gets the profile's (v108.166).
        self.tap_down_ms = int(cfg.get("tap_down_ms", self.tap_down_ms))
        for name in AXES:
            if name in cfg.get("axes", {}):
                self.axes[name].set_config(cfg["axes"][name])
        self.restore_target(cfg.get("target"))
        self.target_exe_path = cfg.get("target_exe") or ""  # to find the target again
        self._resolve_target_if_running()
        self.quick_key1 = cfg.get("quick_key1")
        self.quick_key2 = cfg.get("quick_key2")
        self.key1_btn.setText(self._button_key_label(1))
        self.key2_btn.setText(self._button_key_label(2))
        led_on = cfg.get("led_on", False)
        self.led_chk.blockSignals(True)
        self.led_chk.setChecked(led_on)
        self.led_chk.blockSignals(False)
        try:
            self.spnav.set_led(led_on)
        except Exception:  # the device boundary: a failing LED never stops a load
            pass
        self.hys_pct = int(cfg.get("hys_pct", self.hys_pct))
        self.min_hold_ms = int(cfg.get("min_hold_ms", self.min_hold_ms))
        self.hold_ignore_max = bool(cfg.get("hold_ignore_max", self.hold_ignore_max))
        self._set_auto_select_mode(_auto_mode_from_config(cfg))
        self.version_str = VERSION
        self.lbl3.setText(f"{self.version_str}  {REVISION_DATE}")
        for field, key in ((self.comment1, "comment1"), (self.comment2, "comment2")):
            field.blockSignals(True)
            field.setText(str(cfg.get(key, "")))
            field.blockSignals(False)
        self.setWindowTitle(f"SPNav Key Mapper — {self.version_str}")

    def _button_key_label(self, which):
        """Button 1 / Button 2's label: its key combination, if any."""
        combo = self.quick_key1 if which == 1 else self.quick_key2
        return f"Button {which}: {combo_to_text(combo)}" if combo else f"Button {which}:"

    def _load_config_from_path_impl(self, path):
        """Read a profile file and apply it to every panel and control."""
        try:
            cfg, changed = self._read_profile(path)
            self._apply_profile(cfg)
            with open(LAST_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            self.statusBar().showMessage(
                f"✔ Config loaded{' (migrated)' if changed else ''} from {path}", 3000
            )
            self.profile_path = path
            self.profile_display.setText(os.path.splitext(os.path.basename(path))[0])
            self._apply_auto_mode_selection()
            self._link_to_its_program(path, cfg, quiet=True)
            self.rearm_edit_warning()
            return True
        except Exception as e:
            self.statusBar().showMessage(f"✖ Load failed: {e}", 5000)
            return False

    def _load_config_impl(self):
        """Show the open-file dialog and load the chosen profile."""
        path, _ = QFileDialog.getOpenFileName(self, "Load Config", CONFIG_DIR, "JSON Files (*.json)")
        if not path:
            return None
        return self._load_config_from_path_impl(path)

    def _load_last_config_impl(self):
        """Load last_config.json, the state at the last exit (no profile file is active)."""
        if not os.path.exists(LAST_CONFIG_FILE):
            return
        try:
            cfg, changed = self._read_profile(LAST_CONFIG_FILE)
            self._apply_profile(cfg)
            self.profile_path = None
            self._apply_auto_mode_selection()
            if changed:
                with open(LAST_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
            self.statusBar().showMessage(f"✔ Last config auto-loaded{' (migrated)' if changed else ''}", 3000)
        except Exception:
            pass

    # Helpers ---------------------------------------------------------------
    def _profile_data(self):
        """Everything a profile file stores, taken from the current window."""
        cfg = {
            "axes": {n: self.axes[n].get_config() for n in AXES},
            "target": self.target_hwnd,
            "quick_key1": self.quick_key1,
            "quick_key2": self.quick_key2,
            "comment1": self.comment1.text(),
            "comment2": self.comment2.text(),
            "led_on": self.led_chk.isChecked(),
            "hys_pct": self.hys_pct,
            "min_hold_ms": self.min_hold_ms,
            "hold_ignore_max": self.hold_ignore_max,
            "tap_down_ms": self.tap_down_ms,
            "auto_mode": bool(self.auto_chk.isChecked()),
            "auto_select_mode": self._get_auto_select_mode(),
            "version": self.version_str,
        }
        cfg.update(self._target_fields())
        return cfg

    def _target_fields(self):
        """The target program's profile fields, so Auto-Profiles and re-finding the
        target work later: its EXE and the names in its version information."""
        exe = self._target_program_path() or self.target_exe_path
        if not exe:
            return {
                "target_exe": "",
                "target_file_description": "",
                "target_product_name": "",
                "target_app_name": "",
            }
        try:
            info = version_info_strings(exe, keys=("FileDescription", "ProductName"))
            return {
                "target_exe": exe,
                "target_file_description": (info.get("FileDescription") or [""])[0],
                "target_product_name": (info.get("ProductName") or [""])[0],
                "target_app_name": best_program_name(exe),
            }
        except OSError:
            return {"target_exe": exe, "target_app_name": self._target_program_name()}

    @staticmethod
    def _sanitize_config(cfg):
        """(profile, migrated): the profile with old mode names upgraded ("Press-only")."""
        changed = False
        for axis_data in cfg.get("axes", {}).values():
            for b in axis_data.get("binds", []):
                if b.get("mode") == "Press-only":
                    b["mode"] = "Press/Release"
                    changed = True
        return cfg, changed

    def _suggest_save_path(self):
        """Default Save as path: the loaded profile, else configs/config.json."""
        ensure_dir(CONFIG_DIR)
        return self.profile_path or os.path.join(CONFIG_DIR, "config.json")
