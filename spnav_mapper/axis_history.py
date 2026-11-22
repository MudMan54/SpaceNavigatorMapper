"""Axis history (v108.149): what each axis did, and what its binds sent (no Qt).

While Options > Axis History is checked, every axis panel keeps an
AxisHistory: each 16 ms sample of the axis (the device's value, before the
dead zone) and each key its binds send, with a mark where NoBack held a bind
back. The last KEEP_S seconds are kept. The history window draws them with
drawing(), which returns plain shapes, so the layout can be tested without Qt.

v108.187: ten seconds are kept and five shown (the window scrolls back over
the rest); each key-up carries how long its key was held and each tap its Tap
Dwell; key_log() lists the keys as rows of text that stand still while the
graph scrolls. v108.188: history_beside() puts the window beside the editor,
over the rest of the monitor, and editor_spot() says where the editor goes
meanwhile.
"""

import time
from collections import deque

from .settings import AXES

KEEP_S = 10.0  # seconds kept per axis (v108.187: 10; it was 30)
VIEW_S = 5  # seconds shown at a time; the window scrolls back over the rest of KEEP_S

# What a bind did (an event).
DOWN, UP, TAP, MACRO, HELD, NOBACK_UP = "down", "up", "tap", "macro", "held", "noback-up"
REBOUND_HELD = "rebound-held"  # v108.177: Rebound kept a bind quiet (the spring's bounce)
QUIET = (HELD, REBOUND_HELD)  # nothing sent: a bind kept from starting
EVENT_TEXT = {
    DOWN: "down",
    UP: "up",
    TAP: "tap",
    MACRO: "macro",
    HELD: "held by NoBack",
    REBOUND_HELD: "held by Rebound",
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
        # (time, kind, bind index, key text, value -1..1, ms). v108.187: ms is
        # how long the key was held (a key-up) or the tap's Tap Dwell, else None.
        self.events = deque()
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

    def add_event(self, kind, bind_index, key, value, ms=None):
        """Record what bind `bind_index` did now (`kind`), its key text, at axis value `value`.

        `ms`: how long the key was held (a key-up) or the tap's Tap Dwell, when known.
        """
        ms = None if ms is None else round(float(ms), 1)
        self.events.append((self.clock(), kind, int(bind_index), str(key or ""), float(value), ms))

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


def event_ms(event):
    """An event's ms (the key's hold time at its key-up, or the tap's Tap Dwell), or None."""
    return event[5] if len(event) > 5 else None


def base_kind(kind):
    """An event kind without its "not sent" mark."""
    return kind[len(UNSENT_PREFIX) :] if is_unsent(kind) else kind


def ms_text(ms):
    """'43 ms' for a time in ms ('' for None); tenths below 10 ms."""
    if ms is None:
        return ""
    return f"{ms:.1f} ms" if 0 < ms < 10 else f"{ms:.0f} ms"


def event_label(kind, ms=None):
    """An event's words for a dot's label: "up · held 43 ms", "tap · 175 ms", "down"."""
    text = EVENT_TEXT[kind]
    if ms is None:
        return text
    base = base_kind(kind)
    if base in (UP, NOBACK_UP):
        return f"{text} · held {ms_text(ms)}"
    if base == TAP:
        return f"{text} · {ms_text(ms)}"
    return text


def key_log(series):
    """The keys of one or more axes as rows of plain facts, oldest first (v108.187).

    `series` is [(axis name, samples, events)]. A press and its key-up make one
    row. Each row is a dict: "t" (when it started), "axis", "bind" (index),
    "key", "what" ("held", "down" while still held, "up", "tap", "macro",
    "held by NoBack", "held by Rebound"), "ms" (how long the key was down: a
    hold's time, a tap's Tap Dwell; None when not known), "value" and
    "end_value" (the axis in percent at the press and at the key-up), "sent"
    (False: output was off, it would have been sent), "by_noback" (NoBack let
    the key go) and "gap_ms" (the time since the row before it started).
    """
    rows = []
    for order, (axis, _samples, events) in enumerate(series):
        holding = {}  # (bind index, sent) -> its row, until the key-up
        for event in sorted(events, key=lambda e: e[0]):
            t, kind, index, key, value = event[:5]
            ms, base, sent = event_ms(event), base_kind(kind), not is_unsent(kind)
            row = {
                "t": t,
                "order": order,
                "axis": axis,
                "bind": index,
                "key": key,
                "what": EVENT_TEXT.get(base, base),
                "ms": ms,
                "value": value * 100.0,
                "end_value": None,
                "sent": sent,
                "by_noback": False,
                "gap_ms": None,
            }
            if base == DOWN:
                holding[(index, sent)] = row
            elif base in (UP, NOBACK_UP):
                press = holding.pop((index, sent), None)
                if press is not None:  # the key-up of a press in view: one row for both
                    press.update(
                        what="held",
                        ms=ms if ms is not None else (t - press["t"]) * 1000.0,
                        end_value=value * 100.0,
                        by_noback=base == NOBACK_UP,
                    )
                    continue
                row.update(what="up", by_noback=base == NOBACK_UP)
            elif kind in QUIET:
                row.update(sent=True)  # nothing was to be sent: NoBack or Rebound kept the bind quiet
            rows.append(row)
    rows.sort(key=lambda r: (r["t"], r["order"], r["bind"]))
    for before, row in zip(rows, rows[1:]):
        row["gap_ms"] = (row["t"] - before["t"]) * 1000.0
    return rows


def key_log_text(row):
    """One row of key_log() in words: "held 43 ms (NoBack let go)", "tap 175 ms (not sent)"."""
    what = row["what"]
    text = what
    if what in ("held", "tap") and row["ms"] is not None:
        text = f"{what} {ms_text(row['ms'])}"
    elif what == "up" and row["ms"] is not None:
        text = f"up after {ms_text(row['ms'])}"
    elif what == "down":
        text = "down, still held"
    if row["by_noback"]:
        text += " (NoBack let go)"
    if not row["sent"]:
        text += " (not sent)"
    return text


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
    held = settled = 0
    words = {DOWN: "pressed", TAP: "tapped", MACRO: "played"}
    for event in events:
        kind, index = event[1], event[2]
        base = base_kind(kind)
        if kind == HELD:
            held += 1
        elif kind == REBOUND_HELD:
            settled += 1
        elif base in words:
            key = (index, is_unsent(kind), words[base])
            counts[key] = counts.get(key, 0) + 1
    for (index, not_sent, word), count in sorted(counts.items()):
        parts.append(f"Bind #{index + 1} {word} {count}×" + (" (not sent)" if not_sent else ""))
    if held:
        parts.append(f"NoBack held {held}×")
    if settled:
        parts.append(f"Rebound held {settled}×")
    return " · ".join(parts)


def series_start(series):
    """The time of the first sample or event of `series` ([(axis name, samples, events)]); None when empty."""
    firsts = [s[0][0] for _a, s, _e in series if s] + [min(e[0] for e in ev) for _a, _s, ev in series if ev]
    return min(firsts) if firsts else None


def csv_rows(series):
    """Rows for a CSV file of one or more axes: a header, then every sample and event in time order.

    `series` is [(axis name, samples, events)]; times are seconds from the first of them.
    v108.187: the last column, held_ms, is how long the key was down: at a
    key-up the time it was held, at a tap its Tap Dwell.
    """
    rows = [("axis", "time_s", "value_percent", "event", "bind", "key", "held_ms")]
    start = series_start(series)
    if start is None:
        return rows
    merged = []
    for order, (axis, samples, events) in enumerate(series):
        merged += [(t, order, 0, axis, f"{v * 100:.1f}", "", "", "", "") for t, v in samples]
        for event in events:
            t, kind, i, key, v = event[:5]
            ms = event_ms(event)
            held = "" if ms is None else f"{ms:.1f}"
            merged.append(
                (t, order, 1, axis, f"{v * 100:.1f}", EVENT_TEXT[kind], f"Bind #{i + 1}", key, held)
            )
    for t, _order, _kind, axis, value, event, bind, key, held in sorted(merged):
        rows.append((axis, f"{t - start:.3f}", value, event, bind, key, held))
    return rows


# The colours behind the names drawing() uses (red, green, blue, alpha). They
# are here, without Qt, for the window and for the export's chart (v108.187).
COLOURS = {
    "deadzone": (148, 163, 184, 45),
    "grid": (51, 65, 85, 255),
    "label": (148, 163, 184, 255),
    "trace": (255, 255, 255, 255),  # the axis's line (v108.159: white)
    "plus100": (34, 197, 94, 255),  # the +100% line: green
    "zero": (59, 130, 246, 255),  # the 0 line: blue
    "minus100": (239, 68, 68, 255),  # the −100% line: red
    "noback": (226, 232, 240, 255),  # NoBack, light like the NoBack line on the Bind buttons
    # Each bind's basic colour, the same on every axis (v108.159).
    "bind1": (248, 82, 82, 255),  # red
    "bind2": (251, 146, 60, 255),  # orange
    "bind3": (250, 214, 21, 255),  # yellow
    "bind4": (74, 222, 128, 255),  # green
    "bind5": (96, 165, 250, 255),  # blue
    "bind6": (192, 132, 252, 255),  # purple
}
OUTLINE = (11, 18, 32)  # the graph's background: a ring around each filled dot
AXIS_COLOURS = {  # each axis's line, dots and name
    "X": (45, 212, 191),
    "Y": (96, 165, 250),
    "Z": (250, 204, 21),
    "Rx": (244, 114, 182),
    "Ry": (163, 230, 53),
    "Rz": (192, 132, 252),
}


def colour_rgba(name):
    """(red, green, blue, alpha) of a colour name from drawing(): an axis's, else a named one."""
    if name in AXIS_COLOURS:
        return (*AXIS_COLOURS[name], 255)
    return COLOURS.get(name, COLOURS["label"])


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


def _times(x0, x1, bottom, seconds, text_px, ago=0.0):
    """ "−10 s", "−5 s" and "now" under the plot; scrolled back `ago` seconds, "−7 s", "−4.5 s", "−2 s"."""
    seconds = max(0.1, float(seconds))
    ago = max(0.0, round(float(ago), 2))
    y = bottom + text_px + 5
    return [
        ("text", x0, y, f"−{round(seconds + ago, 2):g} s", "label", "left"),
        ("text", (x0 + x1) / 2, y, f"−{round(seconds / 2 + ago, 2):g} s", "label", "center"),
        ("text", x1, y, f"−{ago:g} s" if ago > 0 else "now", "label", "right"),
    ]


def _text_box(shape, text_px, text_w):
    """The box (left, top, right, bottom) a left-aligned "text" shape covers."""
    _kind, x, y, text = shape[:4]
    return (x, y - text_px * 0.8, x + text_w(text), y + text_px * 0.2)


def _dots(events, x_at, y_at, labelled, text_px, prefix="", text_w=None, x_range=None, avoid=()):
    """A dot for each key in its bind's colour: filled when sent, hollow when not sent
    (output off); a hollow light dot where NoBack or Rebound held a bind back.

    Each label goes beside its dot where it covers no dot, no label placed
    before it and none of the boxes in `avoid` (v108.187: NoBack's labels),
    inside `x_range` (above or below, right or left; v108.159), or is left
    out: the dot's colour still names the bind.
    """
    text_w = text_w or (lambda text: text_width(text))
    shapes = []
    radius = max(5.0, round(text_px * 0.35, 1))
    gap = radius + 2.5
    placed = [
        (x_at(e[0]) - radius, y_at(e[4] * 100) - radius, x_at(e[0]) + radius, y_at(e[4] * 100) + radius)
        for e in events
    ] + list(avoid)
    for event in events:
        t, kind, index, key, value = event[:5]
        x, y = x_at(t), y_at(value * 100)
        colour = "noback" if kind in QUIET else bind_colour(index)
        shapes.append(("circle", x, y, radius, colour, kind not in QUIET and not is_unsent(kind)))
        if not labelled:
            continue
        text = f"{prefix}{key} {event_label(kind, event_ms(event))}".strip()
        w = text_w(text)
        above, below = y - gap, y + gap + round(text_px * 0.75)
        tries = [(x + gap, above), (x + gap, below), (x - gap - w, above), (x - gap - w, below)]
        if value < 0:  # below the line first on the − side
            tries = [tries[1], tries[0], tries[3], tries[2]]
        # v108.187: then one and two lines further away, before the label is given up.
        step = text_px + 2
        near = list(tries)
        for lines in (1, 2):
            tries += [(left, base + (step if base > y else -step) * lines) for left, base in near]
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
    ago=0.0,
    labelled=None,
):
    """One axis's graph as plain shapes, for a widget `width` × `height` pixels.

    `now` is the time at the plot's right edge; `ago` says how many seconds
    before the present that is (the window scrolled back), for the times
    under the plot. `labelled`: False leaves the dots without their labels
    (the live window: text that moves cannot be read), True labels them
    however many, None labels them unless there are too many.

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
    noback_shapes = _noback_shapes(noback, now, seconds, x_at, y_at, text_px)
    shapes += noback_shapes
    bands_y = [y_at(start if side == "+" else -start) for _i, side, start, _k, _n in rows]
    for (index, _side, _start, _key, _note), y in zip(rows, bands_y, strict=True):
        shapes.append(("line", x0, y, x1, y, bind_colour(index), 1.0, "dot"))
    label_shapes, _gutter = _labels(rows, bands_y, x1, width, height, text_px, char_px, text_w)
    points = [(x_at(t), y_at(v * 100)) for t, v in samples]
    if len(points) >= 2:
        shapes.append(("polyline", points, "trace", 2.0))
    if labelled is None:
        labelled = len(events) <= LABEL_EVENTS_UP_TO
    avoid = [_text_box(shape, text_px, text_w) for shape in noback_shapes if shape[0] == "text"]
    shapes += _dots(events, x_at, y_at, labelled, text_px, text_w=text_w, x_range=(x0, x1), avoid=avoid)
    shapes += label_shapes
    shapes += _times(x0, x1, bottom, seconds, text_px, ago)
    return shapes


def drawing_together(
    series, now, seconds, width, height, text_px=TEXT_PX, char_px=CHAR_PX, ago=0.0, labelled=None
):
    """Several axes on one graph, as plain shapes (see drawing(), also for `ago` and `labelled`).

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
    if labelled is None:
        labelled = sum(len(events) for _n, _s, events in series) <= LABEL_EVENTS_UP_TO
    for name, samples, events in series:
        points = [(x_at(t), y_at(v * 100)) for t, v in samples]
        if len(points) >= 2:
            shapes.append(("polyline", points, name, 2.0))
        shapes += _dots(events, x_at, y_at, labelled, text_px, prefix=f"{name}: ", x_range=(x0, x1))
    shapes += _times(x0, x1, bottom, seconds, text_px, ago)
    return shapes


# The history window's view (v108.155): which axes, one graph or one each, the
# text size and the window's size; remembered between starts. v108.187: and
# whether it is attached to the editor (the time span is no longer a choice:
# VIEW_S seconds are shown, the window scrolls back over the rest).
TEXT_SIZES = (1.0, 1.25, 1.5, 1.75, 2.0)
SCREEN_SHARE = 0.8  # not attached, the window opens at 80% of the screen's width and height
# v108.188: and where the editor goes on each monitor while the attached window is open.
DEFAULT_VIEW = {
    "axes": ["X"],
    "together": False,
    "text_size": 1.25,
    "size": None,
    "attached": True,
    "legend": False,
    "editor_spots": {},
}
FREEZE_BUTTON = 1  # v108.188: the puck's Button 1 freezes the graphs while the window is open


def load_view(stored):
    """The history window's remembered view `stored`, each part checked.

    DEFAULT_VIEW fills in anything missing or wrong.
    """
    view = dict(DEFAULT_VIEW)
    view["editor_spots"] = {}  # its own, not DEFAULT_VIEW's
    if not isinstance(stored, dict):
        return view
    axes = [axis for axis in AXES if axis in (stored.get("axes") or ())]
    if axes:
        view["axes"] = axes
    view["together"] = bool(stored.get("together", False))
    view["attached"] = bool(stored.get("attached", True))
    view["legend"] = bool(stored.get("legend", False))
    view["editor_spots"] = clean_spots(stored.get("editor_spots"))
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


# v108.187: the Axis History window attached to the editor's right side.
# v108.188: opening it moves the editor aside (to the top left of its monitor,
# or where it was last put while the window was open) and the window takes the
# rest of the monitor at full height; closing it puts the editor back.
DOCK_MIN_WIDTH = 640  # the least width the attached window is given (before scaling)
SPOT_KEEP = 120  # at least this much of the editor stays on its monitor, each way


def editor_spot(editor, area, remembered=None, bleed=0):
    """Where the editor goes while the attached Axis History window is open (v108.188).

    `editor` is the editor's (x, y, width, height): its frame's corner and its
    own size; `area` the work area of its monitor. Returns the same four for
    the time the window is open. Without `remembered`: the top left of the
    area, the size unchanged (`bleed` pixels of the frame's invisible left
    border go past the screen's edge, so the editor looks flush with it).
    `remembered` is [dx, dy, width, height] from spot_to_remember(): where the
    editor was last put while the window was open, from the area's corner,
    and its size then (None, None: its size is left as it is). A remembered
    place is kept on the monitor; a size larger than the area is not used.
    """
    _x, _y, width, height = (int(n) for n in editor)
    ax, ay, aw, ah = (int(n) for n in area)
    bleed = max(0, int(bleed))
    dx, dy = -bleed, 0
    try:
        dx, dy = int(remembered[0]), int(remembered[1])
        if remembered[2] is not None and remembered[3] is not None:
            w, h = int(remembered[2]), int(remembered[3])
            if 200 <= w <= aw + 64 and 150 <= h <= ah + 64:
                width, height = w, h
    except (IndexError, KeyError, TypeError, ValueError):
        pass
    dx = max(-bleed, min(dx, aw - SPOT_KEEP))
    dy = max(0, min(dy, ah - SPOT_KEEP))
    return ax + dx, ay + dy, width, height


def spot_to_remember(editor, area, size_at_open):
    """[dx, dy, width, height] to remember for editor_spot(): the editor's place from its
    monitor's corner and, when it is no longer `size_at_open`, its size (else None, None)."""
    x, y, width, height = (int(n) for n in editor)
    ax, ay, _aw, _ah = (int(n) for n in area)
    resized = (width, height) != tuple(int(n) for n in size_at_open)
    return [x - ax, y - ay, width if resized else None, height if resized else None]


def clean_spots(stored):
    """The remembered editor places per monitor, {monitor name: [dx, dy, width, height]}, checked."""
    spots = {}
    if not isinstance(stored, dict):
        return spots
    for name, spot in stored.items():
        try:
            dx, dy, width, height = spot
            sized = width is not None and height is not None
            spots[str(name)] = [
                int(dx),
                int(dy),
                int(width) if sized else None,
                int(height) if sized else None,
            ]
        except (TypeError, ValueError):
            continue
    return spots


def history_beside(editor, area, min_width=DOCK_MIN_WIDTH, overlap=0, bleed=(0, 0)):
    """The attached Axis History window's frame (x, y, width, height) (v108.188).

    From the right edge of the editor's frame `editor` to the right edge of
    the work area `area`, over the area's full height, whatever the editor's
    own height. `overlap` pixels of the two frames' invisible borders are laid
    over each other, so the windows look joined; `bleed` (right, bottom)
    pixels of this window's invisible borders go past the screen's edges, so
    it looks flush with them. With less than `min_width` beside the editor,
    the window keeps `min_width` at the area's right edge and covers the
    editor's right side.
    """
    ex, _ey, ew, _eh = (int(n) for n in editor)
    ax, ay, aw, ah = (int(n) for n in area)
    right = ax + aw + max(0, int(bleed[0]))
    bottom = ay + ah + max(0, int(bleed[1]))
    min_width = max(1, min(int(min_width), aw))
    width = max(min_width, right - (ex + ew - int(overlap)))
    return right - width, ay, width, max(1, bottom - ay)
