# SpaceNavigator Mapper — Full Editor README

**Application:** SpaceNavigator Mapper (Windows / PyQt5)  
**Version:** v108.176 (11/14/2026)  
**Purpose:** Map a 3Dconnexion SpaceNavigator's six motion axes and two hardware buttons to keyboard inputs.  
**Interface covered:** the Full Editor, the application's only interface. Compact Mode was removed in v108.137.  
**Logic by:** Don Muddiman  
**Code by:** Don Muddiman, ChatGPT and Claude

> **Documentation basis and version note:** This edition updates the earlier Full Editor README (written from the v71.21 source) to the current source (the version above): the `spnav_mapper` package, which is also built into the single-file edition and the EXE. Everything below was checked against that source and its automated tests, which run the whole application against simulated Qt, Windows and HID layers. Only the original SpaceNavigator has been tested with real hardware. This README documents features and function responsibilities; it does not certify that every code path is bug-free. The release history of every version is in `CHANGELOG.md`.
>
> **Main additions since the v71.21 edition:** six binds per axis (36 motion binds); Tick and Macro modes; NoBack per bind, chosen by right-clicking a Bind button; green Bind Dir and white NoBack lines on the Bind buttons; the axis name and value in each panel's border (the Reset button moved to the right-click menu); Auto Load / Manual On / Off; Auto-Profiles; Save/Reload with a confirm prompt whose file name can be changed; Load Backup; Delete Linked Program; Display sizes and Positions Saved; the system tray and its Profiles menu; one running copy; the EXE build; and this README, as a PDF or in a window, from a right-click on the title.

## 1. What the application does

SpaceNavigator Mapper reads a SpaceNavigator HID device and turns its motion and its two hardware buttons into Windows key-down and key-up events, sent only to a chosen target program. It shows six axis panels, each with six binds. Each bind chooses a direction (positive, negative or both), a mode, a motion band in percent with its own dead zone, a key combination or a macro, NoBack per side and a comment.

**Axes and orientation labels:** `X`, `Y`, `Z` are translational axes; `Rx`, `Ry`, `Rz` are rotational axes. Each axis can move toward its positive (`+`) or negative (`−`) direction. The device's reports are normalized to `−1.00 … +1.00`; bands are percentages of that travel (0–100% on each side).

**Capacity:** 6 axes × 6 binds = **36 motion bindings**, plus **2 SpaceNavigator hardware-button bindings**.

**Supported USB devices:** SpaceNavigator (046D:C626), SpaceNavigator for Notebooks (C628), SpaceTraveler (C623), SpacePilot (C625), SpaceExplorer (C627) and SpacePilot Pro (C629). No 3Dconnexion driver is needed.

## 2. Full Editor — controls and behavior

| Control | What it does |
|--------------|----------------------------------------------|
| **SpaceNavigator Mapper** title (menu bar, top left) | Click: minimize the window to the taskbar. Right-click: a drop-down with **Open README (PDF)** (this README in your PDF viewer) and **Open README in a window** (the same text in a window of the Mapper, with a choice of text sizes). Its border glows with a rainbow while the pointer is over the Mapper. |
| **Profile:** button and display | The display shows the loaded profile's file name (long names scroll). Click it, or the dark gray **Profile:** button beside it, to open the target list (see section 4). |
| **Delete Linked Program** (top of the target list) | Removes the program linked to the loaded profile, then saves and reloads the profile, after a confirm prompt (section 5). |
| **Auto Load / Manual On / Off** | How output is switched on: by the target program being in front (Auto Load), always (Manual On), or never (Off). See section 4. |
| **Target: OFF / ON** | Turns output on or off. In Auto Load it follows the target program automatically; it flashes while the Mapper itself, not its target, is in front. **Target: ON (History)** while the Axis History window is open (section 4). |
| **Save/Reload**, **Save as**, **Load** | The same width, from Target to where the **Profile** box ends; Target keeps its width. |
| **Save/Reload** | Asks first, showing the file name, then saves the profile and loads it again. Keep the name to save over the profile; type a new one to save a new profile and load it (section 5). |
| **Save as** | Opens a file dialog to save the profile under a new `.json` name. |
| **Load** | Opens a file dialog to load a profile. |
| **Button 1: / Button 2:** | Click to pick the key combination for the device's left or right button; the label shows it. The button lights while the hardware button is pressed. |
| **Button comments** | A short note (up to 28 characters) beside each hardware button, as wide as an axis bind's comment; a longer note scrolls. |
| **Axis panel border** | Shows the axis and its live value, such as `X: 0.42` or `Rz: −0.38`. The border blinks while the axis moves with output off. Right-click the border (or an empty spot in the panel) for **Axis History…**, which shows that axis among the others (see *Axis history*). |
| **Bind #1 … #6** | Click to select a bind for Quick Bind; the label shows its keys. Double-click to pick its key combination, or to edit its macro in Macro mode. Right-click for **NoBack** (for the way back: **NoBack −** on a POS bind, **NoBack +** on a NEG bind, both on a FULL bind; none on a Tick bind), **Edit macro…** and **Reset *axis* axis** (clears all six binds of the axis). The menu opens beside the button, its left edge at the button's right edge, so the mouse pointer does not cover its check boxes. |
| **Green line** (top of a Bind button) | The bind's Bind Dir: from the middle to the left for NEG, to the right for POS, both ways for Full; no line for [None]. |
| **White line** (bottom of a Bind button) | The bind's NoBack, toward the way back, opposite the green Bind Dir line: from the middle to the left for NoBack − (a POS bind), to the right for NoBack + (a NEG bind), both ways for both (a FULL bind). |
| **Comment beside each bind** | A note for that bind; it is saved with the profile. |
| **Quick Bind: Bind Dir** | `POS (+)`, `NEG (-)`, `Full` or `[None]` for the selected bind. |
| **Quick Bind: Mode** | `Hold`, `Press/Release`, `Release-only`, `Press/Repeat`, `Tick` or `Macro`. |
| **Min% / Max%** | The selected bind's band; `−` and `+` step the value (0–100); hold one to keep stepping. Their signs fill most of the button, at every Display size. In Tick mode Min% becomes **Tick%** and Max% is not used. |
| **Tap Dwell** (above DZone) | How long each tap of the selected bind holds its key down: 0–200 ms, 45 ms by default; `−` and `+` step it by 5 ms. Used by Press/Release, Press/Repeat, Tick and a macro's Tap steps; greyed out for Hold and Release-only, which send no taps. |
| **DZone %** | The selected bind's own dead zone. The bind starts at DZone% + Min% (at most 100%). |
| **Repeat every (ms)** | For Press/Repeat and for Macro with Play: Repeat: 10–2000 ms in steps of 10. Press/Repeat never taps sooner than its Tap Dwell plus 30 ms; when that is longer, an amber **→ N ms** beside it says how often it really taps. |
| **Play: Once / Repeat** and **Edit macro…** | Shown in Macro mode (see *Macros*). |
| **Hover tips** | Resting the mouse on a menu item, on Bind Dir, Mode, Min%, Max%, DZone and their `−` / `+`, on Button 1 / Button 2, Target, Save/Reload, Save as or Load shows what it does. |
| **Status bar** | Messages, the Auto-Load badge (Waiting / Loaded / Manual) and **Game Time** (time with output on; double-click to reset). |

### Binding directions

- **POS (+):** the bind responds only while the axis value is positive.
- **NEG (−):** the bind responds only while the axis value is negative.
- **Full:** the bind responds on either side. NoBack − is for the way back from its positive side and NoBack + for the way back from its negative side.
- **[None]:** no direction is selected, so the bind does not trigger.

### Binding modes

| Mode | Function |
|---------|---------------------------------------------------|
| **Hold** | Key down when the axis enters the band, key up when it leaves. A Hold key stays down at least 60 ms, and by default keeps holding beyond Max%. Leaving uses a 3% hysteresis so the key does not chatter at the edge. |
| **Press/Release** | One tap (key down, tap dwell, key up) on entering the band; it can tap again after leaving and re-entering. |
| **Release-only** | Sends only a key-up on entering the band. |
| **Press/Repeat** | A tap on entering the band, then a tap every *Repeat every* ms while the axis stays in it (at least Tap Dwell + 30 ms apart). |
| **Tick** | One tap when the axis crosses Tick% moving outward, none on the way back; it rearms once the axis comes back below Tick% (less the 3% hysteresis). A Tick bind has no NoBack: it taps each time it is crossed going out. |
| **Macro** | Plays the bind's steps on entering the band. *Play: Once* plays them each time; *Repeat* plays them again every *Repeat every* ms while the axis stays in the band, never two runs at once. |

The **Tap Dwell**, the time a tap holds its key down, is set per bind in Quick Bind (0–200 ms, 45 ms by default); raise it if a program misses short taps. It is not **Repeat every**, which is the time from one tap to the next in Press/Repeat.

How the two work together (v108.167): a tap presses its key and releases it after its Tap Dwell while the Mapper keeps running (before, the Mapper stopped for the dwell: the device was not read and the other axes waited). After the release the key stays up at least 30 ms before it is pressed again, so a game that reads its keys once a frame sees it released: Press/Repeat taps every *Repeat every* ms, or every Tap Dwell + 30 ms when that is longer (Repeat every 60 ms with a 45 ms dwell: every 75 ms; before, the key was up only 15 ms, or not at all when Repeat every was shorter than the dwell). A tap of a key that is still down or was just released, from the same bind re-entering its band or another bind with the same key, waits for it, and several such taps make one. Two Tap steps of the same key in a macro get 30 ms between them too (a Delay there counts). Switching output off releases every tap still down at once. Two binds that use the same key still share it: a tap of a key that a Hold bind is holding releases it.

A profile from before v108.166 has one tap dwell for every bind (`tap_down_ms`): its binds start with that value.

### How NoBack works

NoBack keeps lower bands quiet while the axis returns toward centre after a higher band on the same side was reached. It is set **per bind**, for the way back:

1. Right-click a Bind button and check NoBack. It is named by the direction the axis moves on the way back, the opposite of the Bind Dir, and only that one is offered: **NoBack −** for a POS bind, **NoBack +** for a NEG bind, both for a FULL bind (one for the way back from each side). A bind without a Bind Dir, or a Tick bind, has no NoBack to set.
2. As the axis travels outward on a side, the Mapper remembers the highest band (of any bind on that side) reached so far.
3. On the **return** toward centre, a bind with NoBack on that side does not start if a higher band was reached earlier in this stroke. A NoBack bind that is still active is released once the axis falls below the highest band reached.
4. Centring the axis, dropping below every band, or crossing to the other side rearms it.
5. Binds without NoBack fire as usual. Every bind counts as a band, Tick binds too: a Tick has no NoBack of its own, but its Tick% is a higher band for the binds below it.

**When NoBack makes a difference.** NoBack only stops a lower bind from *starting again* on the way back, or ends it early. So it changes what is sent when:

- the lower bind's band ends below the higher bind's start (its **Max%** is lower), so the axis enters it again from above on the way back (a Press/Release tap, a Release-only key-up, a Macro, a Hold press);
- the lower bind is a **Hold** bind: its key is released as the axis comes back below the highest band reached, not at the bind's own start;
- the lower bind is **Press/Repeat**: it stops repeating below the highest band reached;
- the axis dips and rises again on the way back (a wobble) above the lowest bind.

With the usual **Max% 100**, a lower **Press/Release** or **Release-only** bind is still inside its band on the way back and never starts again, so NoBack changes nothing for it. (Release-only sends its key-up on entering its band going out, like a Press/Release tap; it sends nothing on the way back.) **Axis History** marks *held by NoBack* only where NoBack really kept a key from being sent (it compares with the binds run without NoBack), so no mark means NoBack made no difference.

NoBack can only hold a bind back below a **higher** band on the same side: the highest bind on a side, or the only one, has nothing to hold. **Options > Axis History** shows whether it is working (see *Axis history*): the binds with NoBack, the highest band reached while it is in force, and every bind it held back.

Changing a bind's Bind Dir from POS to NEG (or back) takes its NoBack along. Changing a bind's Mode to **Tick** sets its NoBack aside: it is not shown or used while the bind is a Tick, and works again if the Mode is changed back. A profile saved before v108.161 with NoBack set for the side a bind does not have (NoBack − on a POS bind under the earlier naming, which did nothing) loads with NoBack for that bind's way back. Profiles saved before v108.138, with NoBack for the whole axis, load with that NoBack applied to every bind of the axis.

### Macros

Choose **Macro** as the Mode, then double-click the Bind button (or click **Edit macro…**) to open the macro editor. A macro is a list of up to 50 steps, played from the top:

- **Tap**: press and release a key or combination (it holds for the tap dwell);
- **Down**: press a key and keep holding it;
- **Up**: release a key held by a Down step;
- **Delay**: wait 0–10,000 ms.

**Move Up**, **Move Down** and **Delete** arrange the steps; **Save** keeps them. Macros play without pausing the device reading. Keys still held by a Down step are released when the macro ends, and turning the Target off, loading a profile or exiting stops a playing macro and releases its keys.

### Hardware buttons and keyboard picker

The keyboard picker offers ordinary keys, modifiers (Ctrl, Shift, Alt), function and special keys, and symbols. Modifiers combine with the chosen main key. **Save & Close** keeps the selection, **Clear** removes it and **Close** leaves without changes. **Button 1** and **Button 2** hold their combination while the hardware button is held.

### Axis history

**Options > Axis History** records what every axis does and shows it as a graph, to see how an axis behaves and why a key fired or did not. It is checked while the **Axis History** window is open; while it is, the Mapper keeps the last 30 seconds of each axis: the device's value every 16 ms (before the dead zone), every key its binds send, and the moments NoBack held a bind back. Checking it opens the **Axis History** window:

- **Axes** (X, Y, Z, Rx, Ry, Rz) choose which axes are shown, any number at once. **All** is green while all six are shown (click it to hide them all) and red otherwise (click it to show all six). Each axis has its own colour, used for its check box, its name and, in **One graph**, its line.
- **Show** lays them out: **Separate graphs** (each axis in its own graph, one under the other; the window scrolls when they do not fit) or **One graph** (the axes over each other, to compare them).
- **Each separate graph** shows its axis from −100% to +100% over the last 5, 10 or 30 seconds (**Show the last**):
  - **Lines:** the axis is a **white** line. The **+100%** line is dashed **green**, **0** dashed **blue** and **−100%** dashed **red** (their labels on the left in the same colours); ±50% are faint. The dead zone is shaded grey.
  - **Bind colours:** each bind has a basic colour of its own, the same on every axis: **Bind #1 red, #2 orange, #3 yellow, #4 green, #5 blue, #6 purple**. A dotted line in that colour marks where the bind starts (its DZone% + Min%, or its Tick%).
  - **The binds' labels** stand in a column to the right of the graph, one row per bind and side, from the top (+100%) down: **Bind**, **#n**, **(key)** and the percent, each in its own column, lined up, and NoBack last. Rows are spread so they never overlap, however close the binds start, and a thin line in the bind's colour joins each row to its start line. When the window is narrow, the keys, then the word *Bind*, are left out; each graph is tall enough for a row per bind side.
  - **Dots:** a dot in the bind's colour for each key it sends (down, up, tap or macro), **filled** when sent and **hollow** when not sent, labelled with its key (*A tap*, *A tap (not sent)*). A label goes beside its dot where it covers no other dot or label, or is left out (the dot's colour still names the bind); more than 14 events in view are shown as dots only.
  - **Sent or not:** while the window is open the Target is on for the current profile, and the keys are sent with this window in front too (it ignores them), so they show as sent (section 4). While output is off (the Mapper's editor or another of its dialogs in front, or the game in front with the mode not letting keys through), the binds still run on a copy that sends nothing, and the keys they would have sent show as hollow dots, *(not sent)*.
  - **NoBack** is shown in a light colour, like the NoBack line on the Bind buttons. In the labels' column a bind with NoBack on that side reads **NoBack**, or **NoBack: nothing to hold** when no higher bind on that side could make it hold. While NoBack is in force, a thin dashed light line marks the highest band reached (*NoBack 45%*); NoBack binds below it stay quiet until the axis returns to centre or drops below every band. A hollow light dot (*A held by NoBack*) marks each key NoBack kept from being sent (only where, without NoBack, the bind would have started; see *When NoBack makes a difference*), and the summary line lists the binds with NoBack as their menus name it (*NoBack: Bind #1 −, Bind #2 −* for POS binds).
- **One graph** shows the lines of every axis shown, each in its axis's colour so they can be told apart, with the binds' dots in their colours and labelled with the axis (such as *X: A down*); the bind lines and dead zones, which differ by axis, are left to the separate graphs.
- **Text size** (**A−** / **A+**: 100% to 200%) sets the size of all the window's text, the graphs' labels included (the binds' labels, the percents, the times and the keys sent); at 100% it is 2 points larger than the app's, and it opens at 125%. Each graph is at least nine lines of that text tall.
- **Pause** freezes the graphs (recording goes on); **Clear** forgets what was recorded; **Save as CSV…** saves the samples and events of the axes shown, as shown (axis, time, value in percent, event, bind, key).
- **The lines under the graphs** sum up each axis shown, for example *X: Peak +72%, −40% · Bind #1 pressed 1× · Bind #2 tapped 1× (not sent) · NoBack held 1× · NoBack: Bind #1 −*.
- **The window** opens at 80% of the width and height of the Mapper's screen, centred; resize it as you like. The axes, the layout, the time span, the text size and the window's size are remembered for next time.

Closing the window, or unchecking **Options > Axis History**, turns it off: recording stops and what was recorded is forgotten. Right-click an axis panel's border for **Axis History…** to open it again with that axis among the ones shown. When the window was open as the Mapper exited, it opens again with the editor next time (not when the Mapper starts in the tray). Recording costs next to nothing; the graphs redraw 20 times a second only while their window is open.

What it shows well: how far you really push an axis (a bind that starts beyond your usual peak never fires), whether the puck drifts or shakes near the centre (widen the dead zone), why a key fired twice (the axis dipped back under a band) or not at all (NoBack, or the band never reached), and how fast your strokes are (for Tick and Press/Repeat).

### Menus

| Menu | Items |
|---------|---------------------------------------------------|
| **Title** (right-click) | Open README (PDF); Open README in a window. |
| **Auto-Profiles** | Enable Auto-Profiles; Switch to… (the profiles whose rules match the program in front: pick one to load it; it stays for that program); Reload Auto-Profiles; Open auto_profiles.json…; Open Auto-Profiles Folder…. No separator lines. |
| **Options** | Minimize to Taskbar; Close to System Tray; Auto-start in System Tray with Windows; Device LED; Axis History (records the axes and shows the graph); Load Backup (the 30 newest backups, and Browse all backups…); Restart as Administrator (shown as Running as Administrator when it is); Exit SpaceNavigator Mapper. |
| **Display** | 85%, Auto / Default (100%) and 110% interface and font size (the Mapper restarts to apply it, from the same folder, with the same profile loaded); Positions Saved (see section 6). The menus' text is 2 points larger than the app's and the menu-bar headings 3 points, at every size. |
| **Taskbar button** (right-click) | **Exit SpaceNavigator Mapper** (under Tasks): the Mapper exits, as Options > Exit does. **Restore SpaceNavigator Mapper**: shows the running Mapper, from the tray, the taskbar or behind other windows; with none running it starts the Mapper. Windows' own **Pin to taskbar** and **Close window** follow. |
| **Tray icon** (right-click) | Restore SpaceNavigator Mapper; Minimize to Taskbar; Profiles (load one and make it active without opening the window); Exit SpaceNavigator Mapper. Its text is 2 points larger than the app's. Double-click the icon to restore the window. |

A drop-down from the menu bar (**Auto-Profiles**, **Options**, **Display**) stays open while the mouse is over it, one of its submenus or the menu bar, and closes on its own 0.4 seconds after the mouse has moved away from them (a short trip across a gap does not close it). One opened from the keyboard stays open until the mouse has been over it.

## 3. Typical setup workflow

1. Open SpaceNavigator Mapper and check that the status bar reports a connected SpaceNavigator.
2. Load a profile, or start from the current one and use **Save as** to give it a name.
3. Start the game or program, click the **Profile** name and choose its window as the target; answer **Yes** to save the target, and its program, in the profile.
4. Choose **Auto Load** (output only while the target is in front) or **Manual On**.
5. Pick an axis, then one of its six binds.
6. Choose **POS**, **NEG** or **Full** and a **Mode**.
7. Set **Min%**, **Max%** (or **Tick%**) and **DZone%**, and **Repeat every** or **Play** where the mode uses them.
8. Double-click the Bind button to assign a key or shortcut (or the macro steps); add a comment.
9. While editing and testing, use **Manual On** (in Auto Load the first change offers to switch), so another program coming in front cannot load a profile over your unsaved changes.
10. Right-click the Bind button to set **NoBack** (− for a POS bind, + for a NEG bind; not for a Tick bind) if lower bands should stay quiet on the way back.
11. Test the movement in the target program, then **Save/Reload** (the same file, or a new name typed in its prompt) or **Save as** (a file dialog).

## 4. Target selection, activation, and safety

The Mapper lists eligible top-level windows with their titles, class names, executable paths and process ids; known system and console windows are left out by pattern (`OMIT_EXE_PATTERNS`, `OMIT_TITLE_PATTERNS`, `OMIT_CLASS_PATTERNS` and `OMIT_PATH_PREFIXES` in `win32.py`). The list refreshes when the target list opens, when the Mapper becomes active and in the background. Click the **Profile** name to see it: **Delete Linked Program** is at the top, then **[None]** and the windows; the profile's saved target is checked.

Keys are sent only when output is on **and**:

- **Auto Load:** the window in front belongs to the target program's process. Output switches on and off as the target comes and goes, and Auto-Profiles may load the matching profile (section 5). The Mapper's own window does not count: going to the Mapper to edit a profile and back to the game keeps your edits (the profile is not loaded again). A loaded profile that is one of the program's (listed in its Auto-Profiles group) stays loaded when that program comes in front: Auto Load loads another only for a program whose profiles do not include it (since v108.171; before, going back to the game with the second of two profiles for it loaded, or one opened with **Load**, loaded the first from its file, and changes not yet saved were gone). The first change to a profile while Auto Load is on asks **Editing in Auto Load: Switch to Manual On while you edit and test?** — **Yes** switches to Manual On (choose Auto Load again after Save/Reload); **No** keeps Auto Load. It asks again after the profile is loaded or saved, or Auto Load is chosen again.
- **Manual On:** any window is in front **except the Mapper itself** (its window, a dialog or a menu). The Mapper never types into itself.
- **Off:** never.

**While the Axis History window is open** the Target is on for the current profile (the button reads **Target: ON (History)**), whatever the mode, and keys are also sent while that window is in front: no control in it takes the keyboard, so the keys land on the window and do nothing, and the history marks them as sent. The mode is not changed or saved; closing the window puts the Target back as the mode has it. Choosing a mode or clicking the Target button meanwhile ends it. The Mapper's editor, its other dialogs and menus still never receive keys.

Turning output off, losing the target, loading a profile, closing or exiting releases every held key and stops macros, so keys are not left stuck. Only one copy of the Mapper runs: launching it again brings the running copy to the front, even from the tray.

## 5. Profiles, saving, loading, and persistence

Profiles are **JSON (`.json`) files** in the `configs` folder beside the launcher (`main.py`, the single-file `.py` or the EXE).

| File | Holds |
|----------------------|--------------------------------------|
| `configs\*.json` | Your profiles. |
| `configs\last_path.txt` | The profile to open at start-up. |
| `configs\last_config.json` | The state at the last exit (used when `last_path.txt` has no valid profile). |
| `configs\auto_profiles.json` | Auto-Profiles rules. |
| `configs\window_state.json` | The editor's saved position on each monitor. |
| `configs\ui_preferences.json` | Interface size, Close to System Tray, LED. |
| `configs\backups\` | A copy of the previous file on every save (never pruned). |
| `%LOCALAPPDATA%\SpaceNavigatorMapper\startup.log` | The start-up and error log (and a copy of this README for the PDF viewer). |

- **Save/Reload** asks first. Its prompt shows the file name: keep it to save over the profile and reload it, or type a new name (with or without `.json`) to save the settings as a new profile in the same folder and load that one; the file loaded before stays as it is. The prompt says what will happen as you type, and refuses names Windows cannot use and the names of the Mapper's own settings files (`last_config`, `auto_profiles`, `ui_preferences`, `window_state`). A name that already exists is replaced, with its previous contents in the backups folder. **Save as** saves under a new name with a file dialog. Every save first copies the previous file into `configs\backups`; a save whose backup fails is not written.
- **Load Backup** (Options) copies the chosen backup into `configs` as a new `…_restored` profile and loads that copy; the backup itself is never changed.
- **Delete Linked Program** (top of the target list) removes the target program from the loaded profile: after **Yes** at the confirm prompt it clears the target, saves the profile (the previous contents go to the backups folder), removes the profile from the Auto-Profiles groups for that program, and reloads it. The profile file itself is kept.
- At start-up the Mapper loads the profile named in `last_path.txt`, else `last_config.json`.

**Auto-Profiles.** In Auto Load the Mapper checks the program in front every 1.5 s and loads the profile its rules choose. `auto_profiles.json` holds groups; each group has a `match` (wildcards for `exe`, `title` or `product`) and `profiles` with a `path`, a `priority` and `enabled`. The first enabled profile by ascending priority wins. **Switch to…** lists the profiles of the group that matches the program in front, lowest priority number first; the one picked is loaded at once and stays for that program in Auto Load (before v108.165 the top-priority profile came back as soon as the program was in front again), until another is picked, **Reload Auto-Profiles** is used, or the Mapper restarts. The file is created from the target programs saved in your profiles on first use, and reloaded when edited. A profile saved (Save/Reload, Save as), loaded, or given a target while its target program is set is added to that program's group, last, with the next priority (a group is made for the program when it has none), so **Switch to…** lists every profile with that target; **Delete Linked Program** takes it out again. Before v108.170 only the profiles there when the file was first made were listed. A group with no pattern at all matches no program, and `last_config.json` is never one of a group's profiles.

### Profile fields

| Field | Content |
|----------------------|--------------------------------------|
| `axes` | The six axes (`X`, `Y`, `Z`, `Rx`, `Ry`, `Rz`), each with `dead`, `selected` and six `binds`. |
| `binds` | Per bind: `direction`, `combo`, `mode`, `min`, `max`, `dead`, `comment`, `noback_plus`, `noback_minus`; `repeat_ms` for Press/Repeat and Macro; `tap_ms` (Tap Dwell) for Press/Release, Press/Repeat, Tick and Macro; `macro` and `macro_repeat` for macros. |
| `target`, `target_exe`, `target_app_name`, `target_product_name`, `target_file_description` | The target window and program. |
| `quick_key1`, `quick_key2` | The key combinations of Button 1 and Button 2. |
| `comment1`, `comment2` | The hardware-button comments. |
| `led_on` | The Device LED setting. |
| `auto_mode`, `auto_select_mode` | Auto Load / Manual On / Off. |
| `hys_pct`, `min_hold_ms`, `hold_ignore_max`, `tap_down_ms` | Bind timing: 3%, 60 ms, true and 45 ms by default. `tap_down_ms` is the Tap Dwell of a bind that has no `tap_ms` of its own. |
| `version` | The Mapper version that saved the file. |

## 6. Monitor sizing and Full Editor layout

The editor is sized for the monitor it is on, using that monitor's resolution and Windows scale setting, and refits when it is dragged to a monitor with another scale (once the drag ends). Each axis grid scrolls rather than clips when space is short. **Display** offers 85%, 100% and 110% for the interface and its fonts; each step makes the text, the menus and the controls larger, and every control is at least tall enough for its text.

On a smaller screen the whole editor, its fonts included, is drawn smaller, so it takes about the same share of the screen as on a 3840 x 2160 monitor at 225%. A screen whose area is at least 1700 x 900 Qt pixels (the screen size divided by the Windows scale, less the taskbar) is not affected; a 1920 x 1080 screen at 125% draws the editor at about 90%, and at 150% at about 75%. **Display** 85% and 110% apply on top of that. `startup.log` records the size the editor needs and the room the screen has (`Editor size: needs …`).

The editor's title bar has no maximize button; a maximize from the keyboard (Windows + Up) or by dragging the window to the top of the screen is undone.

**After changing the resolution or Windows scale.** Windows finishes a scale change only at the next sign-in, and until then Qt programs started after the change get a default font of the wrong size: too large when the scale went down (225% to 100%: more than twice as large), too small when it went up. The Mapper measures the size Windows meant and uses it, so it starts at its normal size; `startup.log` then notes "The Windows scale changed since sign-in". A Mapper that was already running keeps its size. Signing out of Windows and back in finishes the change for every program. Windows' own parts of the window, such as scroll bars, may stay too large until then.

**Two or more monitors.** The Mapper sizes the editor for every monitor connected when it starts: each one gets its own Qt scale factor, so the editor is the same physical size on each, and the window is refitted when it is dragged to another one. Those sizes are fixed until the Mapper restarts. When a monitor is connected after the start (at a Windows sign-in the Mapper can start before every monitor is ready), or a monitor's resolution or Windows scale is changed, the editor would be drawn at the wrong size on it, so the Mapper asks **Monitors Changed: Restart the Mapper now?** while the editor is shown (or when it is next shown from the tray), naming the monitors concerned. **Yes** restarts it, as a Display size change does, and the editor comes back where it was. **No** keeps it as it is, and the question is not asked again for the same monitors. A monitor disconnected, or a taskbar moved, needs nothing, so nothing is asked. Where the window goes is decided from Windows' answer: when Windows moves the just-opened editor to another monitor (it can, between monitors with different scales), the editor is moved back to its monitor, at its full size.

**Positions Saved** (Display menu) lists the connected monitors. Check one: the editor's position on it is saved, and the editor always opens there, at start-up too (on the primary monitor when that one is not connected). With no monitor checked the editor opens in the middle of the screen. Either way, once the editor is shown it is measured again and the window grows, if needed, to hold all of it.

## 7. Operational notes and limitations

- **Platform:** Windows 10 or 11 (Win32 APIs through `ctypes`). **Toolkit:** PyQt5.
- **Device access:** `hidapi` (`hid`); `pywinusb` is used for the LED when available. The LED works on the original SpaceNavigator.
- **Sampling:** the device is read every 8 ms (`POLL_MS`) and the binds run every 16 ms (`GUI_MS`); real timing depends on Windows and the Qt event loop. Whether the device is still plugged in is checked once a second (a read error is noticed at once).
- **Errors:** an unexpected error while the Mapper runs is written to `startup.log` (section 5) and the Mapper keeps running.
- **Running:** `py main.py` (Python 3.10 or newer, after `py -m pip install -r requirements.txt`); `SpaceNavigatorMapper.pyw` starts it without a console; `RUN_DEBUG_WINDOWS.bat` keeps a console open for start-up errors.
- **Single-file edition:** `py tools\build_single_file.py` writes `dist\SpaceNavigator_Mapper_<version>_Complete.py`, with every module, the icon and this README inside.
- **EXE:** `BUILD_EXE_WINDOWS.bat` compiles the Mapper with Nuitka to `SpaceNavigatorMapper.exe` (Python and a C compiler are needed to build it, not to run it).
- **Tray and start-up:** Close to System Tray hides the window on X while mapping continues; Auto-start in System Tray starts the Mapper hidden at Windows sign-in.
- **Programs running as administrator:** Windows does not let a program that is not running as administrator send keys to one that is, and says nothing: the keys simply do not arrive. Some games, launchers and tools run as administrator. The Mapper notices: picking such a program as the target asks **Restart the Mapper as administrator now?**; sending keys while one is in front puts a warning in the status bar (and once a session, for each program, a tray message). **Options > Restart as Administrator** restarts it that way (Windows asks first) and it comes back where it was, with the same profile; the item then reads **Running as Administrator**. Auto-start at Windows sign-in starts the Mapper without administrator rights (Windows never raises a sign-in start), so restart it as administrator when a program needs it. Games protected by anti-cheat software may refuse keys from any other program, administrator or not.
- **One copy at a time:** starting the Mapper again (or the taskbar's **Restore SpaceNavigator Mapper**, which starts it with `--restore`) brings the running copy to the front and ends quietly; a message says it is already running only when its window cannot be found. When the copy running is **another version** (one started at Windows sign-in from an older folder, say), a start asks **Exit it and start** this version? **Yes** asks it to exit and starts this one (a copy older than v108.165 cannot be asked: exit it from its tray icon); **No** shows the running one. Each copy marks its window with its version; one older than v108.168 is named "an older SpaceNavigator Mapper". The taskbar's **Exit SpaceNavigator Mapper** starts it with `--exit`, which asks the running copy to exit and starts nothing. The taskbar's program item can only be renamed, not removed: Windows always shows it.
- **This README:** right-click the title and choose **Open README (PDF)** to read it in your PDF viewer, or **Open README in a window** to read the same text in the Mapper. The window's **Text size** makes the text 100%, 125%, 150%, 175%, 200% or 250% of its normal size (also **A−** / **A+**, Ctrl + plus / minus, Ctrl + 0 for 100%, and Ctrl + mouse wheel); the size is remembered. In the PDF viewer, use its zoom. When no PDF viewer opens, the PDF choice shows the window instead. `tools\build_readme_pdf.py` rebuilds it from `spnav_mapper\resources\SpaceNavigator_Mapper_README.md`.

## 8. Function reference (Python source inventory)

<!-- BEGIN FUNCTION REFERENCE: written by tools/build_readme_pdf.py -->

The inventory lists every **top-level function and class method** of the `spnav_mapper` package of v108.176, with its source line and purpose (the first line of its docstring). It is written by `tools/build_readme_pdf.py` from the source, so it stays complete when the code changes. An underscore prefix means an internal helper or event handler; it does not imply a user-visible control. Nested callbacks are not listed. Line numbers refer to v108.176 and change in later releases.

**645 functions and methods in 42 modules.**

### 8.1. Start-up, paths and preferences

#### `app.py` — 2 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_bring_to_front()` | 22 | Raise and activate the window when it is visible and not minimized. |
| `run()` | 39 | Create the Qt application and the main window, then run the event loop. |

</div>

#### `bootstrap.py` — 9 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `log_path()` | 27 | Return a writable log path independent of EXE extraction or CWD. |
| `note()` | 50 | Append a line and echo it to the console when available. |
| `_message_box()` | 74 | Show a native Windows message box (works before Qt starts). |
| `_show_failure()` | 93 | Log a failure; before the window runs, also show it once in a message box. |
| `_install_exception_handlers()` | 113 | Log uncaught exceptions from Python, threads and Qt callbacks. |
| `launch()` | 155 | Start UI and return an exit code; show/log all startup exceptions. |
| `_ask()` | 213 | A native Yes / No question (works before Qt starts); True for Yes. |
| `_another_copy_running()` | 229 | Another copy holds the instance lock: show it, or replace another version. |
| `_start_ui()` | 288 | Run the Qt application once this copy holds the instance lock. |

</div>

#### `paths.py` — 3 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `entry_point()` | 12 | The script that starts the app (main.py, or the single-file edition). |
| `_restart_app_dir()` | 20 | The folder of the copy that restarted this one (Display size change), or "". |
| `_app_base_dir()` | 33 | Folder holding configs: the EXE's folder, or the launcher's folder. |

</div>

#### `settings.py` — 1 function

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `ensure_dir()` | 18 | Create a folder (and its parents) when missing. |

</div>

#### `restart.py` — 8 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_nuitka_marker()` | 21 | Nuitka's __compiled__ object, or None when not compiled by Nuitka. |
| `compiled_program()` | 29 | The EXE the user started. |
| `successor_environment()` | 53 | The restarted copy's environment: told this copy's folder, without Nuitka's onefile variables. |
| `build_restart_command()` | 64 | Command line that starts the Mapper again (EXE, script or package). |
| `launch_command()` | 71 | Command line that starts the Mapper (EXE, script or package) with `arguments`. |
| `restart_after_display_change()` | 112 | Launch the successor, then close normally (bypassing close-to-tray). |
| `close_for_successor()` | 144 | Close this copy (bypassing close-to-tray) so the one just started takes over. |
| `restart_as_administrator()` | 183 | v108.174: start the Mapper again as administrator (Windows asks first), then close this one. |

</div>

#### `single_instance.py` — 16 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_user32()` | 31 | The user32 DLL, or None outside Windows. |
| `restore_message_id()` | 39 | The registered "show yourself" message (0 when it cannot be registered). |
| `is_restore_message()` | 50 | True for the message a second launch posts to restore the window. |
| `exit_message_id()` | 56 | The registered "exit" message (0 when it cannot be registered). |
| `is_exit_message()` | 67 | True for the message a launch with --exit posts to the running copy. |
| `version_number()` | 79 | 108168 for "v108.168"; 0 when it cannot be read. |
| `version_text()` | 89 | "v108.168" for 108168; "" for 0 (a copy from before v108.168, which does not say). |
| `_user32_for_windows()` | 95 | user32 with the argument types the window search and messages need. |
| `find_running_windows()` | 115 | [(hwnd, pid, version number)] of the running Mapper's Qt windows (0: it does not say). |
| `running_version()` | 151 | The running copy's version number (0: from before v108.168, which does not say). |
| `post_to_windows()` | 156 | Post `message` to the running Mapper's windows; True when one took it. |
| `_restore_existing_window()` | 172 | Ask the already-running mapper to show itself (or, with the exit message, to exit). |
| `accept_messages_from_lower()` | 184 | v108.174: let a start that is not administrator reach this window when it is. |
| `mark_window_version()` | 210 | Mark the running copy's window with its version (see VERSION_PROP); True when done. |
| `unmark_window_version()` | 221 | Remove the version mark before the window goes, as Windows asks. |
| `acquire_single_instance()` | 232 | Claim the single-instance mutex, or ask the running copy to come forward. |

</div>

#### `display_preferences.py` — 6 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `read_preferences()` | 24 | Read ui_preferences.json, or an empty dict. |
| `update_preference()` | 34 | Store one value in ui_preferences.json. |
| `numeric_choice()` | 46 | A stored number when it is one of the offered choices, else the default. |
| `registry_command()` | 57 | A real .exe at runtime, or pythonw.exe + .pyw in development. |
| `auto_start_is_enabled()` | 98 | True when the Windows Run entry starts the Mapper at sign-in. |
| `set_auto_start()` | 112 | Add or remove the Windows Run entry that starts the Mapper in the tray. |

</div>

#### `backups.py` — 4 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_snapshot()` | 10 | Write bytes into a folder under a unique time-stamped file name. |
| `save_with_backup()` | 32 | Preserve the previous bytes, then atomically replace the live profile. |
| `list_backups()` | 58 | The backup files in the backups folder, newest first. |
| `restore_backup()` | 66 | Create a separate editable profile; leave the recovery copy untouched. |

</div>

### 8.2. Windows, keyboard and device

#### `win32.py` — 28 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `matches_any()` | 79 | True when text matches any wildcard pattern (case-insensitive). |
| `is_omitted_target()` | 85 | True when a window must not be offered as a mapping target. |
| `window_title()` | 103 | A window's title text. |
| `window_class()` | 116 | A window's class name. |
| `window_pid()` | 126 | The process id that owns a window. |
| `process_image_path()` | 136 | Full EXE path of a process, or "" when it cannot be opened. |
| `_token_elevation()` | 168 | (True / False, 0) for a process's token, or (None, the Windows error) when it cannot be read. |
| `mapper_elevated()` | 195 | True when the Mapper itself runs as administrator (None: it cannot tell). |
| `process_elevated()` | 206 | True when process `pid` runs as administrator, False when not, None when it cannot tell. |
| `window_elevated()` | 233 | process_elevated() for the program that owns window `hwnd`. |
| `window_exe_path()` | 238 | The executable path of the process that owns a window. |
| `_window_monitor()` | 266 | (device name, work-area left, work-area top) of the window's monitor, or None. |
| `_private_user32()` | 287 | A separate user32 instance: argtypes set here do not affect other callers. |
| `allow_foreground()` | 292 | Let process `pid` bring its window to the front (we must be in front now). |
| `bring_to_front()` | 307 | Put the window in front of all other windows and give it the focus. |
| `window_monitor_name()` | 340 | Device name (such as DISPLAY2) of the monitor Windows says the window is on. |
| `client_offset_on_monitor()` | 350 | (device name, dx, dy): the window's client area relative to its monitor's work area. |
| `normalized_path()` | 370 | A real, normalized path for comparison (case and separators). |
| `list_windows()` | 375 | [(hwnd, title)] for visible top-level windows that have a title. |
| `visible_windows()` | 396 | [hwnd] for every visible top-level window, titled or not. |
| `foreground_window()` | 410 | The window in front. |
| `current_process_id()` | 418 | This process's id. |
| `is_own_window()` | 426 | True when `hwnd` belongs to this process: the Mapper's own window, a dialog or a menu. |
| `same_process()` | 434 | True when two windows belong to the same process. |
| `format_target_item()` | 442 | '<title> — <exe> — <fullpath>', at most 65 characters. |
| `clean_text()` | 456 | Text with invisible format characters removed, trimmed. |
| `version_info_strings()` | 463 | Version-resource strings (product, description) of an executable. |
| `best_program_name()` | 530 | A readable program name from version info or the file name. |

</div>

#### `keyboard_io.py` — 8 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `key_to_scancode()` | 114 | Scan code and extended flag for a key token. |
| `_build_inputs_for_tokens()` | 132 | Build the Windows INPUT records for pressing or releasing keys. |
| `_send_inputs()` | 168 | Send INPUT records with SendInput; returns how many were sent. |
| `_send_inputs_with_fallback()` | 183 | Send INPUT records, one at a time if the batch is refused. |
| `is_modifier()` | 203 | True for the Ctrl, Shift and Alt tokens. |
| `normalize_combo_tokens()` | 208 | Split a combo into its modifier tokens and its other keys. |
| `send_combo()` | 220 | Press (modifiers first) or release (main keys first) a key combination. |
| `combo_to_text()` | 237 | Readable label for a key combination, such as Ctrl+S. |

</div>

#### `devices.py` — 13 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_spnav_interface_priority()` | 37 | Prefer the USB multi-axis controller HID interface over button/LCD interfaces. |
| `_sat()` | 58 | Clamp a normalized axis value to the range -1.0 to +1.0. |
| `_parse_sn_report()` | 67 | Decode a HID report into translation, rotation or button data. |
| `SpaceNavigator.__init__()` | 103 | Start with six zero axes, no buttons pressed and no device open. |
| `SpaceNavigator.open()` | 118 | Find and open the first supported 3Dconnexion HID device. |
| `SpaceNavigator.close()` | 185 | Close the HID handle and the LED fallback device. |
| `SpaceNavigator._device_still_present()` | 208 | True while the opened HID path is still enumerated. |
| `SpaceNavigator.tick()` | 220 | Detect a disconnect (checked once a second) and try to reconnect at a timed interval. |
| `SpaceNavigator.read()` | 240 | Read pending HID reports into the six axes and two button bits. |
| `SpaceNavigator._ensure_pwin_device()` | 274 | Open the pywinusb device used for the LED fallback. |
| `SpaceNavigator._set_led_pywinusb()` | 295 | Switch the device LED through pywinusb. |
| `SpaceNavigator._set_led_hidapi()` | 337 | Switch the device LED through hidapi. |
| `SpaceNavigator.set_led()` | 368 | Switch the device LED with the first backend that works. |

</div>

### 8.3. Macros and Auto-Profiles rules

#### `macros.py` — 12 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_tokens()` | 21 | Key tokens of a macro step value, lower-cased. |
| `normalize_step()` | 30 | A valid step dict, or None. |
| `normalize_macro()` | 48 | The valid steps of `steps` (at most MAX_STEPS); [] for anything else. |
| `step_text()` | 62 | How a step reads in the editor and tooltips, e.g. "Tap CTRL+S" or "Delay 100 ms". |
| `_keys_up_long_enough()` | 76 | Insert waits so a key released is up `min_up_ms` before it is pressed again (v108.167). |
| `expand()` | 100 | The key events and waits of one run: [("down", tokens) \| ("up", tokens) \| ("wait", ms)]. |
| `MacroRun.__init__()` | 126 | Prepare a run of a macro with the key sender and scheduler to use. |
| `MacroRun.start()` | 134 | Start playing the macro from its first step. |
| `MacroRun._advance()` | 141 | Play steps until the next delay, then schedule the rest. |
| `MacroRun._resume()` | 162 | Continue after a delay unless the run was stopped. |
| `MacroRun.stop()` | 167 | Stop now and release whatever this run still holds down. |
| `MacroRun._finish()` | 172 | End the run, release held keys and report completion. |

</div>

#### `auto_profiles.py` — 20 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_lower()` | 28 | Stripped, lower-case text; empty for anything that is not text. |
| `profile_abs_path()` | 36 | Resolve a profile path relative to the configs folder. |
| `file_exists()` | 45 | True when the path is an existing file (never raises). |
| `open_in_os()` | 53 | Open a file or folder with the operating system (Explorer on Windows). |
| `_same_file()` | 74 | True when two paths name the same file. |
| `_rule_path()` | 82 | How a rule names a profile: its file name in the configs folder, else its full path. |
| `_plain_exe_group()` | 91 | True for a group that matches the program by its exe only (no title or product patterns). |
| `link_profile_to_program()` | 100 | List `profile_path` in the Auto-Profiles group of the program `exe_path` (v108.170). |
| `unlink_profile_from_program()` | 152 | Take `profile_path` out of every Auto-Profiles group that matches the program `exe_path`. |
| `AutoProfileManager.__init__()` | 191 | Remember the rules file path and start with no rules loaded. |
| `AutoProfileManager._read_json()` | 197 | Read a JSON file, or None when it is missing or invalid. |
| `AutoProfileManager._write_json()` | 202 | Write the rules file as indented UTF-8 JSON. |
| `AutoProfileManager._bootstrap_from_existing_profiles()` | 208 | Build first-use rules from the target programs saved in existing profiles. |
| `AutoProfileManager.load()` | 271 | Load the rules file, creating it from existing profiles when missing. |
| `AutoProfileManager._reload()` | 281 | Re-read the rules file and remember its modification time. |
| `AutoProfileManager.reload()` | 295 | Re-read the rules file now (after the Mapper wrote it). |
| `AutoProfileManager.reload_if_changed()` | 299 | Re-read the rules file when it was edited since the last read. |
| `AutoProfileManager._match_group()` | 308 | Find the first enabled group whose exe, title or product pattern matches. |
| `AutoProfileManager.pick_profile_for()` | 338 | The profile to load for a program: the matching group's top-priority entry. |
| `AutoProfileManager.candidates_for_current()` | 353 | Every enabled profile of the matching group, by priority (for Switch to…). |

</div>

### 8.4. Main window, profiles and targets

#### `ui/main_window.py` — 38 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_give_refresh_space_to_credit()` | 73 | Remove the Refresh button and enlarge `labels` into its space. |
| `match_comment_font()` | 120 | Give `label` the point size of the comment field `comment` (family unchanged). |
| `MainWindow.__init__()` | 133 | Build the window, load the last profile and start the timers. |
| `MainWindow._build_full_editor()` | 148 | Lay out the header, button row, six axis panels and status bar. |
| `MainWindow._dark_stylesheet()` | 481 | The application's dark style sheet. |
| `MainWindow._title_clicked()` | 547 | A left click on the title sends the window to the taskbar. |
| `MainWindow._title_right_clicked()` | 559 | Right-click on the title: a drop-down to open the README as a PDF or in a window. |
| `MainWindow._enlarge_axis_comment_text()` | 573 | Use the existing field height and reclaim padding for larger type. |
| `MainWindow._apply_custom_titlebar_color()` | 597 | Apply a custom Windows 10/11 title bar color using DWM APIs. |
| `MainWindow._allow_output_now()` | 628 | True when keys may be sent now, with window `fg` in front (mode, target, foreground). |
| `MainWindow.refresh_gui()` | 645 | Each GUI tick: feed axis values and button changes to the binds. |
| `MainWindow._on_hw_button_event()` | 666 | Press or release Button 1/2's combo when the device button changes. |
| `MainWindow.release_all_keys()` | 686 | Release every held key, Button 1/2 and binds alike, and stop macros. |
| `MainWindow.clear_all()` | 696 | Release every held key and say so in the status bar. |
| `MainWindow._after_show_device_scan()` | 701 | Connect hardware after first paint; never block the initial window show. |
| `MainWindow._after_show_window_scan()` | 721 | Build the target list once visible, preserving initial combo semantics. |
| `MainWindow._fg_matches_target()` | 743 | True when the program in front (`fg`, looked up when not given) is the target program. |
| `MainWindow._set_activation()` | 751 | Turn output on or off and update the Target button. |
| `MainWindow._apply_activation()` | 763 | Apply Target ON/OFF, asking for a target when none is set. |
| `MainWindow._get_auto_select_mode()` | 790 | The current mode: Auto Load, Manual On or Off. |
| `MainWindow._set_auto_select_mode()` | 794 | Select Auto Load, Manual On or Off (without signalling unless `emit`). |
| `MainWindow._apply_auto_mode_selection()` | 802 | Apply the selected mode to activation and Auto-Profiles. |
| `MainWindow._on_target_button_toggled()` | 828 | Target button clicked: turn output on or off. |
| `MainWindow._auto_recompute_activation()` | 835 | In Auto Load, activate output only while the target is in front (`fg`: the window in front). |
| `MainWindow._history_window_in_front()` | 848 | True when Axis History holds the Target on and its window (`fg`) is in front. |
| `MainWindow.set_history_target()` | 858 | Target on for the current profile while the Axis History window is open; as before after. |
| `MainWindow._handle_quick_button_press()` | 903 | Button 1/2 pressed on screen: open its key picker. |
| `MainWindow._handle_quick_button_release()` | 909 | Button 1/2 released on screen: restore its look. |
| `MainWindow._repolish()` | 915 | Re-apply the style sheet after a dynamic property changed. |
| `MainWindow._open_quick_picker()` | 921 | Open the key picker for Button 1 or Button 2. |
| `MainWindow._toggle_led()` | 939 | Options > Device LED: switch the device LED. |
| `MainWindow._flash_button_main()` | 946 | Flash a header button amber for a moment (Save/Reload). |
| `MainWindow._flash_hw_button_label()` | 954 | Pulse Button 1 / Button 2 deep red when the device's button is pressed. |
| `MainWindow._on_target_flash_tick()` | 961 | Flash the Target button while the Mapper, not its target, is in front. |
| `MainWindow.focusInEvent()` | 975 | Window focused: start the Target button flash check and refresh the targets. |
| `MainWindow.focusOutEvent()` | 983 | Window unfocused: stop flashing the Target button. |
| `MainWindow._on_game_timer_tick()` | 993 | Count a second of game time while output is on (not Axis History's temporary Target). |
| `MainWindow._on_game_time_label_double_click()` | 1000 | Reset the game time when the label is double-clicked. |

</div>

#### `ui/profiles.py` — 24 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `ProfilesMixin.load_config()` | 26 | Load button: choose a profile file and load it. |
| `ProfilesMixin.load_last_config()` | 32 | Load the profile used last (start-up). |
| `ProfilesMixin._load_config_from_path()` | 39 | Load a profile file and refresh the title. |
| `ProfilesMixin.save_config()` | 45 | Save as button: choose a file and save the profile. |
| `ProfilesMixin.save_config_quick()` | 51 | Save the profile to `path`, else its current file; returns the path. |
| `ProfilesMixin.save_reload_config()` | 57 | Save/Reload: ask first, with the file name editable, then reload exactly the file written. |
| `ProfilesMixin.remove_linked_program()` | 84 | Remove the program linked to the loaded profile, then save and reload it (v108.145). |
| `ProfilesMixin.linked_program()` | 95 | (display name, exe path) of the program linked to the loaded profile, or None. |
| `ProfilesMixin._remove_linked_program_impl()` | 105 | Confirm, then unlink the program, save and reload the profile. |
| `ProfilesMixin.load_backup_config()` | 148 | Load a recovery copy without making the backup itself editable. |
| `ProfilesMixin._save_config_impl()` | 162 | Save as: ask for a .json path and write the profile there. |
| `ProfilesMixin._quick_save_destination()` | 190 | (path, fallback) where Save/Reload writes: the active profile, else the last-used path, else (fallback True) a suggested one under CONFIG_DIR. |
| `ProfilesMixin._save_config_quick_impl()` | 204 | Save without a file dialog to `path`, else the active profile, else the last-used path, else a suggested path under CONFIG_DIR; also refresh last_config.json. |
| `ProfilesMixin._link_to_its_program()` | 225 | v108.170: list a profile with a target program in that program's Auto-Profiles group. |
| `ProfilesMixin._read_profile()` | 249 | (profile, migrated) read from a JSON file. |
| `ProfilesMixin._apply_profile()` | 254 | Put a profile's settings into every panel and control. |
| `ProfilesMixin._button_key_label()` | 288 | Button 1 / Button 2's label: its key combination, if any. |
| `ProfilesMixin._load_config_from_path_impl()` | 293 | Read a profile file and apply it to every panel and control. |
| `ProfilesMixin._load_config_impl()` | 313 | Show the open-file dialog and load the chosen profile. |
| `ProfilesMixin._load_last_config_impl()` | 320 | Load last_config.json, the state at the last exit (no profile file is active). |
| `ProfilesMixin._profile_data()` | 337 | Everything a profile file stores, taken from the current window. |
| `ProfilesMixin._target_fields()` | 358 | The target program's profile fields, so Auto-Profiles and re-finding the target work later: its EXE and the names in its version information. |
| `ProfilesMixin._sanitize_config()` | 381 | (profile, migrated): the profile with old mode names upgraded ("Press-only"). |
| `ProfilesMixin._suggest_save_path()` | 391 | Default Save as path: the loaded profile, else configs/config.json. |

</div>

#### `ui/targets.py` — 13 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `TargetsMixin._target_program_path()` | 35 | Executable path of the target window, or empty. |
| `TargetsMixin._target_program_name()` | 39 | Readable name of the target program. |
| `TargetsMixin.refresh_windows()` | 44 | Refill the list of windows that can be targets (most recently used first). |
| `TargetsMixin._refresh_windows_quietly()` | 95 | refresh_windows for timers and events: an error is logged, never shown. |
| `TargetsMixin._resolve_target_if_running()` | 104 | If the target program is running, make its window the target. True when found. |
| `TargetsMixin._on_app_state_changed()` | 122 | Refresh targets when the Mapper becomes active. |
| `TargetsMixin._maybe_auto_refresh_windows()` | 127 | Background auto-refresh of window list to catch newly opened apps. |
| `TargetsMixin._remember_recent_target()` | 131 | Put a target window first in the list's most-recently-used order. |
| `TargetsMixin.set_target()` | 138 | Make the window chosen in the list the target and recompute output. |
| `TargetsMixin._show_target_picker()` | 148 | Click on the Profile name: the target list, with Delete Linked Program first. |
| `TargetsMixin._apply_target_from_menu()` | 193 | Make the chosen window the target, offer to save it in the loaded profile, then (v108.174) offer to restart as administrator when the target runs as administrator. |
| `TargetsMixin._apply_target_and_save()` | 203 | Make the chosen window the target and offer to save it in the loaded profile. |
| `TargetsMixin.restore_target()` | 244 | Re-select a saved target window, or clear the target. |

</div>

#### `ui/auto_profiles_menu.py` — 11 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `auto_load_status_style()` | 20 | Style sheet for the Auto-Load status badge (loaded, manual, waiting). |
| `_same_path()` | 46 | True when two paths name the same file ("" names none). |
| `AutoProfilesMixin._init_auto_profiles()` | 67 | Set up Auto-Profiles: rules, menu, status badge and timer. |
| `AutoProfilesMixin._ap_update_status_label()` | 88 | Show Auto-Load: Off, Manual On, the loaded profile or Waiting in the badge. |
| `AutoProfilesMixin._ap_program_in_front()` | 111 | (window, exe path, exe name, title, product name) of the program the rules look at. |
| `AutoProfilesMixin._inject_ap_menu()` | 129 | Build the Auto-Profiles menu in the menu bar. |
| `AutoProfilesMixin.note_profile_edit()` | 201 | v108.171: the profile was changed in the editor; in Auto Load, offer Manual On (once). |
| `AutoProfilesMixin.rearm_edit_warning()` | 211 | A profile was loaded or saved, or Auto Load chosen: the next change warns again. |
| `AutoProfilesMixin._offer_manual_on()` | 215 | Ask to switch to Manual On while the profile is being edited. |
| `AutoProfilesMixin._ap_manual_switch_to()` | 230 | Load a profile picked from Switch to…. |
| `AutoProfilesMixin._auto_profiles_tick()` | 246 | In Auto Load, load the profile that matches the program in front. |

</div>

#### `ui/window_chrome.py` — 34 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_icon_candidates()` | 50 | A user icon beside the app first, then the bundled one. |
| `application_icon()` | 61 | The Mapper's icon, from resources or the single file. |
| `_profile_label()` | 81 | The loaded JSON profile (not the foreground game/target). |
| `refresh_title()` | 93 | Show the loaded profile in the window title and tray tip. |
| `restore_from_taskbar()` | 107 | Show the window again: from the tray, the taskbar or a second launch. |
| `profile_items()` | 133 | (name, path, modified) for every profile in the configs folder, sorted by name. |
| `exit_for_second_launch()` | 155 | The taskbar's Exit SpaceNavigator Mapper (a launch with --exit): exit as Options > Exit does. |
| `show_for_second_launch()` | 166 | Another launch found this copy running: show it, in front of all windows. |
| `fill_tray_profiles()` | 194 | The tray's Profiles submenu: every profile in the configs folder, the active one checked. |
| `activate_profile_from_tray()` | 216 | Load `path` as the active profile, as the editor's Load button does. |
| `_add_window_controls()` | 232 | Adds the window controls (Options menu, tray icon) after the editor is built. |
| `read_close_preference()` | 284 | True when X closes to the system tray. |
| `write_close_preference()` | 297 | Store the Close to System Tray choice. |
| `_set_close_preference()` | 318 | Apply and store the Close to System Tray choice. |
| `exit_application()` | 327 | Close the window for real (not to the tray), which shuts down. |
| `view_menu()` | 339 | The Options menu (created when missing). |
| `_add_close_menu()` | 347 | Add Close to System Tray and prepare Exit. |
| `_add_display_menu()` | 366 | Add the rest of Options and the Display menu. |
| `monitor_label()` | 472 | 'Display 2 — 2560 × 1440, 100% (primary)', from Windows' own numbers when available. |
| `_fill_positions_menu()` | 495 | One check box per connected monitor; at most one checked. |
| `_choose_positions_monitor()` | 518 | Positions Saved: save the position on a monitor (or none). |
| `_grown()` | 539 | A copy of a font made larger by some points. |
| `_keep_size()` | 549 | Make the widget's current font size explicit, so a parent's change skips it. |
| `enlarge_menu_bar_headings()` | 559 | Make the menu-bar headings (Auto-Profiles, Options, Display) `points` larger. |
| `_menus_under()` | 580 | `menus` and all their submenus, each once. |
| `grow_menu_fonts()` | 594 | Make each menu and submenu `points` larger than it is now. |
| `enlarge_menu_fonts()` | 607 | Make the menu-bar menus (Auto-Profiles, Options, Display) and their submenus `points` larger. |
| `WindowChromeMixin._init_window_chrome()` | 613 | Set up the icon, menus, tray and title effect. |
| `WindowChromeMixin.nativeEvent()` | 626 | Answer a second launch's "show yourself" message (single_instance). |
| `WindowChromeMixin._init_close_to_tray()` | 641 | Read the Close to System Tray choice. |
| `WindowChromeMixin._init_display_menu()` | 648 | Build the Options and Display menus. |
| `WindowChromeMixin.changeEvent()` | 666 | v108.151: a maximize from the keyboard (Win+Up) or snapping is undone. |
| `WindowChromeMixin.closeEvent()` | 672 | X: hide to the tray, or shut down. |
| `WindowChromeMixin._shutdown_on_close()` | 688 | Release keys, switch the LED off, save last_config.json and close the device. |

</div>

#### `ui/menu_autoclose.py` — 7 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `leave_step()` | 20 | One look at the mouse: (close now, mouse has been over the menu, away since). |
| `MenuAutoClose.__init__()` | 39 | Watch the menus of the menu bar `bar`. |
| `MenuAutoClose.start()` | 54 | A drop-down opened: start watching the mouse. |
| `MenuAutoClose.open_menus()` | 60 | The drop-downs and submenus open now. |
| `MenuAutoClose._bar_rect()` | 66 | The menu bar, in screen coordinates. |
| `MenuAutoClose.check()` | 70 | Look at the mouse; close the open drop-downs once it has been away long enough. True when closed. |
| `install_menu_autoclose()` | 86 | Have the window's menu-bar drop-downs close once the mouse leaves them (None without a menu bar). |

</div>

#### `ui/readme_viewer.py` — 21 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `readme_candidates()` | 48 | Where a README file may be: the package's resources, then the app's folder. |
| `_read()` | 54 | The first README file of that name that can be read, or None. |
| `readme_pdf_bytes()` | 65 | The README PDF's bytes, or None when it cannot be found. |
| `readme_pdf_available()` | 71 | True when the README PDF is inside the script or on disk. |
| `readme_text()` | 78 | The README's Markdown, or a short note when it cannot be found. |
| `readme_copy_name()` | 87 | The copy's file name: one per version, so an open older copy is never in the way. |
| `readme_copy_dir()` | 92 | The log folder, which outlives the EXE's temporary extraction folder. |
| `readme_pdf_path()` | 99 | A PDF of the README that stays on disk, or None. |
| `open_pdf()` | 130 | Open `path` in the default PDF viewer; True when the request was accepted. |
| `window_text()` | 147 | The Markdown without the HTML lines that only shape the PDF (comments, divs). |
| `ReadmeBrowser.__init__()` | 160 | A browser whose zoom keys and Ctrl + wheel step the text size of `viewer`. |
| `ReadmeBrowser.keyPressEvent()` | 165 | Ctrl + plus / minus: next or previous text size; Ctrl + 0: 100%. |
| `ReadmeBrowser.wheelEvent()` | 180 | Ctrl + wheel steps the text size; the wheel alone scrolls. |
| `ReadmeViewer.__init__()` | 192 | Build the README window: Text size, the README, Close. |
| `ReadmeViewer.set_text_size()` | 243 | Show the README text at `size` (1.0 = 100%), one of TEXT_SIZES; remembered for next time. |
| `ReadmeViewer.step_text_size()` | 264 | The next larger (+1) or smaller (-1) text size. |
| `show_readme_window()` | 270 | Open the README window, or bring it forward if it is already open. |
| `_status()` | 281 | Show a message in the status bar for a few seconds. |
| `show_readme_pdf()` | 289 | Open the README PDF in the PDF viewer, else the README window. |
| `readme_menu()` | 300 | The title's drop-down: the README as a PDF, or in a window. |
| `show_readme_menu()` | 317 | Right-click on the title: show the README drop-down at the pointer. |

</div>

### 8.5. Axis panels, key picker and macro editor

#### `ui/axis_panel.py` — 84 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `bind_has_output()` | 43 | True when the bind has something to send: its macro in Macro mode, else its key. |
| `own_style()` | 61 | `declarations` for the widget itself only: ".QPushButton { ... }". |
| `_tick_dir_ok()` | 73 | True when the axis value is on a side the Tick bind's direction allows (not at centre). |
| `_set_ghost()` | 84 | Grey out (or restore) a Quick Bind control that the mode does not use. |
| `_covers()` | 116 | True when a bind with `direction` works on axis side `side` ("+" or "-"). |
| `bind_noback_from()` | 121 | A loaded bind's (NoBack +, NoBack -). |
| `noback_on()` | 138 | True when `bind` has NoBack on axis side `side` and works on that side. |
| `fit_noback_to_direction()` | 152 | Keep NoBack on the side(s) the bind has (v108.161). |
| `chosen_noback_sides()` | 174 | The axis sides with NoBack on that the bind works on. |
| `noback_names()` | 179 | The bind's NoBack as its menu names it: the direction of the way back ("-" for a POS bind). |
| `_read_dead_value()` | 184 | Per-bind dead zone from profile data, accepting older field names. |
| `_status_ignored()` | 195 | Key-sending status messages are not shown. |
| `clamp_tap_ms()` | 245 | A Tap Dwell in ms, 0 to 200 (`default` for one that is not a number). |
| `tap_text()` | 253 | 'Tap Dwell: 45ms', the width of three digits. |
| `give_tip()` | 258 | Set `widget`'s hover tip and keep it to restore after a Tick-mode note. |
| `step_glyph_px()` | 271 | The pixel size of a − / + glyph in a button `side` pixels square. |
| `step_buttons()` | 276 | The red − and green + buttons beside Min%, Max% and DZone. |
| `AxisPanel.__init__()` | 301 | Create an axis panel with six binds and its Quick Bind editor. |
| `AxisPanel.eventFilter()` | 358 | Re-align the bind rows after the panel is shown, moved or resized. |
| `AxisPanel._align_bind_rows()` | 366 | Make the bind rows end where the Quick Bind Mode box ends. |
| `AxisPanel._build_ui()` | 379 | Lay out the Bind buttons, comments and the Quick Bind editor. |
| `AxisPanel._change_dead()` | 630 | Step the selected bind's DZone% up or down. |
| `AxisPanel._change_tap()` | 638 | Step the selected bind's Tap Dwell (0-200 ms). |
| `AxisPanel._bind_tap_ms()` | 646 | A bind's Tap Dwell (the profile's when it has none). |
| `AxisPanel._profile_tap_ms()` | 650 | The profile's Tap Dwell: the one a bind without its own gets. |
| `AxisPanel._change_max()` | 654 | Step the selected bind's Max% (0-100). |
| `AxisPanel._refresh_slot_btn()` | 665 | Update a Bind button's label, colours and Bind Dir/NoBack lines. |
| `AxisPanel._slot_style()` | 708 | The Bind button's stylesheet: selected, bound or empty. |
| `AxisPanel._on_qb_play_change()` | 718 | Store the Macro Play choice (Once or Repeat). |
| `AxisPanel._sync_mode_groups()` | 727 | Show the Play row for Macro, and the repeat row for Press/Repeat or a repeating macro. |
| `AxisPanel._on_qb_repeat_change()` | 739 | Store the Repeat every (ms) choice. |
| `AxisPanel._refresh_repeat_note()` | 748 | v108.167: say so when the Tap Dwell makes Press/Repeat tap less often than Repeat every. |
| `AxisPanel._open_picker_for()` | 768 | Double-click: open the key picker, or the macro editor in Macro mode. |
| `AxisPanel.reset_axis()` | 790 | Clear every bind of the axis back to the defaults. |
| `AxisPanel._on_comment_change()` | 821 | Store a bind's comment as it is typed. |
| `AxisPanel._edited()` | 825 | v108.171: the profile was changed here; in Auto Load the window offers Manual On. |
| `AxisPanel._starts_action()` | 849 | True when `kind` starts what bind `idx` does (a press, a tap, a macro; a Release-only release). |
| `AxisPanel._record()` | 855 | Axis history: note what bind `idx` just did (when recording); in a dry run, as not sent. |
| `AxisPanel._send_combo()` | 867 | Press or release a bind's combo (nothing in a dry run). |
| `AxisPanel._keep_dry_states()` | 872 | Output allowed: the dry run starts from the binds' own states when output goes off. |
| `AxisPanel._copy_run()` | 876 | Run every bind on copies of `states`, sending nothing; returns the copies' new states. |
| `AxisPanel._dry_run()` | 889 | Output off: run every bind on a copy of its state, sending nothing, recording what it would send. |
| `AxisPanel._mark_noback_holds()` | 893 | Run the binds without NoBack (on copies); mark each that would have started but did not. |
| `AxisPanel.contextMenuEvent()` | 904 | Right-click the panel (its border or an empty spot): Axis History… for this axis. |
| `AxisPanel._show_value()` | 918 | The axis name and its value, in the panel's border. |
| `AxisPanel._reset_and_blink()` | 922 | Flash the panel border amber to confirm, then reset the axis. |
| `AxisPanel._toggle_motion_flash()` | 929 | Blink the panel border while the axis moves with output off. |
| `AxisPanel._stop_motion_flash()` | 938 | Stop the motion blink and restore the border. |
| `AxisPanel._show_bind_menu()` | 944 | Right-click on a Bind button: NoBack and Edit macro for the bind, Reset for the axis. |
| `AxisPanel._bind_menu_position()` | 988 | Where Bind button `idx`'s menu opens: its left edge at the button's right edge, level with its top. |
| `AxisPanel._set_bind_noback()` | 996 | Turn NoBack on or off for one bind, for the way back from axis side `side`. |
| `AxisPanel._refresh_bind_lines()` | 1004 | The Bind button's lines: green along the top for its Bind Dir, white along the bottom for its NoBack, toward the way back (v108.161: the opposite of the green: left for a POS bind). |
| `AxisPanel._dir_char()` | 1030 | '+' or '-' for the side of the axis value; None at centre. |
| `AxisPanel._hys()` | 1034 | Hysteresis percentage used when leaving a band. |
| `AxisPanel._min_hold_ms()` | 1038 | Shortest time a Hold key stays down. |
| `AxisPanel._hold_ignore_max()` | 1042 | True when Hold binds keep holding beyond Max%. |
| `AxisPanel._macro_runs()` | 1049 | The macro runs of this panel, keyed by bind index. |
| `AxisPanel._macro_running()` | 1056 | True while the bind's macro is playing (never in a dry run). |
| `AxisPanel._start_macro()` | 1063 | Play bind `idx`'s macro unless it is still playing. True when it started (a dry run plays nothing). |
| `AxisPanel.stop_macros()` | 1081 | Stop playing macros (one bind's, or all) and release the keys they hold. |
| `AxisPanel.set_macro()` | 1091 | The editor's Save: the bind's new steps. |
| `AxisPanel._open_macro_editor()` | 1098 | Open the macro editor for a bind and store the saved steps. |
| `AxisPanel._send_tap()` | 1109 | Press a combo and release it after its Tap Dwell (0-200 ms). |
| `AxisPanel._taps()` | 1122 | The window's TapSender, shared by its axes (made by the first one that taps). |
| `AxisPanel._dir_ok()` | 1134 | True when the axis value is on a side the bind's direction allows. |
| `AxisPanel._reset_noback()` | 1142 | Forget the NoBack side and highest band reached. |
| `AxisPanel._noback_bands()` | 1150 | (start, reached_at(magnitude)) for every mapped bind on this side. |
| `AxisPanel._advance_noback()` | 1171 | Remember the highest mapped band reached during this excursion. |
| `AxisPanel._side_has_noback()` | 1198 | True when a mapped bind has NoBack on this side. |
| `AxisPanel._noback_blocks()` | 1202 | True when NoBack must keep a bind starting at ``start`` quiet. |
| `AxisPanel._bind_minimum()` | 1214 | Where a bind starts: its DZone% plus Min%, capped at 100. |
| `AxisPanel._tick_threshold()` | 1219 | The Tick% at which a Tick bind fires. |
| `AxisPanel._process_bind()` | 1226 | Run one bind's mode (Hold, taps, repeat, macro) for a new axis value. |
| `AxisPanel.update_val()` | 1350 | Take a new axis value: update the display, NoBack and every bind. |
| `AxisPanel.clear_keys()` | 1393 | Release held keys, stop macros and clear active states. |
| `AxisPanel._pulse_bind_button()` | 1411 | Briefly grey a Bind button when its band is reached with output off. |
| `AxisPanel._process_one()` | 1424 | Run one bind for a new axis value: Tick here, every other mode in _process_bind. |
| `AxisPanel._load_selected_into_qb()` | 1452 | Show the selected bind in Quick Bind: Bind Dir, Mode, Play, Repeat and values. |
| `AxisPanel._select_slot()` | 1476 | Select a bind (click on its Bind button) and show it in Quick Bind. |
| `AxisPanel._qb_changed()` | 1484 | Store Bind Dir and Mode from Quick Bind into the selected bind. |
| `AxisPanel._change_min()` | 1498 | Step the selected bind's Min% (Tick% in Tick mode), 0-100. |
| `AxisPanel._apply_selected_mode_ui()` | 1514 | Show the Quick Bind controls the selected mode uses (Tick%, Play, Repeat). |
| `AxisPanel.get_config()` | 1565 | Profile data for the axis: dead zone, selection and six binds. |
| `AxisPanel.set_config()` | 1590 | Load an axis's profile data into its six binds and refresh the panel. |

</div>

#### `ui/keyboard_popup.py` — 15 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `KeyboardPopup.__init__()` | 81 | Build the key picker: keys, modifiers, symbols and its buttons. |
| `KeyboardPopup._apply_modifier_font()` | 250 | Ctrl / Shift / Alt in 12 pt. |
| `KeyboardPopup._flash_button()` | 258 | Briefly highlight a button that was clicked. |
| `KeyboardPopup._gmods()` | 266 | The modifier tokens currently selected. |
| `KeyboardPopup._capture_inline_default()` | 270 | Remember the button's look before it is first shown selected, to restore it later. |
| `KeyboardPopup._apply_red()` | 287 | Show a key or modifier as selected (red). |
| `KeyboardPopup._apply_default()` | 294 | Restore a key button's normal look. |
| `KeyboardPopup._set_mods_enabled()` | 344 | Enable or disable the modifier buttons. |
| `KeyboardPopup._reset_mods_no_cb()` | 360 | Clear the modifiers without triggering their handlers. |
| `KeyboardPopup._dedupe_mods()` | 370 | The selected modifiers, each once, in Ctrl, Shift, Alt order. |
| `KeyboardPopup._toggle_modifier()` | 374 | Add or remove a modifier from the combo. |
| `KeyboardPopup._compose_combo()` | 385 | Combine current mods with selected key OR symbol combo. IMPORTANT: When a symbol is selected, DO NOT apply any extra modifiers from the UI. |
| `KeyboardPopup._pick_key()` | 397 | Choose the main key of the combo. |
| `KeyboardPopup._pick_symbol()` | 417 | Choose a symbol, as its key plus Shift when needed (the modifiers are disabled). |
| `KeyboardPopup._clear_selection()` | 442 | Clear the key and modifiers (Clear button). |

</div>

#### `ui/macro_editor.py` — 13 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `pick_keys()` | 25 | The key or combo chosen in the key picker, or None. |
| `MacroEditor.__init__()` | 37 | Build the macro editor: step list, add, move, delete, Save and Cancel. |
| `MacroEditor.steps()` | 122 | The edited steps, normalized. |
| `MacroEditor._show_steps()` | 126 | Refill the step list and the step counter. |
| `MacroEditor._row()` | 139 | Index of the selected step, or -1. |
| `MacroEditor.add_step()` | 144 | Insert `step` after the selected step (at the end with none selected). |
| `MacroEditor.add_keys()` | 154 | Add a Tap, Down or Up step with keys from the key picker. |
| `MacroEditor.move()` | 160 | Move the selected step up or down. |
| `MacroEditor.delete_selected()` | 169 | Delete the selected step. |
| `MacroEditor.change_selected()` | 177 | A key step: pick its keys again. A Delay step: its wait is the Delay box. |
| `MacroEditor._row_changed()` | 193 | Show the selected Delay step's milliseconds. |
| `MacroEditor._delay_changed()` | 200 | Store a new duration in the selected Delay step. |
| `MacroEditor.save()` | 207 | Accept the edited steps and close. |

</div>

#### `ui/widgets.py` — 15 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `AxisAlignedHeader.align_with_axes()` | 10 | Watch the axis panels so the header's right edge follows theirs. |
| `AxisAlignedHeader.eventFilter()` | 21 | Re-align after a watched widget moves or resizes. |
| `AxisAlignedHeader._align_right_edge()` | 27 | Limit the header's width to the axis panels' right edge. |
| `MatchWidth.__init__()` | 48 | Watch `source`; size `targets` from its next resize on. |
| `MatchWidth.eventFilter()` | 54 | The source was resized: the targets take its width. |
| `MatchWidth.apply()` | 60 | Give every target the source's width; True when one changed. |
| `ScaledHeaderButton.sizeHint()` | 85 | Size of the button's text at the current font. |
| `BindButton.sizeHint()` | 101 | Size of the Bind button's label at the current font. |
| `BindButton.mouseDoubleClickEvent()` | 113 | Emit doubleClicked (open the key picker or macro editor). |
| `BindButton.contextMenuEvent()` | 118 | Right-click: NoBack (for the way back), Edit macro and Reset axis. |
| `AutoModeCombo.__init__()` | 140 | The Auto Load / Manual On / Off selector. |
| `AutoModeCombo.mode()` | 152 | The selected mode. |
| `AutoModeCombo.setMode()` | 157 | Select a mode (Off for anything else). |
| `AutoModeCombo.isChecked()` | 163 | True in Auto Load. |
| `_auto_mode_from_config()` | 168 | The mode a profile stores, accepting the older true/false "auto_mode" field. |

</div>

### 8.6. Display sizing and window placement

#### `ui/scaling.py` — 30 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_env_float()` | 10 | A number from an environment variable, or the default. |
| `saved_view_record()` | 26 | The editor's last placement from any window_state.json layout (v1-v5). |
| `_saved_display_screen()` | 45 | Prefer the monitor on which the Mapper was last positioned. |
| `_screen_scale_metrics()` | 88 | Read the current screen settings in Qt logical units. |
| `_compute_ui_scale()` | 148 | Auto-scale the control/widget sizes from screen resolution + DPI settings. |
| `scale_limits()` | 186 | Lowest and highest interface scale allowed. |
| `scale_from_metrics()` | 197 | The automatic layout scale for one monitor, in Qt logical units. |
| `effective_scale()` | 233 | The layout scale: the monitor's automatic scale times the size factor (Display % and fit). |
| `fit_factor()` | 251 | How much smaller the editor is drawn (1.0: not smaller) on a monitor with `width` x `height` Qt pixels to work in. |
| `scaled_point_size()` | 263 | Scale a font from its \*100%\* point size using the interface preset. |
| `scaled_explicit_point_size()` | 274 | Scale the legacy Sf() fonts consistently with the whole interface. |
| `_apply_dynamic_scale()` | 290 | Work out the interface scale from the monitor and Display size. |
| `S()` | 355 | Scale a pixel size by the interface scale. |
| `Sf()` | 367 | Scale explicit title and label fonts with the interface itself. |
| `button_padding()` | 379 | Scaled QSS padding (logical px); never alter the 100%+ appearance. |
| `button_qss()` | 388 | Scale literal QSS button padding, including active/bound states. |
| `_is_button()` | 408 | True for push buttons (they get their own font rules). |
| `button_fit_height()` | 418 | Compact touch target sized alongside its text, not a fixed 26/32px floor. |
| `readable_control_height()` | 431 | Return a font-safe height: at least `nominal_height`, and tall enough for the text. |
| `set_readable_height()` | 458 | Fix height and retain the requested pre-style height for Qt reflow. |
| `set_readable_square()` | 466 | Scale +/- control width with font and height without truncation. |
| `restore_readable_height()` | 473 | Recheck after styling; a button may shrink back to its own target as well as grow. |
| `input_padding()` | 503 | QLineEdit padding in logical pixels, scaled with fonts below 100%. |
| `scaled_line_edit_height()` | 512 | Use text metrics rather than a native Qt sizeHint with unscaled padding. |
| `fit_scaled_input_height()` | 529 | Set a restorable input target, after optional font overrides. |
| `comment_widths()` | 536 | Minimum and maximum field widths based on the actual scaled font. |
| `fit_scaled_comment_field()` | 551 | Scale axis and hardware-button comment boxes below 100%. |
| `axis_comment_widths()` | 570 | Compact, resizable per-axis comment field limits. |
| `fit_axis_comment_field()` | 588 | Apply a narrower axis comment column on every display preset. |
| `fit_axis_combo_width()` | 609 | Use intrinsic item text width instead of expanding with the editor row. |

</div>

#### `ui/monitor_scale.py` — 14 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `native_monitors()` | 32 | [{name, dpi, primary, width, height, work_w, work_h}] in physical pixels (Windows only). |
| `saved_home_name()` | 101 | Windows device name of the monitor the Mapper was last used on. |
| `monitor_auto_scale()` | 124 | Same arithmetic Qt-side startup uses, from physical Win32 values. |
| `monitor_fit()` | 139 | How much smaller the editor is drawn on this monitor (v108.151; 1.0: not smaller). |
| `monitor_layout_scale()` | 147 | The layout scale the editor would be built with on this monitor (Display % and fit included). |
| `screen_factors()` | 154 | {name: Qt factor}, plus the home monitor that was used. |
| `format_factors()` | 188 | Monitor scale factors as one text line for the log. |
| `_set_pass_through_rounding()` | 194 | Use 125%/150%/175% as-is; Qt 5 otherwise rounds them to 100%/200%. |
| `configure_before_qapplication()` | 206 | Call after the DPI-awareness calls and before QApplication(). |
| `_native()` | 262 | The monitor's Windows scaling as a factor (1.5 for 150%). |
| `monitor_shape()` | 267 | A monitor's name, resolution and scaling (its work area left out: a taskbar change asks nothing). |
| `describe_monitor()` | 272 | 'Display 2 — 1920 × 1080, 100%' for messages. |
| `factors_in_use()` | 280 | {name: the factor Qt draws each monitor with}: ours from start-up, else its Windows scaling. |
| `stale_monitors()` | 292 | [(monitor, why)] for the monitors the editor is drawn at the wrong size on now (v108.163). |

</div>

#### `ui/system_font.py` — 5 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `system_dpi()` | 46 | The DPI Windows was signed in with (0 when unknown). |
| `windows_gui_font()` | 72 | (height in pixels, face name, sign-in DPI) of Windows' default GUI font, or None. |
| `_family_key()` | 96 | A font family name for comparing: Qt names Windows' "MS Shell Dlg" "MS Shell Dlg 2". |
| `corrected_default_points()` | 101 | The point size Qt's default font should have, or None when Qt's is right (or unknown). |
| `fix_stale_default_font()` | 120 | Give Qt's default font the size Windows meant; returns the new size, or None. |

</div>

#### `ui/editor_fit.py` — 12 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `prepare_full_scroll()` | 20 | Let the editor's scroll areas resize with the window. |
| `editor_needed_size()` | 41 | Natural QMainWindow CLIENT width/height needed without axis scrollbars. |
| `fit_controls_to_text()` | 97 | Measure styled Qt controls after construction. |
| `_mouse_held()` | 142 | True while the left mouse button is down (a window drag). |
| `_refit_to_screen()` | 150 | Resize the editor to fit its monitor once a drag between monitors ends. |
| `_windows_screen()` | 191 | The monitor Windows has the window on (Qt's answer when Windows gives none). |
| `_note()` | 198 | Write a line to the start-up log. |
| `_screen_changed()` | 208 | Schedule a refit when the window reaches a monitor with another scale. |
| `_watch_window_screen()` | 218 | Follow the window's monitor changes. |
| `_ScreenWatchFilter.eventFilter()` | 231 | Start following monitor changes once the window has a native handle. |
| `install_screen_watch()` | 238 | Install the monitor-change watch on the main window. |
| `log_editor_fit()` | 256 | Note in startup.log the editor's natural size, its monitor's room and the fit used. |

</div>

#### `ui/placement.py` — 17 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `positions_monitor()` | 53 | The monitor checked in Display > Positions Saved ({screen_name, serial}), or None. |
| `connected_screen()` | 61 | The connected QScreen for a monitor record, or None (no fallback). |
| `set_positions_monitor()` | 74 | Check `screen` in Display > Positions Saved (None: uncheck). |
| `load_window_placement()` | 94 | Read window_state.json, or an empty dict. |
| `_view_positions()` | 106 | The saved editor positions, loaded once per window. |
| `_monitor_positions()` | 122 | Saved editor positions, per monitor. |
| `_position()` | 128 | The position fields of a saved record. |
| `_screen_named()` | 134 | The connected monitor with this name, or None. |
| `_hwnd()` | 141 | The window's native handle, or 0. |
| `window_screen()` | 149 | The monitor the window is on, as Windows sees it (Qt's view as fallback). |
| `save_window_placement()` | 158 | Save the editor's position on its monitor (Positions Saved). |
| `_write_state()` | 214 | Write window_state.json. |
| `_target_screen()` | 232 | (screen, saved position record or None for centred) for the editor about to be shown. |
| `_saved_on()` | 255 | The editor's saved position on monitor `name`, placed on `screen`; None if not saved. |
| `restore_window_placement()` | 261 | Place the editor on its monitor. False when there is nothing to restore. |
| `_keep_on_target_screen()` | 305 | Move a just-restored window back if it opened on another monitor. |
| `settle_editor_size()` | 324 | Grow the just-shown editor to hold its content. True when it was resized. |

</div>

#### `ui/window_placement.py` — 4 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `screen_record()` | 4 | Name, serial number and geometry of a monitor. |
| `select_screen()` | 14 | Prefer a physical identifier, then a unique Windows display name. |
| `read_views()` | 30 | The saved per-view records of window_state.json. |
| `client_rect()` | 51 | Clamp client coordinates while allowing space for the native frame. |

</div>

#### `ui/title_controls.py` — 2 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `title_button_width()` | 9 | Return text width plus CSS padding, borders, and an italic-font margin. |
| `fit_full_editor_title_label()` | 14 | Constrain a styled QLabel to its actual text width. |

</div>

### 8.7. Title effect, Bind lines and scrolling text

#### `ui/title_effect.py` — 18 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `RainbowOverlay.__init__()` | 29 | Overlay that draws the title's rainbow border. |
| `RainbowOverlay.eventFilter()` | 45 | Keep the overlay the size of its widget. |
| `RainbowOverlay.set_wanted()` | 62 | Show or hide the overlay for good (not just between hovers). |
| `RainbowOverlay.set_hover_phase()` | 72 | Set the animation phase and repaint. |
| `RainbowOverlay._rainbow()` | 82 | A rainbow colour for a hue and opacity. |
| `RainbowOverlay._orbit_gradient()` | 87 | The rotating conical gradient of the border. |
| `RainbowOverlay.paintEvent()` | 105 | Paint the animated border. |
| `SweepLine.__init__()` | 161 | Thin line on a Bind button (white NoBack, green Bind Dir). |
| `SweepLine.set_sides()` | 166 | Which way the line runs from the middle: left, right or both. |
| `SweepLine.sides()` | 173 | The sides the line covers. |
| `SweepLine.sweep()` | 177 | (share of the half-width reached, alpha) for the current phase. |
| `SweepLine.paintEvent()` | 188 | Paint the line from the middle out to its current reach. |
| `_noback_glows()` | 228 | Every shown line (NoBack and Bind Dir) on every Bind button. |
| `_cursor_over_app()` | 240 | True when the mouse pointer is over the Mapper's window. |
| `_title_controls()` | 255 | The widgets that get the title effect. |
| `wire_title_effect()` | 261 | Attach the border overlay to the title. |
| `_tick_title_effect()` | 275 | Advance the title and Bind-line animation while hovering. |
| `install_title_effect()` | 298 | Start the title animation timer. |

</div>

#### `ui/profile_marquee.py` — 12 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `scroll_offset()` | 13 | Pixels to scroll a long name after a pause, then pause at the end. |
| `_Marquee._init_marquee()` | 23 | Set up the scrolling clock and timer. |
| `_Marquee._restart()` | 31 | Scroll the text from its start again. |
| `_Marquee.resizeEvent()` | 36 | Restart scrolling when the field changes size. |
| `_Marquee.hideEvent()` | 41 | Stop scrolling while hidden. |
| `_Marquee._overflow()` | 47 | How many pixels the text is wider than the field. |
| `_Marquee._draw_name()` | 60 | Paint the text at its current scroll position. |
| `ProfileDisplay.__init__()` | 70 | The read-only Profile name field, scrolling long names. |
| `ProfileDisplay.paintEvent()` | 75 | Paint the profile name at its scroll position. |
| `ScrollingLineEdit.paintEvent()` | 98 | Paint long comment text scrolling while not being edited. |
| `ScrollingLineEdit.focusInEvent()` | 106 | Restart scrolling from the start when the field gets focus. |
| `ScrollingLineEdit.focusOutEvent()` | 111 | Restart scrolling from the start when the field loses focus. |

</div>

### 8.8. Other modules

#### `axis_history.py` — 27 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `unsent()` | 36 | The not-sent form of an event kind (HELD stays HELD: NoBack holds a bind either way). |
| `is_unsent()` | 41 | True for what a bind would have sent while output was off. |
| `AxisHistory.__init__()` | 49 | An empty history keeping `keep_s` seconds, timed by `clock`. |
| `AxisHistory.add_sample()` | 59 | Record the axis value now. |
| `AxisHistory.add_event()` | 71 | Record what bind `bind_index` did now (`kind`), its key text, at axis value `value`. |
| `AxisHistory.set_noback()` | 75 | Note NoBack's state now (`side` and the highest band start reached), when it changed. |
| `AxisHistory.noback_span()` | 82 | NoBack's states from the last `seconds` seconds before `now`, with the one in force at their start. |
| `AxisHistory.clear()` | 88 | Forget everything recorded. |
| `AxisHistory.span()` | 94 | (samples, events) from the last `seconds` seconds before `now`. |
| `bind_bands()` | 103 | Where each mapped bind starts, as drawn on the graph. |
| `summary()` | 136 | One line: the farthest the axis went each way, and what each bind did. |
| `csv_rows()` | 160 | Rows for a CSV file of one or more axes: a header, then every sample and event in time order. |
| `bind_colour()` | 194 | The colour name of bind `index` (0 for Bind #1), the same on every axis. |
| `text_width()` | 199 | An estimate of `text`'s width in pixels (the window measures with its font instead). |
| `_frame()` | 205 | The plot area and its coordinates: (x0, x1, top, bottom, x_at, y_at). |
| `_grid()` | 235 | The percent lines and their labels. |
| `_times()` | 247 | "−10 s", "−5 s" and "now" under the plot. |
| `_dots()` | 258 | A dot for each key in its bind's colour: filled when sent, hollow when not sent (output off); a hollow light dot where NoBack held a bind back. |
| `_noback_shapes()` | 298 | While NoBack is in force: a thin dashed light line at the highest band reached. |
| `label_rows()` | 324 | One row per bind side for the labels' column, top (+100%) to bottom (−100%). |
| `spread()` | 344 | Baselines for labels wanted at `wanted` (top to bottom), each at least `gap` below the last, kept between `low` and `high` as far as they fit. |
| `_label_columns()` | 361 | The labels' columns: [(column, x offset, width, align)] and the column's total width. |
| `_labels()` | 390 | The labels' column right of the plot, its rows spread so they never overlap, each joined to its start line; returns (shapes, gutter width). |
| `drawing()` | 420 | One axis's graph as plain shapes, for a widget `width` × `height` pixels. |
| `drawing_together()` | 486 | Several axes on one graph, as plain shapes (see drawing()). |
| `load_view()` | 518 | The history window's remembered view `stored`, each part checked. |
| `fit_size()` | 546 | The window's size on a screen with `room` (width, height) to work in. |

</div>

#### `ui/axis_history_window.py` — 39 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_colour()` | 97 | The QColor of a colour name from axis_history.drawing(). |
| `noback_note()` | 104 | The summary's NoBack part, such as " · NoBack: Bind #1 −, Bind #3 +" (empty when no bind has it). |
| `_key_text()` | 117 | The key a bind sends, or "macro". |
| `HistoryGraph.__init__()` | 127 | A graph of `axes` for the Axis History window `window`. |
| `HistoryGraph.paintEvent()` | 133 | Paint the shapes of the current view. |
| `AxisHistoryWindow.__init__()` | 186 | Build the window for the Mapper window `win`. |
| `AxisHistoryWindow.shown_axes()` | 307 | The axes shown, in the panels' order. |
| `AxisHistoryWindow.together()` | 311 | True when the axes are drawn on one graph. |
| `AxisHistoryWindow.seconds()` | 315 | How many seconds are shown. |
| `AxisHistoryWindow.graph()` | 320 | The first graph (each axis has its own unless One graph is chosen). |
| `AxisHistoryWindow.set_axes()` | 324 | Show exactly `axes` (none is allowed). |
| `AxisHistoryWindow.toggle_all()` | 333 | All: hide every axis when all six are shown, else show all six. |
| `AxisHistoryWindow._axis_toggled()` | 337 | A check box changed. |
| `AxisHistoryWindow._view_changed()` | 341 | Rebuild the graphs for the axes and layout chosen, and remember them. |
| `AxisHistoryWindow._build_lanes()` | 348 | One graph per axis shown, or one for all of them. |
| `AxisHistoryWindow._no_focus()` | 364 | No control takes the keyboard: keys the binds send land on the window, which ignores them. |
| `AxisHistoryWindow.keyPressEvent()` | 369 | Ignore every key (Esc and Enter included): with the Target on, they come from the binds. |
| `AxisHistoryWindow.keyReleaseEvent()` | 373 | Ignore every key release. |
| `AxisHistoryWindow._size_lanes()` | 377 | Each graph at least LANE_LINES lines of text tall, and tall enough for a row per bind side in its labels (the window scrolls past that). |
| `AxisHistoryWindow.now()` | 390 | The view's end: the moment Pause was pressed, else now. |
| `AxisHistoryWindow.view()` | 396 | (samples, events) of `axis` in view. |
| `AxisHistoryWindow.shapes()` | 403 | The shapes of a graph of `axes`, `width` × `height` pixels, for text `text_px` tall (`text_w(text)`: its width). |
| `AxisHistoryWindow.refresh()` | 433 | Redraw the graphs and the summary lines. |
| `AxisHistoryWindow.set_text_size()` | 447 | Show the window's text at `size` (one of TEXT_SIZES) × the app's text + 2 points. |
| `AxisHistoryWindow.step_text_size()` | 476 | The next larger (+1) or smaller (-1) text size. |
| `AxisHistoryWindow._room()` | 481 | The available area of the screen the Mapper is on (Qt pixels). |
| `AxisHistoryWindow.place()` | 488 | Size the window (remembered, else most of the screen) and centre it on the Mapper's screen. |
| `AxisHistoryWindow.remember()` | 498 | Remember the axes, layout, time span, text size and window size for next time. |
| `AxisHistoryWindow.show_axis()` | 513 | Show the window, with `axis` among the axes shown when given. |
| `AxisHistoryWindow.toggle_pause()` | 528 | Pause (freeze the view) or resume. |
| `AxisHistoryWindow.clear()` | 538 | Forget what was recorded on every axis. |
| `AxisHistoryWindow.save_csv()` | 545 | Save the samples and events of the axes shown, in view, to a CSV file the user picks. |
| `AxisHistoryWindow.hide_window()` | 567 | Hide the window (recording stopped), remembering its size; the Target goes back as it was. |
| `AxisHistoryWindow.closeEvent()` | 576 | Closing turns Axis History off (v108.156): recording stops and Options > Axis History is unchecked. |
| `axis_history_on()` | 591 | True while the axes are being recorded. |
| `set_axis_history()` | 596 | Options > Axis History: record all six axes (and show the window), or stop and forget. |
| `show_axis_history()` | 625 | Open the Axis History window (on `axis`), turning recording on when it is off. |
| `add_axis_history_option()` | 636 | Add the checkable Options > Axis History; it starts on when it was on at the last exit. |
| `reopen_axis_history()` | 655 | Reopen the window (it was open at the last exit) when the editor is on screen; True when it did. |

</div>

#### `ui/elevation.py` — 7 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_note()` | 34 | Write a line to the start-up log. |
| `_program_name()` | 44 | The program's file name (its window's title when that cannot be read). |
| `ElevationGuard.__init__()` | 58 | For window `win`; `mapper_admin` overrides asking Windows (tests). |
| `ElevationGuard.blocked()` | 67 | True when keys to window `hwnd` are blocked: it runs as administrator and the Mapper does not. |
| `ElevationGuard.tick()` | 76 | Each GUI tick: keys sent to `fg` (output allowed) while it runs as administrator? |
| `ElevationGuard.check_target()` | 100 | A target was picked: when it runs as administrator, offer the restart now. True when asked. |
| `install_elevation_guard()` | 125 | Make the window's guard, and its Options item (Restart as / Running as Administrator). |

</div>

#### `ui/menu_tips.py` — 5 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_plain()` | 55 | The text as shown: no & accelerator marks. |
| `has_own_tip()` | 60 | True when the action was given a tip (Qt's default tip is its text). |
| `tip_for()` | 66 | The tip for an item with `text` in the menu titled `menu_title` ("" for none). |
| `tip_menu()` | 78 | Show tips in `menu` and its submenus, now and each time it opens. |
| `install_menu_tips()` | 101 | Tips for Auto-Profiles, Options, Display (and their submenus) and the tray menu. |

</div>

#### `ui/monitor_watch.py` — 7 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_note()` | 27 | Write a line to the start-up log. |
| `_ShownFilter.eventFilter()` | 38 | A check that waited for the editor to be shown runs once it is. |
| `install_monitor_watch()` | 45 | Follow monitors being connected, disconnected, resized or rescaled. |
| `_watch_screen()` | 66 | Follow one monitor's resolution and scaling. |
| `_changed()` | 74 | A monitor came, went or changed: check once things are quiet. |
| `check_monitors_soon()` | 81 | Check the monitors after `delay` ms (restarted by every new change). |
| `check_monitors()` | 88 | Ask to restart when the editor is drawn at the wrong size on a monitor now. True when asked. |

</div>

#### `ui/profile_buttons.py` — 5 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `profile_button_widths()` | 20 | (Target, each of the three) widths for a row `row_width` wide. |
| `ProfileButtonRow.__init__()` | 37 | Lay out `target` and `buttons` in `row`, leaving `beside`'s width empty at its end. |
| `ProfileButtonRow.eventFilter()` | 56 | The row or the Auto Load selector changed size: share the room again. |
| `ProfileButtonRow.stretches()` | 62 | [Target, Save/Reload, Save as, Load, the empty space and its gap]: the row's stretch factors. |
| `ProfileButtonRow.apply()` | 72 | Set the five stretch factors for the row's width now. |

</div>

#### `ui/save_reload_dialog.py` — 7 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `profile_stem()` | 22 | The typed name without the spaces around it or a ".json" ending. |
| `name_problem()` | 30 | Why `stem` cannot name a profile file, or "" when it can. |
| `SaveReloadDialog.__init__()` | 48 | Build the prompt for saving to `path` (the name can be changed). |
| `SaveReloadDialog.chosen_path()` | 90 | The file to save and reload, or None while the name cannot be used. |
| `SaveReloadDialog.is_new_name()` | 97 | True when the name differs from the loaded profile's. |
| `SaveReloadDialog._update()` | 101 | Say what Save/Reload will do with the name typed; disable it for a name that cannot be used. |
| `ask_save_reload_path()` | 127 | Show the prompt for `path`; the file to save and reload, or None when cancelled. |

</div>

#### `ui/taps.py` — 10 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `tap_key()` | 28 | What identifies a combination: its keys, lower-cased, in order. |
| `repeat_interval_ms()` | 33 | Press/Repeat's time from one tap to the next: Repeat every, but never less than the Tap Dwell plus MIN_UP_MS (the key must be seen up). |
| `TapSender.__init__()` | 47 | Taps through `send`, timed with `schedule` and `clock`. |
| `TapSender._state()` | 52 | The state of one combination's taps (made the first time). |
| `TapSender.tap()` | 58 | Tap `combo` for `dwell_ms`: now, or once the same keys have been up MIN_UP_MS. |
| `TapSender._press()` | 79 | Press now; the release is scheduled after the dwell. |
| `TapSender._release()` | 88 | The dwell is over: release, then start a tap that waited (after MIN_UP_MS). |
| `TapSender._start_waiting()` | 99 | Start the tap that waited for the keys to have been up long enough. |
| `TapSender.held()` | 110 | The combinations a tap has down now. |
| `TapSender.release_all()` | 114 | Release every tap still down, at once, and drop the taps waiting. |

</div>

#### `ui/taskbar.py` — 19 functions

<div class="functions">

| Function / method                 | Line | Purpose                                                    |
|-----------------------------------|-----:|------------------------------------------------------------|
| `_note()` | 55 | Write a line to the start-up log. |
| `taskbar_commands()` | 65 | {"restore": [...], "exit": [...]}: the command lines the taskbar's items start. |
| `icon_location()` | 72 | The icon for the items: the EXE's own, else the Mapper's .ico file (source runs). |
| `relaunch_properties()` | 83 | [(key, text)]: what the window tells the taskbar about its program item. |
| `user_tasks()` | 96 | [(title, program, arguments, description)]: the menu's Tasks. |
| `_guid()` | 132 | A GUID structure from its "{...}" text. |
| `_key()` | 137 | A PROPERTYKEY: a property set's GUID and the property's number in it. |
| `_call()` | 142 | Call method `index` of the COM interface at `pointer`; raise OSError on a failed HRESULT. |
| `_release()` | 154 | IUnknown::Release, for a pointer that holds an interface. |
| `_create()` | 160 | CoCreateInstance: a new object of class `clsid`, as interface `iid`. |
| `_query()` | 173 | IUnknown::QueryInterface for `iid`. |
| `_set_string()` | 188 | IPropertyStore::SetValue with a string (None: remove it), then Commit. |
| `_Com.__enter__()` | 207 | Initialize COM on this thread (Qt usually has already). |
| `_Com.__exit__()` | 214 | Balance a CoInitializeEx that succeeded. |
| `_window_store()` | 221 | The window's property store (SHGetPropertyStoreForWindow). |
| `set_window_relaunch()` | 234 | Name the taskbar's program item Restore SpaceNavigator Mapper (clear=True: remove it). |
| `set_jump_list()` | 247 | Put Exit SpaceNavigator Mapper in the taskbar menu's Tasks. |
| `install_taskbar_menu()` | 305 | Restore and Exit SpaceNavigator Mapper in the taskbar button's right-click menu. |
| `remove_window_relaunch()` | 331 | At exit: the window's relaunch properties are removed, as Windows asks. |

</div>

<!-- END FUNCTION REFERENCE -->

## 9. Implementation and review checklist for future releases

Verified by the automated tests for this version (simulated Windows, Qt and device):

- [x] The Full Editor is the only interface; no Compact Mode controls, state or resize handlers remain.
- [x] All six axes and their 36 binds display, save and load.
- [x] NoBack per bind (offered only for the way back: − for POS, + for NEG, both for FULL) works on outward and inward passes, including the resets at centre, below every band and on crossing sides.
- [x] Binds without NoBack are not suppressed.
- [x] Both hardware buttons press and release their combinations.
- [x] Manual On never types into the Mapper itself; Auto Load sends keys only to the target.
- [x] Macros play Once and Repeat and never leave a key held.
- [x] Each axis's six comment fields line up with their Bind buttons.
- [x] Delete Linked Program asks first, then unlinks, saves and reloads.
- [x] Save/Reload with a new name saves a new profile, loads it and keeps the old file; settings-file names are refused.
- [x] Axis History records samples, keys and NoBack holds, shows several axes (separate or on one graph), saves a CSV and stops when unchecked.
- [x] Auto Load does not reload a profile edited in the Mapper; Switch to… lists the target program's profiles.
- [x] The key picker reports keys, modifiers and symbols; the device's presence is checked once a second.
- [x] The taskbar button's right-click menu offers Restore and Exit SpaceNavigator Mapper; a second start brings the running copy forward without a message box.
- [x] Keys to a program running as administrator: the Mapper warns and offers Restart as Administrator; a copy running as administrator still answers a second start.
- [x] Auto Load keeps a loaded profile of the program in front (and its unsaved changes); the first change in Auto Load offers Manual On.
- [x] Profiles saved or loaded with a target are listed for that program in Auto-Profiles (Switch to…).
- [x] Hover tips have the normal tip look everywhere (a widget's own style is scoped to it); Profile: is a dark gray button.
- [x] A start of one version with another running asks to replace it, instead of showing the old one; a greyed-out − / + keeps its sign's size.
- [x] A tap does not stop the Mapper during its dwell; a key is up at least 30 ms before it is tapped again; Press/Repeat never taps sooner than Tap Dwell + 30 ms and says so.
- [x] Tap Dwell is set per bind above DZone, greyed out for Hold and Release-only; each tap holds its bind's dwell.
- [x] Switch to… keeps the picked profile for its program in Auto Load; Auto-Profiles has no Tap dwell item and no separators; every menu item and the Quick Bind and header controls have hover tips.
- [x] A restart (Display size, Monitors Changed) starts the EXE the user started, not its onefile copy in a temporary folder, and keeps the configs folder.
- [x] On two monitors with different scales, an editor Windows moves at start-up is moved back at its full size; a refit after a drag uses the monitor Windows reports; a monitor connected or changed after start-up offers a restart.

Still to check on the running Windows build:

- [ ] Every mode and NoBack combination in your games, with the real SpaceNavigator.
- [ ] Keys to a game run as administrator, before and after Options > Restart as Administrator.
- [ ] The taskbar button's right-click menu (Restore / Exit SpaceNavigator Mapper) in the EXE and from source, pinned and not pinned.
- [ ] The editor's size and Positions Saved on both monitors at their Windows scale settings, including a sign-in start in the tray and a monitor connected while the Mapper runs.
- [ ] The EXE built by `BUILD_EXE_WINDOWS.bat` on a PC without Python.
- [ ] Both README choices of the title's right-click work in the EXE and the single-file edition.

---

**Source used:** the `spnav_mapper` package of the version named at the top.  
**README scope:** Full Editor user functions and a source-level function inventory.
