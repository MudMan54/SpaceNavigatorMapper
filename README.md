# SpaceNavigator Mapper

Turn a 3Dconnexion SpaceNavigator into a game controller on Windows: each
axis direction and both buttons send the keys you choose to the game you
choose. Logic by Don Muddiman; code by Don Muddiman, ChatGPT and Claude.

## What it does

- **Six axes, six binds each.** Every bind has a direction (+, − or both), a
  Min%/Max% band, its own dead zone, a key combination and a mode:
  - *Hold*: the key stays down while the axis is in the band.
  - *Press/Release*: one tap on entering the band.
  - *Press/Repeat*: taps at a set interval while in the band.
  - *Release-only*: sends only the key-up.
  - *Tick*: one tap when the axis crosses Tick% moving outward.
  - *Macro*: plays the bind's steps (Tap, Down, Up, Delay). *Play: Once*
    plays them each time the axis enters the band; *Repeat* plays them again
    every *Repeat every* ms while it stays there, never two runs at once.
    Double-click the Bind button (or *Edit macro…*) to edit the steps. Turning
    the Target off, loading a profile or exiting stops a macro and releases
    the keys it holds.
- **NoBack + / NoBack −, per bind.** Right-click a Bind button to turn NoBack
  on for that bind, on the + side, the − side or both. Once a higher band on
  that side is reached, the bind stays quiet on the way back; binds without
  NoBack fire as usual. Centring the axis, dropping below every band or
  crossing to the other side rearms it. Every bind, Ticks too, counts as a
  band. A side the bind's Bind Dir does not include can be chosen too; it
  takes effect once the Bind Dir includes it. A bind with NoBack has a white
  line along its bottom that sweeps from the middle: left for NoBack −, right
  for NoBack +, both ways for both. The same menu has *Reset* for the axis.
- **Bind Dir at a glance.** A thin green line along the top of each Bind
  button sweeps from the middle: left for NEG, right for POS, both ways for
  FULL; no line for None.
- **Axis panels.** Each panel's border shows the axis and its value
  ("X: 0.00"), like the Quick Bind border.
- **Title.** Click "SpaceNavigator Mapper" in the menu bar to minimize the
  window to the taskbar; right-click it for a drop-down: *Open README (PDF)*
  opens the README, a PDF reference manual
  (`spnav_mapper/resources/SpaceNavigator_Mapper_README.pdf`), in your PDF
  viewer; *Open README in a window* shows the same text in the Mapper, with
  a Text size choice from 100% to 250% (remembered). With no PDF viewer, the
  PDF choice opens the window.
- **Delete Linked Program.** Click the Profile name: above [None] in the
  target list, it removes the program linked to the loaded profile, then
  saves and reloads the profile, after a confirm prompt. The profile is kept
  (its previous contents go to the backups folder) and is taken out of the
  Auto-Profiles groups for that program.
- **Manual On** never types into the Mapper itself: no keys are sent while
  its own window, a dialog or a menu is in front.
- **Buttons 1 and 2** on the device send their own key combinations.
- **Targets.** Output goes only to the chosen program while it is in front
  (*Auto Load*), always (*Manual On*), or never (*Off*).
- **Auto-Profiles.** Load a profile automatically for the program in front,
  using rules in `configs/auto_profiles.json` (menu: Auto-Profiles).
- **One window, saved position.** In *Display > Positions Saved*, check a
  monitor: the editor's position on it is saved and it always opens there, at
  start-up too (the primary monitor if it is not connected). With no saved
  position it opens in the middle of the screen. Each monitor is sized for its
  own resolution and Windows scale setting; on a monitor with less than
  1700 x 900 Qt pixels of room (1920 x 1080 at 125% or 150%) the editor and its
  fonts are drawn smaller, to the share of the screen it takes on 3840 x 2160
  at 225% (`scaling.fit_factor`). The title bar has no maximize button.
  After the Windows scale changes without signing out, Qt 5.15 starts with a
  default font of the wrong size (QTBUG-101951); `ui/system_font.py` gives it
  the size Windows meant.
- **Tray and start-up.** Close to the system tray, minimize to the taskbar,
  and start hidden in the tray when Windows starts. Right-click the tray icon >
  *Profiles* to make another profile active without opening the window. The
  tray menu's text is 2 points larger than the app's.
  Launching the Mapper again while it runs brings the running copy to the
  front, even from the tray.
- **Save/Reload** asks first, showing the file name. Keep it to save over the
  profile, or type a new name: the settings are saved as a new profile, which
  is then loaded; the old file stays as it is.
- **Axis History** (Options): records the last 30 seconds of every axis, the
  keys its binds send and where NoBack held one back, and shows them as a
  graph with each bind's start line. Right-click an axis panel's border to see
  that axis; Pause, Clear and Save as CSV are in the window.
- **Device LED** on the original SpaceNavigator, **profile backups** on every
  save, and interface sizes from 85% to 110% (menu: Display); one set of
  sizing rules for every size (`tests/test_display_sizes.py`).

Supported USB devices: SpaceNavigator (046D:C626), SpaceNavigator for
Notebooks (C628), SpaceTraveler (C623), SpacePilot (C625), SpaceExplorer
(C627) and SpacePilot Pro (C629). Only the original SpaceNavigator has been
tested with real hardware. No 3Dconnexion driver is needed.

## Run it

Windows 10 or 11 with Python 3.10 or newer:

```bat
py -m pip install -r requirements.txt
py main.py
```

`SpaceNavigatorMapper.pyw` starts it without a console window.
`RUN_DEBUG_WINDOWS.bat` keeps a console open, so you can see startup errors.
The startup log is `%LOCALAPPDATA%\SpaceNavigatorMapper\startup.log`; an
error in a button or menu after start-up is written there too, and the Mapper
keeps running.

### Single-file edition

```bat
py tools\build_single_file.py
```

This writes `dist\SpaceNavigator_Mapper_<version>_Complete.py`: one file with
every module and the icon inside. It runs with `py <file>` and keeps its own
`configs\` folder beside itself.

### EXE

Double-click `BUILD_EXE_WINDOWS.bat`. It installs [Nuitka](https://nuitka.net/)
and the app's packages, compiles the Python code to C and then to one
`SpaceNavigatorMapper.exe` (with the app's icon and its version in the file's
properties), and puts the EXE beside `main.py`, so both use the same
`configs\` folder. You need Python 3.10 or newer and a C compiler: Visual
Studio Build Tools ("Desktop development with C++"), or answer Yes when Nuitka
offers to download MinGW64. The first build takes several minutes; the
generated C code stays in `build\main.build`.

The EXE runs without Python installed. Compiled builds keep `configs\` beside
the EXE, and restart and auto-start use the EXE itself. Some antivirus tools
are suspicious of new single-file EXEs; if yours quarantines it, allow it for
this folder.

## Your settings

Everything is in `configs\` beside `main.py` (or the EXE). The folder is in
`.gitignore`, so your profiles are never committed.

| File | Holds |
|---|---|
| `*.json` | Your profiles |
| `last_path.txt`, `last_config.json` | The profile to open at start, and the state at the last exit |
| `auto_profiles.json` | Auto-Profiles rules |
| `window_state.json` | Each view's saved position on each monitor |
| `ui_preferences.json` | Interface size, close-to-tray, LED |
| `backups\` | A copy of the previous file on every save (never pruned) |

Environment variables for troubleshooting:

| Variable | Effect |
|---|---|
| `SPNAV_UI_SCALE=0.7` | Fixed layout scale instead of the automatic one (not fitted to small screens) |
| `SPNAV_UI_SCALE_MIN`, `SPNAV_UI_SCALE_MAX` | Limits for the automatic scale (default 0.45–1.15) |
| `SPNAV_PER_MONITOR_SCALE=0` | Same layout size on every monitor |

## Project layout

```
main.py                     start the app (also: py -m spnav_mapper)
spnav_mapper/
  bootstrap.py              logged startup, single-instance lock, error dialog
  app.py                    DPI setup, QApplication, main window, deferred scans
  version.py                VERSION and REVISION_DATE (the only place to change them)
  settings.py, paths.py     constants; where configs/ and the launcher are
  devices.py                HID reading and decoding, LED
  keyboard_io.py            scan codes and SendInput
  macros.py                 macro steps and their non-blocking player
  axis_history.py           axis history recording, summary, CSV, graph shapes, window view (no Qt)
  win32.py                  windows, processes, program names, target filter
  auto_profiles.py          Auto-Profiles rules (no Qt)
  backups.py                save with backup, restore
  display_preferences.py    interface size, Windows auto-start
  restart.py                restart after a Display change
  single_instance.py        one copy at a time; a second launch shows the running copy
  ui/
    main_window.py          MainWindow: the editor, input loop, buttons, activation
    axis_panel.py           one axis: six binds, Quick Bind, NoBack per bind, Tick
    targets.py              target list and picker
    profiles.py             load / save / save-as / backups
    save_reload_dialog.py   Save/Reload's prompt, with the file name editable
    axis_history_window.py  the Axis History window (several axes), its graphs and Options switch
    auto_profiles_menu.py   Auto-Profiles menu, timer, status label
    window_chrome.py        icon, title, tray, close-to-tray, Options and Display menus, closing
    placement.py            Display > Positions Saved; the editor's position per monitor
    editor_fit.py           sizing to content, re-fit after a monitor change
    monitor_scale.py        per-monitor scale factors (before QApplication)
    scaling.py              S()/Sf() sizes and readable control heights
    system_font.py          Qt's default font size after a Windows scale change (until sign-out)
    title_effect.py         hover shimmer on the title
    macro_editor.py         the macro step editor
    readme_viewer.py        the title's README drop-down: the PDF, or a window
    keyboard_popup.py, widgets.py, profile_marquee.py, ...
  resources/                the icon and the README (Markdown and PDF)
tests/                      pytest suite (see below)
tools/build_single_file.py  builds the single-file edition
tools/build_readme_pdf.py   updates the README's version and function list, prints the PDF
```

### The README

`spnav_mapper/resources/SpaceNavigator_Mapper_README.md` is the user's
README; edit it there. Then run:

```bat
py tools\build_readme_pdf.py
```

It rewrites the README's **Version:** line and its section 8 (every
function and method with the first line of its docstring), then prints
`SpaceNavigator_Mapper_README.pdf` beside it with [pandoc](https://pandoc.org)
and Chrome or Edge (`--md-only` skips the PDF). The tests fail when the
README no longer matches the source, or when a function has no docstring.

`MainWindow` is put together from mixins (`TargetsMixin`, `ProfilesMixin`,
`AutoProfilesMixin`, `WindowChromeMixin`). Its `__init__`
runs their setup steps in a fixed order; read it first.

## Development

```bat
py -m pip install -r requirements-dev.txt
py -m pytest
py -m ruff check .
py -m ruff format .
```

The tests need neither Windows, a display nor a device. `tests/fakeqt.py` is a
small stand-in for PyQt5, Win32, the registry and a HID SpaceNavigator, with
virtual time. `tests/session.py` starts the whole app on it, moves the axes,
clicks through the menus, and records what a user would see and every key sent.
`tests/test_session.py` checks those sessions, and `tests/test_noback.py`
checks NoBack and Tick against the real axis code, and `tests/test_placement.py`
checks placement on two monitors with different scale factors. GitHub Actions
runs all of this on every push.

These tests don't replace trying a change on Windows with the device.
Real Qt layout, fonts, multiple monitors, the tray and HID timing are only
modelled roughly.

Conventions:

- Catch specific exceptions. A broad `except Exception` belongs only at a real
  boundary (a Win32 call, the HID device, a file, a Qt callback that must
  never crash the app), and should log or show something.
- Change the version only in `spnav_mapper/version.py`, and add a line to
  `CHANGELOG.md`.
- Keep names free of version numbers. History goes in the changelog.

## License

MIT — see `LICENSE`. Use it, change it, share it; keep the copyright
notice, and it comes with no warranty.
