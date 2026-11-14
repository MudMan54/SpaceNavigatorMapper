"""Persistent, profile-independent UI settings and Windows login auto-start.

Only the user's HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
entry is modified; no administrator access or scheduled task is required.
"""

from __future__ import annotations

import json
import ntpath
import os
import subprocess
import sys
from pathlib import Path

from .paths import CONFIG_DIR, entry_point

PREFERENCES_PATH = Path(CONFIG_DIR) / "ui_preferences.json"
AUTOSTART_REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_VALUE_NAME = "SpaceNavigatorMapper"
UI_SCALE_FACTORS = (0.85, 1.0, 1.10)


def read_preferences():
    """Read ui_preferences.json, or an empty dict."""
    try:
        with PREFERENCES_PATH.open("r", encoding="utf-8") as stream:
            result = json.load(stream)
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def update_preference(key, value):
    """Store one value in ui_preferences.json."""
    # Retain Close-to-Tray and any previously saved options.
    current = read_preferences()
    current[key] = value
    PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = PREFERENCES_PATH.with_name(PREFERENCES_PATH.name + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(current, stream, indent=2, ensure_ascii=False)
    os.replace(temp, PREFERENCES_PATH)


def numeric_choice(key, valid, default=1.0):
    """A stored number when it is one of the offered choices, else the default."""
    try:
        value = float(read_preferences().get(key, default))
    except (TypeError, ValueError):
        return default
    return (
        min(valid, key=lambda x: abs(x - value)) if any(abs(x - value) < 0.0001 for x in valid) else default
    )


def registry_command(executable=None, project_root=None):
    """A real .exe at runtime, or pythonw.exe + .pyw in development.

    Both launch with --start-in-tray. The executable/project path is quoted
    with Windows command-line quoting so spaces in folders work correctly.
    """
    if executable is None:
        try:
            containing_dir = __compiled__.containing_dir
        except (NameError, AttributeError):
            pass
        else:
            # Nuitka keeps the user-launched EXE in argv[0], including in Onefile.
            # paths.py may already have changed the working directory.
            exe = Path(containing_dir) / Path(sys.argv[0]).name
            if exe.suffix.lower() != ".exe" or not exe.is_file():
                raise FileNotFoundError(f"Cannot locate the compiled Mapper executable: {exe}")
            return subprocess.list2cmdline([str(exe.resolve()), "--start-in-tray"])

    exe = os.path.abspath(executable or sys.executable)
    basename = ntpath.basename(exe).lower()
    frozen = getattr(sys, "frozen", False) or basename not in (
        "python.exe",
        "pythonw.exe",
        "python3.exe",
        "python3w.exe",
    )
    if frozen:
        args = [exe, "--start-in-tray"]
    else:
        if basename.startswith("python") and basename.endswith(".exe") and not basename.endswith("w.exe"):
            pythonw = os.path.join(os.path.dirname(exe), basename[:-4] + "w.exe")
            if os.path.exists(pythonw):
                exe = pythonw
        launcher = str(entry_point())
        if not os.path.isfile(launcher):
            raise FileNotFoundError("Windows launcher not found: " + launcher)
        args = [exe, launcher, "--start-in-tray"]
    return subprocess.list2cmdline(args)


def auto_start_is_enabled(registry=None):
    """True when the Windows Run entry starts the Mapper at sign-in."""
    if registry is None:
        import winreg as registry
    try:
        with registry.OpenKey(
            registry.HKEY_CURRENT_USER, AUTOSTART_REGISTRY_PATH, 0, registry.KEY_READ
        ) as key:
            value, _ = registry.QueryValueEx(key, AUTOSTART_VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def set_auto_start(enabled, registry=None, command=None):
    """Add or remove the Windows Run entry that starts the Mapper in the tray."""
    if registry is None:
        import winreg as registry
    if enabled:
        command = command or registry_command()
        with registry.CreateKey(registry.HKEY_CURRENT_USER, AUTOSTART_REGISTRY_PATH) as key:
            registry.SetValueEx(key, AUTOSTART_VALUE_NAME, 0, registry.REG_SZ, command)
    else:
        try:
            with registry.OpenKey(
                registry.HKEY_CURRENT_USER, AUTOSTART_REGISTRY_PATH, 0, registry.KEY_SET_VALUE
            ) as key:
                registry.DeleteValue(key, AUTOSTART_VALUE_NAME)
        except FileNotFoundError:
            pass
