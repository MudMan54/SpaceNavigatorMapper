"""Start the Qt application: DPI setup, the main window, deferred scans."""

import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from .paths import CONFIG_DIR
from .ui import scaling as _ui_scaling
from .ui.editor_fit import FIT_CHECK_MS, install_screen_watch, log_editor_fit
from .ui.main_window import MainWindow
from .ui.monitor_watch import install_monitor_watch
from .ui.placement import restore_window_placement
from .ui.taskbar import install_taskbar_menu, remove_window_relaunch
from .ui.window_chrome import application_icon

RESTART_FRONT_DELAYS_MS = (250, 1000)
# After the first paint, so the Shell calls never delay the editor's showing.
TASKBAR_MENU_MS = 600


def _bring_to_front(win):
    """Raise and activate the window when it is visible and not minimized."""
    from .win32 import bring_to_front

    if not win.isVisible() or win.isMinimized():
        return
    try:
        win.raise_()
        win.activateWindow()
    except RuntimeError:
        return
    if bring_to_front(int(win.winId())):
        from .bootstrap import note

        note("Restarted window brought to the front.")


def run():
    """Create the Qt application and the main window, then run the event loop."""

    # --- High DPI awareness ---

    try:
        from PyQt5.QtCore import QCoreApplication, Qt

        QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

        QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(2)

        except Exception:
            pass

    except Exception:
        pass

    # A stable Windows taskbar AppUserModelID keeps the EXE/window icon grouped
    # as SpaceNavigator Mapper instead of a generic Python/Nuitka host.
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MudMan54.SpaceNavigatorMapper")
    except Exception:
        pass
    from .bootstrap import note as _startup_note

    # Fractional Windows scaling and one Qt scale factor per
    # monitor. Both must be decided before QApplication is constructed.
    try:
        from .display_preferences import UI_SCALE_FACTORS, numeric_choice
        from .ui import monitor_scale as _monitor_scale

        _monitor_scale.configure_before_qapplication(
            CONFIG_DIR, numeric_choice("ui_scale_factor", UI_SCALE_FACTORS), note=_startup_note
        )
    except Exception as exc:
        _startup_note("Monitor scaling setup skipped: " + repr(exc))
    _startup_note("Constructing QApplication...")
    app = QApplication(sys.argv)
    _startup_note("QApplication created.")
    # Qt's default quit-on-last-window-closed is required for explicit Exit.
    # In the tray path closeEvent is ignored and the window is hidden rather
    # than closed, so the event loop remains alive without changing this flag.
    try:
        app.setApplicationName("SpaceNavigator Mapper")
        app.setApplicationDisplayName("SpaceNavigator Mapper")
        app.setWindowIcon(application_icon())
    except Exception:
        pass

    _ui_scaling._apply_dynamic_scale(app)

    _startup_note("Constructing MainWindow...")
    w = MainWindow()
    _startup_note("MainWindow constructed.")
    # Remembered monitor and position (Options), always kept across a Display % restart.
    restore_window_placement(w, startup=True, keep="--restart-ui-scale" in sys.argv)
    install_screen_watch(w)
    install_monitor_watch(w)  # v108.163: monitors changed after start-up
    # v108.168: the window says which version runs, for a second start of another one.
    from . import single_instance
    from .version import VERSION

    single_instance.mark_window_version(int(w.winId()), VERSION)
    # v108.174: a start that is not administrator can still show or close this copy when it is.
    single_instance.accept_messages_from_lower(int(w.winId()))
    # v108.165: the taskbar button's right-click menu: Restore and Exit SpaceNavigator Mapper.
    QTimer.singleShot(TASKBAR_MENU_MS, lambda win=w: install_taskbar_menu(win))
    # Only a Windows-login auto-start includes this argument; manual launches
    # remain visible even when the menu checkbox is selected.
    _start_hidden = "--start-in-tray" in sys.argv
    try:
        tray = getattr(w, "_tray", None)
        if tray is None or not tray.isVisible():
            _start_hidden = False  # Never strand the app without a tray icon.
    except Exception:
        _start_hidden = False
    w._started_hidden = bool(_start_hidden)
    if _start_hidden:
        _startup_note("Windows login launch: starting hidden in system tray.")
    else:
        _startup_note("Showing main window...")
        w.show()
        _startup_note("Main window shown.")
        # v108.151: the log says whether the editor fits its monitor.
        QTimer.singleShot(FIT_CHECK_MS, lambda win=w: log_editor_fit(win))
        if "--restart-ui-scale" in sys.argv:
            # Restarted after a Display % change: in front of all windows,
            # once it is shown and again after placement has settled.
            for delay in RESTART_FRONT_DELAYS_MS:
                QTimer.singleShot(delay, lambda win=w: _bring_to_front(win))
    # The delayed calls occur after the event loop starts, allowing the main
    # window to receive its first paint before HID and target enumeration.
    QTimer.singleShot(180, w._after_show_device_scan)
    QTimer.singleShot(330, w._after_show_window_scan)
    # Look for the target program every second until it is found; started
    # now, after the deferred scans, so it never blocks the first paint.
    w._target_rechecker.start()
    _startup_note("Entering Qt event loop.")
    from . import bootstrap

    bootstrap.EVENT_LOOP_RUNNING = True
    code = app.exec_()
    remove_window_relaunch(w)  # as Windows asks, before the window is gone
    single_instance.unmark_window_version(int(w.winId()))
    sys.exit(code)
