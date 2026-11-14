"""Windows single-instance guard; only acquired during bootstrap.launch().

A second launch does not touch the running copy's window itself. Calling
ShowWindow on a window Qt has hidden (closed to the tray) made Windows show
it without Qt painting it: a completely white editor. Instead the second
copy posts a private registered message; the running copy shows itself
through its own "restore from tray" path (window_chrome.restore_from_taskbar)
and comes to the front.
"""

import ctypes
from ctypes import wintypes

# === SINGLE WINDOWS INSTANCE ====================================
# Create the per-session Windows named mutex before Qt/HID startup.  The same
# identifier is used for .py/.pyw and onefile/standalone EXE launches, so a
# second copy cannot interfere with USB polling or configuration files.
_MUTEX_HANDLE = None

RESTORE_MESSAGE_NAME = "MudMan54.SpaceNavigatorMapper.Restore"
# v108.165: the taskbar's Exit SpaceNavigator Mapper (a launch with --exit).
EXIT_MESSAGE_NAME = "MudMan54.SpaceNavigatorMapper.Exit"
WINDOW_TITLES = ("SpaceNavigator Mapper", "SPNav Key Mapper")
_restore_message = None
_exit_message = None

# True when the last blocked launch found the running copy and asked it to show itself.
restored_existing = False


def _user32():
    """The user32 DLL, or None outside Windows."""
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
    user.RegisterWindowMessageW.restype = wintypes.UINT
    return user


def restore_message_id():
    """The registered "show yourself" message (0 when it cannot be registered)."""
    global _restore_message
    if _restore_message is None:
        try:
            _restore_message = int(_user32().RegisterWindowMessageW(RESTORE_MESSAGE_NAME) or 0)
        except (AttributeError, OSError):
            _restore_message = 0
    return _restore_message


def is_restore_message(message_id):
    """True for the message a second launch posts to restore the window."""
    wanted = restore_message_id()
    return bool(wanted) and int(message_id) == wanted


def exit_message_id():
    """The registered "exit" message (0 when it cannot be registered)."""
    global _exit_message
    if _exit_message is None:
        try:
            _exit_message = int(_user32().RegisterWindowMessageW(EXIT_MESSAGE_NAME) or 0)
        except (AttributeError, OSError):
            _exit_message = 0
    return _exit_message


def is_exit_message(message_id):
    """True for the message a launch with --exit posts to the running copy."""
    wanted = exit_message_id()
    return bool(wanted) and int(message_id) == wanted


# v108.168: the running copy marks its window with its version (a window
# property holding the number 108168 for v108.168), so a second start of
# another version can tell, instead of quietly showing the old one.
VERSION_PROP = "MudMan54.SpaceNavigatorMapper.Version"


def version_number(text):
    """108168 for "v108.168"; 0 when it cannot be read."""
    digits = str(text or "").strip().lstrip("vV").split(".")
    try:
        major, minor = int(digits[0]), int(digits[1]) if len(digits) > 1 else 0
    except (ValueError, IndexError):
        return 0
    return major * 1000 + minor if 0 <= minor < 1000 else 0


def version_text(number):
    """ "v108.168" for 108168; "" for 0 (a copy from before v108.168, which does not say)."""
    number = int(number or 0)
    return f"v{number // 1000}.{number % 1000:03d}" if number > 0 else ""


def _user32_for_windows():
    """user32 with the argument types the window search and messages need."""
    _user = _user32()
    _user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user.GetWindowTextLengthW.restype = ctypes.c_int
    _user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user.GetWindowTextW.restype = ctypes.c_int
    _user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user.GetClassNameW.restype = ctypes.c_int
    _user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
    _user.AllowSetForegroundWindow.restype = wintypes.BOOL
    _user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _user.PostMessageW.restype = wintypes.BOOL
    _user.GetPropW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
    _user.GetPropW.restype = wintypes.HANDLE
    return _user


def find_running_windows():
    """[(hwnd, pid, version number)] of the running Mapper's Qt windows (0: it does not say)."""
    found = []
    try:
        _user = _user32_for_windows()
        _callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        _user.EnumWindows.argtypes = [_callback_type, wintypes.LPARAM]
        _user.EnumWindows.restype = wintypes.BOOL

        @_callback_type
        def _locate(hwnd, _parameter):
            count = _user.GetWindowTextLengthW(hwnd)
            if count < 4:
                return True
            textbuf = ctypes.create_unicode_buffer(min(count + 1, 512))
            _user.GetWindowTextW(hwnd, textbuf, len(textbuf))
            if not textbuf.value.startswith(WINDOW_TITLES):
                return True
            # Only Qt windows: an Explorer window open on a folder named
            # "SpaceNavigator Mapper" has the same title.
            classbuf = ctypes.create_unicode_buffer(256)
            _user.GetClassNameW(hwnd, classbuf, len(classbuf))
            if not classbuf.value.startswith("Qt"):
                return True
            pid = wintypes.DWORD(0)
            _user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            version = int(_user.GetPropW(hwnd, VERSION_PROP) or 0)
            found.append((int(hwnd or 0), int(pid.value), version))
            return True

        _user.EnumWindows(_locate, 0)
    except Exception:
        return found
    return found


def running_version(windows):
    """The running copy's version number (0: from before v108.168, which does not say)."""
    return max((version for _hwnd, _pid, version in windows), default=0)


def post_to_windows(windows, message):
    """Post `message` to the running Mapper's windows; True when one took it."""
    posted = False
    try:
        _user = _user32_for_windows()
        for hwnd, pid, _version in windows:
            if pid:
                # Let the running copy come in front of this launch.
                _user.AllowSetForegroundWindow(pid)
            if _user.PostMessageW(hwnd, message, 0, 0):
                posted = True  # every Mapper window; only the main window answers
    except Exception:
        return posted
    return posted


def _restore_existing_window(message=None):
    """Ask the already-running mapper to show itself (or, with the exit message, to exit).

    Never launches another. Returns True when a Mapper window was found and
    the message was posted.
    """
    message = message or restore_message_id()
    if not message:
        return False
    return post_to_windows(find_running_windows(), message)


def accept_messages_from_lower(hwnd):
    """v108.174: let a start that is not administrator reach this window when it is.

    Windows drops messages from a program that is not running as administrator
    to one that is, unless the window allows them: then a second start (or the
    taskbar's Restore / Exit) could not show or close a copy running as
    administrator.
    """
    try:
        _user = _user32()
        _user.ChangeWindowMessageFilterEx.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.DWORD,
            ctypes.c_void_p,
        ]
        _user.ChangeWindowMessageFilterEx.restype = wintypes.BOOL
        msgflt_allow = 1
        for message in (restore_message_id(), exit_message_id()):
            if message:
                _user.ChangeWindowMessageFilterEx(int(hwnd), message, msgflt_allow, None)
        return True
    except Exception:
        return False


def mark_window_version(hwnd, version):
    """Mark the running copy's window with its version (see VERSION_PROP); True when done."""
    try:
        _user = _user32()
        _user.SetPropW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.HANDLE]
        _user.SetPropW.restype = wintypes.BOOL
        return bool(_user.SetPropW(int(hwnd), VERSION_PROP, version_number(version)))
    except Exception:
        return False


def unmark_window_version(hwnd):
    """Remove the version mark before the window goes, as Windows asks."""
    try:
        _user = _user32()
        _user.RemovePropW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
        _user.RemovePropW.restype = wintypes.HANDLE
        _user.RemovePropW(int(hwnd), VERSION_PROP)
    except Exception:
        pass


def acquire_single_instance(*, restore_existing=True, request="restore"):
    """Claim the single-instance mutex, or ask the running copy to come forward.

    `request` "exit" asks the running copy to exit instead (v108.165).
    """
    global _MUTEX_HANDLE, restored_existing
    _dll = ctypes.WinDLL("kernel32", use_last_error=True)
    _create = _dll.CreateMutexW
    _create.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    _create.restype = wintypes.HANDLE
    _handle = _create(None, False, "Local\\MudMan54.SpaceNavigatorMapper.SingleInstance")
    _error = ctypes.get_last_error()  # MUST read immediately after CreateMutexW
    if not _handle:
        raise OSError(_error, "Unable to create the SpaceNavigator Mapper instance lock")
    if _error == 183:  # ERROR_ALREADY_EXISTS: another copy owns the mutex
        restored_existing = False
        try:
            if restore_existing:
                message = exit_message_id() if request == "exit" else restore_message_id()
                restored_existing = _restore_existing_window(message)
        finally:
            _dll.CloseHandle.argtypes = [wintypes.HANDLE]
            _dll.CloseHandle(_handle)
        return False
    _MUTEX_HANDLE = _handle  # keep open for process lifetime
    return True


# Do not acquire the mutex as an import side effect.
# In v108.78, importing core.py could quietly sys.exit(0) here when a
# v108.77/v108.78 EXE was already running in the notification area.
# bootstrap.launch() acquires the same mutex explicitly and reports blocking
# launches instead of silently terminating.
