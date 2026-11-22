"""A profile's note (v108.187): text kept in the profile file, and whether it is important (no Qt).

A profile can carry a note: what the game or the Mapper needs set for the
profile to work (in-game key binds, Run as Administrator, a setting that is
not in the profile). In the file it is

    "note": {"text": "...", "important": true}

written only when there is text, so a profile without a note is as before,
and a profile from before simply has none. A note marked important makes the
profile name flash red and white when the profile is loaded, until the note
has been opened once; after that the name stays red.

v108.189: that the note has been opened is remembered on this PC (in
ui_preferences.json, by what the note says), so the name does not flash again
at the next start. It flashes again when the note's text changes, and on a
PC the note has not been opened on.
"""

import hashlib
import json

from .backups import save_with_backup

NOTE_MAX_CHARS = 4000  # more is cut off: a note, not a document
TIP_CHARS = 600  # as much of the note as the profile name's tip shows
FLASH_MS = 500  # the name changes colour twice a second: one flash a second
RED, WHITE = "#ff4040", "#ffffff"

UNREAD, READ, PLAIN = "unread", "read", "plain"  # what the profile name shows

READ_PREFERENCE = "profile_notes_read"  # ui_preferences.json: the marks of the notes opened on this PC
READ_KEEP = 200  # notes remembered; the oldest are dropped beyond that


def clean_note(text):
    """A note's text as it is kept: a string, its line ends alike, no blank ends, at most NOTE_MAX_CHARS."""
    if not isinstance(text, str):
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return text[:NOTE_MAX_CHARS].rstrip()


def note_from_config(cfg):
    """(text, important) of the note in profile data `cfg`; ("", False) when it has none.

    A note that is only a string (written by hand) is taken as its text.
    """
    note = cfg.get("note") if isinstance(cfg, dict) else None
    if isinstance(note, str):
        return clean_note(note), False
    if not isinstance(note, dict):
        return "", False
    text = clean_note(note.get("text"))
    return text, bool(text and note.get("important"))


def note_to_config(text, important):
    """The "note" entry of a profile file for this note, or None when there is no text."""
    text = clean_note(text)
    return {"text": text, "important": bool(important)} if text else None


def put_note(cfg, text, important):
    """Set (or, without text, remove) the note in profile data `cfg`; returns `cfg`."""
    entry = note_to_config(text, important)
    if entry is None:
        cfg.pop("note", None)
    else:
        cfg["note"] = entry
    return cfg


def write_note_to_profile(path, text, important, backup_directory):
    """Write only the note into the profile file `path`; the rest of the file stays as it is.

    The file's previous contents go to the backups folder first, as with
    every save. Raises OSError or ValueError when the file cannot be read as
    a profile or written.
    """
    with open(path, encoding="utf-8") as stream:
        cfg = json.load(stream)
    if not isinstance(cfg, dict):
        raise ValueError("not a profile file")
    return save_with_backup(path, put_note(cfg, text, important), backup_directory)


def note_mark(text):
    """A short mark of what a note says: another text gives another mark (v108.189)."""
    return hashlib.sha256(clean_note(text).encode("utf-8")).hexdigest()[:16]


def clean_read(stored):
    """The remembered marks as read from the preferences: a list of strings, each once, oldest first."""
    marks = []
    for mark in stored if isinstance(stored, list) else ():
        if isinstance(mark, str) and mark and mark not in marks:
            marks.append(mark)
    return marks


def note_read(stored, text):
    """True when a note saying this has been opened on this PC (v108.189).

    It goes by what the note says, not by its file: the profile can be
    renamed, saved under another name or come back as the last
    configuration at start-up and its note stays read. A note without text
    has nothing to read: True.
    """
    text = clean_note(text)
    return not text or note_mark(text) in clean_read(stored)


def with_note_read(stored, text, keep=READ_KEEP):
    """`stored` with a note saying this remembered as opened (a new list, the newest last).

    Beyond `keep` notes the oldest are dropped. Without text, nothing is added.
    """
    marks = clean_read(stored)
    text = clean_note(text)
    if text:
        mark = note_mark(text)
        if mark in marks:
            marks.remove(mark)
        marks.append(mark)
    return marks[-max(1, int(keep)) :]


def name_state(text, important, seen):
    """What the profile name shows: UNREAD (it flashes), READ (steady red) or PLAIN (as always)."""
    if not (clean_note(text) and important):
        return PLAIN
    return READ if seen else UNREAD


def flash_colour(state, phase):
    """The profile name's colour for `state`: red and white in turn while unread, red once read, else None."""
    if state == UNREAD:
        return RED if phase else WHITE
    return RED if state == READ else None


def name_tip(text, important, seen):
    """The profile name's hover tip: what a click does, and the note (its first TIP_CHARS characters)."""
    text = clean_note(text)
    if not text:
        return (
            "Click: choose the target program's window.\n"
            "Right-click: add a note to this profile (also Options > Profile Note…)."
        )
    shown = text if len(text) <= TIP_CHARS else text[:TIP_CHARS].rstrip() + "…"
    state = name_state(text, important, seen)
    if state == UNREAD:
        head = "⚠ Important note, not opened yet: click the name to read it."
    elif state == READ:
        head = "Important note (right-click to open it; a click chooses the target program's window):"
    else:
        head = "Note (right-click to open it; a click chooses the target program's window):"
    return f"{head}\n\n{shown}"


def tray_line(text, important, seen):
    """A line for the tray icon's tip while an important note has not been opened, else ""."""
    return "\n⚠ Important profile note: open it" if name_state(text, important, seen) == UNREAD else ""
