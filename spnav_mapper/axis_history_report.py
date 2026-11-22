"""The Axis History export's chart report (v108.187): one HTML file, no Qt.

Export in the Axis History window writes the CSV as before and, beside it, a
report to open in a browser: for each axis shown a chart of the whole capture
(the same shapes the window draws, as SVG), every setting of that axis's
binds with the ones that fired marked, and the keys in time order with how
long each was held. The file stands alone: no pictures or scripts to fetch.
"""

import html

from .axis_history import (
    DOWN,
    KEEP_S,
    MACRO,
    OUTLINE,
    TAP,
    base_kind,
    bind_bands,
    bind_colour,
    colour_rgba,
    drawing,
    is_unsent,
    key_log,
    key_log_text,
    ms_text,
    series_start,
    summary,
)

CHART_SIZE = (1200, 380)  # the chart's own pixels; the page scales it to its width
CHART_TEXT_PX, CHART_CHAR_PX, CHART_FONT_PX = 16, 8, 13
MODES_THAT_TAP = ("Press/Release", "Press/Repeat", "Tick", "Macro")
DIRECTIONS = {"Plus": "POS (+)", "Minus": "NEG (-)", "Full": "Full", None: "[None]"}


def _css_colour(name):
    """A colour name from drawing() as CSS: "rgb(…)" or "rgba(…)"."""
    r, g, b, a = colour_rgba(name)
    return f"rgb({r},{g},{b})" if a >= 255 else f"rgba({r},{g},{b},{a / 255:.2f})"


def _n(value):
    """A coordinate with at most one decimal."""
    return f"{value:.1f}".rstrip("0").rstrip(".")


def svg(shapes, width, height, font_px=CHART_FONT_PX):
    """The shapes of axis_history.drawing() as one SVG picture `width` × `height`."""
    background = "rgb({},{},{})".format(*OUTLINE)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
        f'font-family="Segoe UI, Arial, sans-serif" font-size="{font_px}" role="img">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{background}"/>',
    ]
    anchors = {"left": "start", "right": "end", "center": "middle"}
    for shape in shapes:
        kind = shape[0]
        if kind == "rect":
            _, x, y, w, h, colour = shape
            out.append(
                f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" fill="{_css_colour(colour)}"/>'
            )
        elif kind == "line":
            _, x1, y1, x2, y2, colour, stroke, dashed = shape
            dash = (
                ' stroke-dasharray="2 4"' if dashed == "dot" else ' stroke-dasharray="7 5"' if dashed else ""
            )
            out.append(
                f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
                f'stroke="{_css_colour(colour)}" stroke-width="{_n(stroke)}"{dash}/>'
            )
        elif kind == "polyline":
            _, points, colour, stroke = shape
            path = " ".join(f"{_n(x)},{_n(y)}" for x, y in points)
            out.append(
                f'<polyline points="{path}" fill="none" stroke="{_css_colour(colour)}" '
                f'stroke-width="{_n(stroke)}" stroke-linejoin="round"/>'
            )
        elif kind == "circle":
            _, x, y, r, colour, filled = shape
            paint = (
                f'fill="{_css_colour(colour)}" stroke="{background}" stroke-width="1.5"'
                if filled
                else f'fill="none" stroke="{_css_colour(colour)}" stroke-width="2"'
            )
            out.append(f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{_n(r)}" {paint}/>')
        elif kind == "text":
            _, x, y, text, colour, align = shape
            # A rim in the background's colour keeps a label readable where it crosses a line.
            out.append(
                f'<text x="{_n(x)}" y="{_n(y)}" fill="{_css_colour(colour)}" stroke="{background}" '
                f'stroke-width="3.5" stroke-linejoin="round" paint-order="stroke" '
                f'text-anchor="{anchors.get(align, "start")}">{html.escape(str(text))}</text>'
            )
    out.append("</svg>")
    return "\n".join(out)


def bind_table(binds, dead, key_text, profile_tap_ms=45, fired=None):
    """Every setting of an axis's binds, one row (a dict of texts) per bind that is set up.

    `binds` are the axis panel's binds, `dead` the axis's dead zone,
    `key_text(bind)` names a bind's key and `fired` counts what each bind
    index did in the capture ({index: "pressed 2×"}). A bind with neither a
    key nor a Bind Dir is left out.
    """
    fired = fired or {}
    signs = {"+": "", "-": "−", "+-": "±"}
    starts = {band[0]: f"{signs.get(band[1], '')}{band[2]}%" for band in bind_bands(binds, dead, key_text)}
    rows = []
    for index, bind in enumerate(binds):
        mode = bind.get("mode") or "Hold"
        key = key_text(bind)
        if not key and not bind.get("direction"):
            continue
        tick, hold = mode == "Tick", mode == "Hold"
        noback = "".join(
            sign
            for side, sign, name in (("+", "−", "noback_plus"), ("-", "+", "noback_minus"))
            if bind.get(name)
            and not tick
            and bind.get("direction") in ("Full", "Plus" if side == "+" else "Minus")
        )
        try:
            tap_ms = int(bind.get("tap_ms", profile_tap_ms))
        except (TypeError, ValueError):
            tap_ms = int(profile_tap_ms)
        hold_ms = int(bind.get("min_hold_ms") or 0)
        settle = int(bind.get("settle_ms") or 0)
        rows.append(
            {
                "index": index,
                "bind": f"Bind #{index + 1}",
                "key": key,
                "dir": DIRECTIONS.get(bind.get("direction"), "[None]"),
                "mode": mode + (" (repeats)" if mode == "Macro" and bind.get("macro_repeat") else ""),
                "start": starts.get(index, ""),
                "min": f"Tick {int(bind.get('min', 0))}%" if tick else f"{int(bind.get('min', 0))}%",
                "max": "" if tick else f"{int(bind.get('max', 100))}%",
                "dead": "" if tick else f"{int(bind.get('dead', dead))}%",
                "tap": f"{tap_ms} ms" if mode in MODES_THAT_TAP else "",
                "hold": (f"{hold_ms} ms" if hold_ms else "0 (off)") if hold else "",
                "repeat": f"{int(bind.get('repeat_ms', 100))} ms"
                if mode == "Press/Repeat" or (mode == "Macro" and bind.get("macro_repeat"))
                else "",
                "noback": f"NoBack {' '.join(noback)}" if noback else "",
                "rebound": f"{settle} ms" if settle and (tick or noback) else "",
                "on": "" if bind.get("enabled", True) else "switched off",
                "fired": fired.get(index, ""),
                "comment": str(bind.get("comment") or ""),
            }
        )
    return rows


def fired_counts(events):
    """{bind index: "pressed 2× · tapped 1×"} for the events of one axis ("not sent" marked)."""
    words = {DOWN: "pressed", TAP: "tapped", MACRO: "played"}
    counts = {}
    for event in events:
        kind, index = event[1], event[2]
        base = base_kind(kind)
        if base in words:
            key = (index, words[base], is_unsent(kind))
            counts[key] = counts.get(key, 0) + 1
    out = {}
    for (index, word, not_sent), count in sorted(counts.items()):
        text = f"{word} {count}×" + (" (not sent)" if not_sent else "")
        out[index] = f"{out[index]} · {text}" if index in out else text
    return out


BIND_COLUMNS = (
    ("bind", "Bind"),
    ("key", "Key"),
    ("dir", "Bind Dir"),
    ("mode", "Mode"),
    ("start", "Starts at"),
    ("min", "Min% / Tick%"),
    ("max", "Max%"),
    ("dead", "DZone"),
    ("tap", "Tap Dwell"),
    ("hold", "Min Hold"),
    ("repeat", "Repeat every"),
    ("noback", "NoBack"),
    ("rebound", "Rebound"),
    ("on", "Enabled"),
    ("fired", "In this capture"),
    ("comment", "Comment"),
)
OPTIONAL_COLUMNS = ("repeat", "rebound", "on")  # left out of the table when no bind of the axis has one


def bind_columns(rows):
    """BIND_COLUMNS without the optional columns that are empty in every row."""
    return tuple(
        column
        for column in BIND_COLUMNS
        if column[0] not in OPTIONAL_COLUMNS or any(row.get(column[0]) for row in rows)
    )


PAGE_CSS = """
body{background:#0f172a;color:#e2e8f0;font-family:"Segoe UI",Arial,sans-serif;font-size:14px;margin:18px;}
h1{font-size:20px;margin:0 0 4px 0;} h2{font-size:17px;margin:26px 0 6px 0;} h3{font-size:14px;margin:14px 0 4px 0;}
p{margin:4px 0;} .dim{color:#94a3b8;} .chart{border:1px solid #334155;border-radius:5px;overflow:hidden;margin:6px 0;}
.wide{overflow-x:auto;} table{border-collapse:collapse;margin:4px 0 8px 0;}
th,td{border:1px solid #334155;padding:3px 8px;text-align:left;white-space:nowrap;}
th{background:#1f2937;font-weight:600;} td.num{text-align:right;font-variant-numeric:tabular-nums;}
tr.fired td{background:#172554;} tr.quiet td{color:#94a3b8;} .note{border:1px solid #b91c1c;border-radius:5px;
padding:6px 10px;margin:8px 0;white-space:pre-wrap;} .swatch{display:inline-block;width:10px;height:10px;
border-radius:5px;margin-right:6px;}
"""


def _table(columns, rows, row_class=None):
    """An HTML table: `columns` is [(key, heading)] or [(key, heading, "num")], `rows` dicts of texts."""
    head = "".join(f"<th>{html.escape(column[1])}</th>" for column in columns)
    lines = [f"<div class='wide'><table><tr>{head}</tr>"]
    for row in rows:
        cells = []
        for column in columns:
            css = ' class="num"' if len(column) > 2 else ""
            cells.append(
                f"<td{css}>{row.get('_html_' + column[0]) or html.escape(str(row.get(column[0], '')))}</td>"
            )
        css = row_class(row) if row_class else ""
        lines.append(f"<tr{' class=' + chr(34) + css + chr(34) if css else ''}>{''.join(cells)}</tr>")
    lines.append("</table></div>")
    return "\n".join(lines)


def _swatch(index):
    """A dot in a bind's colour, as in the chart."""
    return f'<span class="swatch" style="background:{_css_colour(bind_colour(index))}"></span>'


def key_rows(series):
    """The keys of `series` in time order as dicts of texts, for the report's table."""
    start = series_start(series)
    rows = []
    for row in key_log(series):
        rows.append(
            {
                "time": f"{row['t'] - (start or 0.0):.3f}",
                "gap": "" if row["gap_ms"] is None else ms_text(row["gap_ms"]),
                "axis": row["axis"],
                "bind": f"Bind #{row['bind'] + 1}",
                "_html_bind": _swatch(row["bind"]) + f"Bind #{row['bind'] + 1}",
                "key": row["key"],
                "what": key_log_text(row),
                "ms": "" if row["ms"] is None else f"{row['ms']:.0f}",
                "value": f"{row['value']:+.0f}%",
                "end": "" if row["end_value"] is None else f"{row['end_value']:+.0f}%",
                "sent": row["sent"],
            }
        )
    return rows


def report_html(meta, axes):
    """The whole report as one HTML page.

    `meta` is a dict of texts about the capture ("version", "saved",
    "profile", "target", "mode", "state", "timing", "note", "important",
    "csv", "not_shown"); `axes` is a list of dicts, one per axis shown:
    "axis", "samples", "events", "binds" (the panel's binds), "dead",
    "noback" (AxisHistory.noback_span()), "now" (the capture's end) and
    "key_text" (names a bind's key).
    """
    width, height = CHART_SIZE
    esc = html.escape
    out = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>Axis History — {esc(meta.get('profile') or 'no profile')}</title>",
        f"<style>{PAGE_CSS}</style></head><body>",
        "<h1>SpaceNavigator Mapper — Axis History</h1>",
        f"<p class='dim'>{esc(meta.get('version', ''))} · saved {esc(meta.get('saved', ''))} · "
        f"the last {KEEP_S:g} seconds{' before Pause' if meta.get('paused') else ''}</p>",
        f"<p>Profile: <b>{esc(meta.get('profile') or '[None]')}</b>"
        + (f" · Target: {esc(meta['target'])}" if meta.get("target") else "")
        + (f" · {esc(meta['mode'])}" if meta.get("mode") else "")
        + (f" · {esc(meta['state'])}" if meta.get("state") else "")
        + "</p>",
    ]
    if meta.get("timing"):
        out.append(f"<p class='dim'>Profile timing: {esc(meta['timing'])}</p>")
    if meta.get("note"):
        label = "Important profile note" if meta.get("important") else "Profile note"
        out.append(f"<div class='note'><b>{label}:</b> {esc(meta['note'])}</div>")
    series = [(a["axis"], a["samples"], a["events"]) for a in axes]
    for a in axes:
        fired = fired_counts(a["events"])
        bands = bind_bands(a["binds"], a["dead"], a["key_text"])
        shapes = drawing(
            a["samples"],
            a["events"],
            bands,
            a["dead"],
            a["now"],
            KEEP_S,
            width,
            height,
            title=a["axis"],
            colour=a["axis"],
            text_px=CHART_TEXT_PX,
            char_px=CHART_CHAR_PX,
            noback=a.get("noback") or (),
        )
        rows = bind_table(a["binds"], a["dead"], a["key_text"], meta.get("tap_down_ms", 45), fired)
        for row in rows:
            row["_html_bind"] = _swatch(row["index"]) + esc(row["bind"])
        out += [
            f"<h2>{esc(a['axis'])} axis</h2>",
            f"<p>{esc(summary(a['samples'], a['events']))} · axis dead zone {int(a['dead'])}%</p>",
            f"<div class='chart'>{svg(shapes, width, height)}</div>",
            "<h3>Binds of this axis (the ones that fired are highlighted)</h3>",
            _table(bind_columns(rows), rows, lambda row: "fired" if row["fired"] else "quiet")
            if rows
            else "<p class='dim'>No bind is set up on this axis.</p>",
        ]
    keys = key_rows(series)
    out.append("<h2>Keys, in time order</h2>")
    if keys:
        out.append(
            "<p class='dim'>Time: seconds from the start of the capture (as in the CSV). After the one before: "
            "the time since the row above started. Key down: how long the key was down "
            "(a hold's time, a tap's Tap Dwell).</p>"
        )
        out.append(
            _table(
                (
                    ("time", "Time (s)", "num"),
                    ("gap", "After the one before", "num"),
                    ("axis", "Axis"),
                    ("bind", "Bind"),
                    ("key", "Key"),
                    ("what", "What"),
                    ("ms", "Key down (ms)", "num"),
                    ("value", "Axis at the press", "num"),
                    ("end", "Axis at the key-up", "num"),
                ),
                keys,
                lambda row: "" if row["sent"] else "quiet",
            )
        )
    else:
        out.append("<p class='dim'>No bind did anything in this capture.</p>")
    if meta.get("not_shown"):
        out.append(
            f"<p class='dim'>Binds also fired on {esc(meta['not_shown'])}: tick those axes in the "
            "Axis History window to export them too.</p>"
        )
    out.append(
        "<p class='dim'>White line: the axis. Dashed: +100% (green), 0 (blue), −100% (red). Dotted, in each "
        "bind's colour: where the bind starts. Dots: keys, filled when sent, hollow when not sent "
        "(output was off) or held back by NoBack or Rebound (light)."
        + (f" The samples are in {esc(meta['csv'])}." if meta.get("csv") else "")
        + "</p>"
    )
    out.append("</body></html>")
    return "\n".join(out)
