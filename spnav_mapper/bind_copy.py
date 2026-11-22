"""Copy and paste of a bind (v108.181): all its settings and its comment, in one go.

Copy on a Bind button's right-click menu takes everything that makes the bind
what it is: its keys, Bind Dir, Mode, Min%, Max%, DZone, Tap Dwell, Min Hold,
the Press/Repeat time, NoBack, the Rebound time, its macro and its comment. Paste
puts all of it into another bind: of the same axis, of another axis, or,
after loading another profile, of that profile. The copy is kept while the
Mapper runs and has nothing to do with Windows' clipboard. No Qt.

v108.182: Undo Paste. What the bind was before the last paste is kept, so
the paste can be taken back: one step, the last paste only, until the bind's
axis is loaded from a profile or reset.
"""

import copy as _copy

# What is copied: a bind's settings as the axis panel keeps them. Not its
# running state (whether its key is down, when it last tapped).
SETTINGS = (
    "direction",
    "combo",
    "mode",
    "min",
    "max",
    "dead",
    "repeat_ms",
    "tap_ms",
    "min_hold_ms",  # v108.187: a Hold bind's Min Hold
    "settle_ms",
    "noback_plus",
    "noback_minus",
    "macro",
    "macro_repeat",
    "enabled",  # v108.183: switched on or off
)

_copied = None  # {"settings": {...}, "comment": str, "source": str}


def copy_bind(bind, comment="", source=""):
    """Keep a copy of `bind`'s settings and `comment`; `source` names it ("Z Bind #2")."""
    global _copied
    _copied = {
        "settings": {key: _copy.deepcopy(bind[key]) for key in SETTINGS if key in bind},
        "comment": str(comment or ""),
        "source": str(source or ""),
    }
    return copied()


def copied():
    """The bind that was copied (its own copy, safe to change), or None."""
    return _copy.deepcopy(_copied) if _copied else None


def source():
    """The name of the copied bind ("Z Bind #2"), or "" when nothing was copied."""
    return _copied["source"] if _copied else ""


def clear():
    """Forget the copied bind (and the paste that could be undone)."""
    global _copied
    _copied = None
    forget_paste()


# --- v108.182: Undo Paste -------------------------------------------------------
_before = None  # {"owner": the axis panel, "index": int, "settings": {...}, "comment": str, "name": str}


def remember_before_paste(owner, index, bind, comment="", name=""):
    """Keep what `owner`'s bind number `index` is now, before it is pasted over ("X Bind #4")."""
    global _before
    _before = {
        "owner": owner,
        "index": int(index),
        "settings": {key: _copy.deepcopy(bind[key]) for key in SETTINGS if key in bind},
        "comment": str(comment or ""),
        "name": str(name or ""),
    }


def before_paste():
    """The bind as it was before the last paste: {"owner", "index", "settings", "comment", "name"}, or None."""
    if not _before:
        return None
    return {**_before, "settings": _copy.deepcopy(_before["settings"])}


def undo_name():
    """The name of the bind the last paste went into ("X Bind #4"), or "" when there is none to undo."""
    return _before["name"] if _before else ""


def forget_paste(owner=None):
    """Forget the paste that could be undone: any, or only one that went into `owner`'s bind."""
    global _before
    if _before and (owner is None or _before["owner"] is owner):
        _before = None
