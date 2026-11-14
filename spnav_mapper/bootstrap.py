"""Visible, logged startup for the SpaceNavigator Mapper modular application.

No third-party imports occur before diagnostics and the mutex are initialized.
Both the Python entry point and the Nuitka EXE use this exact startup path.
"""

from __future__ import annotations

import ctypes
import datetime
import os
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

from .version import VERSION

_LOG_PATH = None
_LOG_FILE = None
_FATAL_SHOWN = False
_START_MONOTONIC = time.perf_counter()


def log_path() -> Path:
    """Return a writable log path independent of EXE extraction or CWD."""
    global _LOG_PATH
    if _LOG_PATH is not None:
        return _LOG_PATH
    roots = []
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "SpaceNavigatorMapper")
    roots.append(Path.home() / "SpaceNavigatorMapper")
    roots.append(Path(tempfile.gettempdir()) / "SpaceNavigatorMapper")
    for root in roots:
        try:
            root.mkdir(parents=True, exist_ok=True)
            location = root / "startup.log"
            with location.open("a", encoding="utf-8"):
                pass
            _LOG_PATH = location
            return location
        except OSError:
            continue
    raise OSError("Cannot find a writable startup log location")


def note(message: str) -> None:
    """Append a line and echo it to the console when available."""
    timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"[{timestamp}] [+{time.perf_counter() - _START_MONOTONIC:.3f}s] {message}"
    try:
        p = log_path()
        if p.exists() and p.stat().st_size > 2_000_000:
            older = p.with_suffix(".previous.log")
            try:
                older.unlink(missing_ok=True)
                p.replace(older)
            except OSError:
                pass
        with p.open("a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        pass
    try:
        print(line, flush=True)
    except Exception:
        pass


def _message_box(title: str, message: str, *, error: bool = False) -> None:
    """Show a native Windows message box (works before Qt starts)."""
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(None, str(message), str(title), 0x10 if error else 0x40)
            return
        except Exception:
            pass
    try:
        print(f"{title}: {message}", file=sys.stderr)
    except Exception:
        pass


# True once the Qt event loop runs: from then on an error in a callback is
# logged (startup.log), and the window keeps working without a dialog.
EVENT_LOOP_RUNNING = False


def _show_failure(label: str, exc: BaseException, *, show_dialog: bool = True) -> None:
    """Log a failure; before the window runs, also show it once in a message box."""
    global _FATAL_SHOWN
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    if EVENT_LOOP_RUNNING:
        note(f"ERROR in {label}:\n{details}")
        return
    note(f"STARTUP ERROR in {label}:\n{details}")
    if show_dialog and not _FATAL_SHOWN:
        _FATAL_SHOWN = True
        _message_box(
            "SpaceNavigator Mapper — startup error",
            f"SpaceNavigator Mapper could not start ({label}).\n\n"
            f"{type(exc).__name__}: {exc}\n\n"
            f"Detailed log: {log_path()}\n\n"
            "Run RUN_DEBUG_WINDOWS.bat from the extracted project for more details.",
            error=True,
        )


def _install_exception_handlers() -> None:
    """Log uncaught exceptions from Python, threads and Qt callbacks."""

    def report_unhandled(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        if exc_value is None:
            exc_value = Exception(str(exc_type))
        _show_failure("uncaught Python/Qt callback", exc_value)

    sys.excepthook = report_unhandled
    try:

        def thread_excepthook(args):
            if args.exc_value is not None:
                _show_failure("background thread", args.exc_value)

        threading.excepthook = thread_excepthook
    except Exception:
        pass
    # Record hard crashes (e.g. Qt/C extension faults) even when no console exists.
    # Keep the stream alive for the process lifetime.
    global _LOG_FILE
    try:
        import faulthandler

        if _LOG_FILE is not None:
            try:
                faulthandler.disable()
                _LOG_FILE.close()
            except (OSError, ValueError):
                pass
        _LOG_FILE = log_path().with_name("fatal.log").open("a", encoding="utf-8")
        faulthandler.enable(file=_LOG_FILE, all_threads=True)
    except Exception:
        pass


# v108.165: the taskbar's Restore / Exit SpaceNavigator Mapper start the Mapper with these.
RESTORE_ARG, EXIT_ARG = "--restore", "--exit"


def launch() -> int:
    """Start UI and return an exit code; show/log all startup exceptions."""
    note(f"=== {VERSION} launch requested ===")
    note(f"Python: {sys.version.split()[0]}, executable: {sys.executable}")
    note(f"Platform: {sys.platform}, working directory: {os.getcwd()}")
    _install_exception_handlers()
    if sys.platform != "win32":
        note("This application requires Windows.")
        return 1
    try:
        from .single_instance import acquire_single_instance

        restarting = "--restart-ui-scale" in sys.argv
        if EXIT_ARG in sys.argv:
            # v108.165: the taskbar's Exit SpaceNavigator Mapper: the running
            # copy is asked to exit; with none running, nothing is started.
            from . import single_instance

            if acquire_single_instance(request="exit"):
                note("Exit requested, but no SpaceNavigator Mapper was running.")
            else:
                note(
                    "Asked the running SpaceNavigator Mapper to exit."
                    if single_instance.restored_existing
                    else "Exit requested: the running copy's window was not found."
                )
            return 0
        if restarting:
            # The old app exits via its normal closeEvent, which may persist
            # profiles/window state and briefly retain the named mutex.
            # Never restore/focus that old window during a restart handshake.
            deadline = time.monotonic() + 20.0
            acquired = False
            while time.monotonic() < deadline:
                if acquire_single_instance(restore_existing=False):
                    acquired = True
                    break
                time.sleep(0.15)
            if not acquired:
                note("Restart failed: previous process did not release instance lock.")
                _message_box(
                    "SpaceNavigator Mapper — restart blocked",
                    "The previous copy did not exit. Use the tray Exit command "
                    "and launch SpaceNavigator Mapper again.",
                    error=True,
                )
                return 1
        elif not acquire_single_instance(restore_existing=False):
            outcome = _another_copy_running()
            if outcome is not None:
                return outcome
        note("Single-instance lock acquired.")
    except BaseException as exc:
        _show_failure("single-instance lock", exc)
        return 1
    return _start_ui()


def _ask(title: str, message: str) -> bool:
    """A native Yes / No question (works before Qt starts); True for Yes."""
    if sys.platform != "win32":
        return False
    try:
        mb_yesno, mb_question, mb_foreground, idyes = 0x4, 0x20, 0x10000, 6
        flags = mb_yesno | mb_question | mb_foreground
        return ctypes.windll.user32.MessageBoxW(None, str(message), str(title), flags) == idyes
    except Exception:
        return False


# v108.168: how long a start waits for another version to exit when asked to.
OTHER_VERSION_EXIT_S = 8.0


def _another_copy_running():
    """Another copy holds the instance lock: show it, or replace another version.

    Returns the exit code for this launch, or None when the other copy has
    exited and this one may start (it then holds the lock).
    """
    from . import single_instance
    from .single_instance import acquire_single_instance

    windows = single_instance.find_running_windows()
    running = single_instance.running_version(windows)
    mine = single_instance.version_number(VERSION)
    if windows and running != mine and RESTORE_ARG not in sys.argv:
        # v108.168: another version is running (a copy from before v108.168
        # does not say which). Before, this start quietly showed it, so the
        # new version seemed to have none of its changes.
        known = single_instance.version_text(running)
        name = f"SpaceNavigator Mapper {known}" if known else "An older SpaceNavigator Mapper"
        note(f"Launch found {name} running; this is {VERSION}.")
        if _ask(
            "SpaceNavigator Mapper — another version is running",
            f"{name} is already running (perhaps hidden in the "
            f"notification area).\n\nExit it and start {VERSION}?",
        ):
            single_instance.post_to_windows(windows, single_instance.exit_message_id())
            deadline = time.monotonic() + OTHER_VERSION_EXIT_S
            while time.monotonic() < deadline:
                if acquire_single_instance(restore_existing=False):
                    note(f"{name} exited; starting {VERSION}.")
                    return None
                time.sleep(0.2)
            note(f"{name} did not exit.")
            _message_box(
                "SpaceNavigator Mapper — another version is running",
                f"{name} did not exit. Exit it from its tray icon "
                "(right-click > Exit SpaceNavigator Mapper) or with Options > Exit SpaceNavigator "
                f"Mapper, then start {VERSION} again.",
            )
            return 0
        note(f"Kept {name}; asked it to show itself.")
    shown = bool(windows) and single_instance.post_to_windows(windows, single_instance.restore_message_id())
    note(
        "Launch blocked: another SpaceNavigator Mapper is already running"
        + (" (asked it to show itself)." if shown else ".")
    )
    if shown:
        # v108.165: the running copy is in front; no message box (the
        # taskbar's Restore SpaceNavigator Mapper, or a second start).
        return 0
    _message_box(
        "SpaceNavigator Mapper — already running",
        "SpaceNavigator Mapper is already running.\n\n"
        "The other copy may be hidden in the notification area. To launch a different version, exit it first "
        "(Options > Exit SpaceNavigator Mapper).\n\n"
        f"Log: {log_path()}",
    )
    return 0


def _start_ui() -> int:
    """Run the Qt application once this copy holds the instance lock."""
    try:
        note("Importing the modular UI and device components...")
        from .app import run

        note("Core imported successfully; starting Qt UI...")
        run()
        note("Qt UI returned normally.")
        return 0
    except SystemExit as exc:
        status = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        note(f"Qt event loop exited with code {status}.")
        if status != 0:
            _show_failure("Qt event loop", RuntimeError(f"Qt exit code {status}"))
        return status
    except BaseException as exc:
        _show_failure("application startup", exc)
        return 1
