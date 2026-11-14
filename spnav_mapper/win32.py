"""Win32 window, process and program-name helpers (no Qt).

One implementation of each lookup the Mapper needs: visible top-level
windows, the process and EXE behind a window, the foreground window, and a
friendly program name from an EXE's version resource. The target filter that
hides consoles, system programs and the Mapper itself also lives here.
"""

import ctypes
import os
import unicodedata
from ctypes import wintypes
from fnmatch import fnmatchcase

try:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
except AttributeError:  # not Windows: pure helpers stay importable for tests
    user32 = kernel32 = None

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
EnumWindowsProc = (
    ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    if hasattr(ctypes, "WINFUNCTYPE")
    else None
)

if user32 is not None:
    user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


# --------------------------------------------------------------------------
# Target filter. Edit these lists to hide more programs from the target list.
# Wildcards '*' and '?' are supported (fnmatch rules), case-insensitive.
# --------------------------------------------------------------------------
OMIT_EXE_PATTERNS = [
    'cmd.exe',
    'conhost.exe',
    'powershell.exe',
    'pwsh.exe',
    'nahimic3.exe',
    'dopus.exe',
    'brave.exe',
    'windowsterminal.exe',
    'systemsettings.exe',
    'systemsettingsbroker.exe',
    'taskmgr.exe',
]

OMIT_TITLE_PATTERNS = [
    'command prompt*',
    'windows powershell*',
    'powershell*',
    'windows terminal*',
    'settings*',
]

OMIT_CLASS_PATTERNS = [
    'ConsoleWindowClass',
]

# Programs whose full path starts with one of these (case-insensitive) are
# hidden. By default that is everything under %WINDIR% (e.g. C:\Windows\).
OMIT_PATH_PREFIXES = [(os.environ.get('WINDIR') or r'C:\Windows').lower()]


def matches_any(name, patterns):
    """True when text matches any wildcard pattern (case-insensitive)."""
    text = (name or '').lower()
    return any(fnmatchcase(text, str(p).lower()) for p in (patterns or []))


def is_omitted_target(title, exe_path, class_name):
    """True when a window must not be offered as a mapping target."""
    low = (exe_path or '').lower()
    if any(low.startswith(prefix) for prefix in OMIT_PATH_PREFIXES):
        return True
    if matches_any(class_name, OMIT_CLASS_PATTERNS):
        return True
    if matches_any(os.path.basename(exe_path or '').lower(), OMIT_EXE_PATTERNS):
        return True
    if matches_any(title or '', OMIT_TITLE_PATTERNS):
        return True
    lowered = (title or '').lower()
    return 'spnav' in lowered and 'mapper' in lowered  # the Mapper's own window


# --------------------------------------------------------------------------
# Windows and processes
# --------------------------------------------------------------------------
def window_title(hwnd):
    """A window's title text."""
    try:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except (OSError, AttributeError, ctypes.ArgumentError):
        return ""


def window_class(hwnd):
    """A window's class name."""
    try:
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        return buf.value
    except (OSError, AttributeError, ctypes.ArgumentError):
        return ''


def window_pid(hwnd):
    """The process id that owns a window."""
    try:
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)
    except (OSError, AttributeError, ctypes.ArgumentError):
        return 0


def process_image_path(pid):
    """Full EXE path of a process, or "" when it cannot be opened."""
    if not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        try:
            psapi = ctypes.WinDLL('psapi')
            if psapi.GetModuleFileNameExW(handle, None, buf, len(buf)):
                return buf.value
        except OSError:
            pass
        return ""
    finally:
        kernel32.CloseHandle(handle)


# --- Programs running as administrator (v108.174) -----------------------------
# Windows does not let a program that is not running as administrator send
# keys to one that is (User Interface Privilege Isolation): SendInput reports
# nothing, the keys just do not arrive.
TOKEN_QUERY = 0x0008
TOKEN_ELEVATION_CLASS = 20  # TokenElevation
ERROR_ACCESS_DENIED = 5


def _token_elevation(process_handle):
    """(True / False, 0) for a process's token, or (None, the Windows error) when it cannot be read."""
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process_handle, TOKEN_QUERY, ctypes.byref(token)):
        return None, int(ctypes.get_last_error() or 0)
    try:
        elevated, size = wintypes.DWORD(0), wintypes.DWORD(0)
        ok = advapi32.GetTokenInformation(
            token, TOKEN_ELEVATION_CLASS, ctypes.byref(elevated), ctypes.sizeof(elevated), ctypes.byref(size)
        )
        return (bool(elevated.value) if ok else None), 0
    finally:
        kernel.CloseHandle(token)


def mapper_elevated():
    """True when the Mapper itself runs as administrator (None: it cannot tell)."""
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        elevated, _error = _token_elevation(kernel.GetCurrentProcess())
        return elevated
    except (OSError, AttributeError, ValueError, ctypes.ArgumentError):
        return None


def process_elevated(pid):
    """True when process `pid` runs as administrator, False when not, None when it cannot tell.

    A process whose token this copy may not read is a program running as
    administrator (or a part of Windows): either way it gets no keys from a
    copy that is not.
    """
    if not pid:
        return None
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return True if int(ctypes.get_last_error() or 0) == ERROR_ACCESS_DENIED else None
        try:
            elevated, error = _token_elevation(handle)
        finally:
            kernel.CloseHandle(handle)
        if elevated is None and error == ERROR_ACCESS_DENIED:
            return True
        return elevated
    except (OSError, AttributeError, ValueError, ctypes.ArgumentError):
        return None


def window_elevated(hwnd):
    """process_elevated() for the program that owns window `hwnd`."""
    return process_elevated(window_pid(hwnd))


def window_exe_path(hwnd):
    """The executable path of the process that owns a window."""
    try:
        return process_image_path(window_pid(hwnd))
    except (OSError, AttributeError, ctypes.ArgumentError):
        return ''


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


MONITOR_DEFAULTTONEAREST = 2
if user32 is not None:
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL


def _window_monitor(hwnd):
    """(device name, work-area left, work-area top) of the window's monitor, or None.

    Physical pixels. For a minimized window Windows answers with the monitor
    it will be restored to.
    """
    if user32 is None or not hwnd:
        return None
    try:
        hmon = user32.MonitorFromWindow(int(hwnd), MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return None
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)) or not info.szDevice:
            return None
        return str(info.szDevice), int(info.rcWork.left), int(info.rcWork.top)
    except (OSError, ValueError, TypeError, ctypes.ArgumentError):
        return None


def _private_user32():
    """A separate user32 instance: argtypes set here do not affect other callers."""
    return ctypes.WinDLL("user32")


def allow_foreground(pid):
    """Let process `pid` bring its window to the front (we must be in front now)."""
    try:
        user = _private_user32()
        user.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
        user.AllowSetForegroundWindow.restype = wintypes.BOOL
        return bool(user.AllowSetForegroundWindow(int(pid)))
    except (AttributeError, OSError, ValueError, TypeError, ctypes.ArgumentError):
        return False


HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010


def bring_to_front(hwnd):
    """Put the window in front of all other windows and give it the focus.

    Briefly topmost, then not: that raises it above every other window even
    if Windows refuses the focus. The window is neither moved nor resized.
    True when it became the foreground window.
    """
    if not hwnd:
        return False
    try:
        user = _private_user32()
        user.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user.SetWindowPos.restype = wintypes.BOOL
        user.BringWindowToTop.argtypes = [wintypes.HWND]
        user.SetForegroundWindow.argtypes = [wintypes.HWND]
        user.SetForegroundWindow.restype = wintypes.BOOL
        flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
        user.SetWindowPos(int(hwnd), HWND_TOPMOST, 0, 0, 0, 0, flags)
        user.SetWindowPos(int(hwnd), HWND_NOTOPMOST, 0, 0, 0, 0, flags)
        user.BringWindowToTop(int(hwnd))
        return bool(user.SetForegroundWindow(int(hwnd)))
    except (AttributeError, OSError, ValueError, TypeError, ctypes.ArgumentError):
        return False


def window_monitor_name(hwnd):
    """Device name (such as DISPLAY2) of the monitor Windows says the window is on.

    Qt's own answer can be wrong when monitors use different scale factors,
    so window placement asks Windows.
    """
    found = _window_monitor(hwnd)
    return found[0] if found else ""


def client_offset_on_monitor(hwnd):
    """(device name, dx, dy): the window's client area relative to its monitor's work area.

    Physical pixels, straight from Windows, or None. Unlike Qt's logical
    coordinates this cannot point into the gap Qt leaves between monitors
    that use different scale factors.
    """
    found = _window_monitor(hwnd)
    if found is None:
        return None
    point = wintypes.POINT(0, 0)
    try:
        if not user32.ClientToScreen(int(hwnd), ctypes.byref(point)):
            return None
    except (OSError, ValueError, TypeError, ctypes.ArgumentError):
        return None
    name, left, top = found
    return name, int(point.x) - left, int(point.y) - top


def normalized_path(p):
    """A real, normalized path for comparison (case and separators)."""
    return os.path.normcase(os.path.normpath(os.path.realpath(p or "")))


def list_windows():
    """[(hwnd, title)] for visible top-level windows that have a title."""
    if user32 is None:
        return []
    found = []

    @EnumWindowsProc
    def visit(hwnd, _lparam):
        try:
            if user32.IsWindowVisible(hwnd):
                title = window_title(hwnd)
                if title:
                    found.append((hwnd, title))
        except (OSError, ctypes.ArgumentError):
            pass
        return True

    user32.EnumWindows(visit, 0)
    return found


def visible_windows():
    """[hwnd] for every visible top-level window, titled or not."""
    found = []

    @EnumWindowsProc
    def visit(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    return found


def foreground_window():
    """The window in front."""
    try:
        return user32.GetForegroundWindow()
    except (OSError, AttributeError):
        return None


def current_process_id():
    """This process's id."""
    try:
        return kernel32.GetCurrentProcessId()
    except (OSError, AttributeError):
        return 0


def is_own_window(hwnd):
    """True when `hwnd` belongs to this process: the Mapper's own window, a dialog or a menu."""
    if user32 is None or not hwnd:
        return False
    mine = current_process_id()
    return bool(mine) and window_pid(hwnd) == mine


def same_process(hwnd1, hwnd2):
    """True when two windows belong to the same process."""
    if user32 is None or not hwnd1 or not hwnd2:
        return False
    pid1, pid2 = window_pid(hwnd1), window_pid(hwnd2)
    return pid1 == pid2 and pid1 != 0


def format_target_item(hwnd, title):
    """'<title> — <exe> — <fullpath>', at most 65 characters."""
    title_clean = (title or "").strip().replace("\n", " ")
    path = window_exe_path(hwnd) or ""
    exe = os.path.basename(path) if path else "App"
    parts = [p for p in (title_clean, exe, path) if p]
    label = " — ".join(parts) if parts else exe
    max_chars = 65
    return (label[: max_chars - 3] + "...") if len(label) > max_chars else label


# --------------------------------------------------------------------------
# Friendly program names from the EXE version resource
# --------------------------------------------------------------------------
def clean_text(s):
    """Text with invisible format characters removed, trimmed."""
    if not s:
        return ""
    return "".join(ch for ch in str(s) if unicodedata.category(ch) != "Cf").strip()


def version_info_strings(exe_path, keys=("FileDescription", "ProductName", "InternalName")):
    """Version-resource strings (product, description) of an executable."""
    out = {k: [] for k in keys}
    try:
        if not exe_path:
            return out
        from ctypes import (
            POINTER,
            byref,
            c_ushort,
            c_wchar_p,
            cast,
            create_string_buffer,
            windll,
            wintypes,
        )

        GetFileVersionInfoSizeW = windll.version.GetFileVersionInfoSizeW
        GetFileVersionInfoW = windll.version.GetFileVersionInfoW
        VerQueryValueW = windll.version.VerQueryValueW
        dummy = wintypes.DWORD(0)
        size = GetFileVersionInfoSizeW(wintypes.LPCWSTR(exe_path), byref(dummy))
        if not size:
            return out
        res = create_string_buffer(size)
        if not GetFileVersionInfoW(wintypes.LPCWSTR(exe_path), 0, size, res):
            return out
        tried = set()
        langs = []
        lptr = wintypes.LPVOID()
        ulen = wintypes.UINT(0)
        if (
            VerQueryValueW(res, wintypes.LPCWSTR(r"\VarFileInfo\Translation"), byref(lptr), byref(ulen))
            and ulen.value >= 4
        ):
            arr = cast(lptr.value, POINTER(c_ushort))
            n = int(ulen.value // 4)
            for i in range(n):
                langs.append((arr[2 * i], arr[2 * i + 1]))
        langs = langs + [(0x0409, cp) for cp in (0x04E4, 0x04B0, 0x0000, 0x04E3)]
        seen = set()
        langs = [x for x in langs if (x not in seen and not seen.add(x))]
        cps_try = (0x04E4, 0x04B0, 0x0000, 0x04E3)
        for lang, _cp in langs:
            for cp2 in cps_try:
                tag = f"{lang:04x}{cp2:04x}"
                if tag in tried:
                    continue
                tried.add(tag)
                for key in keys:
                    block = f"\\StringFileInfo\\{tag}\\{key}"
                    wbuf = c_wchar_p()
                    ulen2 = wintypes.UINT(0)
                    if VerQueryValueW(res, wintypes.LPCWSTR(block), byref(wbuf), byref(ulen2)) and wbuf.value:
                        out[key].append(clean_text(wbuf.value))
        return out
    except Exception:
        return out


# Per-exe overrides if a vendor ships generic descriptions
NAME_OVERRIDES = {
    # Example: prefer ProductName for COD
    # 'sp24-cod.exe': 'Call of Duty®: Black Ops 6',
}


def best_program_name(exe_path):
    """A readable program name from version info or the file name."""
    try:
        base = os.path.basename(exe_path or "").lower()
        if base in NAME_OVERRIDES:
            return NAME_OVERRIDES[base]
        vs = version_info_strings(exe_path, keys=("FileDescription", "ProductName", "InternalName"))
        fds = [s for s in vs.get("FileDescription", []) if s]
        pns = [s for s in vs.get("ProductName", []) if s]
        ins = [s for s in vs.get("InternalName", []) if s]

        def detailed(s):
            s2 = (s or "").lower()
            return (
                (":" in s2)
                or any(ch.isdigit() for ch in s2)
                or any(
                    w in s2
                    for w in ("edition", "ultimate", "deluxe", "black ops", "beta", "alpha", "remastered")
                )
            )

        # Prefer a detailed FileDescription
        for s in fds:
            if detailed(s):
                return s
        # Otherwise, longest among FileDescription and ProductName
        cand = fds + pns
        if cand:
            return max(cand, key=len)
        if ins:
            return ins[0]
        return clean_text(base)
    except Exception:
        return clean_text(os.path.basename(exe_path or ""))
