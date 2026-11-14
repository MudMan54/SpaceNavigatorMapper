"""DPI-aware UI sizing helpers and dynamic application scaling."""

import os

# UI scale (auto-tuned). Anchored so that at 2560x1440 the scale equals 0.60.
# You can override via SPNAV_UI_SCALE (e.g., 0.60, 0.85, 1.10).
SCALE = 0.65


def _env_float(name, default):
    """A number from an environment variable, or the default."""
    try:
        value = os.environ.get(name, "").strip()
        if value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


UI_SCALE_INFO = {}
UI_SIZE_FACTOR = 1.0
BASE_UI_SCALE = SCALE  # monitor/DPI scale at the default 100% preset


def saved_view_record(saved):
    """The editor's last placement from any window_state.json layout (v1-v5).

    Files written before v108.137 may hold only the old compact view's
    record; it names the monitor the Mapper was last used on just as well.
    """
    if not isinstance(saved, dict):
        return {}
    views = saved.get("views")
    if isinstance(views, dict):
        for mode in ("full", "compact"):
            if isinstance(views.get(mode), dict):
                return views[mode]
    for key in ("compact_geometry_v10863", "compact_geometry_v10858"):
        if isinstance(saved.get(key), dict):
            return saved[key]
    return saved


def _saved_display_screen(app):
    """Prefer the monitor on which the Mapper was last positioned."""
    # The per-monitor factors were measured against one home
    # monitor before QApplication existed; the baked layout must match it.
    try:
        from .monitor_scale import HOME_NAME

        if HOME_NAME:
            named = [screen for screen in app.screens() if screen.name() == HOME_NAME]
            if len(named) == 1:
                return named[0]
    except (ImportError, AttributeError, RuntimeError):
        pass
    try:
        import json

        from ..paths import CONFIG_DIR

        with open(os.path.join(CONFIG_DIR, "window_state.json"), encoding="utf-8") as stream:
            saved = json.load(stream)
        info = saved_view_record(saved)
        screens = list(app.screens())
        name = str(info.get("screen_name", ""))
        if name:
            named = [screen for screen in screens if screen.name() == name]
            if len(named) == 1:
                return named[0]
        position = info.get("screen_geometry") or {}
        if isinstance(position, dict) and position:
            x, y = int(position.get("x", 0)), int(position.get("y", 0))
            for screen in screens:
                rect = screen.geometry()
                if rect.x() == x and rect.y() == y:
                    return screen
        x, y = int(info.get("x", 0)), int(info.get("y", 0))
        for screen in screens:
            if screen.geometry().contains(x, y):
                return screen
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        pass
    return app.primaryScreen()


def _screen_scale_metrics(screen):
    """Read the current screen settings in Qt logical units.

    availableGeometry()/geometry() are DPI-aware logical pixels under Qt high-DPI.
    logicalDotsPerInch() reflects the Windows display scaling percentage on many
    systems.  devicePixelRatio() is also recorded because some Qt/Windows combos
    report scaling there instead.
    """
    out = {
        "width": 2560,
        "height": 1440,
        "geometry_width": 2560,
        "geometry_height": 1440,
        "logical_dpi": 96.0,
        "physical_dpi": 96.0,
        "device_pixel_ratio": 1.0,
        "scale_percent": 100.0,
        "name": "",
    }
    try:
        if screen is None:
            return out
        try:
            geo = screen.availableGeometry() if hasattr(screen, "availableGeometry") else screen.geometry()
            out["width"] = int(geo.width())
            out["height"] = int(geo.height())
        except Exception:
            pass
        try:
            g = screen.geometry()
            out["geometry_width"] = int(g.width())
            out["geometry_height"] = int(g.height())
        except Exception:
            pass
        try:
            out["logical_dpi"] = float(screen.logicalDotsPerInch())
        except Exception:
            pass
        try:
            out["physical_dpi"] = float(screen.physicalDotsPerInch())
        except Exception:
            pass
        try:
            out["device_pixel_ratio"] = float(screen.devicePixelRatio())
        except Exception:
            pass
        try:
            out["name"] = str(screen.name())
        except Exception:
            pass
        try:
            # 96 DPI = 100%, 120 = 125%, 144 = 150%, etc.
            out["scale_percent"] = max(50.0, min(400.0, out["logical_dpi"] / 96.0 * 100.0))
        except Exception:
            pass
    except Exception:
        pass
    return out


def _compute_ui_scale(_app, ref=(2560, 1440), ref_scale=0.60, min_scale=None, max_scale=None):
    """Auto-scale the control/widget sizes from screen resolution + DPI settings.

    Environment overrides:
        SPNAV_UI_SCALE      exact scale override, e.g. 0.70
        SPNAV_UI_SCALE_MIN  lower clamp, default 0.45
        SPNAV_UI_SCALE_MAX  upper clamp, default 1.15

    Examples of expected output:
        1920x1080 @100% -> smaller scale
        2560x1440 @100% -> about 0.60
        3840x2160 @150% -> larger than 0.60, but clamped to fit
    """
    global UI_SCALE_INFO
    try:
        screen = None
        try:
            screen = _saved_display_screen(_app)
        except Exception:
            screen = None
        m = _screen_scale_metrics(screen)
        s, parts = scale_from_metrics(
            m.get("width"),
            m.get("height"),
            m.get("logical_dpi"),
            m.get("device_pixel_ratio"),
            ref=ref,
            ref_scale=ref_scale,
            min_scale=min_scale,
            max_scale=max_scale,
        )
        UI_SCALE_INFO = dict(m)
        UI_SCALE_INFO.update(parts)
        return s
    except Exception:
        return float(ref_scale)


def scale_limits(min_scale=None, max_scale=None):
    """Lowest and highest interface scale allowed."""
    if min_scale is None:
        min_scale = _env_float("SPNAV_UI_SCALE_MIN", 0.45)
    if max_scale is None:
        max_scale = _env_float("SPNAV_UI_SCALE_MAX", 1.15)
    if min_scale > max_scale:
        min_scale, max_scale = max_scale, min_scale
    return float(min_scale), float(max_scale)


def scale_from_metrics(
    width,
    height,
    logical_dpi=96.0,
    device_pixel_ratio=1.0,
    ref=(2560, 1440),
    ref_scale=0.60,
    min_scale=None,
    max_scale=None,
):
    """The automatic layout scale for one monitor, in Qt logical units.

    Pure arithmetic shared by startup (_compute_ui_scale) and the per-monitor
    factors computed before QApplication exists (ui.monitor_scale).
    """
    min_scale, max_scale = scale_limits(min_scale, max_scale)
    w = max(640, int(width or ref[0]))
    h = max(480, int(height or ref[1]))
    # Available logical resolution determines how much UI can physically fit.
    res_ratio = min(w / float(ref[0]), h / float(ref[1]))
    # DPI/display-scale should affect readability, but not as strongly as resolution.
    dpi = max(72.0, min(288.0, float(logical_dpi or 96.0)))
    dpr = max(1.0, min(4.0, float(device_pixel_ratio or 1.0)))
    dpi_ratio = (dpi / 96.0) ** 0.33
    dpr_ratio = dpr**0.12
    s = ref_scale * res_ratio * dpi_ratio * dpr_ratio
    s = max(min_scale, min(max_scale, s))
    s = float(f"{s:.3f}")
    return s, {
        "computed_scale": s,
        "resolution_ratio": round(res_ratio, 3),
        "dpi_ratio": round(dpi_ratio, 3),
        "dpr_ratio": round(dpr_ratio, 3),
    }


def effective_scale(auto_scale, ui_factor):
    """The layout scale: the monitor's automatic scale times the size factor (Display % and fit).

    A relative multiplier of the resolution/DPI auto-scale, kept between
    0.24 and 1.65.
    """
    return max(0.24, min(1.65, round(float(auto_scale) * float(ui_factor), 3)))


# v108.151: the editor fits monitors with less room. Its look on a 3840x2160
# monitor at 225% Windows scaling (about 1706x912 Qt pixels to work in) is the
# reference: with less room, 1920x1080 at 125% or 150% for example, the
# controls and the fonts all shrink by the same fraction, so the editor takes
# the same share of the screen.
FIT_REFERENCE = (1700, 900)
FIT_MIN = 0.5


def fit_factor(width, height):
    """How much smaller the editor is drawn (1.0: not smaller) on a monitor with
    `width` x `height` Qt pixels to work in."""
    try:
        w, h = float(width), float(height)
    except (TypeError, ValueError):
        return 1.0
    if w <= 0 or h <= 0:
        return 1.0
    return round(max(FIT_MIN, min(1.0, w / FIT_REFERENCE[0], h / FIT_REFERENCE[1])), 3)


def scaled_point_size(base_points, factor=None, minimum=5.5):
    """Scale a font from its *100%* point size using the interface preset.

    Uses floating-point point sizes so 60%, 70%, and 85% remain distinct.
    A small floor avoids zero-height glyphs; 60% is deliberately small.
    """
    if factor is None:
        factor = UI_SIZE_FACTOR
    return max(float(minimum), round(float(base_points) * float(factor), 2))


def scaled_explicit_point_size(n, base_auto_scale=None, factor=None):
    """Scale the legacy Sf() fonts consistently with the whole interface.

    Before v108.88 the 12pt floor was applied *after* the scale factor,
    meaning many Full Editor labels stayed 12pt as the widgets shrank.
    Apply that historical floor to the 100% baseline *first*, then scale
    its result by the same factor as geometry and QApplication fonts.
    """
    if base_auto_scale is None:
        base_auto_scale = BASE_UI_SCALE
    if factor is None:
        factor = UI_SIZE_FACTOR
    baseline = max(12, int(round(int(n) * float(base_auto_scale))))
    return max(6, int(round(baseline * float(factor))))


def _apply_dynamic_scale(_app):
    """Work out the interface scale from the monitor and Display size."""
    global SCALE, BASE_UI_SCALE, UI_SCALE_INFO, UI_SIZE_FACTOR
    try:
        from ..display_preferences import UI_SCALE_FACTORS, numeric_choice

        factor = numeric_choice("ui_scale_factor", UI_SCALE_FACTORS)
        auto = _compute_ui_scale(_app)
        # v108.151: on a monitor with less room than the reference, everything
        # shrinks by the same fraction.
        fit = fit_factor(UI_SCALE_INFO.get("width"), UI_SCALE_INFO.get("height"))
        UI_SIZE_FACTOR = factor * fit  # one size sizes both the controls and the fonts
        BASE_UI_SCALE = effective_scale(auto, 1.0)
        SCALE = effective_scale(auto, factor * fit)
        UI_SCALE_INFO["fit_factor"] = fit
        env = os.environ.get("SPNAV_UI_SCALE", "").strip()
        if env:
            try:
                SCALE = max(0.24, min(1.65, float(env)))
                UI_SIZE_FACTOR = factor  # a fixed scale is not fitted to the monitor
                BASE_UI_SCALE = SCALE / max(0.1, factor)
                UI_SCALE_INFO = {"computed_scale": SCALE, "source": "SPNAV_UI_SCALE"}
            except (TypeError, ValueError):
                print("[UI] SPNAV_UI_SCALE not a float; ignoring.")

        UI_SCALE_INFO["user_factor"] = factor
        UI_SCALE_INFO["font_factor"] = factor
        UI_SCALE_INFO["unified_scaling"] = True
        # Standard Qt controls in Full Editor (axis labels, Bind Dir/Mode,
        # comments, menus, etc.) inherit the QApplication font.  Those fonts
        # must be scaled before MainWindow/AxisPanel construction.
        # v108.152: after the Windows scale changed since sign-in, Qt starts
        # with a default font of the wrong size; give it the size Windows meant.
        try:
            from ..bootstrap import note
            from .system_font import fix_stale_default_font

            fix_stale_default_font(_app, note)
        except ImportError:
            pass
        try:
            font = _app.font()
            points = float(font.pointSizeF())
            if points > 0:
                font.setPointSizeF(scaled_point_size(points, UI_SIZE_FACTOR))
            elif font.pixelSize() > 0:
                font.setPixelSize(max(6, round(font.pixelSize() * UI_SIZE_FACTOR)))
            _app.setFont(font)
        except (AttributeError, RuntimeError, ValueError, TypeError):
            pass
        try:
            from ..bootstrap import note

            info = UI_SCALE_INFO or {}
            note(
                f"Interface size: Display {round(factor * 100)}% x fit {info.get('fit_factor', 1.0)}, "
                f"layout scale {SCALE}, for {info.get('width')}x{info.get('height')} "
                f"(Qt scale {info.get('device_pixel_ratio', 1.0)})"
            )
        except Exception:
            pass
    except Exception as e:
        print(f"[UI] Dynamic scale error: {e}")


def S(n: int) -> int:
    """Scale a pixel size by the interface scale."""
    try:
        n = int(n)
    except Exception:
        return n
    if n <= 0:
        return n
    v = int(round(n * SCALE))
    return 1 if v < 1 else v


def Sf(n: int) -> int:
    """Scale explicit title and label fonts with the interface itself."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return n
    if n <= 0:
        return n
    return scaled_explicit_point_size(n)


# --- Proportional small-scale button metrics ---------------------------------
def button_padding(factor=None, vertical=5, horizontal=8):
    """Scaled QSS padding (logical px); never alter the 100%+ appearance."""
    if factor is None:
        factor = UI_SIZE_FACTOR
    if factor >= 1.0:
        return int(vertical), int(horizontal)
    return max(2, round(vertical * factor)), max(3, round(horizontal * factor))


def button_qss(style, factor=None):
    """Scale literal QSS button padding, including active/bound states.

    Called when a button style changes so the previous 5px padding does not
    reappear after clicking a Bind/NoBack button at a reduced preset.
    """
    if factor is None:
        factor = UI_SIZE_FACTOR
    if factor >= 1.0:
        return style
    import re

    return re.sub(
        r'(padding(?:-(?:top|bottom|left|right))?\s*:\s*)(\d+)(px\s*;)',
        lambda m: m.group(1) + str(max(1, round(int(m.group(2)) * factor))) + m.group(3),
        style,
        flags=re.I,
    )


def _is_button(widget, role=None):
    """True for push buttons (they get their own font rules)."""
    if role in ("QPushButton", "BindButton"):
        return True
    try:
        return any(klass.__name__ == "QPushButton" for klass in type(widget).__mro__)
    except (AttributeError, TypeError):
        return False


def button_fit_height(font_height, target, factor=None):
    """Compact touch target sized alongside its text, not a fixed 26/32px floor.

    Small-scale fonts still get top/bottom breathing room for descenders and
    Windows style borders. Inputs and combo boxes are *not* altered here.
    """
    if factor is None:
        factor = UI_SIZE_FACTOR
    pad_y, _ = button_padding(factor)
    return max(int(target), int(font_height) + 2 * pad_y + 2, 16)


# --- Font-aware control heights ----------------------------------------------
def readable_control_height(widget, nominal_height, role=None):
    """Return a font-safe height: at least `nominal_height`, and tall enough for the text.

    Buttons use the actual scaled font and their QSS padding. Since v108.154
    this holds at every Display size: before, 100% and 110% kept the nominal
    heights, so their controls were no taller than at 85% (combo boxes and
    comments were shorter) although their text was larger.
    """
    target = max(1, int(nominal_height))
    try:
        if hasattr(widget, "ensurePolished"):
            widget.ensurePolished()
        font_height = max(1, int(widget.fontMetrics().height()))
        if _is_button(widget, role):
            return button_fit_height(font_height, target)
        widget_type = role or type(widget).__name__
        padding = 6 if widget_type == "QLabel" else 14
        minimum = font_height + padding
        try:
            minimum = max(minimum, int(widget.sizeHint().height()))
        except (AttributeError, TypeError, ValueError):
            pass
        return max(target, minimum)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return target


def set_readable_height(widget, requested, role=None):
    """Fix height and retain the requested pre-style height for Qt reflow."""
    if _is_button(widget, role):
        # A later QSS/Qt polish pass should not preserve an inflated minimum.
        widget._spnav_scaled_button_target = max(1, int(requested))
    widget.setFixedHeight(readable_control_height(widget, requested, role))


def set_readable_square(widget, requested_width, requested_height):
    """Scale +/- control width with font and height without truncation."""
    h = readable_control_height(widget, requested_height, "QPushButton")
    w = max(int(requested_width), h)
    widget.setFixedSize(w, h)


def restore_readable_height(widget):
    """Recheck after styling; a button may shrink back to its own target as well as grow."""
    try:
        current = int(widget.height())
        if hasattr(widget, "_spnav_fixed_height"):
            required = int(widget._spnav_fixed_height)
            widget.setFixedHeight(required)
            return required != current
        if hasattr(widget, "_spnav_scaled_input_target"):
            required = scaled_line_edit_height(widget, widget._spnav_scaled_input_target)
            if required != current:
                widget.setFixedHeight(required)
                return True
            return False
        if _is_button(widget) and hasattr(widget, "_spnav_scaled_button_target"):
            required = readable_control_height(widget, widget._spnav_scaled_button_target, "QPushButton")
            if required != current:
                widget.setFixedHeight(required)
                return True
            return False
        required = readable_control_height(widget, current)
        if required > current:
            widget.setFixedHeight(required)
            return True
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    return False


# --- Full-editor input/comment proportions -----------------------------------
def input_padding(factor=None, vertical=4, horizontal=6):
    """QLineEdit padding in logical pixels, scaled with fonts below 100%."""
    if factor is None:
        factor = UI_SIZE_FACTOR
    if factor >= 1.0:
        return int(vertical), int(horizontal)
    return max(1, round(vertical * factor)), max(2, round(horizontal * factor))


def scaled_line_edit_height(widget, nominal_height, factor=None):
    """Use text metrics rather than a native Qt sizeHint with unscaled padding.

    Unlike an expanded combo popup, an editable comment row may safely shrink
    to its font height plus its QSS padding (never below `nominal_height`).
    """
    if factor is None:
        factor = UI_SIZE_FACTOR
    try:
        widget.ensurePolished()
        font_height = max(1, int(widget.fontMetrics().height()))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        font_height = max(10, round(17 * factor))
    pad_y, _ = input_padding(factor)
    return max(16, int(nominal_height), font_height + 2 * pad_y + 4)


def fit_scaled_input_height(widget, nominal_height):
    """Set a restorable input target, after optional font overrides."""
    widget._spnav_scaled_input_target = max(1, int(nominal_height))
    widget.setFixedHeight(scaled_line_edit_height(widget, nominal_height))
    return True


def comment_widths(font_char_px, factor=None, max_chars=30, min_chars=8):
    """Minimum and maximum field widths based on the actual scaled font.

    The comment field can expand up to the preferred character count, instead
    of taking all spare horizontal space in a wide Full Editor window.
    """
    if factor is None:
        factor = UI_SIZE_FACTOR
    pad = 2 * input_padding(factor)[1] + 6
    char_width = max(1, int(font_char_px))
    minimum = max(25, min_chars * char_width + pad)
    maximum = max(minimum, max_chars * char_width + pad)
    return minimum, maximum


def fit_scaled_comment_field(widget, nominal_height, max_chars=30, min_chars=8):
    """Scale axis and hardware-button comment boxes below 100%."""
    if UI_SIZE_FACTOR >= 1.0:
        return False
    fit_scaled_input_height(widget, nominal_height)
    try:
        metrics = widget.fontMetrics()
        letter_width = metrics.horizontalAdvance('M')
    except (AttributeError, RuntimeError):
        letter_width = 8
    minimum, maximum = comment_widths(letter_width, max_chars=max_chars, min_chars=min_chars)
    # Set minimum before maximum so stale v108.90 30-character minimums do
    # not coerce the cap back up to an oversized value.
    widget.setMinimumWidth(minimum)
    widget.setMaximumWidth(maximum)
    return True


# --- Axis column widths ------------------------------------------------------
def axis_comment_widths(char_px, factor=None, preferred_chars=18, min_chars=7):
    """Compact, resizable per-axis comment field limits.

    A QLineEdit retains its entire text regardless of its displayed width;
    users can navigate longer comments within the field. Both limits are
    font-relative, so widths track 60%..130% font scaling, with a minimum
    wide enough for short comments.
    """
    if factor is None:
        factor = UI_SIZE_FACTOR
    minimum_chars = max(1, int(min_chars))
    preferred_chars = max(minimum_chars, int(preferred_chars))
    horizontal_pad = input_padding(factor)[1]
    pad = 2 * horizontal_pad + 8
    char_px = max(1, int(char_px))
    return max(32, minimum_chars * char_px + pad), max(32, preferred_chars * char_px + pad)


def fit_axis_comment_field(widget, nominal_height, preferred_chars=18, min_chars=7):
    """Apply a narrower axis comment column on every display preset.

    v108.91 kept a 30-character hard minimum at 100%+, which prevented users
    from making the axis panel narrower. The width is a *range*, not fixed,
    allowing layout shrinkage; QLineEdit data is never shortened.
    """
    fit_scaled_input_height(widget, nominal_height)
    try:
        metrics = widget.fontMetrics()
        char_px = metrics.horizontalAdvance('M')
    except (AttributeError, RuntimeError):
        char_px = max(5, round(10 * UI_SIZE_FACTOR))
    low, high = axis_comment_widths(char_px, preferred_chars=preferred_chars, min_chars=min_chars)
    # Remove any previous 30-character minimum first, then apply the cap.
    widget.setMinimumWidth(0)
    widget.setMaximumWidth(high)
    widget.setMinimumWidth(low)
    return low, high


def fit_axis_combo_width(widget):
    """Use intrinsic item text width instead of expanding with the editor row.

    The popup remains managed by Qt and can be wider than this closed control.
    Unlike a fixed arbitrary pixel width, this works with all UI font presets.
    """
    try:
        fm = widget.fontMetrics()
        longest = max((fm.horizontalAdvance(widget.itemText(i)) for i in range(widget.count())), default=0)
    except (AttributeError, RuntimeError, TypeError):
        return None
    # Measure the actual closed control with this theme's arrow and borders.
    # Qt's label painter also insets text by one pixel on each side.
    from PyQt5.QtWidgets import QStyle, QStyleOptionComboBox

    option = QStyleOptionComboBox()
    widget.initStyleOption(option)
    option.rect.setWidth(longest + 100)
    edit = widget.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, widget)
    width = longest + option.rect.width() - edit.width() + 2
    widget.setMinimumWidth(0)
    widget.setMaximumWidth(width)
    widget.setMinimumWidth(width)
    return width
