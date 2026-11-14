"""The taskbar button's right-click menu (its jump list), v108.165.

Windows puts the program's name at the top of that menu, and it starts
another copy of the program; the Mapper allows one copy, so that launch only
reported that it was already running. Windows always shows that item, but
the window can say what it is called and what it starts (its "relaunch"
properties). Here it is called **Restore SpaceNavigator Mapper** and starts
the Mapper with --restore: the running copy is shown (from the tray, the
taskbar or behind other windows) and the launch ends quietly; with none
running, the Mapper starts.

A task **Exit SpaceNavigator Mapper** is added to the menu: it starts the
Mapper with --exit, which asks the running copy to exit (as Options > Exit
does) and starts nothing.

Both use the Windows Shell's COM interfaces through ctypes. Anything that
fails is noted in startup.log and changes nothing else.
"""

import ctypes
import subprocess
import sys
import uuid

APP_ID = "MudMan54.SpaceNavigatorMapper"  # the process's AppUserModelID (app.py)
RESTORE_TITLE = "Restore SpaceNavigator Mapper"
EXIT_TITLE = "Exit SpaceNavigator Mapper"
RESTORE_ARG, EXIT_ARG = "--restore", "--exit"  # bootstrap.RESTORE_ARG, EXIT_ARG

VT_EMPTY, VT_LPWSTR = 0, 31
CLSCTX_INPROC_SERVER = 1
COINIT_APARTMENTTHREADED = 2

# Interfaces and classes (shobjidl.h, propsys.h) and their method slots.
IID_IPropertyStore = "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"
CLSID_DestinationList = "{77F10CF0-3DB5-4966-B520-B7C54FD35ED6}"
IID_ICustomDestinationList = "{6332DEBF-87B5-4670-90C0-5E57B408A49E}"
CLSID_EnumerableObjectCollection = "{2D3468C1-36A7-43B6-AC24-D3F02FD9607A}"
IID_IObjectCollection = "{5632B1A4-E38A-400A-928A-D4CD63230295}"
IID_IObjectArray = "{92CA9DCD-5622-4BBA-A805-5E9F541BD8C9}"
CLSID_ShellLink = "{00021401-0000-0000-C000-000000000046}"
IID_IShellLinkW = "{000214F9-0000-0000-C000-000000000046}"
QUERY_INTERFACE, RELEASE = 0, 2
STORE_SET_VALUE, STORE_COMMIT = 6, 7
LIST_SET_APP_ID, LIST_BEGIN, LIST_ADD_USER_TASKS, LIST_COMMIT, LIST_ABORT = 3, 4, 7, 8, 11
COLLECTION_ADD_OBJECT = 5
LINK_SET_DESCRIPTION, LINK_SET_WORKING_DIRECTORY, LINK_SET_ARGUMENTS = 7, 9, 11
LINK_SET_ICON_LOCATION, LINK_SET_PATH = 17, 20

APP_MODEL_KEYS = "{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"  # System.AppUserModel.*
KEY_ID, KEY_RELAUNCH_COMMAND, KEY_RELAUNCH_ICON, KEY_RELAUNCH_NAME = 5, 2, 3, 4
TITLE_KEY = ("{F29F85E0-4FF9-1068-AB91-08002B27B3D9}", 2)  # System.Title


def _note(message):
    """Write a line to the start-up log."""
    try:
        from ..bootstrap import note

        note(message)
    except Exception:
        pass


def taskbar_commands():
    """{"restore": [...], "exit": [...]}: the command lines the taskbar's items start."""
    from ..restart import launch_command

    return {"restore": launch_command(RESTORE_ARG), "exit": launch_command(EXIT_ARG)}


def icon_location(program):
    """The icon for the items: the EXE's own, else the Mapper's .ico file (source runs)."""
    if str(program).lower().endswith(".exe") and not str(program).lower().endswith(
        ("python.exe", "pythonw.exe")
    ):
        return str(program), 0
    from ..paths import RESOURCE_DIR

    return f"{RESOURCE_DIR}\\SpaceNavigatorMapper.ico", 0


def relaunch_properties(commands=None):
    """[(key, text)]: what the window tells the taskbar about its program item."""
    commands = commands or taskbar_commands()
    restore = commands["restore"]
    icon, index = icon_location(restore[0])
    return [
        (KEY_ID, APP_ID),
        (KEY_RELAUNCH_COMMAND, subprocess.list2cmdline(restore)),
        (KEY_RELAUNCH_NAME, RESTORE_TITLE),
        (KEY_RELAUNCH_ICON, f"{icon},{index}"),
    ]


def user_tasks(commands=None):
    """[(title, program, arguments, description)]: the menu's Tasks."""
    commands = commands or taskbar_commands()
    program, *arguments = commands["exit"]
    return [
        (EXIT_TITLE, program, subprocess.list2cmdline(arguments), "Stop the Mapper: no more keys are sent.")
    ]


# --- COM through ctypes -------------------------------------------------------
class _GUID(ctypes.Structure):
    _fields_ = [
        ("data1", ctypes.c_uint32),  # DWORD: c_ulong is 8 bytes outside Windows
        ("data2", ctypes.c_ushort),
        ("data3", ctypes.c_ushort),
        ("data4", ctypes.c_ubyte * 8),
    ]


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_uint32)]


class _PROPVARIANT(ctypes.Structure):
    # vt, three reserved words, then the value (a pointer here) in a union of
    # two pointers' size: 16 bytes in 32-bit Windows, 24 in 64-bit.
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("reserved1", ctypes.c_ushort),
        ("reserved2", ctypes.c_ushort),
        ("reserved3", ctypes.c_ushort),
        ("pointer", ctypes.c_void_p),
        ("extra", ctypes.c_void_p),
    ]


def _guid(text):
    """A GUID structure from its "{...}" text."""
    return _GUID.from_buffer_copy(uuid.UUID(text).bytes_le)


def _key(fmtid, pid):
    """A PROPERTYKEY: a property set's GUID and the property's number in it."""
    return _PROPERTYKEY(_guid(fmtid), pid)


def _call(pointer, index, argtypes, *args, restype=ctypes.c_long):
    """Call method `index` of the COM interface at `pointer`; raise OSError on a failed HRESULT."""
    if not pointer or not getattr(pointer, "value", pointer):
        raise OSError("no COM interface")
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    method = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtable[index])
    result = method(pointer, *args)
    if restype is ctypes.c_long and result < 0:
        raise OSError(f"COM method {index} failed: 0x{result & 0xFFFFFFFF:08X}")
    return result


def _release(pointer):
    """IUnknown::Release, for a pointer that holds an interface."""
    if pointer is not None and pointer.value:
        _call(pointer, RELEASE, [], restype=ctypes.c_ulong)


def _create(clsid, iid):
    """CoCreateInstance: a new object of class `clsid`, as interface `iid`."""
    ole32 = ctypes.WinDLL("ole32")
    out = ctypes.c_void_p()
    ole32.CoCreateInstance.restype = ctypes.c_long
    result = ole32.CoCreateInstance(
        ctypes.byref(_guid(clsid)), None, CLSCTX_INPROC_SERVER, ctypes.byref(_guid(iid)), ctypes.byref(out)
    )
    if result < 0 or not out.value:
        raise OSError(f"CoCreateInstance {clsid} failed: 0x{result & 0xFFFFFFFF:08X}")
    return out


def _query(pointer, iid):
    """IUnknown::QueryInterface for `iid`."""
    out = ctypes.c_void_p()
    _call(
        pointer,
        QUERY_INTERFACE,
        [ctypes.c_void_p, ctypes.c_void_p],
        ctypes.byref(_guid(iid)),
        ctypes.byref(out),
    )
    if not out.value:
        raise OSError(f"QueryInterface {iid} gave nothing")
    return out


def _set_string(store, key, text):
    """IPropertyStore::SetValue with a string (None: remove it), then Commit."""
    value = _PROPVARIANT()
    keep = None
    if text is None:
        value.vt = VT_EMPTY
    else:
        keep = ctypes.create_unicode_buffer(str(text))  # SetValue copies it
        value.vt = VT_LPWSTR
        value.pointer = ctypes.cast(keep, ctypes.c_void_p).value
    argtypes = [ctypes.POINTER(_PROPERTYKEY), ctypes.POINTER(_PROPVARIANT)]
    _call(store, STORE_SET_VALUE, argtypes, ctypes.byref(key), ctypes.byref(value))
    _call(store, STORE_COMMIT, [])
    del keep


class _Com:
    """CoInitializeEx for the calls made inside it (balanced when it was needed)."""

    def __enter__(self):
        """Initialize COM on this thread (Qt usually has already)."""
        ole32 = ctypes.WinDLL("ole32")
        ole32.CoInitializeEx.restype = ctypes.c_long
        self.result = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
        return self

    def __exit__(self, *exc):
        """Balance a CoInitializeEx that succeeded."""
        if self.result in (0, 1):  # S_OK, S_FALSE: once per successful call
            ctypes.WinDLL("ole32").CoUninitialize()
        return False


def _window_store(hwnd):
    """The window's property store (SHGetPropertyStoreForWindow)."""
    shell32 = ctypes.WinDLL("shell32")
    store = ctypes.c_void_p()
    shell32.SHGetPropertyStoreForWindow.restype = ctypes.c_long
    result = shell32.SHGetPropertyStoreForWindow(
        ctypes.c_void_p(int(hwnd)), ctypes.byref(_guid(IID_IPropertyStore)), ctypes.byref(store)
    )
    if result < 0 or not store.value:
        raise OSError(f"SHGetPropertyStoreForWindow failed: 0x{result & 0xFFFFFFFF:08X}")
    return store


def set_window_relaunch(hwnd, properties=None, clear=False):
    """Name the taskbar's program item Restore SpaceNavigator Mapper (clear=True: remove it)."""
    properties = properties or relaunch_properties()
    with _Com():
        store = _window_store(hwnd)
        try:
            # The ID first, as Windows reads the relaunch properties under it.
            for pid, text in properties if not clear else reversed(properties):
                _set_string(store, _key(APP_MODEL_KEYS, pid), None if clear else text)
        finally:
            _release(store)


def set_jump_list(tasks=None):
    """Put Exit SpaceNavigator Mapper in the taskbar menu's Tasks."""
    tasks = tasks or user_tasks()
    with _Com():
        destinations = _create(CLSID_DestinationList, IID_ICustomDestinationList)
        collection = array = removed = None
        begun = False
        try:
            _call(destinations, LIST_SET_APP_ID, [ctypes.c_wchar_p], APP_ID)
            slots = ctypes.c_uint()
            removed = ctypes.c_void_p()
            argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            _call(
                destinations,
                LIST_BEGIN,
                argtypes,
                ctypes.byref(slots),
                ctypes.byref(_guid(IID_IObjectArray)),
                ctypes.byref(removed),
            )
            begun = True
            collection = _create(CLSID_EnumerableObjectCollection, IID_IObjectCollection)
            for title, program, arguments, description in tasks:
                link = _create(CLSID_ShellLink, IID_IShellLinkW)
                try:
                    _call(link, LINK_SET_PATH, [ctypes.c_wchar_p], str(program))
                    _call(link, LINK_SET_ARGUMENTS, [ctypes.c_wchar_p], arguments)
                    _call(link, LINK_SET_DESCRIPTION, [ctypes.c_wchar_p], description)
                    from ..paths import APP_DIR

                    _call(link, LINK_SET_WORKING_DIRECTORY, [ctypes.c_wchar_p], str(APP_DIR))
                    icon, index = icon_location(program)
                    _call(link, LINK_SET_ICON_LOCATION, [ctypes.c_wchar_p, ctypes.c_int], icon, index)
                    store = _query(link, IID_IPropertyStore)
                    try:
                        _set_string(store, _key(*TITLE_KEY), title)
                    finally:
                        _release(store)
                    _call(collection, COLLECTION_ADD_OBJECT, [ctypes.c_void_p], link)
                finally:
                    _release(link)
            array = _query(collection, IID_IObjectArray)
            _call(destinations, LIST_ADD_USER_TASKS, [ctypes.c_void_p], array)
            _call(destinations, LIST_COMMIT, [])
            begun = False
        finally:
            if begun:
                try:
                    _call(destinations, LIST_ABORT, [])
                except OSError:
                    pass
            for pointer in (array, collection, removed, destinations):
                try:
                    _release(pointer)
                except OSError:
                    pass


def install_taskbar_menu(win):
    """Restore and Exit SpaceNavigator Mapper in the taskbar button's right-click menu."""
    if sys.platform != "win32":
        return False
    done = True
    try:
        commands = taskbar_commands()
    except (OSError, ValueError) as exc:
        _note(f"Taskbar menu unavailable: {exc}")
        return False
    try:
        win._taskbar_hwnd = int(win.winId())
        set_window_relaunch(win._taskbar_hwnd, relaunch_properties(commands))
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        done = False
        _note(f"Taskbar menu: could not name the program item: {exc}")
    try:
        set_jump_list(user_tasks(commands))
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        done = False
        _note(f"Taskbar menu: could not add Exit SpaceNavigator Mapper: {exc}")
    if done:
        _note("Taskbar menu: Restore SpaceNavigator Mapper and Exit SpaceNavigator Mapper.")
    return done


def remove_window_relaunch(win):
    """At exit: the window's relaunch properties are removed, as Windows asks."""
    hwnd = getattr(win, "_taskbar_hwnd", None)
    if not hwnd or sys.platform != "win32":
        return
    try:
        set_window_relaunch(hwnd, clear=True)
    except (OSError, AttributeError, TypeError, ValueError):
        pass
