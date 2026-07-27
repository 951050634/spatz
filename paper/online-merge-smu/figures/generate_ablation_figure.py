#!/usr/bin/env python3
"""Generate the A0/A1/A2 ablation comparison figure.

Figure contract
---------------
Core conclusion: Offloading only the row-wise scalar recurrence to the SMU
retains the RVV vector path's lower per-element cost and is therefore the
fastest design at the two larger measured anchors; Full SMU remains slightly
faster only at the smallest anchor.
Archetype: quantitative grid with a dominant absolute-cycle panel and a
normalized comparison panel.
Evidence: all A0/A1/A2 measurements at the three recorded anchors; medians and
the full min--max range over three measured repetitions are retained.
Backend: Python-only direct SVG generation and Python Cairo/Rsvg export.
Output: editable SVG, PDF, 600 dpi TIFF, and 600 dpi PNG at 180 x 88 mm.

No observations are excluded and no simulated values are used.
"""

from __future__ import annotations

import csv
import html
import math
from pathlib import Path

import cairo
import gi
from PIL import Image

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "ablation_a0_a1_a2.csv"
OUTPUT = HERE / "smu_ablation_comparison.svg"

WIDTH = 1800
HEIGHT = 880
FINAL_WIDTH_MM = 180
FINAL_HEIGHT_MM = 88
EXPORT_DPI = 600

# Editable-text export policy equivalent to Matplotlib's svg.fonttype='none'
# and pdf.fonttype=42 settings. The SVG writer emits live <text> elements.
SVG_TEXT_POLICY = "svg.fonttype = 'none'; pdf.fonttype = 42"
FONT_POLICY = "font.size = 7"  # Final-size target; 18 SVG units exceed 5 pt.
FONT_SIZE = 18

DARK = "#272727"
GREY = "#767676"
GRID = "#D7DFE7"
A0 = "#8A929A"
A1 = "#176B87"
A2 = "#D1843E"
WHITE = "#FFFFFF"

METHODS = ("A0", "A1", "A2")
METHOD_META = {
    "A0": (A0, "Software scalar + RVV vector"),
    "A1": (A1, "SMU scalar + RVV vector"),
    "A2": (A2, "Full SMU"),
}
CASES = ((1, 1), (8, 32), (16, 64))


def esc(value: object) -> str:
    return html.escape(str(value))


def text(x, y, value, size=FONT_SIZE, anchor="middle", weight="normal",
         color=DARK, rotate=None):
    transform = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}"'
            f'{transform}>{esc(value)}</text>')


def line(x1, y1, x2, y2, color=GREY, width=2, dash=None):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
            f'y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"'
            f'{dash_attr}/>' )


def rect(x, y, width, height, fill, stroke="none", stroke_width=0,
         radius=0, opacity=1.0):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
            f'height="{height:.1f}" rx="{radius}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{stroke_width}" '
            f'opacity="{opacity}"/>')


def circle(x, y, radius, fill, stroke=WHITE, stroke_width=2):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>')


def diamond(x, y, radius, fill, stroke=WHITE, stroke_width=2):
    points = [(x, y - radius), (x + radius, y),
              (x, y + radius), (x - radius, y)]
    encoded = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
    return (f'<polygon points="{encoded}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{stroke_width}"/>')


def header():
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,Helvetica,DejaVu Sans,sans-serif}</style>',
    ]


def load_data():
    rows = {}
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (int(row["N"]), int(row["D"]), row["implementation"])
            rows[key] = {
                "n": int(row["measured_repeats"]),
                "min": float(row["cycles_min"]),
                "median": float(row["cycles_median"]),
                "max": float(row["cycles_max"]),
            }
    expected = {(n, d, method) for n, d in CASES for method in METHODS}
    if set(rows) != expected:
        missing = sorted(expected - set(rows))
        extra = sorted(set(rows) - expected)
        raise ValueError(f"source-data mismatch: missing={missing}, extra={extra}")
    if any(row["min"] > row["median"] or row["median"] > row["max"]
           for row in rows.values()):
        raise ValueError("each row must satisfy min <= median <= max")
    return rows


def add_legend(elements):
    x = 115
    y = 116
    for method in METHODS:
        color, label = METHOD_META[method]
        if method == "A1":
            elements.append(diamond(x, y - 5, 9, color, color, 1.5))
        else:
            elements.append(circle(x, y - 5, 8, color, color, 1.5))
        elements.append(text(x + 19, y, f"{method}: {label}", 18,
                             "start", "normal", DARK))
        x += 355 if method != "A1" else 340


def absolute_cycles_panel(elements, rows):
    elements += [text(52, 58, "a", 29, "start", "bold"),
                 text(105, 56, "End-to-end cycles across the ablation", 25,
                      "start", "bold"),
                 text(105, 82, "Points show medians; whiskers span min–max over three measured repetitions", 18,
                      "start", "normal", GREY)]
    add_legend(elements)

    left, top, plot_w, plot_h = 105, 170, 975, 580
    ymin, ymax = 1000.0, 40000.0

    def y_of(value):
        if value <= 0:
            raise ValueError("log-scale cycle values must be strictly positive")
        return top + plot_h * ((math.log10(ymax) - math.log10(value)) /
                              (math.log10(ymax) - math.log10(ymin)))

    ticks = (1000, 2000, 5000, 10000, 20000, 40000)
    for tick in ticks:
        y = y_of(tick)
        elements += [line(left, y, left + plot_w, y, GRID, 1),
                     text(left - 12, y + 5, f"{tick:,}", 18, "end",
                          "normal", GREY)]
    elements += [line(left, top, left, top + plot_h, DARK, 2),
                 line(left, top + plot_h, left + plot_w, top + plot_h,
                      DARK, 2),
                 text(31, top + plot_h / 2, "Cycles (log scale)", 17,
                      "middle", "bold", DARK, -90)]

    centers = [left + plot_w * (index + 0.5) / len(CASES)
               for index in range(len(CASES))]
    offsets = {"A0": -64, "A1": 0, "A2": 64}
    for center, (n, d) in zip(centers, CASES):
        for method in METHODS:
            row = rows[n, d, method]
            color = METHOD_META[method][0]
            x = center + offsets[method]
            y_min = y_of(row["min"])
            y_max = y_of(row["max"])
            y_med = y_of(row["median"])
            elements += [line(x, y_max, x, y_min, color, 3),
                         line(x - 9, y_max, x + 9, y_max, color, 3),
                         line(x - 9, y_min, x + 9, y_min, color, 3)]
            if method == "A1":
                elements.append(diamond(x, y_med, 11, color, WHITE, 2))
            else:
                elements.append(circle(x, y_med, 10, color, WHITE, 2))
        elements.append(text(center, top + plot_h + 34, f"({n}, {d})", 18,
                             "middle", "bold"))
    elements.append(text(left + plot_w / 2, top + plot_h + 72,
                         "Workload (N, D)", 18, "middle", "bold"))


def speedup_panel(elements, rows):
    elements += [text(1142, 58, "b", 29, "start", "bold"),
                 text(1195, 56, "Speedup over A0", 25, "start", "bold"),
                 text(1195, 82, "Higher is better; A0 is fixed at 1×", 18,
                      "start", "normal", GREY)]
    left, top, plot_w, plot_h = 1190, 170, 540, 580
    ymax = 6.0

    def y_of(value):
        return top + plot_h * (1 - value / ymax)

    for tick in range(0, 7):
        y = y_of(tick)
        elements += [line(left, y, left + plot_w, y, GRID, 1),
                     text(left - 10, y + 5, f"{tick}×", 18, "end",
                          "normal", GREY)]
    elements += [line(left, top, left, top + plot_h, DARK, 2),
                 line(left, top + plot_h, left + plot_w, top + plot_h,
                      DARK, 2),
                 line(left, y_of(1), left + plot_w, y_of(1), GREY, 2, "7 5")]

    group_centers = [left + plot_w * (index + 0.5) / len(CASES)
                     for index in range(len(CASES))]
    bar_width = 54
    for center, (n, d) in zip(group_centers, CASES):
        base = rows[n, d, "A0"]["median"]
        speedups = {method: base / rows[n, d, method]["median"]
                    for method in ("A1", "A2")}
        for offset, method in ((-30, "A1"), (30, "A2")):
            speedup = speedups[method]
            x = center + offset - bar_width / 2
            y = y_of(speedup)
            elements.append(rect(x, y, bar_width, top + plot_h - y,
                                 METHOD_META[method][0], WHITE, 1))
            elements.append(text(center + offset, y - 10, f"{speedup:.2f}×",
                                 18, "middle", "bold",
                                 METHOD_META[method][0]))
        if speedups["A1"] > speedups["A2"]:
            winner = "A1"
            advantage = rows[n, d, "A2"]["median"] / rows[n, d, "A1"]["median"]
        else:
            winner = "A2"
            advantage = rows[n, d, "A1"]["median"] / rows[n, d, "A2"]["median"]
        elements.append(text(center, top - 24,
                             f"{winner} fastest ({advantage:.2f}×)", 18,
                             "middle", "bold", METHOD_META[winner][0]))
        elements.append(text(center, top + plot_h + 34, f"({n}, {d})", 17,
                             "middle", "bold"))
    elements.append(text(left + plot_w / 2, top + plot_h + 72,
                         "Workload (N, D)", 18, "middle", "bold"))


def export(svg_path):
    handle = Rsvg.Handle.new_from_file(str(svg_path))
    pdf_path = svg_path.with_suffix(".pdf")
    surface = cairo.PDFSurface(str(pdf_path), WIDTH, HEIGHT)
    context = cairo.Context(surface)
    handle.render_cairo(context)
    surface.finish()

    scale = EXPORT_DPI / 254.0
    image = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                               round(WIDTH * scale), round(HEIGHT * scale))
    context = cairo.Context(image)
    context.scale(scale, scale)
    handle.render_cairo(context)
    png_path = svg_path.with_suffix(".png")
    image.write_to_png(str(png_path))
    with Image.open(png_path) as preview:
        preview.save(svg_path.with_suffix(".tiff"), dpi=(EXPORT_DPI, EXPORT_DPI),
                     compression="tiff_lzw")


def main():
    rows = load_data()
    elements = header()
    absolute_cycles_panel(elements, rows)
    speedup_panel(elements, rows)
    elements += [text(105, 846,
                      "All configurations use identical inputs, numerical semantics, and timing boundaries; n = 3 measured repetitions per point.",
                      18, "start", "normal", GREY),
                 "</svg>", ""]
    OUTPUT.write_text("\n".join(elements), encoding="utf-8")
    export(OUTPUT)
    print(f"Generated {OUTPUT.name}, PDF, PNG, and TIFF from {SOURCE.name}")


if __name__ == "__main__":
    main()
