"""Monitor-relative placement records for window_state.json."""


def screen_record(screen):
    """Name, serial number and geometry of a monitor."""
    g = screen.geometry()
    return {
        "screen_name": screen.name(),
        "serial": getattr(screen, "serialNumber", lambda: "")(),
        "screen_geometry": dict(x=g.x(), y=g.y(), w=g.width(), h=g.height()),
    }


def select_screen(screens, primary, info):
    """Prefer a physical identifier, then a unique Windows display name."""
    candidates = list(screens)
    for key in ("serial", "screen_name"):
        if info.get(key):
            matches = [s for s in candidates if screen_record(s)[key] == info[key]]
            if len(matches) == 1:
                return matches[0]
            if matches:
                candidates = matches
    for screen in candidates:
        if screen_record(screen)["screen_geometry"] == info.get("screen_geometry"):
            return screen
    return primary or next(iter(candidates), None)


def read_views(saved):
    """The saved per-view records of window_state.json."""
    if not isinstance(saved, dict):
        return {}
    if isinstance(saved.get("views"), dict):
        return {
            mode: info
            for mode, info in saved["views"].items()
            if mode in ("compact", "full") and isinstance(info, dict)
        }
    views = {}
    compact = saved.get("compact_geometry_v10863") or saved.get("compact_geometry_v10858")
    if isinstance(compact, dict):
        views["compact"] = compact
    geom = saved.get("window_geometry")
    if isinstance(geom, dict):
        mode = saved.get("mode") or ("compact" if saved.get("compact_mode") else "full")
        views.setdefault(mode, {**saved, **geom})
    return views


def client_rect(info, area, size, margins):
    """Clamp client coordinates while allowing space for the native frame."""
    ax, ay, aw, ah = area
    left, top, right, bottom = margins
    w = max(1, min(size[0], aw - left - right))
    h = max(1, min(size[1], ah - top - bottom))

    def origin(key, start):
        try:
            relative = info.get("relative_" + key)
            return start + int(relative) if relative is not None else int(info.get(key, start))
        except (ValueError, TypeError, OverflowError):
            return start

    x, y = origin("x", ax), origin("y", ay)
    return (max(ax + left, min(x, ax + aw - right - w)), max(ay + top, min(y, ay + ah - bottom - h)), w, h)
