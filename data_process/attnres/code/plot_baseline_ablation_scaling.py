#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generate publication-ready SVG figures for baseline/scaling/ablation results."""

from pathlib import Path
import html
import math

OUT = Path(__file__).resolve().parent.parent / "pic"

BLUE = "#3B6FB6"
ORANGE = "#E07A2D"
TEAL = "#2A9D8F"
PURPLE = "#7562A8"
GOLD = "#E9C46A"
RED = "#C84C4C"
GRAY = "#65727E"
LIGHT = "#EEF2F5"
DARK = "#202A33"

NS = [1, 2, 4, 8]
DS = [1, 8, 16, 32]
B2 = [
    [1966, 1968, 1995, 1977],
    [3387, 3426, 3455, 3504],
    [6739, 6772, 6812, 6867],
    [13080, 12885, 13078, 13547],
]
B3 = [
    [1124, 1121, 1203, 1388],
    [1106, 1228, 1351, 1610],
    [1194, 1436, 1655, 2136],
    [1290, 1732, 2281, 3263],
]
SPEEDUP = [[B2[r][c] / B3[r][c] for c in range(4)] for r in range(4)]

FSM_CASES = ["(1,1)", "(8,32)", "(16,64)"]
FSM_SCALAR = [20, 160, 320]
FSM_VECTOR = [9, 2063, 8214]
FSM_OTHER = [1095, 1040, 1022]


def esc(value):
    return html.escape(str(value))


def header(width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,"Noto Sans",sans-serif;fill:#202A33}'
        '.axis{stroke:#34424F;stroke-width:1.4}.grid{stroke:#D9E0E5;stroke-width:1}'
        '.minor{fill:#65727E}.title{font-weight:700}.label{font-weight:600}</style>',
    ]


def finish(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines + ["</svg>\n"]), encoding="utf-8")


def txt(x, y, value, size=13, anchor="middle", cls="", weight=None, fill=None, rotate=None):
    attrs = []
    if cls:
        attrs.append(f'class="{cls}"')
    if weight:
        attrs.append(f'font-weight="{weight}"')
    if fill:
        attrs.append(f'fill="{fill}"')
    if rotate is not None:
        attrs.append(f'transform="rotate({rotate} {x} {y})"')
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
            + " ".join(attrs) + f'>{esc(value)}</text>')


def line(x1, y1, x2, y2, color="#34424F", width=1.4, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"{d}/>'


def rect(x, y, w, h, fill, stroke="none", radius=0, opacity=1.0):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="{fill}" stroke="{stroke}" rx="{radius}" opacity="{opacity}"/>')


def circle(x, y, r, fill, stroke="white", sw=1.5):
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def color_interp(t):
    # light blue -> teal -> gold -> orange, chosen for print legibility.
    stops = [(238, 244, 249), (111, 183, 191), (233, 196, 106), (210, 92, 54)]
    t = min(1.0, max(0.0, t))
    p = t * (len(stops) - 1)
    i = min(len(stops) - 2, int(p))
    f = p - i
    rgb = tuple(round(stops[i][j] * (1 - f) + stops[i + 1][j] * f) for j in range(3))
    return "#%02x%02x%02x" % rgb


def speedup_heatmap():
    width, height = 850, 650
    left, top = 145, 105
    cw, ch = 135, 95
    lines = header(width, height)
    lines += [txt(width / 2, 38, "SMU Speedup over RTL-Aligned RVV Baseline", 22, cls="title"),
              txt(width / 2, 65, "Direct measurements only; each cell is B2-R cycles / B3 cycles", 12, cls="minor")]
    vmin, vmax = 1.0, 10.2
    for c, d in enumerate(DS):
        lines.append(txt(left + c * cw + cw / 2, top - 20, f"D = {d}", 14, cls="label"))
    for r, n in enumerate(NS):
        lines.append(txt(left - 24, top + r * ch + ch / 2 + 5, f"N = {n}", 14, "end", "label"))
        for c, _ in enumerate(DS):
            val = SPEEDUP[r][c]
            t = (val - vmin) / (vmax - vmin)
            fill = color_interp(t)
            x, y = left + c * cw, top + r * ch
            lines.append(rect(x, y, cw - 3, ch - 3, fill, "white", 7))
            text_fill = "white" if val > 7.0 else DARK
            lines.append(txt(x + cw / 2, y + 39, f"{val:.2f}×", 22, weight="700", fill=text_fill))
            lines.append(txt(x + cw / 2, y + 65, f"{B2[r][c]} / {B3[r][c]}", 11, fill=text_fill))
    # color bar
    bx, by, bw, bh = left, top + 4 * ch + 38, 4 * cw - 3, 17
    for i in range(120):
        lines.append(rect(bx + bw * i / 120, by, bw / 120 + 0.5, bh, color_interp(i / 119)))
    for tick in [1, 2, 4, 6, 8, 10]:
        x = bx + bw * (tick - vmin) / (vmax - vmin)
        lines += [line(x, by + bh, x, by + bh + 6, DARK, 1), txt(x, by + bh + 22, f"{tick}×", 11)]
    lines.append(txt(left + 2 * cw, by + 52, "Speedup = B2-R median cycles / B3 median cycles", 12, cls="minor"))
    finish(OUT / "paper_baseline_speedup_heatmap.svg", lines)


def cycles_lines():
    width, height = 1080, 720
    left, right, top, bottom = 95, 45, 90, 95
    pw, ph = width - left - right, height - top - bottom
    ymax = 14500
    x_positions = [left + i * pw / 3 for i in range(4)]
    ymap = lambda v: top + ph * (1 - v / ymax)
    lines = header(width, height)
    lines += [txt(width / 2, 38, "Cycle Scaling across Matrix Dimensions", 22, cls="title"),
              txt(width / 2, 65, "Solid: Full SMU (B3)    Dashed: RTL-aligned RVV baseline (B2-R)", 12, cls="minor")]
    for tick in range(0, 14001, 2000):
        y = ymap(tick)
        lines += [line(left, y, width - right, y, "#D9E0E5", 1), txt(left - 12, y + 4, f"{tick:,}", 11, "end")]
    lines += [line(left, top, left, top + ph), line(left, top + ph, width - right, top + ph)]
    for i, d in enumerate(DS):
        lines.append(txt(x_positions[i], top + ph + 28, str(d), 12))
    lines += [txt(left + pw / 2, height - 25, "Vector dimension D", 14, cls="label"),
              txt(25, top + ph / 2, "Median cycles", 14, rotate=-90, cls="label")]
    colors = [BLUE, TEAL, ORANGE, PURPLE]
    for r, n in enumerate(NS):
        pts2 = " ".join(f"{x_positions[c]:.1f},{ymap(B2[r][c]):.1f}" for c in range(4))
        pts3 = " ".join(f"{x_positions[c]:.1f},{ymap(B3[r][c]):.1f}" for c in range(4))
        lines.append(f'<polyline points="{pts2}" fill="none" stroke="{colors[r]}" stroke-width="2.3" stroke-dasharray="7 5"/>')
        lines.append(f'<polyline points="{pts3}" fill="none" stroke="{colors[r]}" stroke-width="3.0"/>')
        for c in range(4):
            lines.append(circle(x_positions[c], ymap(B2[r][c]), 4.0, "white", colors[r], 2))
            lines.append(circle(x_positions[c], ymap(B3[r][c]), 4.7, colors[r]))
    # legend
    lx, ly = left + 30, top + 30
    lines += [rect(lx - 18, ly - 25, 300, 142, "white", "#CBD4DB", 6, 0.94)]
    for r, n in enumerate(NS):
        y = ly + r * 27
        lines += [line(lx, y, lx + 38, y, colors[r], 3), circle(lx + 19, y, 4.2, colors[r]),
                  txt(lx + 48, y + 4, f"N = {n}", 12, "start")]
    lines += [line(lx + 145, ly, lx + 183, ly, DARK, 3), txt(lx + 193, ly + 4, "B3", 12, "start"),
              line(lx + 145, ly + 28, lx + 183, ly + 28, DARK, 2.3, "7 5"),
              txt(lx + 193, ly + 32, "B2-R", 12, "start")]
    finish(OUT / "paper_baseline_cycles_scaling.svg", lines)


def fsm_absolute():
    width, height = 940, 650
    left, right, top, bottom = 95, 45, 85, 95
    pw, ph = width - left - right, height - top - bottom
    totals = [FSM_SCALAR[i] + FSM_VECTOR[i] + FSM_OTHER[i] for i in range(3)]
    ymax = 11000
    ymap = lambda v: top + ph * (1 - v / ymax)
    lines = header(width, height)
    lines += [txt(width / 2, 38, "Full-SMU End-to-End Cycle Decomposition", 22, cls="title"),
              txt(width / 2, 64, "Absolute cycles; command/setup/wait is non-busy overhead", 12, cls="minor")]
    for tick in range(0, 10001, 2000):
        y = ymap(tick)
        lines += [line(left, y, width - right, y, "#D9E0E5", 1), txt(left - 12, y + 4, f"{tick:,}", 11, "end")]
    lines += [line(left, top, left, top + ph), line(left, top + ph, width - right, top + ph)]
    centers = [left + pw * (i + 0.5) / 3 for i in range(3)]
    barw = 115
    for i, x in enumerate(centers):
        accum = 0
        for val, color, label in [(FSM_OTHER[i], GRAY, "Other"), (FSM_VECTOR[i], TEAL, "Vector"), (FSM_SCALAR[i], ORANGE, "Scalar")]:
            y1, y2 = ymap(accum + val), ymap(accum)
            lines.append(rect(x - barw / 2, y1, barw, y2 - y1, color, "white", 1))
            if y2 - y1 > 25:
                lines.append(txt(x, (y1 + y2) / 2 + 5, f"{val:,}", 12, weight="700", fill="white"))
            accum += val
        lines += [txt(x, top + ph + 28, FSM_CASES[i], 13, cls="label"),
                  txt(x, ymap(totals[i]) - 10, f"Total {totals[i]:,}", 12, weight="700")]
    lines += [txt(left + pw / 2, height - 25, "Matrix size (N,D)", 14, cls="label"),
              txt(25, top + ph / 2, "Cycles", 14, rotate=-90, cls="label")]
    lx, ly = left + pw - 240, top + 20
    for j, (name, color) in enumerate([("Scalar FSM", ORANGE), ("Vector update", TEAL), ("Command/setup/wait", GRAY)]):
        lines += [rect(lx, ly + j * 27 - 12, 16, 16, color), txt(lx + 25, ly + j * 27 + 1, name, 12, "start")]
    finish(OUT / "paper_ablation_fsm_cycles_absolute.svg", lines)


def fsm_normalized():
    width, height = 940, 650
    left, right, top, bottom = 95, 45, 85, 95
    pw, ph = width - left - right, height - top - bottom
    lines = header(width, height)
    lines += [txt(width / 2, 38, "Full-SMU Normalized Cycle Breakdown", 22, cls="title"),
              txt(width / 2, 64, "Bottleneck shifts from fixed overhead to vector streaming", 12, cls="minor")]
    for tick in [0, 20, 40, 60, 80, 100]:
        y = top + ph * (1 - tick / 100)
        lines += [line(left, y, width - right, y, "#D9E0E5", 1), txt(left - 12, y + 4, f"{tick}%", 11, "end")]
    lines += [line(left, top, left, top + ph), line(left, top + ph, width - right, top + ph)]
    centers = [left + pw * (i + 0.5) / 3 for i in range(3)]
    barw = 130
    for i, x in enumerate(centers):
        total = FSM_SCALAR[i] + FSM_VECTOR[i] + FSM_OTHER[i]
        segments = [(FSM_OTHER[i] / total, GRAY, "Other"),
                    (FSM_VECTOR[i] / total, TEAL, "Vector"),
                    (FSM_SCALAR[i] / total, ORANGE, "Scalar")]
        accum = 0.0
        for frac, color, _ in segments:
            y1 = top + ph * (1 - (accum + frac))
            y2 = top + ph * (1 - accum)
            lines.append(rect(x - barw / 2, y1, barw, y2 - y1, color, "white", 1))
            if frac > 0.045:
                lines.append(txt(x, (y1 + y2) / 2 + 5, f"{frac * 100:.1f}%", 13, weight="700", fill="white"))
            accum += frac
        lines.append(txt(x, top + ph + 28, FSM_CASES[i], 13, cls="label"))
    lines += [txt(left + pw / 2, height - 25, "Matrix size (N,D)", 14, cls="label"),
              txt(25, top + ph / 2, "Share of end-to-end cycles", 14, rotate=-90, cls="label")]
    lx, ly = left + pw - 240, top + 20
    for j, (name, color) in enumerate([("Scalar FSM", ORANGE), ("Vector update", TEAL), ("Command/setup/wait", GRAY)]):
        lines += [rect(lx, ly + j * 27 - 12, 16, 16, color), txt(lx + 25, ly + j * 27 + 1, name, 12, "start")]
    finish(OUT / "paper_ablation_fsm_cycles_normalized.svg", lines)


def break_even_table():
    width, height = 1080, 600
    lines = header(width, height)
    lines += [txt(width / 2, 38, "Directly Measured Break-Even Matrix", 22, cls="title"),
              txt(width / 2, 65, "All 16 coordinates favor Full SMU; no model predictions are mixed into the table", 12, cls="minor")]
    left, top = 90, 110
    rowh, firstw, cw = 82, 100, 215
    headers = ["N", "D=1", "D=8", "D=16", "D=32"]
    widths = [firstw] + [cw] * 4
    x = left
    for h, w in zip(headers, widths):
        lines.append(rect(x, top, w - 2, 54, DARK, "white", 4))
        lines.append(txt(x + w / 2, top + 34, h, 14, weight="700", fill="white"))
        x += w
    for r, n in enumerate(NS):
        y = top + 56 + r * rowh
        lines.append(rect(left, y, firstw - 2, rowh - 2, LIGHT, "white", 3))
        lines.append(txt(left + firstw / 2, y + rowh / 2 + 5, str(n), 16, weight="700"))
        for c in range(4):
            val = SPEEDUP[r][c]
            fill = color_interp((val - 1) / 9.2)
            x = left + firstw + c * cw
            lines.append(rect(x, y, cw - 2, rowh - 2, fill, "white", 3))
            tf = "white" if val > 7 else DARK
            lines.append(txt(x + cw / 2, y + 30, f"{B2[r][c]:,} / {B3[r][c]:,}", 14, weight="600", fill=tf))
            lines.append(txt(x + cw / 2, y + 58, f"{val:.3f}×", 18, weight="700", fill=tf))
    lines += [txt(width / 2, height - 78, "Cell format: B2-R median cycles / B3 median cycles; speedup", 12, cls="minor"),
              txt(width / 2, height - 48, "Measured speedup range: 1.424× at (1,32) to 10.140× at (8,1)", 13, cls="label")]
    finish(OUT / "paper_baseline_break_even_table.svg", lines)


def main():
    speedup_heatmap()
    cycles_lines()
    fsm_absolute()
    fsm_normalized()
    break_even_table()
    print(f"Generated 5 SVG figures in {OUT}")


if __name__ == "__main__":
    main()
