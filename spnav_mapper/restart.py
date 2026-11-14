"""Safe UI-scale restart for source, standalone, and Nuitka Onefile builds.

A new copy uses --restart-ui-scale to wait for the original Windows mutex to
be released. The original exits through its existing closeEvent rather than
leaving the mapper running in the system tray.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .paths import entry_point

# v108.164: the restarted copy keeps the old copy's folder (and so its configs).
APP_DIR_ENV = "SPNAV_RESTART_APP_DIR"


def _nuitka_marker():
    """Nuitka's __compiled__ object, or None when not compiled by Nuitka."""
    try:
        return __compiled__  # type: ignore[name-defined]  # noqa: F821 (Nuitka marker)
    except NameError:
        return None


def compiled_program(executable, argv0, containing_dir=None, original_argv0=None):
    """The EXE the user started.

    v108.164: a Nuitka onefile EXE unpacks itself into a temporary folder and
    runs the copy there; sys.executable is that copy. Restarting it started
    the Mapper from the temporary folder, so its configs folder was there too:
    the loaded profile was not loaded again, and Load opened that folder. The
    EXE the user started is in argv[0] (and __compiled__.original_argv0), in
    the folder __compiled__.containing_dir.
    """
    candidates = []
    if original_argv0:
        candidates.append(Path(original_argv0))
    if containing_dir and argv0:
        candidates.append(Path(containing_dir) / Path(argv0).name)
    if argv0:
        candidates.append(Path(argv0))
    candidates.append(Path(executable))
    for candidate in candidates:
        if candidate.suffix.lower() == ".exe" and candidate.is_file():
            return candidate
    return Path(executable)


def successor_environment(app_dir, environ=None):
    """The restarted copy's environment: told this copy's folder, without Nuitka's onefile variables."""
    env = {
        k: v
        for k, v in (os.environ if environ is None else environ).items()
        if not k.upper().startswith("NUITKA_")
    }
    env[APP_DIR_ENV] = str(app_dir)
    return env


def build_restart_command(executable=None, argv0=None, project_root=None, compiled=None):
    """Command line that starts the Mapper again (EXE, script or package)."""
    return launch_command(
        "--restart-ui-scale", executable=executable, argv0=argv0, project_root=project_root, compiled=compiled
    )


def launch_command(*arguments, executable=None, argv0=None, project_root=None, compiled=None):
    """Command line that starts the Mapper (EXE, script or package) with `arguments`.

    v108.165: also the taskbar's Restore and Exit SpaceNavigator Mapper.
    """
    executable = str(executable or sys.executable)
    argv0 = str(argv0 if argv0 is not None else sys.argv[0])
    if project_root is None:
        from .paths import APP_DIR

        project_root = APP_DIR
    project_root = Path(project_root)
    marker = _nuitka_marker()
    if compiled is None:
        compiled = marker is not None or bool(getattr(sys, "frozen", False))
    if compiled:
        # The EXE the user started, never the onefile copy in a temporary
        # folder; never a Python source launcher.
        binary = compiled_program(
            executable,
            argv0,
            getattr(marker, "containing_dir", None) or project_root,
            getattr(marker, "original_argv0", None),
        )
        return [str(binary), *arguments]

    # Restart using the installed Python interpreter (including Python 3.15),
    # not a build venv. The .pyw suppresses a new console on Windows.
    binary = Path(executable)
    if sys.platform == "win32" and binary.name.lower() == "python.exe":
        pythonw = binary.with_name("pythonw.exe")
        if pythonw.is_file():
            binary = pythonw
    launcher = entry_point()
    if not launcher.is_file():
        launcher = Path(argv0).resolve()
    if not launcher.is_file():
        raise FileNotFoundError(f"Cannot locate SpaceNavigator Mapper entry point: {launcher}")
    return [str(binary), str(launcher), *arguments]


def restart_after_display_change(window):
    """Launch the successor, then close normally (bypassing close-to-tray)."""
    from .bootstrap import note

    try:
        command = build_restart_command()
        from .paths import APP_DIR

        note("Restart requested for new display scale: " + subprocess.list2cmdline(command))
        successor = subprocess.Popen(command, cwd=APP_DIR, close_fds=True, env=successor_environment(APP_DIR))
        # This window is in front (Display was just clicked), so it may let
        # the restarted copy come to the front of all windows.
        from .win32 import allow_foreground

        pid = getattr(successor, "pid", None)
        if pid:
            allow_foreground(pid)
    except (OSError, ValueError) as exc:
        note("Unable to restart after display change: " + repr(exc))
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.warning(
            window,
            "Display Size",
            "The new size was saved, but automatic restart failed: "
            + str(exc)
            + "\n\nPlease exit fully and relaunch.",
        )
        return False
    return close_for_successor(window, "Display Size")


def close_for_successor(window, title):
    """Close this copy (bypassing close-to-tray) so the one just started takes over."""
    from .bootstrap import note

    # Existing app close handles save/config, HID cleanup, and position memory.
    try:
        window._force_exit = True
        closed = window.close()
        if not closed:
            note("Restart: application close was not accepted; successor waits for mutex.")
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.warning(
                window,
                title,
                "A restart was launched but this window did not close. Please use Options → Exit.",
            )
            return False
        note(f"{title} restart: previous window closed successfully.")
        return True
    except Exception as exc:
        note("Restart window close error: " + repr(exc))
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.warning(
            window,
            title,
            "New version is starting, but the existing window could not close: " + str(exc),
        )
        return False
    finally:
        window._force_exit = False


# ShellExecute's answers of 32 and below are errors; 5 (access denied) is the
# Windows prompt declined.
SHELL_EXECUTE_OK = 32


def restart_as_administrator(window):
    """v108.174: start the Mapper again as administrator (Windows asks first), then close this one.

    Needed to send keys to a program that runs as administrator. The new copy
    comes back where this one was, with the same profile. The Windows prompt
    declined: nothing changes.
    """
    import ctypes

    from .bootstrap import note
    from .paths import APP_DIR

    command = build_restart_command()
    try:
        shell32 = ctypes.windll.shell32
        result = int(
            shell32.ShellExecuteW(
                None, "runas", command[0], subprocess.list2cmdline(command[1:]), str(APP_DIR), 1
            )
            or 0
        )
    except (OSError, AttributeError, ValueError) as exc:
        note("Restart as administrator failed: " + repr(exc))
        window.statusBar().showMessage("Could not restart as administrator: " + str(exc), 6000)
        return False
    if result <= SHELL_EXECUTE_OK:
        note(f"Restart as administrator not started (ShellExecute {result}).")
        window.statusBar().showMessage(
            "Not restarted as administrator: the Windows prompt was declined.", 6000
        )
        return False
    note("Restart as administrator: " + subprocess.list2cmdline(command))
    return close_for_successor(window, "Restart as Administrator")
