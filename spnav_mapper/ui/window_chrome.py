"""Window icon, title, taskbar/tray, close-to-tray and the Display menu.

* The title and tray tooltip name the loaded profile.
* "Close to System Tray": the X button hides the window and mapping keeps
  running; "Exit SpaceNavigator Mapper" always quits.
* The Display menu changes the interface size and restarts the app.
* Auto-start with Windows starts the app hidden in the tray.
"""

import json
import os
from ctypes import wintypes

from PyQt5.QtCore import QEvent, QTimer
from PyQt5.QtGui import QFont, QGuiApplication, QIcon
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QFileDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)

from ..backups import list_backups
from ..display_preferences import (
    UI_SCALE_FACTORS,
    auto_start_is_enabled,
    numeric_choice,
    set_auto_start,
    update_preference,
)
from ..paths import APP_DIR, CONFIG_DIR, LAST_CONFIG_FILE, RESOURCE_DIR
from ..settings import ensure_dir
from ..single_instance import exit_message_id, is_exit_message, is_restore_message, restore_message_id
from .axis_history_window import add_axis_history_option
from .editor_fit import prepare_full_scroll
from .placement import (
    connected_screen,
    positions_monitor,
    restore_window_placement,
    save_window_placement,
    set_positions_monitor,
)

PREFS_FILE = os.path.join(CONFIG_DIR, "ui_preferences.json")


def _icon_candidates():
    """A user icon beside the app first, then the bundled one."""
    for filename in (
        "SpaceNavigatorMapper.ico",
        "SpaceNavigatorMapper.png",
        "SpaceNavigatorMapper_default.ico",
    ):
        for root in dict.fromkeys((APP_DIR, RESOURCE_DIR)):
            yield os.path.join(root, filename)


def application_icon():
    """The Mapper's icon, from resources or the single file."""
    for candidate in _icon_candidates():
        if os.path.isfile(candidate):
            icon = QIcon(candidate)
            if not icon.isNull():
                return icon
    # The single-file edition carries the icon inside the script.
    embedded = globals().get("_single_file_icon")
    if embedded:
        import base64

        from PyQt5.QtGui import QPixmap

        pixmap = QPixmap()
        pixmap.loadFromData(base64.b64decode(embedded), "ICO")
        return QIcon(pixmap)
    return QIcon()


def _profile_label(win):
    """The loaded JSON profile (not the foreground game/target)."""
    if win.profile_path:
        return os.path.splitext(os.path.basename(str(win.profile_path)))[0] or "Unnamed"
    name = win.profile_display.text().strip()
    if name and name.lower() not in ("[none]", "none"):
        return name
    if getattr(win, "_shadow_loaded", False):
        return "Last configuration"
    return "No configuration loaded"


def refresh_title(win):
    """Show the loaded profile in the window title and tray tip."""
    name = _profile_label(win)
    # Windows displays this window title in the taskbar hover preview.
    caption = "SpaceNavigator Mapper — " + name
    # Windows tray tooltip limit is 127 UTF-16 chars on some versions.
    tray_tip = ("SpaceNavigator Mapper\nLoaded: " + name)[:125]
    if win.windowTitle() != caption:
        win.setWindowTitle(caption)
    tray = getattr(win, "_tray", None)
    if tray is not None and tray.toolTip() != tray_tip:
        tray.setToolTip(tray_tip)


def restore_from_taskbar(win):
    """Show the window again: from the tray, the taskbar or a second launch."""
    win.showNormal()
    win.raise_()
    win.activateWindow()
    # A Windows-login launch was never visible before the first restore:
    # apply the saved placement once its native window exists.
    if getattr(win, "_started_hidden", False):
        win._started_hidden = False
        restore_window_placement(win)
    # v108.163: monitors connected or changed while it was hidden (a sign-in
    # launch can start before every monitor is ready): offer a restart.
    from .monitor_watch import check_monitors_soon

    check_monitors_soon(win)


# configs/ files that are not profiles.
NOT_PROFILES = {
    "last_config.json",
    "auto_profiles.json",
    "ui_preferences.json",
    "window_state.json",
}


def profile_items():
    """(name, path, modified) for every profile in the configs folder, sorted by name."""
    items = []
    try:
        ensure_dir(CONFIG_DIR)
        for fn in os.listdir(CONFIG_DIR):
            low = fn.lower()
            if not low.endswith(".json") or low in NOT_PROFILES or low.startswith("window_"):
                continue
            path = os.path.join(CONFIG_DIR, fn)
            if os.path.isfile(path):
                try:
                    modified = os.path.getmtime(path)
                except OSError:
                    modified = 0
                items.append((os.path.splitext(fn)[0], path, modified))
    except OSError:
        pass
    items.sort(key=lambda item: item[0].lower())
    return items


def exit_for_second_launch(win):
    """The taskbar's Exit SpaceNavigator Mapper (a launch with --exit): exit as Options > Exit does."""
    try:
        from ..bootstrap import note

        note("The taskbar's Exit SpaceNavigator Mapper asked the running copy to exit.")
    except Exception:
        pass
    exit_application(win)


def show_for_second_launch(win):
    """Another launch found this copy running: show it, in front of all windows.

    Hidden in the tray, it is shown the same way as Restore from the tray:
    by Qt, so it is painted (Windows showing it directly left it white).
    Minimized, it comes back at its size (the editor cannot be maximized).
    """
    if win.isVisible():
        if win.isMinimized():
            win.showNormal()
        win.raise_()
        win.activateWindow()
    else:
        restore_from_taskbar(win)
    try:
        from ..win32 import bring_to_front

        bring_to_front(int(win.winId()))
    except (RuntimeError, OSError, AttributeError, TypeError, ValueError):
        pass
    try:
        from ..bootstrap import note

        note("Another launch asked the running copy to show itself.")
    except Exception:
        pass


def fill_tray_profiles(win, menu):
    """The tray's Profiles submenu: every profile in the configs folder, the active one checked."""
    menu.clear()
    current = getattr(win, "profile_path", "") or ""
    current = os.path.abspath(current) if current else ""
    items = profile_items()
    if not items:
        menu.addAction("No profiles in the configs folder").setEnabled(False)
        return
    group = QActionGroup(menu)
    group.setExclusive(True)
    for name, path, _modified in items:
        choice = QAction(name.replace("&", "&&"), menu)
        choice.setCheckable(True)
        choice.setChecked(bool(current) and os.path.abspath(path) == current)
        choice.setToolTip(path)
        choice.triggered.connect(lambda _checked=False, w=win, p=path: activate_profile_from_tray(w, p))
        group.addAction(choice)
        menu.addAction(choice)
    menu._profile_group = group  # keep the group alive with the menu


def activate_profile_from_tray(win, path):
    """Load `path` as the active profile, as the editor's Load button does."""
    name = os.path.splitext(os.path.basename(path))[0]
    loaded = bool(win._load_config_from_path(path))  # the status bar says why when it fails
    win._refresh_windows_quietly()
    tray = getattr(win, "_tray", None)
    if tray is not None:
        if loaded:
            tray.showMessage(
                "SpaceNavigator Mapper", f"Active profile: {name}", QSystemTrayIcon.Information, 2500
            )
        else:
            tray.showMessage("SpaceNavigator Mapper", f"Could not load {name}", QSystemTrayIcon.Warning, 4000)
    return loaded


def _add_window_controls(win):
    """Adds the window controls (Options menu, tray icon) after the editor is built."""
    view = view_menu(win)  # created here; renamed "Options" with the Display menu
    minimize = QAction("Minimize to Taskbar", win)
    minimize.setToolTip("Keep SpaceNavigator Mapper running while minimized")
    minimize.triggered.connect(win.showMinimized)
    view.addAction(minimize)

    try:
        # Notification-area icon is OPTIONAL. The regular Windows taskbar
        # entry stays available even when no system tray is present.
        if QSystemTrayIcon.isSystemTrayAvailable():
            tray = QSystemTrayIcon(win)
            icon = win.windowIcon()
            if icon.isNull():
                icon = application_icon()
            if not icon.isNull():
                tray.setIcon(icon)
            menu = QMenu(win)
            restore = menu.addAction("Restore SpaceNavigator Mapper")
            restore.triggered.connect(lambda *_: restore_from_taskbar(win))
            minimize_tray = menu.addAction("Minimize to Taskbar")
            minimize_tray.triggered.connect(win.showMinimized)
            menu.addSeparator()
            # Profiles: pick one to load and make it the active profile,
            # without opening the window.
            profiles = menu.addMenu("Profiles")
            profiles.aboutToShow.connect(lambda w=win, m=profiles: fill_tray_profiles(w, m))
            fill_tray_profiles(win, profiles)
            win._tray_profiles_menu = profiles
            menu.addSeparator()
            exit_app = menu.addAction("Exit SpaceNavigator Mapper")
            exit_app.triggered.connect(lambda _checked=False, w=win: exit_application(w))
            grow_menu_fonts(menu, TRAY_MENU_EXTRA_POINTS)  # Profiles too
            tray.setContextMenu(menu)

            def _tray_activated(reason):
                if reason == QSystemTrayIcon.DoubleClick:
                    restore_from_taskbar(win)

            tray.activated.connect(_tray_activated)
            win._tray = tray
            win._tray_menu = menu  # kept with the window
            tray.show()
    except Exception as exc:  # a tray that fails is left out; the taskbar entry remains
        from ..bootstrap import note

        note("System tray icon unavailable: " + repr(exc))
    # Every profile load and save refreshes the title; this sets the first one.
    refresh_title(win)


def read_close_preference():
    """True when X closes to the system tray."""
    try:
        with open(PREFS_FILE, encoding="utf-8") as stream:
            saved = json.load(stream)
        if not isinstance(saved, dict):
            return False
        # Retain the user's prior checkbox choice from v108.73-v108.80.
        return bool(saved.get("close_to_system_tray", saved.get("minimize_to_taskbar_on_close", False)))
    except (OSError, ValueError, TypeError):
        return False


def write_close_preference(enabled):
    """Store the Close to System Tray choice."""
    # Atomic replace: never leave half-written settings after a forced exit.
    ensure_dir(CONFIG_DIR)
    values = {}
    try:
        with open(PREFS_FILE, encoding="utf-8") as stream:
            old = json.load(stream)
            if isinstance(old, dict):
                values = old
    except (OSError, ValueError, TypeError):
        pass
    values["close_to_system_tray"] = bool(enabled)
    # Do not keep an out-of-date parallel setting in the JSON file.
    values.pop("minimize_to_taskbar_on_close", None)
    temporary = PREFS_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(values, stream, indent=2, ensure_ascii=False)
    os.replace(temporary, PREFS_FILE)


def _set_close_preference(win, checked):
    """Apply and store the Close to System Tray choice."""
    win._close_to_tray = bool(checked)
    try:
        write_close_preference(bool(checked))
    except OSError as exc:
        win.statusBar().showMessage("Could not save close preference: " + str(exc), 5000)


def exit_application(win):
    """Close the window for real (not to the tray), which shuts down."""
    # The X button is intercepted when close-to-tray is selected.
    # An explicit Exit command must bypass that behavior to release HID,
    # stop input and persist the final configuration as before.
    win._force_exit = True
    try:
        win.close()
    finally:
        win._force_exit = False


def view_menu(win):
    """The Options menu (created when missing)."""
    for action in win.menuBar().actions():
        if action.text().replace("&", "").strip().lower() in ("view", "options"):
            return action.menu()
    return win.menuBar().addMenu("View")


def _add_close_menu(win):
    """Add Close to System Tray and prepare Exit."""
    view = view_menu(win)
    choice = QAction("Close to System Tray", win)
    choice.setCheckable(True)
    choice.setChecked(bool(win._close_to_tray))
    choice.setToolTip(
        "When checked, X hides the window in the notification area; mapping continues. Restore from the tray icon."
    )
    choice.toggled.connect(lambda checked, w=win: _set_close_preference(w, checked))
    view.addAction(choice)

    # Without an explicit Exit in View, a user who hides the tray icon
    # would have no convenient way to close the process with X intercepted.
    exit_action = QAction("Exit SpaceNavigator Mapper", win)
    exit_action.triggered.connect(lambda _checked=False, w=win: exit_application(w))
    win._exit_action = exit_action


def _add_display_menu(win):
    """Add the rest of Options and the Display menu."""
    view = view_menu(win)

    def toggle_auto_start(enabled):
        try:
            set_auto_start(bool(enabled))
            win.statusBar().showMessage(
                "Start with Windows: " + ("on (hidden in system tray)" if enabled else "off"), 5000
            )
        except (OSError, ValueError) as exc:
            action.blockSignals(True)
            action.setChecked(not bool(enabled))
            action.blockSignals(False)
            QMessageBox.warning(win, "Start with Windows", str(exc))

    # v108.144: no separator lines in Options (after Close to System Tray,
    # before Exit).
    action = QAction("Auto-start in System Tray with Windows", win)
    action.setCheckable(True)
    try:
        action.setChecked(auto_start_is_enabled())
    except (OSError, ImportError):
        action.setChecked(False)
    action.setToolTip(
        "Start with Windows sign-in, hidden in notification area. Manual launches still show the window."
    )
    action.toggled.connect(toggle_auto_start)
    view.addAction(action)

    view.setTitle("Options")
    view.addAction(win.led_chk)
    add_axis_history_option(win, view)  # v108.149
    backup_menu = view.addMenu("Load Backup")
    # v108.174: Restart as Administrator (or Running as Administrator).
    from .elevation import install_elevation_guard

    install_elevation_guard(win, view)
    view.addAction(win._exit_action)

    def load_backup(path):
        win.load_backup_config(str(path))

    def browse_backups():
        directory = os.path.join(CONFIG_DIR, "backups")
        path, _ = QFileDialog.getOpenFileName(
            win, "Load Backup Configuration", directory, "JSON Files (*.json)"
        )
        if path:
            load_backup(path)

    def refresh_backups():
        backup_menu.clear()
        try:
            backups = list_backups(os.path.join(CONFIG_DIR, "backups"))
            for path in backups[:30]:
                choice = backup_menu.addAction(path.name.replace("&", "&&"))
                choice.triggered.connect(lambda checked=False, p=path: load_backup(p))
            if not backups:
                backup_menu.addAction("No backups yet").setEnabled(False)
        except OSError as exc:
            backup_menu.addAction("Backups unavailable").setEnabled(False)
            win.statusBar().showMessage(f"Could not list backups: {exc}", 5000)
        backup_menu.addSeparator()
        backup_menu.addAction("Browse all backups…", browse_backups)

    backup_menu.aboutToShow.connect(refresh_backups)
    # Display: one size for the interface and its fonts (the app restarts), then Positions Saved.
    display_menu = win.menuBar().addMenu("Display")
    key = "ui_scale_factor"
    # The same 100% fallback as start-up marks a size that is no longer offered.
    current = numeric_choice(key, UI_SCALE_FACTORS)
    group = QActionGroup(win)
    group.setExclusive(True)
    for factor in UI_SCALE_FACTORS:
        choice = QAction("Auto / Default (100%)" if factor == 1.0 else f"{round(factor * 100)}%", win)
        choice.setCheckable(True)
        choice.setChecked(abs(current - factor) < 0.001)
        choice.setToolTip("Scale interface and fonts together; restarts automatically.")
        group.addAction(choice)
        display_menu.addAction(choice)

        def choose(_checked=False, factor=factor):
            try:
                if abs(numeric_choice(key, UI_SCALE_FACTORS) - factor) < 0.001:
                    win.statusBar().showMessage("That interface/font size is already selected.", 3000)
                    return
                update_preference(key, factor)  # profiles are not changed
            except OSError as exc:
                QMessageBox.warning(win, "Display Size", "Could not save setting: " + str(exc))
                return
            win.statusBar().showMessage("Applying interface + font size and restarting...", 3000)
            # After the menu's dispatch completes; closeEvent then saves the window state.
            from ..restart import restart_after_display_change

            QTimer.singleShot(0, lambda: restart_after_display_change(win))

        choice.triggered.connect(choose)

    display_menu.addSeparator()
    positions = display_menu.addMenu("Positions Saved")
    positions.setToolTipsVisible(True)
    positions.aboutToShow.connect(lambda w=win, m=positions: _fill_positions_menu(w, m))
    _fill_positions_menu(win, positions)


def monitor_label(screen, index):
    """'Display 2 — 2560 × 1440, 100%  (primary)', from Windows' own numbers when available."""
    name = screen.name()
    short = name.rsplit("\\", 1)[-1] or f"Monitor {index}"
    if short.upper().startswith("DISPLAY") and short[7:].isdigit():
        short = f"Display {short[7:]}"
    scale, primary = None, screen is QGuiApplication.primaryScreen()
    try:
        from .monitor_scale import native_monitors

        info = next((m for m in native_monitors() if m.get("name") == name), None)
    except Exception:  # not on Windows / no monitor API
        info = None
    if info and info.get("width") and info.get("height"):
        size = f"{info['width']} × {info['height']}"
        scale = f"{round(100 * int(info.get('dpi', 96) or 96) / 96)}%"
        primary = bool(info.get("primary", primary))
    else:
        g = screen.geometry()
        size = f"{g.width()} × {g.height()}"
    return f"{short} — {size}" + (f", {scale}" if scale else "") + ("  (primary)" if primary else "")


def _fill_positions_menu(win, menu):
    """One check box per connected monitor; at most one checked."""
    menu.clear()
    chosen = positions_monitor()
    chosen_screen = connected_screen(chosen)
    for index, screen in enumerate(QGuiApplication.screens(), 1):
        action = QAction(monitor_label(screen, index), menu)
        action.setCheckable(True)
        action.setChecked(chosen_screen is not None and screen.name() == chosen_screen.name())
        action.setToolTip(
            "Checked: the editor's position on this monitor is saved, and it always opens "
            "there, at start-up too. Unchecked: it opens centred."
        )
        action.toggled.connect(lambda on, w=win, s=screen: _choose_positions_monitor(w, s if on else None))
        menu.addAction(action)
    if chosen and chosen_screen is None:
        missing = QAction(f"{chosen['screen_name']} (not connected; the primary monitor is used)", menu)
        missing.setCheckable(True)
        missing.setChecked(True)
        missing.toggled.connect(lambda on, w=win: on or _choose_positions_monitor(w, None))
        menu.addAction(missing)


def _choose_positions_monitor(win, screen):
    """Positions Saved: save the position on a monitor (or none)."""
    try:
        set_positions_monitor(win, screen)
    except OSError as exc:
        win.statusBar().showMessage(f"Could not save Positions Saved: {exc}", 5000)
        return
    if screen is None:
        win.statusBar().showMessage("Positions Saved: no monitor; positions are not restored.", 5000)
    else:
        win.statusBar().showMessage(
            f"Positions Saved: {monitor_label(screen, 0).split('  (')[0]}. The editor opens there.", 5000
        )
        # Bring the current view to its saved position on that monitor now.
        restore_window_placement(win)


MENU_POINTS = 2.0  # the menus and submenus, above the app's text size
MENU_BAR_HEADING_POINTS = 3.0  # the headings in the menu bar


def _grown(font, points):
    """A copy of a font made larger by some points."""
    font = QFont(font)
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() + points)
    elif font.pixelSize() > 0:
        font.setPixelSize(font.pixelSize() + max(1, round(points * 96 / 72)))
    return font


def _keep_size(widget):
    """Make the widget's current font size explicit, so a parent's change skips it."""
    font = QFont(widget.font())
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF())
    elif font.pixelSize() > 0:
        font.setPixelSize(font.pixelSize())
    widget.setFont(font)


def enlarge_menu_bar_headings(win, points=1.0):
    """Make the menu-bar headings (Auto-Profiles, Options, Display) `points` larger.

    Only the headings: the title widgets in the menu bar's corner and the
    menus (sized by enlarge_menu_fonts) keep their font size.
    """
    bar = win.menuBar()
    for child in bar.findChildren(QWidget):
        if not isinstance(child, QMenu):
            _keep_size(child)
    for action in bar.actions():
        menu = action.menu()
        if menu is not None:
            _keep_size(menu)
    bar.setFont(_grown(bar.font(), points))


# The tray icon's right-click menu (and its Profiles submenu) is this much larger.
TRAY_MENU_EXTRA_POINTS = 2.0


def _menus_under(menus):
    """`menus` and all their submenus, each once."""
    out, seen = [], set()
    pending = [m for m in menus if m is not None]
    while pending:
        menu = pending.pop(0)
        if id(menu) in seen:
            continue
        seen.add(id(menu))
        out.append(menu)
        pending.extend(a.menu() for a in menu.actions() if a.menu() is not None)
    return out


def grow_menu_fonts(menus, points):
    """Make each menu and submenu `points` larger than it is now.

    Every new size is worked out before any is set, so a submenu grows by
    `points` once whether or not it inherits its parent menu's font.
    """
    if not isinstance(menus, (list, tuple)):
        menus = [menus]
    sized = [(menu, _grown(menu.font(), points)) for menu in _menus_under(menus)]
    for menu, font in sized:
        menu.setFont(font)


def enlarge_menu_fonts(win, points=1.0):
    """Make the menu-bar menus (Auto-Profiles, Options, Display) and their submenus `points` larger."""
    grow_menu_fonts([action.menu() for action in win.menuBar().actions()], points)


class WindowChromeMixin:
    def _init_window_chrome(self):
        """Set up the icon, menus, tray and title effect."""
        self.setWindowIcon(application_icon())
        # On startup, last_config.json is automatically loaded if the full
        # path was lost, and was intentionally given profile_path=None.
        self._shadow_loaded = bool(
            getattr(self, "_shadow_loaded", False)
            or (not self.profile_path and os.path.isfile(LAST_CONFIG_FILE))
        )
        _add_window_controls(self)
        restore_message_id()  # registered once, before a second launch asks
        exit_message_id()

    def nativeEvent(self, event_type, message):
        """Answer a second launch's "show yourself" message (single_instance)."""
        try:
            if message:
                msg = wintypes.MSG.from_address(int(message))
                if is_restore_message(msg.message):
                    QTimer.singleShot(0, lambda w=self: show_for_second_launch(w))
                    return True, 0
                if is_exit_message(msg.message):  # v108.165: the taskbar's Exit SpaceNavigator Mapper
                    QTimer.singleShot(0, lambda w=self: exit_for_second_launch(w))
                    return True, 0
        except Exception:  # never let an exception escape a native-event hook
            pass
        return super().nativeEvent(event_type, message)

    def _init_close_to_tray(self):
        """Read the Close to System Tray choice."""
        self._force_exit = False
        self._close_to_tray = read_close_preference()
        _add_close_menu(self)
        prepare_full_scroll(self)

    def _init_display_menu(self):
        """Build the Options and Display menus."""
        _add_display_menu(self)
        # Auto-Profiles, Options, Display and their submenus: two points
        # larger than the app's text, and the headings in the menu bar three,
        # at every Display size (before v108.154 only at 85%, so the menus
        # were no larger at 100% and the headings smaller).
        enlarge_menu_fonts(self, MENU_POINTS)
        enlarge_menu_bar_headings(self, MENU_BAR_HEADING_POINTS)
        # v108.160: a drop-down closes once the mouse has moved away from it.
        from .menu_autoclose import install_menu_autoclose

        install_menu_autoclose(self)
        # v108.165: a hover tip on every menu item.
        from .menu_tips import install_menu_tips

        install_menu_tips(self)

    def changeEvent(self, event):
        """v108.151: a maximize from the keyboard (Win+Up) or snapping is undone."""
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and self.isMaximized():
            QTimer.singleShot(0, self.showNormal)

    def closeEvent(self, event):
        """X: hide to the tray, or shut down."""
        if self._close_to_tray and not self._force_exit:
            # Remember the position, then hide. Do not run _shutdown_on_close:
            # it releases the HID device and writes last_config.json.
            save_window_placement(self)
            tray = getattr(self, "_tray", None)
            # Never strand a hidden process when Windows has no notification area.
            if tray is not None and tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable():
                event.ignore()
                self.hide()  # Hide removes taskbar button; HID/Qt timers keep running.
                return
            # No working tray: normal close safely shuts down the mapper.
        save_window_placement(self)
        return self._shutdown_on_close(event)

    def _shutdown_on_close(self, event):
        """Release keys, switch the LED off, save last_config.json and close the device."""
        # Button 1/2 and every bind's held key are released and macros stop,
        # so exiting never leaves a key down in the game.
        self.release_all_keys()
        try:
            self.spnav.set_led(False)
        except Exception:  # the device boundary: closing goes on
            pass
        try:
            ensure_dir(CONFIG_DIR)
            with open(LAST_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._profile_data(), f, indent=2, ensure_ascii=False)
        except OSError:
            pass
        try:
            self.spnav.close()
        except Exception:  # the device boundary
            pass
        super().closeEvent(event)
