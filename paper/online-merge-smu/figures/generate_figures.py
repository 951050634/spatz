#!/usr/bin/env python3
"""Generate editable SVG figures from the recorded SMU experiment artifacts.

Figure contract
---------------
Core conclusion: The SMU wins over the RTL-aligned RVV baseline at every
measured coordinate, then exposes vector streaming as the large-workload
bottleneck while retaining low component slowdown under shared-TCDM execution.
Archetypes: quantitative grid (scaling figure) and asymmetric quantitative
summary (concurrency/proxy figure).
Evidence: all 16 direct B2-R/B3 coordinates; all recorded FSM anchors; all
recorded C1/C2/C3 concurrency summaries; all resource scopes; all VCD samples.
Exports: editable-text SVG at double-column width. Resource and toggle panels
carry explicit nonphysical-proxy labels.
"""

from __future__ import annotations

import csv
import html
import json
import math
import statistics
from pathlib import Path

import cairo
import gi
from PIL import Image

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg

# The direct SVG writer keeps text as SVG <text> nodes. These Matplotlib
# equivalent policies document the editable-text and PDF-font contract.
SVG_TEXT_POLICY = "svg.fonttype = 'none'; pdf.fonttype = 42"
# "font.size": 8 at the 180 mm final-width contract; panel-specific calls
# scale this baseline for titles, annotations, and dense heatmap labels.
FONT_SIZE = 16
FINAL_WIDTH_MM = 180
EXPORT_DPI = 600  # dpi=600


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

BLUE = "#0F4D92"
BLUE_SOFT = "#85A9D6"
TEAL = "#42949E"
GREEN = "#2E9E44"
ROSE = "#B64342"
GOLD = "#D9A441"
VIOLET = "#7562A8"
GREY = "#767676"
LIGHT = "#E9EEF3"
DARK = "#272727"


def esc(value: object) -> str:
    return html.escape(str(value))


def text(x, y, value, size=FONT_SIZE, anchor="middle", weight="normal", color=DARK):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}">'
            f'{esc(value)}</text>')


def line(x1, y1, x2, y2, color=GREY, width=2, dash=None):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
            f'y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"{dash_attr}/>')


def rect(x, y, width, height, fill, stroke="none", sw=0, radius=0):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
            f'height="{height:.1f}" rx="{radius}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>')


def circle(x, y, radius, fill, stroke="white", sw=1.5):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def header(width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,Helvetica,DejaVu Sans,sans-serif}'
        '.label{font-weight:700}.minor{fill:#767676}</style>',
    ]


def save(path: Path, elements: list[str]):
    path.write_text("\n".join(elements + ["</svg>", ""]), encoding="utf-8")


def export_raster_and_pdf(svg_path: Path, width: int, height: int, dpi: int = EXPORT_DPI):
    """Render Python-generated SVG through Cairo/Rsvg for delivery previews."""
    handle = Rsvg.Handle.new_from_file(str(svg_path))
    pdf_path = svg_path.with_suffix(".pdf")
    surface = cairo.PDFSurface(str(pdf_path), width, height)
    context = cairo.Context(surface)
    handle.render_cairo(context)
    surface.finish()

    scale = dpi / 254.0  # 1800 SVG units span 180 mm in the figure contract.
    png_path = svg_path.with_suffix(".png")
    image = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                               round(width * scale), round(height * scale))
    context = cairo.Context(image)
    context.scale(scale, scale)
    handle.render_cairo(context)
    image.write_to_png(str(png_path))
    with Image.open(png_path) as preview:
        preview.save(svg_path.with_suffix(".tiff"), dpi=(dpi, dpi), compression="tiff_lzw")


def load_scaling():
    path = ROOT / "work-artifacts/work-online-merge-stage4-scaling-determinism-20260715T152231Z/analysis.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["break_even"]["rows"]
    return {(r["N"], r["D"]): (r["B2_R_cycles_median"]["decimal"],
                              r["B3_cycles_median"]["decimal"],
                              r["speedup_B3_vs_B2_R"]["decimal"])
            for r in rows}


def load_fsm():
    path = ROOT / "work-artifacts/work-online-merge-stage5b-fsm-analysis-20260715T183542Z/fsm_breakdown.csv"
    grouped = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (int(row["N"]), int(row["D"]))
            grouped.setdefault(key, []).append(row)
    result = {}
    for key, rows in grouped.items():
        result[key] = {
            field: statistics.median(float(r[field]) for r in rows)
            for field in ("scalar_cycles", "vector_cycles",
                          "command_setup_wait_error_nonoverlap_cycles")
        }
    return result


def load_concurrency():
    path = ROOT / "work-artifacts/work-online-merge-stage6j-analysis-clean-20260716T204000Z/concurrency_summary.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_resources():
    path = ROOT / "work-artifacts/work-online-merge-stage7b-resource-analysis-clean-20260716T015813Z/resource_summary.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_toggles():
    path = ROOT / "work-artifacts/work-online-merge-stage8c-analysis-clean-20260716T154500Z/toggle_summary.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def interpolate(start, end, ratio):
    ratio = max(0.0, min(1.0, ratio))
    return tuple(round(a + (b - a) * ratio) for a, b in zip(start, end))


def heat_color(value):
    rgb = interpolate((229, 239, 248), (22, 119, 73), (value - 1.4) / (10.2 - 1.4))
    return "#%02x%02x%02x" % rgb


def scaling_bottleneck():
    data = load_scaling()
    fsm = load_fsm()
    width, height = 1800, 980
    e = header(width, height)
    e += [text(58, 62, "a", 30, "start", "bold"),
          text(126, 58, "Full SMU speedup over RVV baseline", 26, "start", "bold"),
          text(126, 88, "Direct medians at all 16 measured coordinates; speedup = B2-R / B3", 18, "start", "normal", GREY)]
    left, top, cell_w, cell_h = 80, 145, 142, 118
    ns, ds = [1, 2, 4, 8], [1, 8, 16, 32]
    for col, d in enumerate(ds):
        e.append(text(left + col * cell_w + cell_w / 2, top - 22, f"D={d}", 19, "middle", "bold"))
    for row, n in enumerate(ns):
        y = top + row * cell_h
        e.append(text(left - 14, y + cell_h / 2 + 6, f"N={n}", 19, "end", "bold"))
        for col, d in enumerate(ds):
            b2, b3, speedup = data[n, d]
            x = left + col * cell_w
            fill = heat_color(speedup)
            e.append(rect(x, y, cell_w - 5, cell_h - 5, fill, "white", 2, 7))
            color = "white" if speedup > 6 else DARK
            e += [text(x + cell_w / 2, y + 47, f"{speedup:.2f}×", 27, "middle", "bold", color),
                  text(x + cell_w / 2, y + 78, f"{int(b2):,} / {int(b3):,} cycles", 14, "middle", "normal", color)]

    plot_l, plot_t, plot_w, plot_h = 760, 145, 940, 385
    e += [text(738, 62, "b", 30, "start", "bold"),
          text(806, 58, "Cycle scaling exposes vector streaming", 26, "start", "bold"),
          text(806, 88, "Solid: B3. Dashed: B2-R. Colors encode row count N.", 18, "start", "normal", GREY)]
    ymax, ymin = 15000, 1000
    log_y = lambda value: plot_t + plot_h * (math.log10(ymax) - math.log10(value)) / (math.log10(ymax) - math.log10(ymin))
    x_of = lambda d: plot_l + (ds.index(d) / 3) * plot_w
    for tick in (1000, 2000, 5000, 10000):
        y = log_y(tick)
        e += [line(plot_l, y, plot_l + plot_w, y, "#D7DFE7", 1), text(plot_l - 12, y + 5, f"{tick:,}", 15, "end", "normal", GREY)]
    e += [line(plot_l, plot_t, plot_l, plot_t + plot_h, DARK, 2),
          line(plot_l, plot_t + plot_h, plot_l + plot_w, plot_t + plot_h, DARK, 2)]
    palette = [BLUE, TEAL, VIOLET, ROSE]
    for color, n in zip(palette, ns):
        for method, dash, width_line in ((0, "8 6", 2.5), (1, None, 3.4)):
            points = []
            for d in ds:
                value = data[n, d][method]
                points.append(f"{x_of(d):.1f},{log_y(value):.1f}")
            dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
            e.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="{width_line}"{dash_attr}/>')
            for d in ds:
                e.append(circle(x_of(d), log_y(data[n, d][method]), 5.5, "white" if method == 0 else color, color, 2))
        e.append(text(plot_l + plot_w + 16, log_y(data[n, 32][1]) + 5, f"N={n}", 16, "start", "bold", color))
    for d in ds:
        e.append(text(x_of(d), plot_t + plot_h + 31, str(d), 17))
    e += [text(plot_l + plot_w / 2, plot_t + plot_h + 66, "Vector dimension D", 18, "middle", "bold"),
          text(plot_l + 28, plot_t + 20, "Median cycles (log scale)", 17, "start", "bold", DARK)]

    e += [text(58, 650, "c", 30, "start", "bold"),
          text(126, 646, "B3 cost shifts from control to vector update", 26, "start", "bold"),
          text(126, 676, "FSM anchors use all three recorded repetitions per coordinate", 18, "start", "normal", GREY)]
    cases = [(1, 1), (8, 32), (16, 64)]
    names = ["(1, 1)", "(8, 32)", "(16, 64)"]
    chart_l, chart_t, chart_w, chart_h = 105, 718, 1575, 190
    bar_w = 250
    centers = [chart_l + 280, chart_l + 785, chart_l + 1290]
    fields = [("command_setup_wait_error_nonoverlap_cycles", "Command / setup / wait", GREY),
              ("vector_cycles", "Vector update", TEAL),
              ("scalar_cycles", "Scalar FSM", GOLD)]
    for center, case, name in zip(centers, cases, names):
        values = fsm[case]
        total = sum(values[field] for field, _, _ in fields)
        y_bottom = chart_t + chart_h
        for field, _, color in fields:
            fraction = values[field] / total
            h = fraction * chart_h
            y_bottom -= h
            e.append(rect(center - bar_w / 2, y_bottom, bar_w, h, color, "white", 1))
            if h > 34:
                e.append(text(center, y_bottom + h / 2 + 6, f"{fraction * 100:.1f}%", 18, "middle", "bold", "white"))
        e.append(text(center, chart_t + chart_h + 31, name, 20, "middle", "bold"))
    legend_x = 1020
    for idx, (_, label, color) in enumerate(reversed(fields)):
        y = 702
        x = legend_x + idx * 220
        e += [rect(x, y - 14, 18, 18, color), text(x + 28, y, label, 16, "start")]
    path = OUT / "smu_scaling_bottleneck.svg"
    save(path, e)
    export_raster_and_pdf(path, width, height)


def concurrency_proxies():
    concurrency = load_concurrency()
    resources = load_resources()
    toggles = load_toggles()
    width, height = 1800, 690
    e = header(width, height)

    e += [text(60, 62, "a", 30, "start", "bold"),
          text(126, 58, "Shared-TCDM component slowdown", 22, "start", "bold"),
          text(126, 88, "N=16, D=64; bars show concurrent / standalone slowdown", 17, "start", "normal", GREY)]
    scenarios = [row for row in concurrency if row["scenario"] in {"C1", "C2", "C3"}]
    scenarios.sort(key=lambda row: row["scenario"])
    left, top, plot_w, plot_h = 90, 145, 500, 350
    y_of = lambda value: top + plot_h * (1.04 - value) / 0.06
    for tick in (1.00, 1.02, 1.04):
        y = y_of(tick)
        e += [line(left, y, left + plot_w, y, "#D7DFE7", 1), text(left - 10, y + 5, f"{tick:.2f}×", 14, "end", "normal", GREY)]
    e += [line(left, top, left, top + plot_h, DARK, 2), line(left, top + plot_h, left + plot_w, top + plot_h, DARK, 2)]
    for index, row in enumerate(scenarios):
        center = left + 95 + index * 165
        pairs = [(float(row["slowdown_core_median"]), BLUE, "core"),
                 (float(row["slowdown_smu_median"]), ROSE, "SMU")]
        for offset, (value, color, _) in zip((-30, 30), pairs):
            y = y_of(value)
            e.append(rect(center + offset - 22, y, 44, top + plot_h - y, color, "white", 1, 3))
            e.append(text(center + offset, y - 10, f"{(value - 1) * 100:+.2f}%", 13, "middle", "bold", color))
        e.append(text(center, top + plot_h + 30, row["scenario"], 18, "middle", "bold"))
        congestion = float(row["congestion_ratio_median"]) * 100
        e.append(text(center, top + plot_h + 53, f"{congestion:.2f}% cong.", 13, "middle", "normal", GREY))
    e += [rect(left + 18, top + 20, 16, 16, BLUE), text(left + 44, top + 34, "core", 15, "start"),
          rect(left + 120, top + 20, 16, 16, ROSE), text(left + 146, top + 34, "SMU", 15, "start"),
          text(left + plot_w / 2, top + plot_h + 84, "C1: register stream; C2: stream; C3: 16 bank phases", 14, "middle", "normal", GREY)]

    e += [text(650, 62, "b", 30, "start", "bold"),
          text(716, 58, "Generic logic proxy", 22, "start", "bold"),
          text(716, 88, "Yosys post-techmap generic cells; scopes are non-additive", 17, "start", "normal", GREY)]
    left2, top2, width2, height2 = 690, 150, 470, 330
    max_cells = max(int(row["post_num_cells"]) for row in resources)
    for idx, row in enumerate(resources):
        y = top2 + idx * 74
        cells = int(row["post_num_cells"])
        label = row["decomposition_label"].replace(" approximation", "")
        e.append(text(left2, y + 26, label, 16, "start", "bold"))
        e.append(rect(left2, y + 38, width2 * cells / max_cells, 22, VIOLET if row["scope"] == "full" else BLUE_SOFT, "none", 0, 4))
        e.append(text(left2 + width2 * cells / max_cells + 8, y + 56, f"{cells:,}", 15, "start", "bold"))
    e.append(text(left2, top2 + height2 + 28, "Proxy only: no library, timing, or physical-area claim.", 15, "start", "normal", GREY))

    e += [text(1215, 62, "c", 30, "start", "bold"),
          text(1281, 58, "Zero-delay RTL toggles", 22, "start", "bold"),
          text(1281, 88, "Known-bit VCD transitions; proxy only, not an energy measurement", 17, "start", "normal", GREY)]
    left3, top3, width3, height3 = 1235, 145, 500, 350
    coordinates = [(1, 1), (8, 32), (16, 64)]
    selected = {(int(row["N"]), int(row["D"]), row["implementation"]): int(row["total_bit_toggles"])
                for row in toggles}
    ymax = max(selected[n, d, impl] for n, d in coordinates for impl in ("B2-R", "B3"))
    y_log = lambda value: top3 + height3 * (math.log10(ymax) - math.log10(value)) / (math.log10(ymax) - math.log10(1_000_000))
    for tick in (1_000_000, 10_000_000, 40_000_000):
        y = y_log(tick)
        e += [line(left3, y, left3 + width3, y, "#D7DFE7", 1), text(left3 - 10, y + 5, f"{tick / 1e6:.0f}M", 14, "end", "normal", GREY)]
    e += [line(left3, top3, left3, top3 + height3, DARK, 2), line(left3, top3 + height3, left3 + width3, top3 + height3, DARK, 2)]
    for idx, (n, d) in enumerate(coordinates):
        center = left3 + 95 + idx * 160
        for offset, impl, color in ((-28, "B2-R", BLUE), (28, "B3", ROSE)):
            value = selected[n, d, impl]
            y = y_log(value)
            e.append(rect(center + offset - 21, y, 42, top3 + height3 - y, color, "white", 1, 3))
        e.append(text(center, top3 + height3 + 30, f"({n},{d})", 17, "middle", "bold"))
    e += [rect(left3 + 16, top3 + 20, 16, 16, BLUE), text(left3 + 42, top3 + 34, "B2-R", 15, "start"),
          rect(left3 + 108, top3 + 20, 16, 16, ROSE), text(left3 + 134, top3 + 34, "B3", 15, "start"),
          text(left3 + width3 / 2, top3 + height3 + 60, "Total known-bit toggles (log scale)", 15, "middle", "normal", GREY)]
    path = OUT / "smu_concurrency_proxies.svg"
    save(path, e)
    export_raster_and_pdf(path, width, height)


if __name__ == "__main__":
    scaling_bottleneck()
    concurrency_proxies()
    print("Generated smu_scaling_bottleneck.svg and smu_concurrency_proxies.svg")
