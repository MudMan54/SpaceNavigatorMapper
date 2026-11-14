"""Qt's default font after the Windows scale changed since sign-in (v108.152).

Qt 5.15 builds its default font from Windows' default GUI font. Windows makes
that font for the DPI the user signed in with (the system DPI), which stays
the same until the next sign-in, but Qt converts it to points with the
monitor's current DPI. So after the Windows scale is changed without signing
out (or the resolution is changed and Windows picks another scale), every Qt
program started afterwards gets a default font too large or too small by the
ratio of the two (QTBUG-101951): from 225% down to 100%, 2.25 times too large.

A program that was already running keeps its fonts, which is why the Mapper
looked right when brought back from the tray and too large when started again.

fix_stale_default_font() measures the size Windows meant and gives Qt that
size when the two disagree. When nothing changed since sign-in, the two agree
and nothing is touched.
"""

import ctypes
import sys

DEFAULT_GUI_FONT = 17  # GetStockObject index
LOGPIXELSY = 90  # GetDeviceCaps index
TOLERANCE = 0.05  # Qt's rounding stays well inside 5%


class LOGFONTW(ctypes.Structure):
    _fields_ = [
        ("lfHeight", ctypes.c_long),
        ("lfWidth", ctypes.c_long),
        ("lfEscapement", ctypes.c_long),
        ("lfOrientation", ctypes.c_long),
        ("lfWeight", ctypes.c_long),
        ("lfItalic", ctypes.c_ubyte),
        ("lfUnderline", ctypes.c_ubyte),
        ("lfStrikeOut", ctypes.c_ubyte),
        ("lfCharSet", ctypes.c_ubyte),
        ("lfOutPrecision", ctypes.c_ubyte),
        ("lfClipPrecision", ctypes.c_ubyte),
        ("lfQuality", ctypes.c_ubyte),
        ("lfPitchAndFamily", ctypes.c_ubyte),
        ("lfFaceName", ctypes.c_wchar * 32),
    ]


def system_dpi():
    """The DPI Windows was signed in with (0 when unknown)."""
    try:
        user32 = ctypes.windll.user32
        try:
            dpi = int(user32.GetDpiForSystem())  # Windows 10 1607 and later
        except (AttributeError, OSError):
            dpi = 0
        if dpi > 0:
            return dpi
        gdi32 = ctypes.windll.gdi32
        user32.GetDC.restype = ctypes.c_void_p
        user32.GetDC.argtypes = [ctypes.c_void_p]
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.GetDeviceCaps.argtypes = [ctypes.c_void_p, ctypes.c_int]
        dc = user32.GetDC(None)
        if not dc:
            return 0
        try:
            return int(gdi32.GetDeviceCaps(dc, LOGPIXELSY))
        finally:
            user32.ReleaseDC(None, dc)
    except (AttributeError, OSError, TypeError, ValueError):
        return 0


def windows_gui_font():
    """(height in pixels, face name, sign-in DPI) of Windows' default GUI font, or None."""
    if sys.platform != "win32":
        return None
    try:
        gdi32 = ctypes.windll.gdi32
        gdi32.GetStockObject.restype = ctypes.c_void_p
        gdi32.GetStockObject.argtypes = [ctypes.c_int]
        gdi32.GetObjectW.restype = ctypes.c_int
        gdi32.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        handle = gdi32.GetStockObject(DEFAULT_GUI_FONT)
        if not handle:
            return None
        font = LOGFONTW()
        if not gdi32.GetObjectW(handle, ctypes.sizeof(font), ctypes.byref(font)):
            return None
        dpi = system_dpi()
        if dpi <= 0 or not font.lfHeight:
            return None
        return int(font.lfHeight), str(font.lfFaceName), dpi
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _family_key(name):
    """A font family name for comparing: Qt names Windows' "MS Shell Dlg" "MS Shell Dlg 2"."""
    return str(name or "").strip().lower().removesuffix(" 2")


def corrected_default_points(qt_points, qt_family, gui_font):
    """The point size Qt's default font should have, or None when Qt's is right (or unknown)."""
    if not gui_font:
        return None
    try:
        height, face, dpi = gui_font
        points, height, dpi = float(qt_points), abs(int(height)), float(dpi)
    except (TypeError, ValueError):
        return None
    if points <= 0 or height <= 0 or dpi < 48:
        return None
    if _family_key(qt_family) != _family_key(face):
        return None  # not the font Qt made from it: nothing to compare
    wanted = round(height * 72.0 / dpi, 2)
    if abs(points - wanted) <= TOLERANCE * wanted:
        return None
    return wanted


def fix_stale_default_font(app, note=None):
    """Give Qt's default font the size Windows meant; returns the new size, or None."""
    gui_font = windows_gui_font()
    if gui_font is None:
        return None
    try:
        font = app.font()
        points = float(font.pointSizeF())
        wanted = corrected_default_points(points, font.family(), gui_font)
        if note is not None:
            note(
                f"Default font: {font.family()} {points:g} pt; Windows' GUI font {gui_font[1]} "
                f"{abs(gui_font[0])} px at the sign-in DPI {gui_font[2]}"
            )
        if wanted is None:
            return None
        font.setPointSizeF(wanted)
        app.setFont(font)
        if note is not None:
            note(
                f"The Windows scale changed since sign-in: Qt's default font was {points:g} pt, "
                f"now {wanted:g} pt. Sign out of Windows and back in to finish the change."
            )
        return wanted
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
