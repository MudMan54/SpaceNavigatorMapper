"""Axis history (v108.149): what each axis did, and what its binds sent (no Qt).

While Options > Axis History is checked, every axis panel keeps an
AxisHistory: each 16 ms sample of the axis (the device's value, before the
dead zone) and each key its binds send, with a mark where NoBack held a bind
back. The last KEEP_S seconds are kept. The history window draws them with
drawing(), which returns plain shapes, so the layout can be tested without Qt.
"""

import time
from collections import deque

from .settings import AXES

KEEP_S = 30.0  # seconds kept per axis
WINDOWS_S = (5, 10, 30)  # the history window's choices of how much to show

# What a bind did (an event).
DOWN, UP, TAP, MACRO, HELD, NOBACK_UP = "down", "up", "tap", "macro", "held", "noback-up"
EVENT_TEXT = {
    DOWN: "down",
    UP: "up",
    TAP: "tap",
    MACRO: "macro",
    HELD: "held by NoBack",
    NOBACK_UP: "up (NoBack)",
}
SENT = {DOWN, UP, TAP, MACRO, NOBACK_UP}  # events that sent a key; HELD sent nothing
# v108.156: what a bind would have sent while output was off (Target off, or
# the Mapper's own window in front): the same kinds, marked "not sent".
UNSENT_PREFIX = "unsent-"
for _kind in SENT:
    EVENT_TEXT[UNSENT_PREFIX + _kind] = EVENT_TEXT[_kind] + " (not sent)"


def unsent(kind):
    """The not-sent form of an event kind (HELD stays HELD: NoBack holds a bind either way)."""
    return UNSENT_PREFIX + kind if kind in SENT else kind


def is_unsent(kind):
    """True for what a bind would have sent while output was off."""
    return kind.startswith(UNSENT_PREFIX)


class AxisHistory:
    """One axis's recent samples and bind events, the oldest dropped after keep_s seconds."""

    def __init__(self, keep_s=KEEP_S, clock=time.perf_counter):
        """An empty history keeping `keep_s` seconds, timed by `clock`."""
        self.keep_s = float(keep_s)
        self.clock = clock
        self.samples = deque()  # (time, value -1..1)
        self.events = deque()  # (time, kind, bind index, key text, value -1..1)
        # v108.158: NoBack's state, recorded when it changes: (time, side "+"
        # or "-", highest band start reached), or (time, None, -1) when off.
        self.noback = deque()

    def add_sample(self, value):
        """Record the axis value now."""
        now = self.clock()
        self.samples.append((now, float(value)))
        cutoff = now - self.keep_s
        while self.samples and self.samples[0][0] < cutoff:
            self.samples.popleft()
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
        while len(self.noback) > 1 and self.noback[1][0] < cutoff:
            self.noback.popleft()  # the one before the cutoff is the state then

    def add_event(self, kind, bind_index, key, value):
        """Record what bind `bind_index` did now (`kind`), its key text, at axis value `value`."""
        self.events.append((self.clock(), kind, int(bind_index), str(key or ""), float(value)))

    def set_noback(self, side, level):
        """Note NoBack's state now (`side` and the highest band start reached), when it changed."""
        state = (side, int(level)) if side and level is not None and level >= 0 else (None, -1)
        last = (self.noback[-1][1], self.noback[-1][2]) if self.noback else (None, -1)
        if state != last:
            self.noback.append((self.clock(), *state))

    def noback_span(self, now, seconds):
        """NoBack's states from the last `seconds` seconds before `now`, with the one in force at their start."""
        start = now - seconds
        before = [n for n in self.noback if n[0] < start]
        return before[-1:] + [n for n in self.noback if start <= n[0] <= now]

    def clear(self):
        """Forget everything recorded."""
        self.samples.clear()
        self.events.clear()
        self.noback.clear()

    def span(self, now, seconds):
        """(samples, events) from the last `seconds` seconds before `now`."""
        start = now - seconds
        return (
            [s for s in self.samples if start <= s[0] <= now],
            [e for e in self.events if start <= e[0] <= now],
        )


def bind_bands(binds, dead, key_text):
    """Where each mapped bind starts, as drawn on the graph.

    [(bind index, sides "+", "-" or "+-", start percent, key, NoBack sides)],
    for binds with a key (or macro) and a Bind Dir; `key_text(bind)` names
    the key, and the NoBack sides are those of its sides with NoBack on (none
    for a Tick bind). A bind starts at its DZone% plus Min%; a Tick bind at
    its Tick%.
    """
    sides_of = {"Plus": "+", "Minus": "-", "Full": "+-"}
    bands = []
    for index, bind in enumerate(binds):
        sides = sides_of.get(bind.get("direction"), "")
        has_output = bool(bind.get("macro")) if bind.get("mode") == "Macro" else bool(bind.get("combo"))
        if not sides or not has_output:
            continue
        try:
            if bind.get("mode") == "Tick":
                start = max(0, min(100, int(bind.get("min", 0))))
            else:
                start = max(0, min(100, int(bind.get("dead", dead)) + int(bind.get("min", 0))))
        except (TypeError, ValueError):
            continue
        # A Tick bind has no NoBack (v108.162), whatever its profile says.
        tick = bind.get("mode") == "Tick"
        noback = "" if tick else "".join(side for side in sides if bind.get(NOBACK_KEYS[side]))
        bands.append((index, sides, start, key_text(bind), noback))
    return bands


NOBACK_KEYS = {"+": "noback_plus", "-": "noback_minus"}  # a bind's NoBack + / NoBack −


def summary(samples, events):
    """One line: the farthest the axis went each way, and what each bind did."""
    if not samples:
        return "Nothing recorded yet: move the axis."
    high = max(max(v for _t, v in samples), 0.0) * 100
    low = min(min(v for _t, v in samples), 0.0) * 100
    parts = [f"Peak +{high:.0f}%, −{abs(low):.0f}%"]
    counts = {}
    held = 0
    words = {DOWN: "pressed", TAP: "tapped", MACRO: "played"}
    for _t, kind, index, _key, _value in events:
        base = kind[len(UNSENT_PREFIX) :] if is_unsent(kind) else kind
        if kind == HELD:
            held += 1
        elif base in words:
            key = (index, is_unsent(kind), words[base])
            counts[key] = counts.get(key, 0) + 1
    for (index, not_sent, word), count in sorted(counts.items()):
        parts.append(f"Bind #{index + 1} {word} {count}×" + (" (not sent)" if not_sent else ""))
    if held:
        parts.append(f"NoBack held {held}×")
    return " · ".join(parts)


def csv_rows(series):
    """Rows for a CSV file of one or more axes: a header, then every sample and event in time order.

    `series` is [(axis name, samples, events)]; times are seconds from the first of them.
    """
    rows = [("axis", "time_s", "value_percent", "event", "bind", "key")]
    firsts = [s[0][0] for _a, s, _e in series if s] + [e[0][0] for _a, _s, e in series if e]
    if not firsts:
        return rows
    start = min(firsts)
    merged = []
    for order, (axis, samples, events) in enumerate(series):
        merged += [(t, order, 0, axis, f"{v * 100:.1f}", "", "", "") for t, v in samples]
        merged += [
            (t, order, 1, axis, f"{v * 100:.1f}", EVENT_TEXT[kind], f"Bind #{i + 1}", key)
            for t, kind, i, key, v in events
        ]
    for t, _order, _kind, axis, value, event, bind, key in sorted(merged):
        rows.append((axis, f"{t - start:.3f}", value, event, bind, key))
    return rows


# The graph's text: its line height and digit width in pixels. The margins,
# the dots and the text offsets follow them, so larger text gets room.
TEXT_PX, CHAR_PX = 13, 7
LABEL_EVENTS_UP_TO = 14  # more events than this in view: dots only, no labels
# v108.159: each bind has a basic colour of its own, the same on every axis,
# for its dots, its start line and its row in the labels (the window gives
# the names "bind1" … "bind6" their colours: red, orange, yellow, green,
# blue, purple).
BIND_COLOUR_COUNT = 6
LABEL_GUTTER_SHARE = 0.45  # the labels' column takes at most this share of the width


def bind_colour(index):
    """The colour name of bind `index` (0 for Bind #1), the same on every axis."""
    return f"bind{int(index) % BIND_COLOUR_COUNT + 1}"


def text_width(text, char_px=CHAR_PX):
    """An estimate of `text`'s width in pixels (the window measures with its font instead)."""
    wide = sum(1 for c in text if c.isupper() or c in "#%@MWmw")
    return round((len(text) + 0.35 * wide) * char_px)


def _frame(width, height, now, seconds, text_px, char_px, titled, right=12):
    """The plot area and its coordinates: (x0, x1, top, bottom, x_at, y_at)."""
    left = 6 * char_px + 14  # room for "−100%"
    top = text_px + 10 if titled else max(14, round(text_px * 0.7) + 5)
    bottom_margin = text_px + 13  # room for the times
    x0, x1 = left, max(left + 10, width - right)
    bottom = max(top + 20, height - bottom_margin)
    mid = (top + bottom) / 2.0
    half = (bottom - top) / 2.0
    seconds = max(0.1, float(seconds))

    def x_at(t):
        return x1 - (now - t) / seconds * (x1 - x0)

    def y_at(percent):
        return mid - max(-100.0, min(100.0, percent)) / 100.0 * half

    return x0, x1, top, bottom, x_at, y_at


# v108.159: +100% green, 0 blue and −100% red, dashed; ±50% stay faint.
REFERENCE = (
    (100, "plus100", "+100%"),
    (50, "grid", "+50%"),
    (0, "zero", "0"),
    (-50, "grid", "−50%"),
    (-100, "minus100", "−100%"),
)


def _grid(x0, x1, y_at, text_px):
    """The percent lines and their labels."""
    shapes = []
    for percent, colour, _text in REFERENCE:
        dashed = colour != "grid"
        shapes.append(("line", x0, y_at(percent), x1, y_at(percent), colour, 1.5 if dashed else 1.0, dashed))
    for percent, colour, text in REFERENCE:
        label = "label" if colour == "grid" else colour
        shapes.append(("text", x0 - 6, y_at(percent) + round(text_px * 0.3), text, label, "right"))
    return shapes


def _times(x0, x1, bottom, seconds, text_px):
    """ "−10 s", "−5 s" and "now" under the plot."""
    seconds = max(0.1, float(seconds))
    y = bottom + text_px + 5
    return [
        ("text", x0, y, f"−{seconds:g} s", "label", "left"),
        ("text", (x0 + x1) / 2, y, f"−{seconds / 2:g} s", "label", "center"),
        ("text", x1, y, "now", "label", "right"),
    ]


def _dots(events, x_at, y_at, labelled, text_px, prefix="", text_w=None, x_range=None):
    """A dot for each key in its bind's colour: filled when sent, hollow when not sent
    (output off); a hollow light dot where NoBack held a bind back.

    Each label goes beside its dot where it covers no dot and no label placed
    before it, inside `x_range` (above or below, right or left; v108.159), or
    is left out: the dot's colour still names the bind.
    """
    text_w = text_w or (lambda text: text_width(text))
    shapes = []
    radius = max(5.0, round(text_px * 0.35, 1))
    gap = radius + 2.5
    placed = [
        (x_at(t) - radius, y_at(v * 100) - radius, x_at(t) + radius, y_at(v * 100) + radius)
        for t, _k, _i, _key, v in events
    ]
    for t, kind, index, key, value in events:
        x, y = x_at(t), y_at(value * 100)
        colour = "noback" if kind == HELD else bind_colour(index)
        shapes.append(("circle", x, y, radius, colour, kind != HELD and not is_unsent(kind)))
        if not labelled:
            continue
        text = f"{prefix}{key} {EVENT_TEXT[kind]}".strip()
        w = text_w(text)
        above, below = y - gap, y + gap + round(text_px * 0.75)
        tries = [(x + gap, above), (x + gap, below), (x - gap - w, above), (x - gap - w, below)]
        if value < 0:  # below the line first on the − side
            tries = [tries[1], tries[0], tries[3], tries[2]]
        for left, baseline in tries:
            box = (left, baseline - text_px * 0.8, left + w, baseline + text_px * 0.2)
            if x_range is not None and (box[0] < x_range[0] or box[2] > x_range[1]):
                continue
            if any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in placed):
                continue
            placed.append(box)
            shapes.append(("text", left, baseline, text, colour, "left"))
            break
    return shapes


def _noback_shapes(entries, now, seconds, x_at, y_at, text_px):
    """While NoBack is in force: a thin dashed light line at the highest band reached.

    Below that line, binds with NoBack on that side are held back until the
    axis returns to centre (or drops below every band). v108.161: no longer
    shaded down to centre, nor a thick bar: those blocks, redrawn as the axis
    moved, looked like artifacts around the axis's line.
    """
    shapes = []
    start = now - max(0.1, float(seconds))
    entries = list(entries)
    for i, (t, side, level) in enumerate(entries):
        if not side or level < 0:
            continue
        end = entries[i + 1][0] if i + 1 < len(entries) else now
        a, b = max(t, start), min(end, now)
        if b <= a:
            continue
        xa, xb = x_at(a), x_at(b)
        y = y_at(level if side == "+" else -level)
        shapes.append(("line", xa, y, xb, y, "noback", 1.0, True))
        label_y = y - round(text_px * 0.3) - 2 if side == "+" else y + text_px + 2
        shapes.append(("text", xa + 4, label_y, f"NoBack {level}%", "noback", "left"))
    return shapes


def label_rows(bands):
    """One row per bind side for the labels' column, top (+100%) to bottom (−100%).

    Each row: (bind index, side, start percent, key, NoBack note). The note
    is "NoBack", or "NoBack: nothing to hold" when no higher bind on that
    side could make it hold, or "".
    """
    rows = []
    for band in bands:
        index, sides, start, key = band[:4]
        noback_sides = band[4] if len(band) > 4 else ""
        for side in sides:
            note = ""
            if side in noback_sides:
                higher = any(other[2] > start and side in other[1] for other in bands)
                note = "NoBack" if higher else "NoBack: nothing to hold"
            rows.append((index, side, start, key, note))
    return sorted(rows, key=lambda r: (-r[2] if r[1] == "+" else r[2], r[0]))


def spread(wanted, low, high, gap):
    """Baselines for labels wanted at `wanted` (top to bottom), each at least `gap` below the last,
    kept between `low` and `high` as far as they fit."""
    ys = []
    for y in wanted:
        ys.append(max(y, ys[-1] + gap) if ys else y)
    if ys and ys[-1] > high:  # past the bottom: move up from there
        ys[-1] = high
        for i in range(len(ys) - 2, -1, -1):
            ys[i] = min(ys[i], ys[i + 1] - gap)
    if ys and ys[0] < low:  # past the top as well: they cannot all fit; start at the top
        ys[0] = low
        for i in range(1, len(ys)):
            ys[i] = max(ys[i], ys[i - 1] + gap)
    return ys


def _label_columns(rows, width, char_px, text_w):
    """The labels' columns: [(column, x offset, width, align)] and the column's total width.

    Columns: "Bind", "#n", "(key)", the percent (right-aligned) and the NoBack
    note. The key, then the word "Bind", are left out when the column would
    take more than LABEL_GUTTER_SHARE of the width.
    """
    gap = char_px
    texts = {
        "bind": ["Bind"],
        "number": [f"#{r[0] + 1}" for r in rows],
        "key": [f"({r[3]})" if r[3] else "" for r in rows],
        "percent": [f"{'' if r[1] == '+' else '−'}{r[2]}%" for r in rows],
        "note": [r[4] for r in rows],
    }
    swatch = round(char_px * 1.6) + gap
    for leave_out in ((), ("key",), ("key", "bind")):
        columns, x = [], swatch
        for name in ("bind", "number", "key", "percent", "note"):
            if name in leave_out or not any(texts[name]):
                continue
            w = max(text_w(t) for t in texts[name])
            columns.append((name, x, w, "right" if name == "percent" else "left"))
            x += w + gap
        if x + 8 <= LABEL_GUTTER_SHARE * width:
            break
    return columns, x + 8


def _labels(rows, bands_y, x1, width, height, text_px, char_px, text_w):
    """The labels' column right of the plot, its rows spread so they never overlap, each joined
    to its start line; returns (shapes, gutter width)."""
    if not rows:
        return [], 0
    columns, gutter = _label_columns(rows, width, char_px, text_w)
    gx = width - gutter + 4
    wanted = [y + round(text_px * 0.35) for y in bands_y]
    ys = spread(wanted, text_px, height - 4, text_px + 1)
    shapes = []
    r = max(3.5, round(char_px * 0.5, 1))
    for (index, side, start, key, note), y_band, y in zip(rows, bands_y, ys, strict=True):
        colour = bind_colour(index)
        middle = y - round(text_px * 0.35)
        shapes.append(("line", x1, y_band, gx - 2, middle, colour, 1.0, False))
        shapes.append(("circle", gx + r + 2, middle, r, colour, True))
        values = {
            "bind": "Bind",
            "number": f"#{index + 1}",
            "key": f"({key})" if key else "",
            "percent": f"{'' if side == '+' else '−'}{start}%",
            "note": note,
        }
        for name, offset, w, align in columns:
            if values[name]:
                x = gx + offset + (w if align == "right" else 0)
                shapes.append(("text", x, y, values[name], "noback" if name == "note" else colour, align))
    return shapes, gutter


def drawing(
    samples,
    events,
    bands,
    dead,
    now,
    seconds,
    width,
    height,
    title=None,
    colour="trace",
    text_px=TEXT_PX,
    char_px=CHAR_PX,
    noback=(),
    text_w=None,
):
    """One axis's graph as plain shapes, for a widget `width` × `height` pixels.

    Each shape is a tuple whose first item names it:
    ("rect", x, y, w, h, colour), ("line", x1, y1, x2, y2, colour, width, dashed)
    with dashed False, True or "dot", ("polyline", [(x, y), ...], colour, width),
    ("circle", x, y, r, colour, filled), ("text", x, y, text, colour, align) with
    align "left", "right" or "center" and y the text's baseline.

    Colours are names: "deadzone", "grid", "label", "plus100" / "zero" /
    "minus100" (the +100%, 0 and −100% lines: green, blue, red), "trace" (the
    axis's line: white), "bind1" … "bind6" (each bind's dots, start line and
    labels), "noback" (NoBack: the highest band reached while it is in force,
    from `noback` (see AxisHistory.noback_span()), and the binds it held
    back), and `colour` for the `title` above the plot.

    The binds' labels stand in a column right of the plot ("Bind", "#n",
    "(key)", the percent, NoBack), one row per bind side, spread so that rows
    never overlap, each joined to its start line. `text_px` and `char_px` are
    the text's line height and digit width; `text_w(text)` measures text
    (estimated when not given).
    """
    text_w = text_w or (lambda text: text_width(text, char_px))
    rows = label_rows(bands)
    gutter = _label_columns(rows, width, char_px, text_w)[1] if rows else 0
    x0, x1, top, bottom, x_at, y_at = _frame(
        width, height, now, seconds, text_px, char_px, bool(title), right=12 + gutter
    )
    shapes = []
    dz = max(0.0, min(100.0, float(dead)))
    if dz > 0:
        shapes.append(("rect", x0, y_at(dz), x1 - x0, y_at(-dz) - y_at(dz), "deadzone"))
    shapes += _grid(x0, x1, y_at, text_px)
    if title:
        shapes.append(("text", x0, text_px + 2, title, colour, "left"))
    shapes += _noback_shapes(noback, now, seconds, x_at, y_at, text_px)
    bands_y = [y_at(start if side == "+" else -start) for _i, side, start, _k, _n in rows]
    for (index, _side, _start, _key, _note), y in zip(rows, bands_y, strict=True):
        shapes.append(("line", x0, y, x1, y, bind_colour(index), 1.0, "dot"))
    label_shapes, _gutter = _labels(rows, bands_y, x1, width, height, text_px, char_px, text_w)
    points = [(x_at(t), y_at(v * 100)) for t, v in samples]
    if len(points) >= 2:
        shapes.append(("polyline", points, "trace", 2.0))
    shapes += _dots(
        events, x_at, y_at, len(events) <= LABEL_EVENTS_UP_TO, text_px, text_w=text_w, x_range=(x0, x1)
    )
    shapes += label_shapes
    shapes += _times(x0, x1, bottom, seconds, text_px)
    return shapes


def drawing_together(series, now, seconds, width, height, text_px=TEXT_PX, char_px=CHAR_PX):
    """Several axes on one graph, as plain shapes (see drawing()).

    `series` is [(axis name, samples, events)]; each axis's line is drawn in
    the colour named after it, and named in that colour above the plot, so
    the axes can be told apart; the dots keep their binds' colours. The binds'
    start lines and the dead zones, which differ by axis, are left to the
    separate graphs.
    """
    x0, x1, top, bottom, x_at, y_at = _frame(width, height, now, seconds, text_px, char_px, True)
    shapes = _grid(x0, x1, y_at, text_px)
    x = x0
    for name, _samples, _events in series:
        shapes.append(("text", x, text_px + 2, name, name, "left"))
        x += (len(name) + 2) * char_px
    labelled = sum(len(events) for _n, _s, events in series) <= LABEL_EVENTS_UP_TO
    for name, samples, events in series:
        points = [(x_at(t), y_at(v * 100)) for t, v in samples]
        if len(points) >= 2:
            shapes.append(("polyline", points, name, 2.0))
        shapes += _dots(events, x_at, y_at, labelled, text_px, prefix=f"{name}: ", x_range=(x0, x1))
    shapes += _times(x0, x1, bottom, seconds, text_px)
    return shapes


# The history window's view (v108.155): which axes, one graph or one each, the
# time span, the text size and the window's size; remembered between starts.
TEXT_SIZES = (1.0, 1.25, 1.5, 1.75, 2.0)
SCREEN_SHARE = 0.8  # the window opens at 80% of the screen's width and height
DEFAULT_VIEW = {"axes": ["X"], "together": False, "seconds": 10, "text_size": 1.25, "size": None}


def load_view(stored):
    """The history window's remembered view `stored`, each part checked.

    DEFAULT_VIEW fills in anything missing or wrong.
    """
    view = dict(DEFAULT_VIEW)
    if not isinstance(stored, dict):
        return view
    axes = [axis for axis in AXES if axis in (stored.get("axes") or ())]
    if axes:
        view["axes"] = axes
    view["together"] = bool(stored.get("together", False))
    if stored.get("seconds") in WINDOWS_S:
        view["seconds"] = stored["seconds"]
    try:
        size = float(stored.get("text_size", view["text_size"]))
        view["text_size"] = min(TEXT_SIZES, key=lambda choice: abs(choice - size))
    except (TypeError, ValueError):
        pass
    try:
        width, height = (int(n) for n in stored.get("size"))
        if width >= 200 and height >= 150:
            view["size"] = [width, height]
    except (TypeError, ValueError):
        pass
    return view


def fit_size(size, room, share=SCREEN_SHARE):
    """The window's size on a screen with `room` (width, height) to work in.

    The remembered `size` when there is one, else `share` of the room; never
    larger than the room.
    """
    room_w, room_h = (max(200, int(n)) for n in room)
    width, height = size if size else (round(room_w * share), round(room_h * share))
    return min(int(width), room_w), min(int(height), room_h)
