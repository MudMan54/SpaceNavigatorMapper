# SpaceNavigator Mapper — Release notes

Release notes, newest first: the README of v108.115 and earlier, continued
with every update since. The user's README is the PDF reference manual,
`spnav_mapper/resources/SpaceNavigator_Mapper_README.pdf`: right-click the
"SpaceNavigator Mapper" title in the app to open it.

## v108.189 — An opened note stays read; Axis History asks Windows for the monitor

- **A note that has been opened is remembered on this PC.** The profile name
  of an important note flashes until the note has been opened once, and
  from then on stays red: at the next load and at the next start of the
  Mapper too. Before, it flashed again at every load of the profile, so at
  every start. What is remembered is what the note says
  (`profile_notes_read` in `ui_preferences.json`: a short mark of the text,
  `note_mark()`), not its file, so the profile can be renamed or saved
  under another name. The name flashes again when the note's text changes,
  and on a PC where it has not been opened. Writing or changing a note in
  its window counts as having read it.
- **Axis History asks Windows which monitor the editor is on**
  (`placement.window_screen()`), as the editor's own placement has since
  v108.163. With two monitors at different scale factors Qt can name the
  wrong one; opening the window attached then moved the editor to the top
  left of the other monitor.
- **Axis History that was open at the last exit opens again only once the
  editor is in its place** (`reopen_axis_history()`). At start-up the
  Mapper checks for 750 ms that Windows has the editor on its monitor and
  moves it back when not; the window opened at 600 ms and moved the editor
  aside in the middle of that.
- **Button 1 freezes and resumes Axis History, press after press**: pause,
  resume, pause, resume. As in v108.188; a test now goes through two rounds.
  Nothing is exported by the press: Export CSV/HTML stays a button.
- **`startup.log` says where the editor's position was saved** at exit or on
  hiding to the tray (monitor, position, size, the monitor checked in
  Positions Saved), next to the line that says where the next start
  restored it, and when Axis History moved the editor aside and back.
- **Not found: the editor starting on the primary monitor with the second
  one checked in Positions Saved** (reported on v108.188 with Axis History
  closed at the exit). The code that saves and restores the editor's
  position is the same as in v108.186, and the simulated two-monitor
  sessions restore it on the checked monitor. The two Axis History changes
  above remove the ways found by which v108.187 and v108.188 could move
  the editor to another monitor. If it happens again, the last lines of
  `startup.log` (`%LOCALAPPDATA%\SpaceNavigatorMapper`) show what was saved
  and what was restored.
- Untested on Windows, like v108.178 to v108.188.

## v108.188 — Axis History takes the screen beside the editor; Button 1 freezes it

- **Opening Axis History moves the editor aside** (Attach to editor ticked):
  to the top left of its monitor, its size unchanged, not stretched. The
  window takes the rest of that monitor: from the editor's right edge to the
  screen's right edge, over the full height of the work area
  (`history_beside()`, `editor_spot()`). In v108.187 the window was as tall
  as the editor and the editor moved only when there was no room.
- **Closing it puts the editor back** where, and as large as, it was before
  the window opened, always (v108.187 did not when the editor had been
  moved meanwhile). So do unticking Attach to editor and exiting with the
  window open: the position saved for the editor is its own.
- **The editor's place while the window is open is a setting of its own.**
  Move or resize the editor then and the window stays beside it; that place
  (and the size, if changed) is remembered per monitor
  (`axis_history_view.editor_spots` in `ui_preferences.json`) and used the
  next time the window opens. It never touches the editor's usual position
  (Positions Saved).
- **The window no longer drags the editor along.** Dragging the Axis History
  window by its title bar moves that window only; moving the editor brings
  it back beside the editor.
- **Button 1 on the SpaceNavigator freezes the graphs** while the window is
  open (`freeze_button_pressed()`): a press freezes, as Pause does, the next
  press resumes. From inside the game, without leaving it. Always Button 1,
  whatever it is bound to; while the window is open its own key is not
  sent, and with the window closed it is its bind's again. Button 2 is not
  affected.
- **Export CSV/HTML** is the Export button's name (it was Export…).
- **The Profile Note window's text**, the note's included, is in the font of
  the Auto-Profiles drop-down: the app's text 2 points larger
  (`note_font()`).
- Untested on Windows, like v108.178 to v108.187.

## v108.187 — Min Hold; a profile's note; Axis History beside the editor, with a chart export

- **Why a game could miss a Hold bind's key although it was sent.** A Hold
  bind holds its key while the axis is in its band, and a quick flick can be
  in a band for one 16 ms sample. The profile's 60 ms guard for that was
  passed by whenever the axis was more than 6% below the bind's Min%, so a
  bind with a high Min% (a prone bind at 59%) let its key go on the very next
  sample: key down, key up 16 ms later. The key was sent each time, as the
  history showed; some games do not act on a key held that briefly. (A Tick
  with a 175 ms Tap Dwell worked because its key is down 175 ms whatever the
  axis does.)
- **Min Hold**, per bind (`AxisPanel._hold_kept()`): the shortest time a Hold
  bind keeps its key down, 0 to 500 ms in steps of 5. The key still goes
  down at once; when the axis leaves the band sooner, the key-up waits until
  the key has been down that long. Coming back into the band meanwhile keeps
  the key down (one press). NoBack letting a lower bind go waits for it too.
  Output going off, switching the bind off or exiting lets go at once.
- **In Quick Bind it is the Tap Dwell line.** A Hold bind sends no taps, so
  in Hold mode that line and its − / + read and set **Min Hold**; in the
  tapping modes it is Tap Dwell as before (greyed out only in Release-only).
  No control was added and the editor's size is unchanged. Each bind keeps
  both values. A Bind button's tip names its Min Hold; Copy and Paste carry
  it; Reset axis clears it.
- **Saved with the profile, per bind** (`"min_hold_ms": 175` in the bind,
  left out at 0). A profile from before has none: every Hold bind works as
  it did. Tap Dwell was already saved per bind (since v108.166); a Tap Dwell
  that is not the profile's is now kept for a bind in another mode too, so
  trying Hold does not lose it. The profile's own `min_hold_ms` (60) is
  still the guard of a bind without a Min Hold.
- **A profile's note** (`profile_note.py`, `ui/profile_note_dialog.py`):
  Options > Profile Note…, or a right-click on the profile name. Text, an
  **Important** check box, Save Note. Save Note writes the note, and only
  the note, into the profile's file at once (`"note": {"text": …,
  "important": true}`, left out without text). For what the profile cannot
  hold: the game's own settings, Run as Administrator.
- **An important note flashes the profile name** red and white, once a
  second, when the profile is loaded, until the note has been opened once (a
  click on the flashing name opens it); after that the name stays red.
  Save/Reload, or Auto Load coming back to the same profile, does not start
  the flash again. The name's tip shows the note; the tray icon's tip says
  when an important note has not been opened.
- **Axis History keeps 10 seconds and shows 5** (it kept 30 and showed 5, 10
  or 30). A scroll bar under the graphs goes back over the rest; the times
  under each graph say what is in view. *Show the last* is gone.
- **Text that stands still.** While the graphs run, the dots have no labels:
  a label that crosses the window in five seconds cannot be read. The keys
  are listed under the graphs instead, the newest on top, in rows that change
  only when a key arrives: axis, bind, key, *held 176 ms* or *tap 45 ms*, the
  axis's value at the press and the key-up, and the time since the key
  before. Pause puts the labels back on the dots, now with the times
  (*CTRL up · held 176 ms*).
- **How long each key was down** is recorded with it: a key-up carries the
  time its key was held, a tap its Tap Dwell (`AxisHistory.add_event(…, ms)`).
- **Attach to editor** (ticked at first): the window is joined to the
  editor's right side, as tall as the editor and reaching the screen's right
  edge, and moves with it; dragged by its title bar, the editor comes along.
  With too little room beside the editor, the editor moves left first and
  goes back when the window closes; the editor's saved position is its own.
  Unticked: a window of its own, as before.
- **Export…** (it was Save as CSV…) saves the whole 10 seconds of the axes
  shown: the CSV, with a new last column `held_ms`, and beside it a chart
  report (`.html`, `axis_history_report.py`): each axis's graph, every
  setting of its binds with the ones that fired highlighted, and the keys in
  time order with how long each was down. One file, nothing to fetch.
- **Legend** shows or hides the explanation under the graphs (hidden at
  first); the controls are in three short rows, so the window can be narrow.
- A dot's label keeps clear of NoBack's labels and goes a line or two
  further from its dot before it is left out.
- Untested on Windows, like v108.178 to v108.186.

## v108.186 — A paused Axis History no longer drains away

- **Pause held the clock but not the picture.** The paused view still read
  the live history, whose rolling 30-second window kept trimming underneath,
  so after about 20 seconds the paused graphs slowly erased from left to
  right — too fast to analyse a stroke.
- **Pause now freezes a copy** of every axis's history at that moment. The
  graphs, the summary lines and *Save as CSV* all read the frozen copy, so
  the view holds for as long as needed while recording goes on underneath;
  *Resume* returns to live, and *Clear* still resumes first.
- Untested on Windows, like v108.178 to v108.185.

## v108.185 — A reset bind's button flickered; Reset keeps no old DZone

- **A Bind button flickered rapidly once a key was picked for it after
  Reset.** Two faults met. *Reset* put the axis's dead zone back to 5% but
  left each bind the DZone it had: a bind set to DZone 0% stayed at 0% and,
  reset to Full with Min 0%, counted as reached with the puck at rest. And a
  Bind button whose band is reached while no keys are being sent was greyed
  on every tick and restored by a timer 120 ms later, so it flickered some
  sixty times a second for as long as the band was held: with the Target
  off since long ago, and since v108.184 in Manual On too, where it showed
  at once.
- **Reset gives each bind its DZone back** (5%), with the rest of its
  settings. A bind just reset is no longer reached at rest. (With a key and
  the target program in front, such a bind in Hold would have held its key
  all the time.)
- **The Bind button blinks in step with the border** (`_update_band_blink()`):
  grey on the border's beat while its band is reached and no keys are being
  sent, its own style again at once when the band is left or the keys are
  being sent. No flicker, in any mode.
- A bind you set yourself to Full, Min 0% and DZone 0% is still reached at
  rest: that is what those settings say. Its button does not blink while the
  puck rests (the border is not blinking then).
- Untested on Windows, like v108.178 to v108.184.

## v108.184 — The border blinks in Manual On; green for the axis moved most

- **The axis borders did not blink in Manual On.** The blink was tied to the
  Target being off, and in Manual On the Target is always on. It now follows
  whether keys are being sent on that tick (`AxisPanel._sending`): the
  border blinks while the axis moves with the Target off, and with it on
  while the Mapper itself is in front (it never types into itself). So it
  blinks in Manual On as in Auto Load and Off while you work in the editor,
  and still not while the target program is in front. A Bind button's grey
  flash when its band is reached follows the same rule.
- **Green for the axis moved the most** (`MainWindow._axis_moved_most()`):
  of the axes beyond their dead zones, the one farthest from its centre
  blinks green; the others blink blue as before. The puck rarely moves one
  axis alone, and this shows which axis a push really is.
- **A Bind button's tip starts with the axis and the direction**: *Z axis,
  Bind #2: POS (+)*, kept up to date with the Bind Dir.
- Untested on Windows, like v108.178 to v108.183.

## v108.183 — Switch a bind off and on

- **Bind Enabled**, a check mark at the top of a Bind button's right-click
  menu (`AxisPanel._set_bind_enabled()`). Unticked, the bind is switched
  off: it keeps all its settings and its comment but sends nothing. Ticked
  again, it is as it was. For trying a profile without one bind, or keeping
  a spare bind ready.
- A bind that is switched off takes no part: it is no band for the NoBack
  or Rebound of the other binds, and nothing of it shows in Axis History.
  Switched off while it holds a key or plays a macro, it lets go at once.
- Its Bind button is ghosted (still dashed-outlined when selected), without
  its Bind Dir line, NoBack line and Rebound dot, and its tip says it is
  switched off. Being a check mark, a click on it leaves the menu open.
- Saved with the profile (`"enabled": false`, written only for a bind that
  is off); a profile from before has every bind on. Copy and Paste carry
  it; Reset axis switches every bind on.
- Untested on Windows, like v108.178 to v108.182.

## v108.182 — Undo Paste

- **Undo Paste** on a Bind button's right-click menu, under Paste. A paste
  replaced a bind without asking and could not be taken back. What the bind
  was (its settings and its comment) is now kept before each paste, and
  *Undo Paste*, from any bind's menu on any axis, puts it back; the bind
  lets go of its key first and starts from rest, as with a paste.
- One step: the last paste only, and once. It is ghosted when there is
  nothing to undo, and its tip names the bind it would put back. Loading
  that bind's axis from a profile, or resetting the axis, leaves nothing to
  undo. The status bar says what was undone; an undo counts as a change to
  the profile.
- Untested on Windows, like v108.178 to v108.181.

## v108.181 — Copy and Paste a bind

- **Copy and Paste on a Bind button's right-click menu** (`bind_copy.py`,
  `AxisPanel._copy_bind()` / `_paste_bind()`). *Copy* takes everything that
  makes the bind what it is: its keys, Bind Dir, Mode, Min%, Max%, DZone, Tap
  Dwell, the Press/Repeat time, NoBack, the Rebound time, its macro, and its
  comment. *Paste* replaces another bind with all of it: a bind of the same
  axis, of another axis, or, after loading another profile, of that profile.
- The copy is the Mapper's own (not Windows' clipboard), kept while the
  Mapper runs, and can be pasted any number of times. Changing the copied
  bind afterwards does not change the copy.
- *Paste* is ghosted until a bind has been copied; its tip names the bind
  the copy came from. The status bar says what was copied and where it went.
- A bind that is pasted into stops first (a held key is released, a playing
  macro stopped) and starts from rest. A paste counts as a change to the
  profile, like any edit (in Auto Load the Manual On question comes up).
- Untested on Windows, like v108.178 to v108.180.

## v108.180 — The dot is clear of the Bind button's text

- **Blank space at both sides of the label.** The Rebound dot bounced over
  the first or last letters of the Bind button's text. A button with the dot
  now keeps more blank space at each side of its label
  (`BindButton.set_side_space()`): enough for the dot and a small gap, and
  the same at both ends, so the label stays centred. The button grows by
  that much; a bind without the dot is as it was.
- The dot's distance from the end of the button follows the button's height
  (it followed its width), so it does not move in as a button gets wider.
- Untested on Windows, like v108.178 and v108.179.

## v108.179 — Rebound off until chosen; a bouncing dot

- **Rebound is off by default.** A new bind, and a bind loaded from a profile
  that has no Rebound time for it, has Rebound off (the v108.177 and v108.178
  tests gave every Tick bind and every bind with NoBack 150 ms). A time saved
  in a profile is kept as it is.
- **"Rebound: Off" recommends a starting point.** With the pointer on
  *Rebound: Off* in a Bind button's menu, a tip comes up at once, without the
  hover wait: "Rebound is off for this bind. Recommended starting point:
  150 ms." It goes when the pointer moves on to the times (or anywhere else),
  and comes up only where Rebound applies and no time is chosen. The 150 ms
  item's own tip names it the recommended starting point.
- **A tip keeps clear of a submenu that is about to open.** The tip of an
  item with a submenu (Rebound, Load Backup, Switch to…, Positions Saved)
  leaves the submenu's place free, so the two do not cover each other.
- **A dot, bouncing up and down** (`ReboundBounce`): the upright line that
  moved sideways in the v108.178 test is an amber dot at the end of the Bind
  button on its Bind Dir side (right for POS, left for NEG, both for FULL).
  It starts at the top, by the Bind Dir line, falls to the bottom and bounces
  four times, lower each time, rests there, fades and starts again; with the
  pointer away from the window it rests at the bottom.
- Untested on Windows, like v108.178.

## v108.178 — Rebound, tips of the Mapper's own, drop-downs that stay open

- **"Settle" is "Rebound".** The guard is the rebound settle guard; in the
  editor it reads *Rebound: 150 ms* (the Bind button's right-click menu, its
  tip, Axis History's "held by Rebound"). A profile keeps the time as
  `settle_ms`, so profiles saved with the v108.177 test load as they are.
- **Rebound is ghosted where it does not apply.** A bind that is neither a
  Tick nor has NoBack on shows *Rebound: 150 ms* greyed out. A disabled menu
  item looked like any other before: the style sheet's text colour covered
  every state (`QMenu::item:disabled` now has the ghost colour).
- **A bouncing line on the Bind button** (`ReboundBounce`, title_effect.py):
  a bind with Rebound has an upright amber line at the end of its button on
  its Bind Dir side (right for POS, left for NEG, both for FULL). While the
  pointer is over the window it starts a little way in, falls to the end and
  bounces off it four times, lower each time, rests and starts again; with
  the pointer away it rests at the end.
- **Hover tips** (ui/tips.py, tip_place.py): every tip is shown in a window
  of the Mapper's own, white on black, in the font of the Auto-Profiles,
  Options and Display drop-downs, wrapped at the width of an axis's comment
  box. It stands at the right edge of the button or text it explains, else
  at the left edge, below or above: never under the mouse pointer, and inside
  the Mapper's window while there is room (a drop-down's tip stays off the
  drop-down and its open submenu; for something large it stands beside the
  pointer). Qt still decides when a tip is due; moving on to a neighbouring
  item brings the next tip up quickly.
- **Drop-downs stay open** (`StayOpen`, menu_autoclose.py): a click on a
  setting (an item with a check mark) changes it and leaves the drop-down
  open, brought up to date; it closes once the mouse has left it. A Bind
  button's menu now closes that way too. An item that opens a window or a
  dialog (Axis History, Edit macro, Browse all backups), loads a profile,
  moves the editor (Positions Saved) or restarts it (a Display size) closes
  the drop-down as before, as does the Auto Load question when a change
  brings it up.
- **A Bind button's menu** uses the font of the menu bar's drop-downs.
- **Display**: no blank line (a separator) before Positions Saved.
- Untested on Windows: the tip window, the menus and the line are checked on
  a model of Qt only.

## v108.177 — Settle: the spring's bounce is not a new push

- **A quick release from a high band could send the lower bind's key.** Let
  go of the puck and its spring throws it back through the centre and out
  again for a moment. To the binds that bounce looked like a new push: a
  lower bind's NoBack was rearmed the moment the axis centred (or crossed to
  the other side), and a lower Tick was crossed going out again. With crouch
  at 37% and prone at 68%, going prone quickly sometimes ended in a crouch.
- **Settle, per bind** (`settle.py`, `AxisPanel._advance_settle()`): once a
  band higher than the bind was reached, a Tick bind or a bind with NoBack
  may not start again until the axis has rested below the bind's own start
  (or at the centre, or on the other side) for its Settle time without a
  break. A hand takes longer than that to come back; the spring does not.
  Only the way back from a higher band arms it: the way out is never
  delayed, a bind with nothing above it is never held, and a bind without
  NoBack that is not a Tick works as before.
- **Right-click a Bind button > Settle**: Off, 50, 100, 150 (the default),
  200, 250, 300, 400 or 500 ms; greyed out for a bind that is neither a Tick
  nor has NoBack on. The Bind button's tip shows it. Saved with the bind
  (`settle_ms`); a profile from before has 150 ms.
- **Axis History** marks the bounce it kept quiet "held by Settle" (a hollow
  light dot, like NoBack's) and counts it in the summary, so the Settle time
  can be tuned by looking at a stroke.
- A behaviour change to know: with Settle on, dipping below a lower Tick and
  pushing out again in less than the Settle time, after a higher band, no
  longer taps it. Set that bind's Settle lower, or Off, if that is wanted.
- Untested on Windows with the device: the bounce in the tests is modelled
  (80% let go, back out to 42% within 64 ms).

## v108.176 — Releases build themselves

- **Pushing a version tag publishes the EXE.** A new GitHub Actions workflow
  (`.github/workflows/release.yml`) runs on a tag such as `v108.176`: it
  checks the code (ruff and the tests), builds `SpaceNavigatorMapper.exe`
  with Nuitka on a Windows runner — the same call as
  `BUILD_EXE_WINDOWS.bat` — refuses a tag that does not match
  `spnav_mapper/version.py`, and publishes a release with that version's
  notes from this file and the EXE attached. A release drafted on the
  website with a new `v…` tag works too: the workflow adds the EXE and the
  notes to it. "Run workflow" on the Actions page builds the EXE without
  making a release. The app itself is unchanged.

## v108.175 — Ready for GitHub

- **MIT license.** The project now carries a `LICENSE` file (MIT, Don
  Muddiman), named in `pyproject.toml` and at the end of the README. No code
  changed.
- Checked for publishing: 197 tests, ruff clean, the GitHub Actions workflow
  valid, no machine-local paths in the tree, and builds (`dist/`, caches,
  `configs/`) ignored by `.gitignore`.

## v108.174 — Programs running as administrator

- **Keys to a program running as administrator were lost without a word.**
  Windows does not let a program that is not running as administrator send
  keys to one that is (User Interface Privilege Isolation): SendInput reports
  success and the keys never arrive, so a game, launcher or tool started as
  administrator seemed to ignore the Mapper. Now (`ui/elevation.py`):
  - picking such a program as the target asks "Restart the Mapper as
    administrator now?";
  - sending keys while one is in front says in the status bar that Windows
    blocks them, and the tray says so once a session for each program;
  - **Options > Restart as Administrator** starts the Mapper again that way
    (Windows asks first; `restart.restart_as_administrator()`, ShellExecute
    "runas"), and it comes back where it was, with the same profile.
    Declining Windows' prompt changes nothing. Running as administrator, the
    item reads "Running as Administrator".
- How it tells: the program's token says whether it is elevated
  (`win32.process_elevated()`); a token the Mapper may not read is taken as
  elevated, and a program it cannot tell about at all never warns. The
  Mapper's own state is noted in startup.log.
- A copy running as administrator lets a start that is not (a second start,
  the taskbar's Restore and Exit) reach its window: Windows drops messages
  from lower to higher programs unless the window allows them
  (`single_instance.accept_messages_from_lower()`).
- Tests: the warnings (keys sent or not, output off, a program running as
  administrator, one that is not, one that cannot be told, once in the tray),
  the question for a target, Running as Administrator, the menu item and the
  restart accepted and declined.

## v108.173 — Button comments as wide as the axis comments

- The comment boxes beside Button 1 and Button 2 are as wide as an axis
  bind's comment box (`widgets.MatchWidth`: they take its width once it is
  laid out, and again whenever it changes size). They still scroll a comment
  longer than the box.

## v108.172 — Fainter greyed-out controls

- The Quick Bind controls a mode does not use (Tap Dwell in Hold and
  Release-only, Max% and DZone in Tick) are greyed out more faintly, with
  see-through colours that leave them just readable on the panel: a label's
  text about 3:1 against the background (was 3.7:1), a − / + button's face
  only a little lighter than the panel (was a solid grey) and its sign about
  2.7:1 against the face.

## v108.171 — Editing in Auto Load: a warning, and changes are no longer lost

- **Auto Load reloaded a profile over changes not yet saved.** When the
  profile loaded was not the one Auto Load would pick for the program (the
  second of two profiles with the same target, or one opened with Load or
  Save as), going back to the game to test loaded the top-priority profile
  from its file, and the changes were gone. Now a loaded profile that is one
  of the program's (in its Auto-Profiles group) stays loaded when that
  program comes in front, and a profile that is loaded already is never
  loaded again from its file; Auto Load loads another only for a program
  whose profiles do not include it. Reload Auto-Profiles still loads what
  the rules give.
- **A warning when editing in Auto Load.** The first change to the profile
  while Auto Load is on (Quick Bind, a key, a macro, NoBack, a comment,
  Button 1 / 2, Reset axis) asks "Editing in Auto Load — Switch to Manual
  On while you edit and test?". Yes switches to Manual On at once; No keeps
  Auto Load. It asks again after the profile is loaded or saved, or Auto
  Load is chosen again.
- Tests: the warning (Yes and No, once per editing), and going back to the
  game with an edited second profile of it.

## v108.170 — Profiles with the same target are all in Switch to…

- **Switch to… listed no profiles for a target** that two new profiles were
  saved with. Its list comes from auto_profiles.json, and that file was made
  once, from the profiles there at first use; a profile made or given a
  target later was in no rule, so Switch to… (and Auto Load) did not know
  it. Now a profile saved (Save/Reload, Save as), loaded, or given a target
  in the target list, while it has a target program, is added to that
  program's group, last, with the next priority; a group is made for the
  program when it has none (`auto_profiles.link_profile_to_program()`). A
  profile already in the group, turned off or not, is left as it is; a
  group matching by window title or product is not used; a rules file that
  cannot be read (being edited) is never overwritten. Delete Linked Program
  takes it out, as before.
- **A group with no pattern matched every program.** The first-use rules
  made a group for every .json file in configs (last_config.json and the
  settings files too), and one without a program had no pattern, so it
  matched whatever was in front. Now a group with no pattern matches
  nothing; first-use rules come from profiles with a target program only;
  last_config.json is never loaded or listed from a rule.
- Tests: linking new and second profiles, profiles already there, hand-made
  groups kept, an unreadable rules file left alone; a pattern-less group;
  the session's two profiles with one target in Switch to….

## v108.169 — Readable tips on the − / + buttons; Profile: is a button

- **The − / + buttons' tips** showed in the buttons' 20 px bold sign size
  (greyed out) or blank (white letters). Qt styles a tip with the style
  sheet of the widget it is shown for, and the buttons' styles had no
  selector, so they styled the tip too. Their styles (and the greyed-out
  labels', the Repeat every note's and the title's) are now for the widget
  only, with an exact class selector (`own_style()`: ".QPushButton { … }",
  which the tip's label does not match).
- **Profile:** is a dark gray button (as Target is when off), in its own
  italic font, level with the profile name; a click opens the target list,
  as the label did. It has a tip.
- Tests: the styles' selectors; the Profile button; the target list opened
  from it.

## v108.168 — A greyed-out − / + keeps its size; another version running is no longer shown quietly

- **A greyed-out − / + kept the small text size.** The ghost style (Tap
  Dwell's − / + in Hold and Release-only, Max% and DZone's in Tick) replaced
  the buttons' own style, sign size included. It now keeps the sign's size
  and padding (`_set_ghost`, `_spnav_glyph_style`).
- **Starting a new version showed the old one.** Since v108.165 a second
  start quietly brings the running copy to the front. When that copy is
  another version (started at Windows sign-in from an older folder, or
  left in the tray), the new version seemed to have none of its changes:
  small − / + signs, no Tap Dwell. Each copy now marks its window with its
  version (a window property, `single_instance.VERSION_PROP`), and a start
  that finds another version (or a copy from before v108.168, which does not
  say) asks "Exit it and start v108.168?": Yes posts it the Exit message
  (copies from v108.165 on answer it) and starts once it has gone, waiting
  up to 8 s; otherwise it says how to exit it from its tray icon. No shows
  the running copy. The taskbar's Restore always shows the running copy.
  The mark is removed at exit.
- Tests: the launches with the same version, another one (kept, replaced,
  not exiting), an unknown one and the taskbar's Restore; version numbers;
  the greyed-out signs' size.

## v108.167 — Tap Dwell and Repeat every work together

- **A tap no longer stops the Mapper for its dwell.** It pressed its key,
  slept for the Tap Dwell on the GUI thread, then released it: meanwhile the
  SpaceNavigator was not read and every other axis and bind waited, and a
  Press/Repeat bind with a short Repeat every and a long dwell kept the
  Mapper asleep most of the time (10 ms and 200 ms: 95%). Now the release is
  scheduled (`ui/taps.py`, one TapSender for the window's axes).
- **The key is up long enough between taps.** It was up only for what was
  left of Repeat every after the dwell (60 ms and 45 ms: 15 ms; none when
  Repeat every was shorter than the dwell), so a game reading its keys once
  a frame could see one long press. A tapped key now stays up at least 30 ms
  (`MIN_KEY_UP_MS`) before it is pressed again; Press/Repeat taps every
  Repeat every or Tap Dwell + 30 ms, whichever is longer, and Quick Bind shows
  an amber "→ N ms" beside Repeat every (with a tip) when that is longer.
- A tap of a key that is still down or just released (a bind re-entering
  its band, another bind with the same key) waits for it; taps asked for
  while one waits make one, not a queue that goes on after the axis left the
  band. Switching output off, or anything that releases all keys, releases
  the taps still in their dwell at once and drops the waiting ones.
- **Macros:** two Tap steps of the same key in a row released it and pressed
  it again at once; a 30 ms wait is put between them (a Delay there counts,
  and modifiers are not waited for).
- Tips for Repeat every; the Tap Dwell tip says how the two combine.
- Tests: taps released after their dwell without waiting, another key not
  held up, a key tapped again (down or just up) waiting and joining, release
  of all keys mid-dwell, a dwell of 0, the Press/Repeat interval and its
  note, and the macro gaps. The NoBack cases record each tap as one event.

## v108.166 — Tap Dwell, per bind, above DZone

- **Tap Dwell** in Quick Bind, above DZone, with − / + (5 ms a step, 0 to
  200 ms, 45 ms by default): how long each tap of the selected bind holds
  its key down. It is not Press/Repeat's Repeat every (the time from one tap
  to the next). Used by Press/Release, Press/Repeat, Tick and a macro's Tap
  steps; greyed out (and its tip says so) for Hold and Release-only, which
  send no taps. Before, one tap dwell served every bind of the profile, set
  in Auto-Profiles > Tap dwell (ms)… (removed in v108.165).
- Saved per bind as `tap_ms` for the modes that tap. A profile without it
  (older ones) gives every bind its `tap_down_ms`, which is still saved as
  the default; the profile's tap_down_ms is now read before its axes.
- Tests: each tap's hold time for binds with their own dwell, without one,
  of 0 and of over 200 ms; the controls' greying by mode, stepping, limits
  and what is saved.

## v108.165 — Profile buttons, larger − / +, hover tips, taskbar Restore / Exit, Switch to… keeps its pick

- **Save/Reload, Save as and Load are the same width** and end where the
  Profile box ends (the space under Auto Load stays empty); Target keeps its
  width (`ui/profile_buttons.py`: the row's stretch factors, recomputed on
  resize, so no size hint changes). At 85% Target keeps its text width and
  the three share the rest.
- **The − / + buttons of Min%, Max% and DZone** show a real minus sign (as
  wide as +) at 72% of the button's side, bold, so they grow with every
  Display size; the buttons keep their size.
- **Hover tips** on every item of Auto-Profiles, Options, Display (their
  submenus, and the items Switch to… and Load Backup fill in as they open)
  and the tray menu (`ui/menu_tips.py`), and on Bind Dir, Mode, Min%/Tick%,
  Max%, DZone and their − / +, Button 1 / Button 2, Target, Save as and
  Load. The Tick-mode note on Max% and DZone keeps their tip below it, and
  Target keeps its tip as its label changes.
- **Auto-Profiles: no Tap dwell (ms)…** item (a profile still keeps its
  tap_down_ms, 45 ms by default); the menu has no separators.
- **Switch to… keeps its pick.** It loads one of the profiles whose rules
  match the program in front, but in Auto Load the top-priority profile was
  loaded again within a second of that program being in front again. The
  pick now stays for that program (by exe name) until another is picked,
  Reload Auto-Profiles is used or the Mapper restarts, while the rules still
  list it.
- **The taskbar button's right-click menu** (`ui/taskbar.py`): Windows' item
  with the program's name started a second copy, which only said that the
  Mapper was already running. Windows always shows that item; the window now
  names it **Restore SpaceNavigator Mapper** and makes it start the Mapper
  with --restore (its relaunch properties), and a Task **Exit SpaceNavigator
  Mapper** starts it with --exit (the jump list). A launch with --restore,
  or any second start, brings the running copy forward and ends without a
  message box (one is shown only when the running copy's window is not
  found); with none running it starts the Mapper. A launch with --exit posts
  a registered Exit message to the running copy, which exits as Options >
  Exit does, and never starts the Mapper. The relaunch properties are
  removed at exit. Failures are noted in startup.log and change nothing
  else. `restart.launch_command()` builds these command lines, as it does
  the restart's.
- Tests: the profile row's widths; tips on every menu item and control; the
  − / + glyphs; Auto-Profiles' items; a Switch to… session script; the
  taskbar items' commands, names and icon, the COM structures' sizes, and
  the --restore / --exit launches and the Exit message.

## v108.164 — A Display change restarts with the same profile

- **After a Display size change the loaded profile was not loaded, and Load
  opened a temporary folder** (the EXE). The onefile EXE unpacks itself into
  a temporary folder and runs the copy there; the restart started that copy
  (sys.executable) instead of the EXE you started, so the restarted Mapper
  took the temporary folder for its own: its configs folder was there, empty,
  and the copy ran from a folder the first one's exit deletes. The restart
  now starts the EXE you started (`restart.compiled_program()`:
  `__compiled__.original_argv0`, the EXE beside `__compiled__.containing_dir`,
  or argv[0]), without the old copy's Nuitka variables, and tells it the old
  copy's folder (SPNAV_RESTART_APP_DIR, honoured only with
  --restart-ui-scale, `paths._restart_app_dir()`), so it uses the same
  configs folder and loads the same profile whatever it is started from.
  The Monitors Changed restart (v108.163) uses the same restart.
- Tests: the restart command for a onefile copy, a bare argv[0], Nuitka's
  original_argv0 and a standalone EXE; the folder handed to the restarted
  copy.

## v108.163 — Dual-monitor fixes: start-up placement, refit, monitors changed

Checked the dual-monitor code for what can make it fail now and then:

- **The editor could stay on the wrong monitor at start-up** (since
  v108.153). Between monitors with different scales, Windows can move the
  just-shown editor to the other monitor; the checks at 0, 250 and 750 ms
  move it back. But when the editor grew to hold its content (100 ms) while
  it was on the wrong monitor, it grew there, on the monitor Qt named, and
  that rect became the one it was "moved back" to, so it stayed on the wrong
  monitor. `settle_editor_size()` now uses the monitor the editor was placed
  on and Windows' answer for where it is; while it is elsewhere only the
  rect it is moved back to grows.
- **Refit after a drag, and the fit line in startup.log, use the monitor
  Windows reports** (`_refit_to_screen()`, `log_editor_fit()`), like saving
  and placement already did. Qt's own answer can name the other monitor
  while the monitors use different scale factors, and the editor was then
  fitted into, and moved onto, that one.
- **Monitors changed after start-up** (new `ui/monitor_watch.py`). The
  per-monitor Qt factors and the editor's layout are fixed when the Mapper
  starts. A monitor connected later (at a Windows sign-in the Mapper can
  start in the tray before every monitor is ready) had no factor of its own,
  and a monitor whose resolution or scaling changed kept its old one, so the
  editor was drawn at the wrong size there until the Mapper was restarted.
  Now, 2 s after Windows reports a monitor added, removed, resized or
  rescaled, and 1 s after the editor is shown from the tray, the Mapper works
  out the factor each monitor needs (`monitor_scale.stale_monitors()`) and,
  when one is more than 2% off and the editor is shown, asks "Monitors
  Changed: Restart the Mapper now?", naming the monitors. Yes restarts it
  the way a Display size change does (the editor comes back where it was);
  No is remembered for those monitors. A disconnected monitor, or a taskbar
  that moved, asks nothing; factors set by the user
  (QT_SCREEN_SCALE_FACTORS, SPNAV_UI_SCALE, SPNAV_PER_MONITOR_SCALE=0) are
  never second-guessed. It is noted in startup.log.
- Tests: a stray-then-grow start-up, a refit with Qt naming the other
  monitor, and monitors connected, rescaled, disconnected, declined, hidden
  in the tray and reported by Qt's screenAdded signal.

## v108.162 — No NoBack for Tick binds; the Bind menu opens beside the button

- **A Tick bind has no NoBack.** A Tick taps when the axis crosses Tick%
  going out and never on the way back, so NoBack had little to do for it.
  Its right-click menu no longer offers NoBack, its Bind button shows no
  white NoBack line and its tooltip reads "Right-click: Edit macro, Reset
  axis"; the Axis History labels show no NoBack for it. The engine ignores
  NoBack on a Tick bind (`noback_on()`), so a Tick taps each time it is
  crossed going out. A Tick still counts as a band for the binds below it.
  A NoBack set before the bind became a Tick is kept in the profile and
  works again if the Mode is changed back.
- **The Bind button's right-click menu opens beside the button**, its left
  edge at the button's right edge and level with its top
  (`AxisPanel._bind_menu_position()`), so the mouse pointer no longer covers
  its check boxes. It has no separator lines.
- README: *When NoBack makes a difference* said a lower Release-only bind
  sends no release on the way back. Release-only sends its key-up on
  entering its band going out, like a Press/Release tap, so NoBack changes
  it only where the axis enters its band again from above (a lower Max%) or
  wobbles. Corrected; the Tick mode and the NoBack steps say Tick has none.
- Tests: the NoBack cases now expect a Tick with NoBack to tap on every
  outward crossing; the session checks the menus of a Tick and a Hold bind
  (items, no separators, opened at the button's right edge).

## v108.161 — NoBack only for the way back; no NoBack blocks in Axis History

- The NoBack shading (v108.158: from the highest band reached down to
  centre, with a thick light bar at the top, a new block each time NoBack's
  level rose) is gone; it looked like blocky artifacts around the axis's
  line. NoBack in force is now a thin dashed light line at the highest band
  reached, labelled "NoBack 45%".
- **NoBack is offered only for the way back**, the direction opposite the
  Bind Dir, and named by it: a POS bind's menu has only "NoBack -", a NEG
  bind's only "NoBack +", a FULL bind's both (one for the way back from each
  side); a bind without a Bind Dir has none. (v108.139 offered NoBack + and
  NoBack - on every bind, + and - meaning the axis side, so NoBack - on a POS
  bind did nothing.) NoBack is still stored per side ("noback_plus" for the
  + side), so profiles keep working:
  - the white line on the Bind button now sweeps toward the way back,
    opposite the green Bind Dir line (left for a POS bind);
  - a POS or NEG bind keeps NoBack only on its own side: NoBack set for the
    other side moves to its own (`fit_noback_to_direction()`), on loading a
    profile and when its Bind Dir changes, so an earlier "NoBack -" on a POS
    bind now works, and a bind changed from NEG to POS takes its NoBack along;
  - the tooltip says "NoBack - on (quiet on the way back)"; the Axis History
    summary names NoBack the same way ("NoBack: Bind #1 −").
- Checked with the case from the report (Bind #1 + at 30% with NoBack,
  Bind #2 + at 60%, out to 80% and back, then out to 40%): Press/Release
  taps A at 30% out, B at 60%, nothing on the way back, A again at 30% on the
  next stroke, as described. With Bind #1's Max% at 45%, without NoBack A
  taps again at 44% on the way back; with NoBack it is "held by NoBack".

## v108.160 — Menus close when the mouse leaves; NoBack marks only real holds

- **Menus:** a drop-down from the menu bar (Auto-Profiles, Options,
  Display) stays open while the mouse is over it, one of its submenus or the
  menu bar, and closes 0.4 s after the mouse has moved away from all of them
  (`ui/menu_autoclose.py`; the mouse is looked at every 0.1 s while a
  drop-down is open). Moving along the menu bar to another heading keeps it
  open; a drop-down opened from the keyboard stays open until the mouse has
  been over it once. Before, a drop-down stayed open until a click.
- **NoBack in Axis History:** "held by NoBack" was marked whenever NoBack
  ended a bind on the way back, including a lower Press/Release or Tick bind
  that was still in its band (the usual Max% 100) and would have sent
  nothing more without NoBack. With NoBack on or off the keys were the same,
  so NoBack looked as if it did nothing, except for a misleading mark. Each
  axis's binds now also run on copies with NoBack left out (sending and
  recording nothing); a bind that starts there but not in its own run (or,
  with output off, in its dry run) is marked "held by NoBack". No mark now
  means NoBack made no difference. What NoBack does is unchanged.
- The README explains when NoBack makes a difference: a lower bind whose
  Max% ends below the higher bind's start, Hold (released early), Press/Repeat
  (stops repeating), Release-only (no release on the way back), or a wobble on
  the way back.

## v108.159 — Axis History: aligned bind labels, colours per bind

- **The binds' labels no longer overlap.** They stood on their start lines,
  right-aligned inside the graph, so binds starting close together (and many
  binds, larger text or a smaller window) wrote over each other. They now
  stand in a column right of the graph, one row per bind and side, top
  (+100%) to bottom: "Bind", "#n", "(key)" and the percent in columns of
  their own, lined up (the percent right-aligned), then NoBack. Rows are
  spread at least a line apart, kept in order, and joined to their start
  lines by a thin line in the bind's colour. The columns are measured with
  the window's font; when they would take more than 45% of the width, the
  keys, then the word "Bind", are left out. Each graph is tall enough for a
  row per bind side.
- **Dot labels no longer overlap** either: each goes above or below, right or
  left of its dot, where it covers no other dot or label and stays inside
  the graph, or is left out.
- **Colours:** +100% dashed green, 0 dashed blue, −100% dashed red (their
  labels too); the axis's line white. Each bind has a basic colour, the same
  on every axis: Bind #1 red, #2 orange, #3 yellow, #4 green, #5 blue, #6
  purple, for its dots (filled: sent; hollow: not sent), its dotted start
  line, its labels' row and its dots' labels. NoBack stays light; a bind it
  held back is a hollow light dot.
- **Fixed:** in separate graphs the axis's line took the colour of the last
  bind line drawn (grey, or white with NoBack) instead of its own.
- In One graph the axes' lines keep the axes' colours, so they can be told
  apart; the dots take their binds' colours.

## v108.158 — Axis History shows NoBack

- NoBack is drawn in white, like the NoBack line on the Bind buttons:
  - a bind with NoBack on a side: its dashed start line in white, labelled
    "· NoBack", or "· NoBack (no higher band: nothing to hold)" when no
    higher bind on that side could make it hold (NoBack only keeps a bind
    quiet below a higher band reached in the same stroke);
  - while NoBack is in force: a solid white line at the highest band reached
    ("NoBack 45%"), shaded down to centre, from when it was reached until the
    axis returns to centre (the axis panels now record NoBack's state as it
    changes);
  - a bind it held back: a hollow white dot, "A held by NoBack" (it was a
    hollow orange dot, "A NoBack held"; the CSV says "held by NoBack").
- The summary line lists the binds with NoBack: "· NoBack: Bind #1 +, Bind #2 +".

## v108.157 — Target on while Axis History is open

- Opening the Axis History window turns the Target on for the current
  profile (the button reads "Target: ON (History)", green), whatever the
  mode; closing it puts the Target back as the mode (Auto Load, Manual On,
  Off) has it, releasing any key still held. The mode is not changed or
  saved, game time does not count, and choosing a mode or clicking the
  Target button meanwhile ends it.
- With the Axis History window in front, the binds now send their keys, so
  the history shows them as sent (orange) instead of "not sent" (grey). No
  control in the window takes the keyboard and the window ignores every key
  (Esc and Enter included), so the keys land there and do nothing. The
  Mapper's editor, its other dialogs and menus still never receive keys.

## v108.156 — Axis History: text size, All, closing, key markers

- **A− / A+** did nothing: the Mapper's dark style sheet keeps a window's
  font from reaching the widgets inside it, so the graphs and controls kept
  the app's size. The graphs now paint with the window's text size directly,
  every control gets it, and the window's style sheet carries it too. The
  binds' labels, the percents, the times and the keys sent all follow it.
- **Closing the window turns Axis History off**: Options > Axis History is
  unchecked, recording stops and what was recorded is forgotten (before,
  closing kept recording and the option stayed checked). Right-click an axis
  > Axis History… or the option opens it again. When the window was open at
  the last exit, it opens again with the editor (not when starting in the
  tray); before, recording started without the window.
- **All** is a toggle: green while all six axes are shown (click: hide them
  all), red otherwise (click: show all six). With no axis ticked the window
  says "No axis is shown: tick one above, or click All."; Save as CSV… asks
  for an axis. (v108.155 kept at least one axis ticked.)
- **The keys sent are orange dots again** (v108.155 drew them in the axis's
  colour, on top of the axis's line of the same colour, so they could not be
  seen), larger (they follow the text size), with a dark ring, and their
  labels are orange.
- **Keys not sent are marked too.** The Mapper never types into itself
  (v108.144), and the Axis History window is the Mapper's: while it was in
  front no key was sent, so nothing was marked. While Axis History records
  and output is off (Target off, or a Mapper window in front), each axis's
  binds now also run on copies of their state with sending turned off (NoBack,
  hysteresis and Max% included), and the history marks what they would have
  sent with grey dots labelled "(not sent)"; the summary counts them apart
  ("Bind #1 tapped 2× (not sent)") and the CSV names them ("tap (not sent)").
  The copies start from the binds' states when output goes off and are never
  used for sending.

## v108.155 — Axis History: several axes at once, larger text and window

- **Axes**: six check boxes (X, Y, Z, Rx, Ry, Rz, each in its own colour)
  and **All** replace the Axis drop-down; any number of axes is shown at once.
  The last one cannot be unchecked. Right-clicking an axis panel adds that
  axis to the ones shown.
- **Show**: **Separate graphs** (one per axis, one under the other, each with
  its binds' start lines and dead zone; the window scrolls when they do not
  fit) or **One graph** (the axes' lines and dots over each other, each in
  its colour, named on top; dots labelled "X: A down").
- **Text size** A− / A+ (100% to 200%, opens at 125%): the window's text is
  the app's + 2 points at 100% (it was the app's) and the graphs' labels use
  it (they were 85% of the app's). The graphs' margins, dots and label
  offsets follow the text, and each graph is at least nine lines tall.
- **The window** opens at 80% of the width and height of the Mapper's screen,
  centred (it was 900 x 520 layout units: about 405 x 234 pixels at the
  smallest layout scale).
- The axes, the layout, the time span, the text size and the window's size
  are remembered (`axis_history_view` in `ui_preferences.json`).
- One summary line per axis shown. **Save as CSV…** saves every axis shown,
  with an `axis` column first (`axis,time_s,value_percent,event,bind,key`).

## v108.154 — Every Display size step is larger

- Above 85% the menus were small: at 85% the menus were 2 points and the
  menu-bar headings (Auto-Profiles, Options, Display) 3 points larger than the
  app's text, but at 100% and 110% the menus only 1 point and the headings not
  at all, so the headings were smaller at 100% (8 pt) than at 85% (9.8 pt).
  Now the menus get 2 points and the headings 3 at every size: 9.8 / 11 /
  11.8 pt for the headings, 8.8 / 10 / 10.8 pt for the menus.
- The axis windows did not grow above 85%. Only 85% made each control tall
  enough for its text; 100% and 110% kept fixed heights, so the Bind buttons
  and comments were as tall at 100% as at 85%, and the Bind Dir and Mode boxes
  and the − / + buttons shorter, while the text was larger. Every size now
  uses the same rule (at least its nominal height, and tall enough for its
  text and padding): on 1920 x 1080 at 100%, the Bind buttons are 22 / 26 /
  28 px at 85% / 100% / 110%, the Bind Dir and Mode boxes 26 / 28 / 30 px.
  85% is unchanged. The widths at 100% and 110% keep their own rules.
- New `tests/test_display_sizes.py` starts the whole app at each Display size
  and checks that every step makes the text, the menus and the controls
  larger.

## v108.153 — The window holds the editor at start-up

- With no monitor checked in Display > Positions Saved, the editor's content
  was slightly larger than its window at start-up, until a monitor was
  checked. The window's size was measured before it was first shown, and the
  controls change once it is: each button's height is fitted to its styled
  font (below 100% size) and the bind rows are lined up with Quick Bind.
  Checking a monitor placed the window again, now measured correctly.
- 100 ms and 400 ms after the editor is placed, it is measured again and
  grows to hold its content, within the monitor's work area: centred, it stays
  centred; at a saved position, it stays there as far as it fits. It never
  shrinks, and it is left alone while the mouse button is held (a drag).
  `startup.log` notes "Editor grown to hold its content: WxH -> WxH".

## v108.152 — Normal size after a resolution or scale change

- After the resolution was changed from 3840 x 2160 to 1920 x 1080 (Windows
  went from 225% to a lower scale), the Mapper restored from the tray looked
  right, but started again it was huge. Windows makes its default GUI font for
  the DPI signed in with and keeps that until the next sign-in; Qt 5.15
  converts it with the monitor's current DPI (QTBUG-101951), so every Qt
  program started after the change got a default font 2.25 times too large
  (225% to 100%). Every label, combo box, menu and comment that uses it, and
  every control sized to its text, grew with it.
- At start-up the Mapper now compares Qt's default font with the size Windows
  meant (Windows' GUI font at the sign-in DPI) and, when they disagree, uses
  Windows' size before Display % and the fit to the screen are applied. When
  nothing changed since sign-in the two agree and nothing is touched; it also
  covers the other direction (signed in at 100%, then raised).
- `startup.log` notes the default font, each monitor's size and Windows scale,
  the interface size (Display % x fit, layout scale; before only printed to a
  console) and, in the "Editor size" line, the font and scroll-bar sizes.

## v108.151 — Fits 1920 x 1080 screens; no maximize button

- On a smaller screen the editor is now drawn smaller, fonts included, so it
  takes about the same share of the screen as on 3840 x 2160 at 225%. Before,
  the layout could not go below its smallest automatic size, so the same
  editor filled a 1920 x 1080 screen at 125% or 150% (even at Display 85%).
  The editor keeps its size on any screen with at least 1700 x 900 Qt pixels
  to work in (screen size / Windows scale, less the taskbar); 1920 x 1080 at
  125% draws it at about 90%, at 150% at about 75%. Display 85% / 110% apply
  on top. The same factor goes into each monitor's Qt scale, so dragging the
  editor between monitors keeps it the same share of each screen.
- The lowest layout scale is now 0.24 for every Display choice (it was 0.35
  except at 60% and 70%), so the smaller fit is not cut short.
- `startup.log` notes, 1.5 s after start-up, the size the editor needs and the
  room its screen has (`Editor size: needs WxH, <screen> has WxH (fit …,
  layout scale …)`).
- The editor's maximize ("full window") button is gone. A maximize from the
  keyboard (Windows + Up) or by dragging the window to the top of the screen
  is undone.

## v108.150 — README text sizes; Code by

- The README window (right-click the title > Open README in a window) has a
  **Text size** choice: 100%, 125%, 150%, 175%, 200% or 250%. **A−** and
  **A+** step it, as do Ctrl + plus / minus and Ctrl + mouse wheel; Ctrl + 0
  goes back to 100%. Headings and tables grow with the text, and the size is
  remembered for the next time. (The PDF viewer has its own zoom.)
- The README and its PDF name the authors under "Logic by: Don Muddiman":
  **Code by: Don Muddiman, ChatGPT and Claude**.

## v108.149 — Axis history

- New **Options > Axis History**. While checked, the Mapper records the last
  30 seconds of every axis: the device's value every 16 ms (before the dead
  zone), each key its binds send (down, up, tap, macro) and each moment
  NoBack held a bind back. Checking it opens the Axis History window.
- The window graphs one axis over the last 5, 10 or 30 seconds: the axis as
  a line from −100% to +100%, the dead zone shaded, a dashed line where each
  bind starts (DZone% + Min%, or Tick%) labelled with its key, dots for keys
  sent and hollow dots where NoBack held a bind back. A line underneath sums
  it up (the farthest the axis went each way, how often each bind fired, how
  often NoBack held). Pause freezes the view, Clear forgets, and Save as
  CSV… saves the samples and events shown.
- Right-click an axis panel's border (or an empty spot in it) > Axis
  History… opens the window on that axis. Closing the window keeps
  recording; unchecking the option stops and forgets. The choice is
  remembered for the next start.
- Recording is a few list appends per tick; the graph redraws only while its
  window is open.

## v108.148 — Save/Reload under a new name

- Save/Reload's prompt now shows the file name in an edit box (selected, so
  typing replaces it), with ".json" after it. Keep the name and click
  Save/Reload to save over the profile and reload it, as before. Type a new
  name to save the current settings as a new profile in the same folder and
  load that one; the file loaded before is kept as it was. The status bar
  says "Saved as <name>.json and reloaded", the title shows the new profile,
  and the next start opens it.
- As you type, the prompt says what will happen: a new profile, an existing
  file that will be replaced (its previous contents go to the backups
  folder), or why a name cannot be used (characters Windows does not allow,
  names such as CON, or the Mapper's own settings files, last_config,
  auto_profiles, ui_preferences and window_state); Save/Reload is greyed out
  until the name can be used. A ".json" typed at the end is accepted.
- Cancel (or closing the prompt) saves and reloads nothing, as before.

## v108.147 — Leaner code, two Auto Load dead ends fixed

The code is about 1,400 lines (14%) shorter with the same behaviour: every
scripted session (start-up, strokes, binds, NoBack, macros, profiles, tray,
restart, exit) gives the same keys, windows and files as v108.146, except
where noted below.

- **Auto Load kept your edits only until you went back to the game.** With
  the Mapper itself in front, Auto-Profiles found no rule for it and forgot
  the loaded profile; back in the game it loaded the profile again from its
  file, so unsaved edits were lost. The Mapper's own window, dialogs and
  menus are now ignored.
- **Auto-Profiles > Switch to… was always empty.** Opening the menu puts the
  Mapper in front, so it listed the Mapper's profiles (none). It now lists the
  profiles whose rules match the target program.
- **Saving a picked target** (Profile name > a window > Yes) now saves the
  target's program (its EXE and names) too, not only the window, so the
  target is found again at the next start and Auto-Profiles can use it.
- **Load** now also loads the profile's tap dwell (it was only loaded at
  start-up and by Save/Reload).
- **Faster input loop:** the device's presence was checked by listing every
  HID device on each 16 ms tick; it is now checked once a second (a read
  error still closes the device at once). The window in front is looked up
  once per tick instead of up to four times, the target list asks Windows for
  each window's program once, and the 0.8-second title timer is gone (every
  load and save already updates the title).
- **Removed dead ends:** three copies of the profile loader (now one), the
  axis panel's layered "_base" methods (merged), the hidden Refresh button's
  blink and click handlers, the compact view's leftover attributes, the old
  check-box interface of the Auto Load / Manual On / Off selector, an unused
  font-size setting, an unused profile combo box, about 200 broad
  `except Exception` handlers around code that cannot fail, and duplicate
  target-program fields (`selected_exe`).
- An error in a button or menu after start-up is written to `startup.log`
  and the Mapper keeps running; before, many were silently ignored, and the
  rest showed a "could not start" message.
- New tests: the key picker (keys, modifiers, symbols, Clear, a preset
  combination), the device presence check, Auto Load with the Mapper in
  front, and Switch to… with the Mapper in front.

## v108.146 — README drop-down on the title

- Right-clicking the "SpaceNavigator Mapper" title now shows a drop-down
  with two choices: **Open README (PDF)** opens the README reference manual
  in your PDF viewer, as in v108.145; **Open README in a window** shows the
  same README (its Markdown) in a window of the Mapper, with no PDF viewer
  needed. Pressing Esc or clicking elsewhere closes the drop-down without
  opening anything. If the PDF cannot be found, its choice is greyed out;
  if no PDF viewer opens it, the window opens instead.
- The README window leaves out the HTML lines that only shape the PDF.
- The README's own text no longer names a version except on its Version
  line, which `tools/build_readme_pdf.py` keeps current.

## v108.145 — Delete Linked Program; the README is a PDF

- The Profile drop-down's first entry is now **Delete Linked Program**,
  replacing v108.144's Delete Current Profile. It removes the program linked
  to the loaded profile (its target), then saves and reloads the profile; the
  profile file and its binds are kept. It asks first ("Remove the linked
  program … from game.json, then save and reload game.json?", No by default).
  Yes clears the target, saves (the previous contents go to the backups
  folder), removes the profile from the Auto-Profiles groups for that program
  so Auto Load no longer picks it for it, and reloads. It is greyed out when
  no program is linked.
- Right-clicking the "SpaceNavigator Mapper" title opens the README as a PDF
  in your PDF viewer: the Full Editor README (reference manual) brought up to
  date for v108.145, in the same style (header, footer, page numbers, table
  of contents). It covers every control, mode, NoBack per bind, macros,
  menus, targets and Manual On, profiles and their files, Auto-Profiles,
  Load Backup, Delete Linked Program, monitor sizing and Positions Saved,
  the tray, and the EXE and single-file builds. Section 8 lists all 434
  functions and methods with their purpose. The PDF is copied to
  `%LOCALAPPDATA%\SpaceNavigatorMapper` first, so it opens from the EXE and
  the single-file edition too. With no PDF viewer, the same text opens in a
  window.
- New `tools/build_readme_pdf.py` rebuilds the README: it writes the version
  line and the function reference from the source into
  `SpaceNavigator_Mapper_README.md`, then prints the PDF with pandoc and
  Chrome or Edge. Every function now has a one-line docstring, and tests
  check that the README matches the source.
- The EXE build and the single-file edition carry the README PDF and its
  Markdown (from `spnav_mapper\resources`) instead of this file.
- Display > Positions Saved's status message no longer mentions "both views".

## v108.144 — Delete Current Profile; Manual On ignores the Mapper; README window

- Manual On no longer types into the Mapper itself. While the Mapper's own
  window, one of its dialogs or a menu is in front, no keys are sent (in any
  mode); Hold keys are released and macros stop, as when the target loses
  the focus.
- Clicking the Profile name (or "Profile:") opens the target list; with a
  profile loaded it now starts with **Delete Current Profile**, above
  [None]. It asks first (No is the default). Yes copies the profile to the
  backups folder, deletes its file, clears the editor (no binds, keys,
  comments or target) and saves that state, so the deleted profile does not
  come back at the next start. Restore it from Options > Load Backup.
- Options has no separator lines (they were after Close to System Tray and
  before Exit SpaceNavigator Mapper).
- Right-click the "SpaceNavigator Mapper" title to open this README in a
  window. A left click still minimizes to the taskbar. The EXE build and the
  single-file edition carry the README inside.

## v108.143 — Build the EXE with one double-click

- New `BUILD_EXE_WINDOWS.bat`: installs Nuitka and the app's packages,
  compiles the app to C and then to a single `SpaceNavigatorMapper.exe` with
  the SpaceNavigator Mapper icon, no console window, and the version
  (as 108.143.0.0), product name and copyright in the file's properties. The EXE
  is put beside `main.py`, sharing its `configs\` folder. A test checks that
  everything the batch file names exists and that its version reads right.

## v108.142 — Save/Reload asks first

- Save/Reload now shows a confirm prompt naming the file it will write
  ("Save the current settings to game.json, then reload it?"). *Yes* saves
  and reloads as before (the file's previous contents go to the backups
  folder); *No* saves and reloads nothing, and the status bar says
  "Save/Reload cancelled". With no profile open, the prompt says it will be
  saved as a new profile.

## v108.141 — Macros

- New Mode for any bind: **Macro**. The bind plays a list of steps instead
  of its key: *Tap* (press and release a key or combo), *Down* and *Up* (hold
  a key across steps), and *Delay* (0–10,000 ms). Up to 50 steps.
- Quick Bind shows **Play: Once / Repeat** for a Macro bind. *Once* plays the
  macro each time the axis enters the bind's band. *Repeat* plays it on entry
  and again every *Repeat every* ms (start to start) while the axis stays in
  the band; a new run never starts while one is playing. Leaving the band
  lets the playing run finish.
- The macro editor opens from a double-click on the Bind button, *Edit
  macro…* in Quick Bind, or the Bind button's right-click menu. Add Tap/Down/
  Up with the key picker, Add Delay, Move Up/Down, Change…, Delete; Save or
  Cancel. The Bind button shows "Macro (n)" and its tooltip lists the steps.
- Macros never block the SpaceNavigator: waits are timed, not slept. A tap
  holds its key for the usual tap time.
- Safety: a macro stops at once, releasing every key it holds, when output
  is not allowed (Target off, another window in front), on Target OFF, when a
  profile is loaded, when the axis is reset or its Mode changes, and on exit.
  Keys still held by a Down step are released when the macro ends.
- Exiting now also releases any key a Hold bind is holding.
- A Macro bind counts as a band for NoBack, like any bind with a key.
- Profiles save `macro` (the steps) and `macro_repeat` with the bind, and
  `repeat_ms` for Macro binds too. Versions before v108.141 load a Macro bind
  as one that sends nothing.

## v108.140 — Bind Dir line; comment rows fixed; larger tray menu

- Fixed: in v108.139 each axis's comment boxes sat one row below their Bind
  buttons (the first comment beside Bind #2, and so on).
- A thin green line along the top of each Bind button shows its Bind Dir: it
  starts in the middle and sweeps left for NEG, right for POS and both ways
  for FULL; None has no line. The button keeps its own style; the line is
  drawn over it, in step with the white NoBack line along the bottom (it
  sweeps while the pointer is over the window and rests at full length
  otherwise).
- The tray icon's right-click menu and its Profiles submenu are 2 points
  larger.
- Menus are enlarged from their original sizes all at once, so a submenu
  grows by the intended amount even if it takes its parent menu's font.

## v108.139 — NoBack line; axis name and value in the border

- A bind with NoBack now has a small white line along the bottom of its Bind
  button instead of the white orbiting outline. It starts in the middle and
  sweeps left for NoBack −, right for NoBack +, and both ways when both are
  on. It sweeps (about 1.3 s each, on the title's timer) while the pointer is
  over the window, and rests at full length otherwise.
- NoBack + and NoBack − can both be chosen in a Bind button's menu whatever
  its Bind Dir. A side the Bind Dir does not include waits: a POS bind never
  fires on the − side, so its NoBack − takes effect once its Bind Dir is FULL
  or NEG. The tooltip says when a side is waiting.
- The Reset button and the header row are gone from each axis panel; Reset
  is in every Bind button's right-click menu, and the panel's border flashes
  amber to confirm. The axis and its value ("X: 0.00") are in the panel's
  border, like "Quick Bind (edits selected bind)". The panels are shorter by
  the old header row.

## v108.138 — NoBack per bind; the title minimizes

- NoBack is set for each bind instead of a whole axis side. Right-click a
  Bind button: *NoBack +* and *NoBack −* for that bind (only the sides its
  Bind Dir works on can be changed), and *Reset <axis> axis*, the same as the
  axis's Reset button. The NoBack + / NoBack − buttons at the top of each
  axis are gone.
- A bind with NoBack stays quiet on the way back once a higher band on that
  side was reached; a bind without it fires as usual. Every bind (Ticks too)
  still counts as a band, and rearming is unchanged: centring the axis,
  dropping below every band or crossing to the other side.
- A bind with NoBack has the title's effect in white: a faint white outline
  with an orbiting white spark, moving in step with the title while the
  pointer is over the window. Its tooltip says which side has NoBack.
- Profiles save `noback_plus` / `noback_minus` with each bind and no longer
  write `suppress_plus` / `suppress_minus`. Older profiles load with every
  bind on a side that had NoBack + / NoBack − getting it for that side, so
  they behave exactly as before. (Versions before v108.138 do not read the
  new keys: a profile saved here and opened in an older version has no
  NoBack.)
- Clicking "SpaceNavigator Mapper" in the menu bar minimizes the window to
  the taskbar (pointing-hand cursor and a tooltip say so).
- After the brief flash while the axis is in a bind's band (window not
  activated), a Bind button goes back to its own colour; the selected bind
  used to turn red.

## v108.137 — One window: the compact view is removed

- The compact view is gone; the Mapper is the editor alone. Removed with it:
  Options > Show Full Editor (F12) and Show Compact Window (Shift+F12), the
  clickable title that switched views, and about 1,100 lines of code
  (`ui/compact_view.py`, `ui/compact_fit.py`). The title stays in the menu bar
  with its hover shimmer.
- Display > Positions Saved now saves the editor's position. Positions the
  old compact view had saved are ignored and dropped from `window_state.json`
  the next time it is written; the editor's own saved positions are kept.
- The version and date under the credit are the size of the bind comment
  lines and right-justified. The credit alone grows into the space the
  Refresh button left.
- Fixed: the editor sometimes turned completely white when SpaceNavigator
  Mapper was launched again while it was running. The second launch called
  ShowWindow on the running copy's window; when that window was hidden in the
  tray, Windows showed it without Qt painting it. Now the second launch only
  posts a private message to the running copy, which shows itself the same
  way as Restore from the tray and comes to the front. Only Qt windows are
  asked (not, say, an Explorer window on a folder of the same name).
- Tray > Profiles no longer lists `ui_preferences.json` as a profile.

## v108.136 — Tray: Profiles submenu

- Right-click the tray icon > Profiles: every profile in the configs folder
  (the same list as the compact view's Profile box), the active one checked.
  Choosing one loads it as the active profile, exactly as choosing it in the
  compact view does, without opening the window; a tray notification confirms
  it ("Active profile: …") or reports a failure. The list is read again each
  time the submenu opens.

## v108.135 — Save as: white with black letters

- The Save as button is white (#ffffff) with black letters in the compact
  view and the full editor; light gray on hover, a little darker while pressed.

## v108.134 — Compact view never full screen; scrolling comments; new colours

- Compact view: no maximize button, and it cannot go full screen (Win+Up, a
  title-bar double-click or another tool are undone at once, back to its
  content size). The full editor keeps its maximize button. The window flags
  are changed on the existing window: it is not recreated, moved or resized.
- All comment fields (the 36 bind comments and the Button 1 / Button 2
  comments) scroll text that is longer than the field, like the profile name.
  While a field is being edited it behaves as before (cursor, selection).
- The Auto-Profiles, Options and Display headings in the menu bar highlight in
  medium gray (#6b7280) with white letters, in both views (they were amber).
- Save/Reload is red (#dc2626) with white letters in both views; darker red on
  hover, darkest while a hardware button press is shown.

## v108.133 — Headings three points larger at 85%; always centred without saved positions

- At 85%, the menu-bar headings (Auto-Profiles, Options, Display) are three
  points larger (one in v108.132). The corner title and the menus are unchanged.
- With no monitor positions saved (nothing checked in Display > Positions
  Saved), the compact view and the full editor always open centred on the
  monitor they are on: at start-up (primary monitor), after a Display %
  restart, when switching views and when coming back from the tray.
  Switching views no longer keeps the previous view's top-left corner.

## v108.132 — 85% menu-bar headings; centred when no position is saved

- At 85%, the menu-bar headings (Auto-Profiles, Options, Display) are one
  point larger too. The title in the menu bar's corner and the menus (already
  two points larger at 85%) keep their size.
- A view with no saved position opens in the middle of the screen:
  - nothing checked in Display > Positions Saved: start-up is centred on the
    primary monitor (as before), and a Display % restart is now centred on the
    monitor the Mapper was on (it used to keep the old position);
  - a monitor checked, but this view has no position saved on it yet: centred
    on that monitor (it used to take the other view's position).
  Switching views with nothing checked still keeps the window where it is.

## v108.131 — 85% menus, restart in front, compact spacing at 85%

- At 85%, the Auto-Profiles, Options and Display menus and all their submenus
  get one more point (two points larger than the base font; one at 100% and
  110%).
- After a Display % restart the Mapper comes to the front of all windows. The
  closing copy allows the new one to take the foreground
  (AllowSetForegroundWindow), and the new one raises itself once it is shown
  and again a second later (briefly topmost, then not; never moved or resized).
- Compact view at 85%: the space between the Profile line and the Target row
  (and the rest of the layout) appeared only after the full editor had been
  opened and closed. Below 100% the control heights are re-checked after the
  window has been sized; the compact window is now resized to its content
  after that check, keeping its top-left corner.
- The placement tests no longer write to the real startup.log.

## v108.130 — Display > Positions Saved; larger menus; compact spacing

Replaces v108.129's monitor rules (and its Options > Always Remember Monitor
and Positions item).

- Display > Positions Saved lists the connected monitors with a check box
  each; at most one is checked. With a monitor checked, the compact view's
  and the full editor's positions on it are saved (when a view is closed,
  hidden or switched while on it, and at once when the monitor is checked),
  and both views always open there at those positions: at start-up, after a
  Display % restart and when switching views. Checking a monitor moves the
  current view there. If the checked monitor is not connected, the primary
  monitor is used at the same positions as far as they fit, and the menu
  shows it as not connected. With only one monitor, checking it means the
  positions are always restored.
- Nothing checked: positions are not restored. Start-up is centred on the
  primary monitor; switching views keeps the window where it is (same
  monitor, same top-left corner); a Display % restart keeps monitor and
  position.
- The Auto-Profiles, Options and Display menus, and all their submenus, are
  one point larger.
- Compact view: two points (3 px) more space between the Profile line and the
  Target row.

## v108.129 — Both views on one monitor; remembered monitor and positions; no Refresh button

Built on v108.119 (v108.120 to v108.128 are left out).

- Both views share one monitor. Switching views opens the other view on the
  monitor the window is on now: drag the full editor to another monitor and
  return to the compact view, and it opens there; the same the other way round.
  Each view's position is remembered per monitor (relative to its work area);
  a view not yet used on a monitor opens at its last position, clamped.
- Options > Always Remember Monitor and Positions (on by default): start on
  the monitor and at the positions last used, or the primary monitor if that
  one is not connected. Off: start centred on the primary monitor. A restart
  after a Display % change always keeps monitor and position.
- window_state.json version 5: "monitor", "views" (both on that monitor) and
  "per_monitor". Older files are read as before.
- The Refresh button is gone from both views (the target list refreshes when
  the target picker opens, when the Mapper becomes active, and in the
  background). In the compact view, Target, Save/Reload, Save as and Load share
  the row evenly; in the full editor the credit and version text are enlarged
  into the space Refresh used (up to 1.6x, without widening the header).

## v108.119 — Compact view stays on its monitor after a Display % change

On two monitors with different Windows scale settings, picking a new size in
the Display menu restarted the Mapper with the compact view on the other
monitor.

- Cause: with a scale factor per monitor, Qt's logical desktop has a gap
  between monitors, and Qt can report a window's position inside it. The
  position saved on closing then matched no monitor, so nothing was saved and
  the restart used an older record from the other monitor.
- Each view's monitor and position are now taken from Windows
  (`MonitorFromWindow`, `ClientToScreen`) in physical pixels and converted to
  that monitor's scale. Qt's geometry is the fallback.
- After a view is restored, the Mapper checks three times in the first second
  that Windows put it on the chosen monitor, and moves it back if not (at most
  twice). `startup.log` records each restore and any correction.
- `tests/test_placement.py` covers saving in the gap, the scale conversion and
  the correction.

## v108.118 — Cleaned-up repository

Same behaviour as v108.117. Recorded sessions of the whole app (startup, both
views, every menu, axis strokes, buttons, profiles, Auto-Profiles, tray,
restart, first run, Windows-login start) produce the same screens, keys and
files before and after, apart from the items under "Changed".

- The 6,400-line `core.py` and its 16 patch layers, which rewrote `MainWindow`
  and `AxisPanel` at import time, are now ordinary classes in focused modules.
  `MainWindow.__init__` lists its setup steps in order.
- One implementation of each Win32 lookup (`win32.py`), one builder for the
  data a profile stores, and Tick mode folded into the axis panel.
- Dead code removed: 540 lines of methods nested after a `return`, the
  modifier-hold overlay (it never found a bind), a second copy of the target
  filter, an unwired "New profile" action, calls to theme methods that never
  existed, an orphaned Bind Dir/Mode row, and replaced status-label code.
- Bare `except:` replaced; needless `try/except: pass` around plain Qt calls
  removed; names without version suffixes; formatted with ruff.
- A `pytest` suite that starts the whole app on a stand-in for Qt and Win32,
  GitHub Actions, and `tools/build_single_file.py` for the single-file edition.

Changed:

- The hidden target list no longer stays signal-blocked after a refresh with
  no target selected.
- Saved profiles list `comment1`/`comment2` once, after the quick keys, in
  every file. Save As used a different order; the content is unchanged.
- The status bar no longer flashes stale "Ready v108.xx" messages at startup.

## v108.117 — Tick works with NoBack

NoBack + and NoBack − now include Tick binds. Based on v108.116, so the mixed-monitor scaling fix is kept.

- A Tick counts as a band starting at its Tick%. Reaching it suppresses lower binds on the return stroke, as a higher bind does.
- A Tick below a band already reached does not fire again until the binds are rearmed. A Tick crossed in the same sample that reaches a higher band still fires on the way out.
- The NoBack buttons stay enabled, with their real on/off colours, while a Tick bind is selected.
- Binds rearm when the axis centres, crosses to the other side, or drops below the lowest band on that side (less the hysteresis). The last rule covers a DZone of 0 or a puck that rests just outside the dead zone.
- NoBack keeps tracking the stroke while the target window is out of focus. Focus returning during the return stroke no longer lets a lower bind fire.
- A fast push that reaches a higher band in one sample no longer stops a lower bind from starting on the way out.
- With NoBack off, every mode behaves exactly as in v108.116.

## v108.116 — Mixed-monitor scaling

The compact view and the full editor are sized correctly on every monitor, including monitors with different resolutions or Windows scale settings. Dragging the window to another monitor re-sizes it once it is dropped, and switching views onto another monitor uses that monitor's size.

- Windows scale settings such as 125%, 150% and 175% are used as-is. Earlier builds rounded them to 100% or 200%.
- The startup layout size is now measured on the compact view's saved monitor. Earlier builds used the primary monitor.
- Set the environment variable `SPNAV_PER_MONITOR_SCALE=0` to turn off per-monitor sizing. A `QT_SCREEN_SCALE_FACTORS` value of your own is always kept.
- `startup.log` records the factor chosen for each monitor and each re-fit.

## v108.115 — Separate window positions

Place the compact view and full editor on their preferred monitors. Switching views or closing the window saves the current position. The first full-editor opening uses the compact monitor when no full position has been saved.

## v108.114 — Restore Device LED on connection

The SpaceNavigator applies the requested LED state when its HID connection opens, including at Windows sign-in and after reconnection.

## v108.113 — Compact toolbar

Refresh is now the last button in the compact toolbar.

## v108.112 — Compiled EXE auto-start

Run the compiled Mapper from its permanent folder. In Options, enable Auto-start in System Tray with Windows. If it was already enabled by an earlier build, turn it off and back on to replace the old login command.

## v108.111 — Options and button bindings

Options includes a checkable Device LED setting above Load Backup, with Exit SpaceNavigator Mapper at the bottom. The full editor starts its button row with Button 1 and its comment. Menus and combo-box popups share the Bind Dir selection colors and outline.

## v108.110 — Compact menu title

Both views place the title toggle before Auto-Profiles. Compact mode shows the credit and version on one row.

## v108.109 — Full editor header

The title toggle precedes Auto-Profiles in the menu bar. The credit and version start at the top of the profile header, which follows the right edge of the axis panels.

## v108.108 — Bind button hover tip

Empty axis Bind buttons show “Double Click to Set” on hover. Assigning a binding clears the tip.

## v108.107 — Narrower full editor

The editor fits its three axis columns. The credit ends at Don Muddiman and the bind instruction has been removed.

## v108.106 — Narrower axis panels

Quick Bind measures the longest direction and mode selections using the current font and Qt style. The axis columns hug their controls, with the comments and NoBack pair aligned to Mode.

## v108.105 — Axis comments aligned to Mode

Based on v108.103. The right edges of the six comment fields and the NoBack group follow the right edge of the Mode dropdown in each axis panel.

## v108.103 — Axis comment alignment

The NoBack pair aligns with the right edge of the six axis comment fields. Each field is sized for 26 visible characters in the enlarged comment font.

## v108.102 — Axis bind rows

Long profile names scroll in the compact selector and the full editor. Bind buttons fit their labels. Axis comments use a larger font within their original field height.

## v108.101 — NoBack return-stroke fix

November 5, 2026. NoBack + and NoBack − suppress lower binds after a higher mapped band is reached on the selected side. Centering the axis or crossing to the other side rearms the binds. Tick uses its own directional threshold.

## v108.100 — Modular GitHub Project

Uses the same multi-file project and Windows build workflow as v108.97.
Run `py main.py` or the included Windows launcher. Build scripts and the official
application icon are included.

Retains the v108.99 fixes: Save As updates the active profile; the compact
Profile list only rebuilds when its entries or selection change; the hidden
Target selector no longer refreshes. Configuration backups remain available.
Place your existing configs folder alongside main.py to retain your profiles,
backups, and preferences. No single-file embedded module loader is used.

Revision date: 11/04/2026.

---

## v108.97 — Target Indicator Contrast

Revision date: 11/04/2026. Active green Target buttons now use black text in
both compact and full-editor views. Configuration backups are retained.

## v108.96 — Configuration Backups

Revision date: 11/04/2026.

Save/Reload first copies the existing profile into `configs/backups`, then saves
and reloads the current settings. The backup name includes the original profile
name and local date/time down to microseconds. For a first-time save, the backup
contains the new settings. If backup creation fails, the profile is not overwritten.
The live profile is replaced atomically to reduce partial-write risk.

Options → Load Backup lists the newest 30 backups; Browse all backups opens the
complete folder. Loading creates a separate profile with `_restored` in its name,
so later Save/Reload clicks cannot overwrite the backup or the original profile.
Use Save as to give the restored configuration a shorter name if desired.
Backups are retained until you remove them; they are not auto-load candidates.

Version numbers in the application, package metadata, and Windows build resource
are all v108.96. The prior compact layout and custom application icon are retained.

---

## v108.94 — Compact Layout and Display Presets

Revised from v108.94. Title restored in both views: **SpaceNavigator Mapper**.
Compact mode stacks the title above the full credit line, uses the full-editor
title background, adds space after Profile, and fits its height to the controls
with modest bottom padding.
The application name, profile file locations, keyboard mapping, and Windows
single-instance identifier are unchanged.

Current **Display** options: **85%, Auto / Default (100%), 110%**. They resize
both widgets and fonts, save the choice, and restart the app automatically.
Retired display settings (60%, 70%, 115%, 130%) fall back to 100% when an
older preference is loaded; stored profiles are not modified.

Compact view: smaller upper and lower title-row margins, credit and version
text matching the **Load** button font height, and button padding/colors
matching the Full Editor (blue standard, gray Target, amber Quick/Save, green
Target active). Long profile and target popup entries remain readable.

Full Editor at 85%: **Reset / NoBack+ / NoBack-** controls are shifted left;
NoBack- is aligned to the right edge of the comment-field column where the
available geometry permits. When the header controls are inherently wider,
they stay as far left as possible without clipping or overlap.

For 2560×1440 Windows displays, test at both 85% and 100%, including the
compact credit ending in **1954**. Monitor DPI and font substitution can
change rendered metrics; final visual validation must occur on Windows.

The ZIP contains the full modular Python project, `RUN_DEBUG_WINDOWS.bat`,
`BUILD_WINDOWS_FAST.bat`, `BUILD_WINDOWS_ONEFILE.bat`, custom icon and tests.

---

## v108.93 — Compact Header and Dropdown Fit

Based on v108.92. This release only tightens **Compact View** spacing:

- **SpaceNavigator Mapper** title has smaller vertical padding and a font-aware
  fixed height, while retaining its click-to-expand action and rainbow border.
- Profile, Mode (Auto Load/Manual On/Off), and Target **closed dropdowns** are
  narrower and no longer expand based on the longest loaded item.
- **Opened dropdown lists remain wide** so the full profile/target names and
  choices are still readable. Full target text is also available in tooltips.
- Compact card margins and top-row spacing are reduced slightly.
- The familiar compact window starting size (687×188) and saved monitor
  location are unchanged. The Full Editor is unchanged.

Test compact mode at your preferred 60%, 70%, 85%, or 100% scale on Windows.
The title/controls may render slightly differently depending on Windows DPI.

## v108.92 — Narrower Axis Fields, Direct Display Menu

Based on v108.91. In every Full Editor axis configuration panel:

- **Bind #1–#6 comments** now have a smaller font-relative width range
  (about 7–18 characters visible). The full comment is still saved and can
  be edited by scrolling within the text box. Applies at 60% through 130%.
- **Bind Dir** and **Mode** dropdown controls use the width of their longest
  option plus room for the arrow, rather than stretching across the row.
  Dropdown choices and mapping behavior are unchanged.
- **Display** now opens **directly** to the six scale choices:
  60%, 70%, 85%, Auto/Default (100%), 115%, 130%. There is no intervening
  “Interface + Font Size” submenu. Selection still saves and automatically
  restarts the app.

No changes to HID, bind logic, profile format, compact window placement,
tray behavior, icons, or the native build process. Check appearance on Windows
at your chosen screen resolution before replacing the prior EXE.

## v108.91 — Full Editor Comment & Toolbar Scaling

Based on the working v108.90 modular project. At **60%, 70%, and 85%**,
Full Editor axis comment boxes and Button 1/2 comment boxes now use the
actual scaled font to determine their preferred width and height. They no
longer expand into oversized fields or impose a 30-character minimum width.

The Full Editor's **Refresh, Target, Quick/Save, Save as, Load, Button 1,
and Button 2** controls use a content-sized button hint at those reduced
presets. Their widths adjust automatically when their text changes, avoiding
truncated hardware-key labels. The Profile filename field and editable-field
padding also scale proportionately. **100% and larger layouts are unchanged.**
The Auto Load/Manual On/Off dropdown and other dropdown popup menus are
unchanged.

Select a size directly under **Display** to set a preset. The existing
automatic restart applies the saved selection. Settings and profiles are
preserved. The device/axis input and mapping logic were not modified.

Test both Compact and Full Editor at 60%, 70%, and 85% on Windows before
replacing your working v108.90 EXE; tests here cannot verify visual Qt layout
on your particular monitor/DPI combination.

## v108.90 — Proportional Button Scaling

**v108.90** is based on the working v108.89 modular project. At 60%, 70%,
and 85% interface+font size settings, button heights and padding now follow
the scaled font instead of retaining large fixed dimensions. The Full Editor
Bind buttons also use text-sized widths (including when the assigned key
combination changes), and the Profile/Target/Save action buttons no longer
expand to fill unused row space. The small +/- buttons scale proportionally.

- The existing height safeguards for input text fields and dropdowns remain.
- 100%, 115%, and 130% button sizing is unchanged.
- Display setting changes continue to save and automatically restart.
- No config schema, device input, binding logic, monitor memory, or tray logic
  was changed.

Actual appearance depends on Windows/Qt DPI and still needs user testing.

## v108.90 — Unified Interface and Font Scaling

This update keeps the working v108.87 modular mapper and consolidates the
previously independent **Interface Size** and **Font Size** preferences.

- **Display** scale choices now scale widgets and fonts together at
  **60%, 70%, 85%, 100% (automatic/default), 115%, or 130%**.
- The Full Editor's standard Qt fonts, its explicitly-sized headings/help text,
  and the Compact View's stylesheet fonts all follow the same chosen preset.
- Applies on the next **full application restart** to rebuild widget layouts;
  merely closing to the system tray does **not** restart the program.
- Old `font_scale_factor` values in `configs/ui_preferences.json` are retained
  for backward compatibility but ignored by v108.90; `ui_scale_factor` is the
  single source of truth. Existing profiles are unchanged.
- At 60% the text is deliberately small, and minimum control heights may be
  larger than a strict geometric 60% if required to prevent clipping.
- Windows/Qt visual validation is still needed, especially across monitors.

The v108.87 hover and compact-credit updates remain intact.

## v108.83–v108.86 — Historical Display Changes

Display updates (building on v108.84 and the tested v108.82 modular baseline):

- Restores the full compact header credit ending in **1954**, with extra text width to prevent clipping.
- Shows just **v108.86** in the version label (no trailing release-description text).
- **Options → Auto-start in System Tray with Windows** registers/removes a per-user Windows Run entry. Automatic login starts hidden in the notification area; normal manual launches stay visible. Moving the EXE requires re-enabling this option at its new location.
- Earlier releases provided independent **Interface Size** (60%–130%) and **Font Size** settings; v108.90 replaces them with one unified selector.
- Display preferences are stored in `configs/ui_preferences.json` independently of profiles. **Restart the app after changing a size setting**; immediate font/geometry resizing could break legacy fixed-size widgets. The existing dual-monitor window position is preserved.
- Auto size is calculated from the **last saved compact monitor**, falling back to the primary display when unavailable. Small screens can still require scrollbars.

**Windows login setting:** applies to the current Windows user only, without administrator rights. Disabling removes the Run entry. Requires working Windows system tray; otherwise the main window is displayed. An actual Windows sign-in is not simulated in the automated tests.

## v108.82

**v108.82 startup hotfix:** Corrects a Python local-import scope collision
(`QTimer`) in `spnav_mapper/core.py::run()` that caused v108.81 to exit
immediately after first showing the UI. This release retains deferred HID/window
scans and the Options → Close to System Tray option. Run `RUN_DEBUG_WINDOWS.bat`
first, then build the Windows EXE.


### Changes since v108.80

- **Close to System Tray** (Options menu checkbox): clicking X hides the window from the taskbar while HID mapping keeps running. Double-click the notification-area icon, or choose **Restore SpaceNavigator Mapper** from its menu, to show the window. **Exit SpaceNavigator Mapper** fully quits, including when the close-to-tray option is checked. The setting migrates from the older `minimize_to_taskbar_on_close` preference.
- **Earlier first window paint**: initial HID device discovery and enumeration of running target windows are deferred briefly until after the Qt window shows. Startup log timestamps include elapsed seconds to isolate any remaining delay. No USB read loop parameters or bind processing were changed.
- **Faster repeat launches of Onefile builds**: Nuitka now uses a cached extraction directory. First start may still be slower, and some antivirus tools may add delay. Standalone folder builds avoid Onefile extraction entirely.

> **v108.80 startup fix:** Fixed `UnboundLocalError` when creating the Qt application.
> The local `QApplication` import inside `run()` was shadowing the module-level import.
> Run `RUN_DEBUG_WINDOWS.bat` first. Existing v108.77 backup remains in `legacy_reference/`.

> **v108.80 startup fix:** Run `RUN_DEBUG_WINDOWS.bat` to capture startup output.
> If nothing opens, check `%LOCALAPPDATA%\SpaceNavigatorMapper\startup.log`.
> An older copy running in the notification area will block a second instance. See [TROUBLESHOOTING_STARTUP.md](TROUBLESHOOTING_STARTUP.md).

## SpaceNavigator Mapper

**v108.80 — modular GitHub preparation release.** Windows/PyQt5 mapping utility for legacy 3Dconnexion/Logitech six-axis HID controllers.

This project reorganizes the working v108.77 source into importable modules. The existing runtime UI and window-compatibility patches remain in `spnav_mapper/core.py` in their original order to reduce regression risk. This is **a first-phase modularization, not a claim that all legacy code has already been refactored or removed**. The original source is preserved under `legacy_reference/` for comparison.

### Supported devices (physical validation varies)

SpaceTraveler (046D:C623), SpacePilot (046D:C625), SpaceNavigator (046D:C626), SpaceExplorer (046D:C627), SpaceNavigator for Notebooks (046D:C628), and SpacePilot Pro (046D:C629). Device support beyond the original SpaceNavigator has not been validated with physical hardware.

### Run from source (Windows)

1. Install **64-bit Python 3.11 or 3.12**.
2. From this folder, open Command Prompt and run:

   ```bat
   py -3.12 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   .venv\Scripts\python main.py
   ```

   You can also double-click `SpaceNavigatorMapper.pyw` after installing dependencies into the Python association used by Windows.

Profiles/settings are stored in `configs/` beside `main.py` during source runs and beside the EXE for a compiled run. This folder is ignored by Git to avoid publishing personal profiles or paths. Copy `configs/` when transferring existing configurations.

### Full Editor Options and Display controls (v108.90)

The former **View** menu is now **Options**. It contains window switching,
minimizing, Close to System Tray, exit, and Windows login auto-start settings.
The **Display** menu shows the six interface/font size actions directly.
Interface presets are 60%, 70%, 85%, Auto/Default (100%), 115%, and 130%.
The 60% and 70% choices are relative to the monitor/DPI automatic scale;
the adjusted minimum allows them to work even on 1920×1080 displays, although
some fixed-size Qt widgets may still clip or need scrollbars. Full Editor and Compact View fonts now scale together with controls, including
previously fixed-size title fonts and stylesheet-defined text. Small text can
be difficult to read at 60%; Qt may preserve a minimum height to prevent
clipping. Changes require quitting the app completely and reopening it.


The Full Editor's clickable **SpaceNavigator Mapper** title is now only as wide
as its text and existing rounded-border padding. The hover rainbow effect and
click-to-switch-to-compact behavior are unchanged.

### Compile Windows EXE with Nuitka

- Run **`BUILD_WINDOWS_ONEFILE.bat`** for one portable EXE (slower startup due to extraction).
- Run **`BUILD_WINDOWS_FAST.bat`** for a faster-starting EXE plus `.dist` dependencies.
- Compiler output and errors are written to `BUILD_LAST_RUN.log`. The build helper requires 64-bit Python 3.11 or 3.12, sets up its own build environment, and includes the supplied `SpaceNavigatorMapper_default.ico`.
- The EXE is not prebuilt or signed. Building requires internet to install dependencies and possibly download compiler support tools; runtime doesn't depend on online compilation.

### Structure

| Path | Responsibilities |
|---|---|
| `main.py`, `SpaceNavigatorMapper.pyw` | Launch entry points |
| `spnav_mapper/single_instance.py` | One-process Windows mutex |
| `spnav_mapper/devices.py` | HID enumeration, six-axis decoding, LED support |
| `spnav_mapper/keyboard_io.py` | Keyboard scan codes and Windows SendInput |
| `spnav_mapper/paths.py` | Executable-relative config paths |
| `spnav_mapper/settings.py` | Shared constants, 36-bind settings |
| `spnav_mapper/ui/scaling.py` | DPI/monitor scaling helpers |
| `spnav_mapper/ui/title_controls.py` | Full Editor title label sizing |
| `spnav_mapper/ui/keyboard_popup.py` | Key assignment dialog |
| `spnav_mapper/ui/widgets.py` | Bind and automatic-profile widgets |
| `spnav_mapper/ui/axis_panel.py` | Six-bind axis editor |
| `spnav_mapper/core.py` | MainWindow, target/profile features and legacy compatibility patches |
| `spnav_mapper/resources/` | Official icon |
| `legacy_reference/` | v108.77 source for regression reference, **not imported at runtime** |

### Tests

```bat
py -3.12 -m unittest discover -s tests -v
```

Tests verify pure report decoding, IDs, bind count, and scan-code helpers. **They do not substitute for Windows UI, input-device, profile-save/load, or compiled-EXE testing.**

### Before publishing on GitHub

- Choose a project **LICENSE** (none has been assumed on your behalf).
- Check the attribution/credits and review all source for embedded personal details or environment-specific information before making the repository public.
- Run a Windows regression pass: startup, compact/full toggle, second-monitor positioning, config load/save, all six bind slots, minimize and exit, tray tooltip, second instance blocking, rainbow hover.
- Verify the icon license/ownership and any third-party dependencies before distribution.
- Build and test both EXE formats on Windows.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.


#### v108.86: readable controls with 60%, 70%, and 85% interface scaling

Windows DPI and native font rendering put a lower bound on control height.
The previous UI scaled fixed button and dropdown heights down to 12–20
logical pixels while retaining a 9-point font or larger. This clipped
letters at the bottom of the Profile and Bind Dir/Mode controls, and at
60% also clipped the Reset, NoBack, Bind, target, save/load, and comment
controls.

The updated control-sizing helper keeps scaled widths and layout spacing,
but measures Qt font metrics and styled size hints before setting a control
height. It rechecks styled widgets after the window has been built and when
switching views. At small scales, some controls will stay taller than the
nominal preset to preserve text readability; scrolling is retained where
necessary. Existing 100% and larger preset heights are unchanged.

To test on Windows, choose **Display → 85%/70%/60%**,
restart, then inspect the Full Editor (Profile, Bind Dir, Mode, six bind
buttons, Reset and NoBack) and Compact view (Target, Save, Load,
Button 1/2 and comments). Run `RUN_DEBUG_WINDOWS.bat` for diagnostic output.


### Display scaling (v108.90)

Open **Display** and select a new preset. The
application immediately saves the setting and **restarts itself**; the next
copy waits for the old instance to release its Windows mutex, so there is no
second copy running simultaneously. The previous process exits normally,
not to the system tray, ensuring configuration and window geometry are saved.
At the smaller scale presets, Bind buttons are allowed to use a narrower
preferred width instead of expanding across each entire row. For text
readability, buttons keep minimum heights based on their font/style metrics,
so they may not shrink exactly in proportion to the percentage.

If an automatic restart fails, the setting is still saved; exit fully through
**Options → Exit** and run the app again. Diagnostic log:
`%LOCALAPPDATA%\SpaceNavigatorMapper\startup.log`.
