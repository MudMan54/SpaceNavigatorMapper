"""Per-monitor sizing for monitors with different resolutions or Windows scaling.

The Mapper bakes its widget sizes (S()/Sf()) once, for one "home" monitor.
Before v108.116 that made the window the wrong size on any other monitor,
and dragging the window across did not re-size it.

Before QApplication exists, this module measures every monitor with Win32 and
hands Qt one scale factor per screen (QT_SCREEN_SCALE_FACTORS).  Qt then draws
the same window at the size it would have had if it had been built for that
monitor, and re-draws it whenever the window moves to another screen.  The
home monitor keeps exactly its Windows scaling factor, so it looks as before.

Opt out with SPNAV_PER_MONITOR_SCALE=0.  A QT_SCREEN_SCALE_FACTORS value set
by the user is always respected.
"""

import json
import os

ENV_DISABLE = "SPNAV_PER_MONITOR_SCALE"
ENV_MARK = "SPNAV_AUTO_SCREEN_FACTORS"  # value we wrote, so restarts recompute
QT_ENV = "QT_SCREEN_SCALE_FACTORS"
MIN_RELATIVE, MAX_RELATIVE = 0.35, 3.0

HOME_NAME = ""
INFO = {"active": False, "reason": "not configured", "monitors": []}
PER_MONITOR, SHARED_LAYOUT = "per-monitor factors", "monitors share one layout size"
# v108.163: a monitor drawn with a factor more than 2% off is drawn at the wrong size.
STALE_SHARE = 0.02


def native_monitors():
    """[{name, dpi, primary, width, height, work_w, work_h}] in physical pixels (Windows only)."""
    import ctypes
    from ctypes import wintypes

    # Private DLL instances: argtypes here never affect other user32 callers.
    user32 = ctypes.WinDLL("user32")
    try:
        shcore = ctypes.WinDLL("shcore")
    except OSError:
        shcore = None

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
    )
    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, MonitorEnumProc, wintypes.LPARAM]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    if shcore is not None:
        shcore.GetDpiForMonitor.argtypes = [
            wintypes.HMONITOR,
            ctypes.c_int,
            ctypes.POINTER(wintypes.UINT),
            ctypes.POINTER(wintypes.UINT),
        ]
        shcore.GetDpiForMonitor.restype = ctypes.c_long

    found = []

    def visit(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            return True
        dpi = 96
        if shcore is not None:
            dpi_x, dpi_y = wintypes.UINT(), wintypes.UINT()
            # MDT_EFFECTIVE_DPI (0): the Windows "Scale" setting of this monitor.
            if shcore.GetDpiForMonitor(hmonitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                dpi = int(dpi_x.value) or 96
        work, whole = info.rcWork, info.rcMonitor
        found.append(
            {
                "name": info.szDevice,
                "dpi": dpi,
                "primary": bool(info.dwFlags & 1),
                "width": int(whole.right - whole.left),
                "height": int(whole.bottom - whole.top),
                "work_w": int(work.right - work.left),
                "work_h": int(work.bottom - work.top),
            }
        )
        return True

    callback = MonitorEnumProc(visit)  # keep a reference during the call
    user32.EnumDisplayMonitors(None, None, callback, 0)
    return found


def saved_home_name(config_dir):
    """Windows device name of the monitor the Mapper was last used on."""
    try:
        from .scaling import saved_view_record

        with open(os.path.join(config_dir, "window_state.json"), encoding="utf-8") as stream:
            saved = json.load(stream)
        # Display > Positions Saved: the selected monitor is where the Mapper opens.
        try:
            with open(os.path.join(config_dir, "ui_preferences.json"), encoding="utf-8") as stream:
                chosen = json.load(stream).get("positions_saved_monitor")
            if isinstance(chosen, dict) and chosen.get("screen_name"):
                return str(chosen["screen_name"])
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        monitor = saved.get("monitor") if isinstance(saved, dict) else None
        if isinstance(monitor, dict) and monitor.get("screen_name"):
            return str(monitor["screen_name"])
        return str(saved_view_record(saved).get("screen_name", "") or "")
    except (OSError, ValueError, TypeError, AttributeError):
        return ""


def monitor_auto_scale(monitor):
    """Same arithmetic Qt-side startup uses, from physical Win32 values.

    With PassThrough rounding Qt reports logical DPI 96, a device pixel ratio
    of dpi/96, and an available geometry of work-area / ratio.
    """
    from .scaling import scale_from_metrics

    ratio = max(0.5, float(monitor.get("dpi", 96) or 96) / 96.0)
    scale, _parts = scale_from_metrics(
        round(monitor["work_w"] / ratio), round(monitor["work_h"] / ratio), 96.0, ratio
    )
    return scale


def monitor_fit(monitor):
    """How much smaller the editor is drawn on this monitor (v108.151; 1.0: not smaller)."""
    from .scaling import fit_factor

    ratio = max(0.5, float(monitor.get("dpi", 96) or 96) / 96.0)
    return fit_factor(round(monitor["work_w"] / ratio), round(monitor["work_h"] / ratio))


def monitor_layout_scale(monitor, ui_factor):
    """The layout scale the editor would be built with on this monitor (Display % and fit included)."""
    from .scaling import effective_scale

    return effective_scale(monitor_auto_scale(monitor), ui_factor * monitor_fit(monitor))


def screen_factors(monitors, home_name, ui_factor):
    """{name: Qt factor}, plus the home monitor that was used.

    A monitor's factor is its own Windows scaling times how much larger or
    smaller the Mapper's layout would be there than on the home monitor.
    """
    if not monitors:
        return {}, ""
    layout = {m["name"]: monitor_layout_scale(m, ui_factor) for m in monitors}

    def factors_for(home):
        base = layout[home["name"]]
        result = {}
        for monitor in monitors:
            native = max(0.5, float(monitor.get("dpi", 96) or 96) / 96.0)
            relative = layout[monitor["name"]] / base if base > 0 else 1.0
            relative = max(MIN_RELATIVE, min(MAX_RELATIVE, relative))
            monitor["relative"] = round(relative, 4)
            result[monitor["name"]] = round(native * relative, 4)
        return result

    home = next((m for m in monitors if m["name"] == home_name), None)
    if home is None:
        home = next((m for m in monitors if m["primary"]), monitors[0])
    factors = factors_for(home)
    if min(factors.values()) < 0.999:
        # Qt 5 can lose 1-px borders below a factor of 1. Build the layout for
        # the monitor with the smallest one and let Qt enlarge it elsewhere:
        # every monitor still gets the same physical size.
        home = min(monitors, key=lambda m: layout[m["name"]])
        factors = factors_for(home)
    return factors, home["name"]


def format_factors(factors):
    """Monitor scale factors as one text line for the log."""
    # Qt 5.14+: "name=factor;name=factor"; names are like \\.\DISPLAY1.
    return ";".join(f"{name}={value:.4f}" for name, value in sorted(factors.items()))


def _set_pass_through_rounding():
    """Use 125%/150%/175% as-is; Qt 5 otherwise rounds them to 100%/200%."""
    try:
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QGuiApplication

        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        return True
    except (ImportError, AttributeError, RuntimeError, TypeError):
        return False


def configure_before_qapplication(config_dir, ui_factor, note=print):
    """Call after the DPI-awareness calls and before QApplication()."""
    global HOME_NAME, INFO
    INFO = {"active": False, "reason": "", "monitors": [], "ui_factor": ui_factor}
    pass_through = _set_pass_through_rounding()
    ours = os.environ.get(ENV_MARK)
    current = os.environ.get(QT_ENV)
    if current and current == ours:
        os.environ.pop(QT_ENV, None)  # inherited from our own restart: recompute
        current = None
    os.environ.pop(ENV_MARK, None)
    if os.environ.get(ENV_DISABLE, "").strip().lower() in ("0", "off", "false", "no"):
        INFO["reason"] = ENV_DISABLE + "=0"
    elif current:
        INFO["reason"] = "user-defined " + QT_ENV + " kept"
    elif os.environ.get("SPNAV_UI_SCALE", "").strip():
        INFO["reason"] = "SPNAV_UI_SCALE fixes one size for every monitor"
    elif os.environ.get("QT_ENABLE_HIGHDPI_SCALING", "").strip() == "0":
        INFO["reason"] = "QT_ENABLE_HIGHDPI_SCALING=0"
    elif not pass_through:
        INFO["reason"] = "Qt older than 5.14"
    else:
        try:
            monitors = native_monitors()
            factors, home = screen_factors(monitors, saved_home_name(config_dir), ui_factor)
            INFO["monitors"] = monitors
            if len(factors) > 1 and any(abs(m["relative"] - 1.0) > 0.005 for m in monitors):
                spec = format_factors(factors)
                os.environ[QT_ENV] = spec
                os.environ[ENV_MARK] = spec
                HOME_NAME = home
                INFO.update(active=True, reason=PER_MONITOR, home=home, spec=spec)
            else:
                HOME_NAME = home
                INFO.update(reason=SHARED_LAYOUT, home=home)
        except (OSError, AttributeError, ValueError, KeyError, ZeroDivisionError) as exc:
            INFO["reason"] = "monitor query failed: " + repr(exc)
    try:
        note(
            "Monitor scaling: "
            + INFO["reason"]
            + (
                " " + INFO.get("spec", "") + " (home " + INFO.get("home", "") + ")"
                if INFO.get("active")
                else ""
            )
            + "".join(
                f"; {m['name']} {m['width']}x{m['height']} at {round(m['dpi'] / 96 * 100)}%"
                for m in INFO.get("monitors", ())
            )
        )
    except Exception:
        pass
    return INFO


def _native(monitor):
    """The monitor's Windows scaling as a factor (1.5 for 150%)."""
    return max(0.5, float(monitor.get("dpi", 96) or 96) / 96.0)


def monitor_shape(monitor):
    """A monitor's name, resolution and scaling (its work area left out: a taskbar change asks nothing)."""
    return tuple(monitor.get(k) for k in ("name", "width", "height", "dpi"))


def describe_monitor(monitor):
    """'Display 2 — 1920 × 1080, 100%' for messages."""
    short = str(monitor.get("name", "")).rsplit("\\", 1)[-1]
    if short.upper().startswith("DISPLAY") and short[7:].isdigit():
        short = f"Display {short[7:]}"
    return f"{short} — {monitor.get('width')} × {monitor.get('height')}, {round(_native(monitor) * 100)}%"


def factors_in_use(info, monitors):
    """{name: the factor Qt draws each monitor with}: ours from start-up, else its Windows scaling."""
    ours = {}
    for part in str(info.get("spec") or "").split(";"):
        name, _sep, value = part.rpartition("=")
        try:
            ours[name] = float(value)
        except ValueError:
            pass
    return {m["name"]: ours.get(m["name"], _native(m)) for m in monitors}


def stale_monitors(info, monitors):
    """[(monitor, why)] for the monitors the editor is drawn at the wrong size on now (v108.163).

    The Qt factors and the editor's layout are fixed at start-up for the
    monitors connected then (`info` is INFO). A monitor connected since (at a
    Windows sign-in the Mapper can start before every monitor is ready), or a
    monitor whose resolution or scaling changed, needs another factor until
    the Mapper restarts. A monitor that was disconnected changes nothing.
    """
    if info.get("reason") not in (PER_MONITOR, SHARED_LAYOUT) or not monitors:
        return []
    started = {m["name"]: m for m in info.get("monitors") or ()}
    home = started.get(info.get("home"))
    if home is None:
        return []
    ui_factor = info.get("ui_factor", 1.0)
    base = monitor_layout_scale(home, ui_factor)
    in_use = factors_in_use(info, monitors)
    stale = []
    for monitor in monitors:
        before = started.get(monitor["name"])
        same = before is not None and monitor_shape(before) == monitor_shape(monitor)
        # Unchanged since start-up: measured as then (a moved taskbar changes nothing).
        measured = before if same else monitor
        relative = monitor_layout_scale(measured, ui_factor) / base if base > 0 else 1.0
        wanted = _native(monitor) * max(MIN_RELATIVE, min(MAX_RELATIVE, relative))
        if abs(in_use[monitor["name"]] - wanted) <= STALE_SHARE * wanted:
            continue
        if before is None:
            why = "connected since the Mapper started"
        elif not same:
            why = "was " + describe_monitor(before).split(" — ", 1)[-1]
        else:
            why = "sized for the monitors as they were"
        stale.append((monitor, why))
    return stale
