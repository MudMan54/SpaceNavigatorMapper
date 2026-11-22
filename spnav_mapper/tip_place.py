"""Where a hover tip goes (v108.178): beside what it explains, never under the pointer.

Rectangles are (x, y, width, height) and points (x, y), in screen pixels; no Qt.

A tip is put, in this order, at the right edge of its button or text (after
its end), at the left edge (before its beginning), below it or above it: the
first place that is wholly inside the Mapper's window, off the mouse pointer
and off whatever must stay readable (an open drop-down and its submenu). For
something large (an axis panel) the tip goes beside the pointer instead. When
the window has no room it may leave the window but not the screen.
"""

GAP = 6  # between a tip and what it explains
ORDER = ("right", "left", "below", "above")
POINTER = (-10, -10, 30, 38)  # the mouse pointer's arrow around its tip: dx, dy, width, height


def _inside(x, y, w, h, area):
    """True when the rectangle lies wholly inside `area`."""
    ax, ay, aw, ah = area
    return x >= ax and y >= ay and x + w <= ax + aw and y + h <= ay + ah


def _hits(x, y, w, h, rect):
    """True when the rectangle overlaps `rect`."""
    rx, ry, rw, rh = rect
    return x < rx + rw and rx < x + w and y < ry + rh and ry < y + h


def _clamp(value, low, high):
    """`value` kept between `low` and `high` (`low` when there is no room)."""
    return max(low, min(value, high))


def spots(anchor, size, area, gap=GAP):
    """The four places for a tip of `size` around `anchor`: name -> (x, y).

    Beside the anchor the tip is level with its top; below or above it starts
    where the anchor starts. Both are slid along to stay inside `area`.
    """
    ax, ay, aw, ah = anchor
    w, h = size
    x0, y0, aw0, ah0 = area
    level = _clamp(ay, y0, y0 + ah0 - h)
    along = _clamp(ax, x0, x0 + aw0 - w)
    return {
        "right": (ax + aw + gap, level),
        "left": (ax - gap - w, level),
        "below": (along, ay + ah + gap),
        "above": (along, ay - gap - h),
    }


def place_tip(anchor, size, bounds, cursor, order=ORDER, avoid=(), outer=None, gap=GAP):
    """The top-left corner for a tip of `size` that explains `anchor`.

    `bounds`: the Mapper's window; `outer`: the screen, used when the window
    has no room; `cursor`: the mouse pointer; `avoid`: rectangles the tip must
    not cover; `order`: the places to try, first to last.
    """
    w, h = size
    under_pointer = (cursor[0] - 2, cursor[1] - 2, 5, 5)
    pointer = (cursor[0] + POINTER[0], cursor[1] + POINTER[1], POINTER[2], POINTER[3])
    # Something large: beside the pointer, not at the far edge of the thing.
    large = anchor[3] > 3 * h
    anchors = (pointer, anchor) if large else (anchor, pointer)
    keep_clear = [under_pointer, *avoid]

    def clear(x, y, rects):
        return not any(_hits(x, y, w, h, rect) for rect in rects)

    areas = [bounds] + ([outer] if outer else [])
    for area in areas:
        for around in anchors:
            found = spots(around, size, area, gap)
            for name in order:
                x, y = found[name]
                if _inside(x, y, w, h, area) and clear(x, y, keep_clear):
                    return x, y
    # No clear place: inside the largest area, off the pointer if that can be.
    area = areas[-1]
    found = spots(pointer, size, area, gap)
    last = None
    for name in ("below", "above", "right", "left"):
        x = _clamp(found[name][0], area[0], area[0] + area[2] - w)
        y = _clamp(found[name][1], area[1], area[1] + area[3] - h)
        if last is None:
            last = (x, y)
        if clear(x, y, [under_pointer]):
            return x, y
    return last
