"""Hover tips for every item of the menu bar's menus and the tray menu (v108.165).

An item keeps a tip it was given where it is made; the others get theirs
here, by their text. Items a menu fills in as it opens (Switch to…'s
profiles, Load Backup's files) get their menu's tip for its items each time
it opens.
"""

TIPS = {
    # Auto-Profiles
    "Enable Auto-Profiles": (
        "Checked: in Auto Load, the profile that auto_profiles.json gives for the program in front "
        "is loaded whenever that program changes. Unchecked: the loaded profile stays."
    ),
    "Switch to…": (
        "The profiles whose rules match the program in front, lowest priority number first. "
        "Pick one to load it now; it stays for that program until you pick another."
    ),
    "Reload Auto-Profiles": (
        "Read auto_profiles.json again and load the profile it gives for the program in front "
        "(a profile picked with Switch to… is forgotten)."
    ),
    "Open auto_profiles.json…": "Show auto_profiles.json (which program loads which profile) in Explorer.",
    "Open Auto-Profiles Folder…": "Open the folder that holds auto_profiles.json.",
    "(No candidates for current app)": "No rule in auto_profiles.json matches the program in front.",
    # Options
    "Device LED": "Switch the SpaceNavigator's LED on or off.",
    "Load Backup": (
        "The copies kept each time a profile is saved, newest first. Pick one to load it as a new "
        "profile (…_restored); the backup itself is kept."
    ),
    "Browse all backups…": "Choose any backup file to load as a new profile.",
    "No backups yet": "A backup is kept each time a profile is saved.",
    "Backups unavailable": "The backups folder could not be read.",
    "Exit SpaceNavigator Mapper": (
        "Stop the Mapper: no more keys are sent. It exits even with Close to System Tray checked."
    ),
    # Display
    "Positions Saved": (
        "Check the monitor the editor always opens on, at its saved position. None checked: it opens centred."
    ),
    # The tray icon's menu
    "Restore SpaceNavigator Mapper": "Show the editor.",
    "Minimize to Taskbar": "Put the editor on the taskbar, minimized; the Mapper keeps running.",
    "Profiles": "Load a profile and make it the active one, without opening the editor.",
}

# Items a menu fills in as it opens, by the menu's title.
ITEM_TIPS = {
    "Switch to…": "Load this profile now, for the program in front.",
    "Load Backup": "Load this backup as a new profile (…_restored); the backup itself is kept.",
}


def _plain(text):
    """The text as shown: no & accelerator marks."""
    return str(text or "").replace("&&", "\0").replace("&", "").replace("\0", "&")


def has_own_tip(action):
    """True when the action was given a tip (Qt's default tip is its text)."""
    tip = _plain(action.toolTip())
    return bool(tip) and tip != _plain(action.text())


def tip_for(text, menu_title=""):
    """The tip for an item with `text` in the menu titled `menu_title` ("" for none)."""
    text = _plain(text)
    if text in TIPS:
        return TIPS[text]
    if "(not connected" in text:  # Positions Saved: the checked monitor is not connected
        return (
            "This monitor is not connected: the editor opens on the primary monitor. Uncheck it to save none."
        )
    return ITEM_TIPS.get(_plain(menu_title), "")


def tip_menu(menu):
    """Show tips in `menu` and its submenus, now and each time it opens."""
    try:
        menu.setToolTipsVisible(True)
        title = menu.title()
        for action in menu.actions():
            if action.isSeparator():
                continue
            if not has_own_tip(action):
                tip = tip_for(action.text(), title)
                if tip:
                    action.setToolTip(tip)
            submenu = action.menu()
            if submenu is not None:
                tip_menu(submenu)
        if not getattr(menu, "_spnav_tips", False):
            menu._spnav_tips = True
            # Connected after the menu's own filling, so it sees the new items.
            menu.aboutToShow.connect(lambda m=menu: tip_menu(m))
    except RuntimeError:  # the menu is being destroyed
        pass


def install_menu_tips(win):
    """Tips for Auto-Profiles, Options, Display (and their submenus) and the tray menu."""
    bar = getattr(win, "menuBar", None)
    for action in bar().actions() if bar is not None else ():
        if action.menu() is not None:
            if not has_own_tip(action):
                action.setToolTip(tip_for(action.text()))
            tip_menu(action.menu())
    tray_menu = getattr(win, "_tray_menu", None)
    if tray_menu is not None:
        tip_menu(tray_menu)
