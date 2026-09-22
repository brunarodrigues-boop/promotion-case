"""Inline SVG charts for the systems page.

Everything is generated rather than hand-drawn so a number on the page cannot
drift from the number in the data file behind it. No JS and no chart library:
the page has to survive being emailed around and opened offline.
"""

PURPLE = "#8b7dc8"
PURPLE_D = "#6f5fb0"
INK = "#1a1a1a"
GREY = "#999"
LINE = "#e0daf0"
AMBER = "#e0a33e"
RED = "#d3736b"
GREEN = "#6fae86"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _band(v, good, ok):
    """Colour by value, so a reader can scan for the weak rows."""
    if v >= good:
        return GREEN
    if v >= ok:
        return AMBER
    return RED


def hbars(rows, unit="%", width=680, rowh=26, label_w=150, vmin=0, vmax=None,
          good=None, ok=None, note_w=96, colour=PURPLE, steps=None):
    """Horizontal bars. rows = [(label, value, note)].

    vmin is deliberately settable: accuracy between 60 and 95 on a 0-100 axis
    is a row of near-identical bars, which hides exactly the differences the
    chart exists to show.
    """
    bar_w = width - label_w - note_w - 16
    h = len(rows) * rowh + 26
    # From zero, let the step decide the top so the labels are round numbers.
    if vmax is None:
        vmax, _, steps = nice_axis(max([r[1] for r in rows] + [1]))
    out = [f'<svg viewBox="0 0 {width} {h}" width="100%" height="{h}" '
           f'role="img" class="chart">']
    span = (vmax - vmin) or 1

    # axis gridlines
    steps = steps or 5
    for i in range(steps + 1):
        v = vmin + span * i / steps
        x = label_w + bar_w * i / steps
        out.append(f'<line x1="{x:.1f}" y1="14" x2="{x:.1f}" y2="{h-20}" '
                   f'stroke="{LINE}" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{h-8}" font-size="9" fill="{GREY}" '
                   f'text-anchor="middle">{v:.0f}{unit}</text>')

    for i, (lab, val, note) in enumerate(rows):
        y = 18 + i * rowh
        w = max(1.0, bar_w * (min(val, vmax) - vmin) / span) if val > vmin else 1.0
        col = _band(val, good, ok) if good is not None else colour
        out.append(f'<text x="{label_w-8}" y="{y+12}" font-size="11" fill="{INK}" '
                   f'text-anchor="end">{esc(lab)}</text>')
        out.append(f'<rect x="{label_w}" y="{y+2}" width="{w:.1f}" height="{rowh-10}" '
                   f'rx="3" fill="{col}" opacity="0.88"/>')
        out.append(f'<text x="{label_w+w+7:.1f}" y="{y+12}" font-size="10.5" '
                   f'font-weight="700" fill="{INK}">{val:g}{unit}</text>')
        if note:
            out.append(f'<text x="{width-4}" y="{y+12}" font-size="9.5" fill="{GREY}" '
                       f'text-anchor="end">{esc(note)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def nice_axis(v, divisions=4):
    """An axis top and step a person would have chosen.

    Picking the top first and then dividing by four gives ticks like 62.5 and
    187.5. Picking the *step* first and letting the top follow gives round
    numbers, which is the only thing an axis label is for.
    """
    import math
    if v <= 0:
        return 1, 1, 1
    raw = v / divisions
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = next((m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag), 10 * mag)
    top = step * math.ceil(v / step)
    return top, step, int(round(top / step))


def vbars(rows, width=680, height=190, unit="", colour=PURPLE, highlight=None,
          vmax=None, rotate=None):
    """Vertical bars. rows = [(label, value, caption)]."""
    pad_l, pad_b, pad_t = 38, 34, 14
    # Long labels under narrow bars collide, so tip them when they cannot fit.
    longest = max((len(str(r[0])) for r in rows), default=0)
    slot = (width - pad_l - 10) / max(1, len(rows))
    if rotate is None:
        rotate = longest * 5.6 > slot
    if rotate:
        pad_b = 30 + min(52, int(longest * 3.6))
    bw = (width - pad_l - 10) / max(1, len(rows))
    if vmax:
        ticks = 4
        step = vmax / ticks
    else:
        vmax, step, ticks = nice_axis(max([r[1] for r in rows] + [1]))
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
           f'role="img" class="chart">']
    plot_h = height - pad_b - pad_t
    for i in range(ticks + 1):
        v = step * i
        y = pad_t + plot_h - plot_h * v / vmax
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-6}" y2="{y:.1f}" '
                   f'stroke="{LINE}"/>')
        out.append(f'<text x="{pad_l-6}" y="{y+3:.1f}" font-size="9" fill="{GREY}" '
                   f'text-anchor="end">{v:,.0f}{unit}</text>')
    for i, (lab, val, cap) in enumerate(rows):
        bh = plot_h * val / vmax
        x = pad_l + i * bw + bw * 0.16
        w = bw * 0.68
        y = pad_t + plot_h - bh
        col = PURPLE_D if (highlight and lab in highlight) else colour
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{bh:.1f}" '
                   f'rx="3" fill="{col}" opacity="0.88"/>')
        out.append(f'<text x="{x+w/2:.1f}" y="{y-4:.1f}" font-size="9.5" '
                   f'font-weight="700" fill="{INK}" text-anchor="middle">'
                   f'{val:,.0f}{unit}</text>')
        base = pad_t + plot_h
        if rotate:
            out.append(f'<text x="{x+w/2:.1f}" y="{base+11:.1f}" font-size="9.5" '
                       f'fill="{GREY}" text-anchor="end" '
                       f'transform="rotate(-38 {x+w/2:.1f} {base+11:.1f})">{esc(lab)}</text>')
            if cap:
                out.append(f'<text x="{x+w/2:.1f}" y="{base+21:.1f}" font-size="8.5" '
                           f'fill="{GREY}" text-anchor="end" '
                           f'transform="rotate(-38 {x+w/2:.1f} {base+21:.1f})">{esc(cap)}</text>')
        else:
            out.append(f'<text x="{x+w/2:.1f}" y="{base+13:.1f}" font-size="9.5" '
                       f'fill="{GREY}" text-anchor="middle">{esc(lab)}</text>')
            if cap:
                out.append(f'<text x="{x+w/2:.1f}" y="{base+24:.1f}" font-size="8.5" '
                           f'fill="{GREY}" text-anchor="middle">{esc(cap)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def stacked(segments, width=680, height=42, colours=None):
    """One horizontal 100% bar. segments = [(label, n)]."""
    total = sum(n for _, n in segments) or 1
    cols = colours or [PURPLE, "#a396d6", "#bdb2e2", "#d6cfee", "#ebe6f7"]
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
           f'class="chart">']
    x = 0.0
    for i, (lab, n) in enumerate(segments):
        w = width * n / total
        out.append(f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="20" '
                   f'fill="{cols[i % len(cols)]}"/>')
        if w > 42:
            out.append(f'<text x="{x+w/2:.1f}" y="14" font-size="10" font-weight="700" '
                       f'fill="white" text-anchor="middle">{100*n/total:.0f}%</text>')
        x += w
    x = 0.0
    for i, (lab, n) in enumerate(segments):
        w = width * n / total
        if w > 58:
            out.append(f'<text x="{x+w/2:.1f}" y="34" font-size="9.5" fill="{GREY}" '
                       f'text-anchor="middle">{esc(lab)}</text>')
        x += w
    out.append("</svg>")
    return "\n".join(out)
