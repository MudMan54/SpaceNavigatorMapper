"""Windows SendInput/key-combination processing."""

import ctypes
from ctypes import wintypes

try:
    user32 = ctypes.windll.user32
except AttributeError:
    user32 = None  # Allow testing pure key helpers on non-Windows hosts.

# --- keyboard send helpers ---
if not hasattr(wintypes, "ULONG_PTR"):
    wintypes.ULONG_PTR = (
        ctypes.c_ulonglong
        if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_ulonglong)
        else ctypes.c_ulong
    )
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.ULONG_PTR),
    ]


class _INPUTunion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("uu",)
    _fields_ = [("type", wintypes.DWORD), ("uu", _INPUTunion)]


SC = {
    'a': 0x1E,
    'b': 0x30,
    'c': 0x2E,
    'd': 0x20,
    'e': 0x12,
    'f': 0x21,
    'g': 0x22,
    'h': 0x23,
    'i': 0x17,
    'j': 0x24,
    'k': 0x25,
    'l': 0x26,
    'm': 0x32,
    'n': 0x31,
    'o': 0x18,
    'p': 0x19,
    'q': 0x10,
    'r': 0x13,
    's': 0x1F,
    't': 0x14,
    'u': 0x16,
    'v': 0x2F,
    'w': 0x11,
    'x': 0x2D,
    'y': 0x15,
    'z': 0x2C,
    '1': 0x02,
    '2': 0x03,
    '3': 0x04,
    '4': 0x05,
    '5': 0x06,
    '6': 0x07,
    '7': 0x08,
    '8': 0x09,
    '9': 0x0A,
    '0': 0x0B,
    'f1': 0x3B,
    'f2': 0x3C,
    'f3': 0x3D,
    'f4': 0x3E,
    'f5': 0x3F,
    'f6': 0x40,
    'f7': 0x41,
    'f8': 0x42,
    'f9': 0x43,
    'f10': 0x44,
    'f11': 0x57,
    'f12': 0x58,
    'esc': 0x01,
    'tab': 0x0F,
    'backspace': 0x0E,
    'enter': 0x1C,
    'space': 0x39,
    'shift': 0x2A,
    'ctrl': 0x1D,
    'alt': 0x38,
    'left': 0x4B,
    'right': 0x4D,
    'up': 0x48,
    'down': 0x50,
    'home': 0x47,
    'end': 0x4F,
    'pageup': 0x49,
    'pagedown': 0x51,
    'delete': 0x53,
}
EXT_KEYS = {'left', 'right', 'up', 'down', 'home', 'end', 'pageup', 'pagedown', 'delete'}
_key_cache = {}


def key_to_scancode(token):
    """Scan code and extended flag for a key token."""
    if not token:
        return None, False
    t = str(token).strip().lower()
    if t in _key_cache:
        return _key_cache[t]
    if t in SC:
        res = (SC[t], t in EXT_KEYS)
        _key_cache[t] = res
        return res
    _key_cache[t] = (None, False)
    return None, False


_input_cache = {}


def _build_inputs_for_tokens(tokens, press=True):
    """Build the Windows INPUT records for pressing or releasing keys."""
    if not tokens:
        return None, 0
    # Cache by normalized tuple and press flag
    try:
        key = (tuple(tokens), bool(press))
        cache_hit = _input_cache.get(key)
        if cache_hit:
            arr, n = cache_hit
            if arr is not None and n > 0:
                return arr, n
    except Exception:
        pass

    valid = []
    for tok in tokens:
        sc, ext = key_to_scancode(tok)
        if sc is not None:
            valid.append((sc, ext))
    n = len(valid)
    if n == 0:
        return None, 0
    arr_type = INPUT * n
    arr = arr_type()
    flags_base = KEYEVENTF_SCANCODE | (0 if press else KEYEVENTF_KEYUP)
    for i, (sc, ext) in enumerate(valid):
        arr[i].type = INPUT_KEYBOARD
        arr[i].ki = KEYBDINPUT(0, sc, flags_base | (KEYEVENTF_EXTENDEDKEY if ext else 0), 0, 0)
    try:
        _input_cache[(tuple(tokens), bool(press))] = (arr, n)
    except Exception:
        pass
    return arr, n


def _send_inputs(arr, n):
    """Send INPUT records with SendInput; returns how many were sent."""
    if not arr or n <= 0 or user32 is None:
        return False
    try:
        return user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(arr[0])) == n
    except Exception:
        return False


# v108.174: how many key events have been sent (the Mapper sees from it that
# it sent keys while a program running as administrator was in front).
SENT_EVENTS = 0


def _send_inputs_with_fallback(seq, press=True):
    """Send INPUT records, one at a time if the batch is refused."""
    global SENT_EVENTS
    SENT_EVENTS += 1
    arr, n = _build_inputs_for_tokens(seq, press)
    if _send_inputs(arr, n):
        return True
    ok = True
    flags_base = KEYEVENTF_SCANCODE | (0 if press else KEYEVENTF_KEYUP)
    for t in seq:
        sc, ext = key_to_scancode(t)
        if sc is None:
            continue
        try:
            user32.keybd_event(0, ctypes.c_ubyte(sc), flags_base | (KEYEVENTF_EXTENDEDKEY if ext else 0), 0)
        except Exception:
            ok = False
    return ok


def is_modifier(tok):
    """True for the Ctrl, Shift and Alt tokens."""
    return (tok or "").lower() in ("ctrl", "shift", "alt")


def normalize_combo_tokens(tokens):
    """Split a combo into its modifier tokens and its other keys."""
    if tokens is None:
        return [], []
    if isinstance(tokens, str):
        tokens = [tokens]
    seq = [t for t in tokens if t]
    mods = [t for t in seq if is_modifier(t)]
    mains = [t for t in seq if not is_modifier(t)]
    return mods, mains


def send_combo(tokens, down=True, status_callback=None):
    """Press (modifiers first) or release (main keys first) a key combination."""
    mods, mains = normalize_combo_tokens(tokens)
    if down:
        press_seq = mods + mains
        ok = _send_inputs_with_fallback(press_seq, True)
    else:
        release_seq = list(reversed(mains)) + list(reversed(mods))
        ok = _send_inputs_with_fallback(release_seq, False)
    if status_callback:
        label = (
            "+".join([*(m.upper() for m in mods), *(k.upper() for k in mains)]) if (mods or mains) else "None"
        )
        status_callback(f"Sent {label} {'down' if down else 'up'}")
    return ok


def combo_to_text(tokens):
    """Readable label for a key combination, such as Ctrl+S."""
    if not tokens:
        return ""
    if isinstance(tokens, str):
        return tokens.upper()
    return "+".join(t.upper() for t in tokens if t)
