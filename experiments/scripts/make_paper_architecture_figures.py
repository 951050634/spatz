#!/usr/bin/env python3
"""Generate all manuscript figures with Python SVG/Cairo.

The script reads only frozen CSV evidence for quantitative panels. It does not
run workloads, simulation, synthesis, or fitting.
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


ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "plots"
SCALING = ROOT / "experiments" / "parsed" / "final_scaling_model.csv"
WORKLOAD = ROOT / "experiments" / "parsed" / "final_workload_comparison.csv"
AREA = ROOT / "experiments" / "parsed" / "final_area.csv"

# Direct SVG keeps live text; Cairo embeds the selected sans-serif fonts in PDF.
SVG_TEXT_POLICY = "svg.fonttype = 'none'; pdf.fonttype = 42"
EXPORT_DPI = 600
fig_width_mm = 180.0

BLUE = "#4C72B0"
BLUE_PALE = "#E4ECF7"
GREEN = "#4E8F65"
GREEN_PALE = "#E5F1E9"
RED = "#B75455"
ORANGE = "#C47A3A"
ORANGE_PALE = "#F7EBDD"
PURPLE = "#86649B"
DARK = "#3F3F3F"
MID = "#747474"
GRID = "#D9DDE1"
LIGHT = "#F2F3F4"
WHITE = "#FFFFFF"


def esc(value: object) -> str:
    return html.escape(str(value))


def header(width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,Helvetica,DejaVu Sans,sans-serif}</style>',
        '<defs>',
        *[
            f'<marker id="arrow-{name}" markerWidth="8" markerHeight="8" refX="7" refY="4" '
            f'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="{color}"/></marker>'
            for name, color in (("dark", DARK), ("mid", MID), ("blue", BLUE),
                                ("green", GREEN), ("orange", ORANGE),
                                ("purple", PURPLE))
        ],
        '</defs>',
    ]


def text(x: float, y: float, value: str, size: float = 20,
         anchor: str = "middle", weight: str = "normal", color: str = DARK,
         rotate: float | None = None) -> str:
    transform = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ""
    lines = value.split("\n")
    if len(lines) == 1:
        body = esc(lines[0])
    else:
        body = "".join(
            f'<tspan x="{x:.1f}" dy="{0 if i == 0 else size * 1.12:.1f}">{esc(line)}</tspan>'
            for i, line in enumerate(lines)
        )
        y -= (len(lines) - 1) * size * 0.55
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}" '
            f'dominant-baseline="middle"{transform}>{body}</text>')


def rect(x: float, y: float, width: float, height: float, fill: str = WHITE,
         stroke: str = DARK, stroke_width: float = 2, radius: float = 10,
         dash: str | None = None) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
            f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"'
            f'{dash_attr}/>')


def line(x1: float, y1: float, x2: float, y2: float, color: str = DARK,
         width: float = 2, dash: str | None = None, arrow_end: bool = False,
         arrow_start: bool = False) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    color_name = {DARK: "dark", MID: "mid", BLUE: "blue", GREEN: "green",
                  ORANGE: "orange", PURPLE: "purple"}.get(color, "dark")
    end_attr = f' marker-end="url(#arrow-{color_name})"' if arrow_end else ""
    start_attr = f' marker-start="url(#arrow-{color_name})"' if arrow_start else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width}"{dash_attr}{end_attr}{start_attr}/>')


def polyline(points: list[tuple[float, float]], color: str = DARK, width: float = 2,
             dash: str | None = None, arrow_end: bool = True) -> str:
    encoded = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    color_name = {DARK: "dark", MID: "mid", BLUE: "blue", GREEN: "green",
                  ORANGE: "orange", PURPLE: "purple"}.get(color, "dark")
    end_attr = f' marker-end="url(#arrow-{color_name})"' if arrow_end else ""
    return (f'<polyline points="{encoded}" fill="none" stroke="{color}" '
            f'stroke-width="{width}"{dash_attr}{end_attr}/>')


def box(elements: list[str], x: float, y: float, width: float, height: float,
        label: str, fill: str = WHITE, stroke: str = DARK, size: float = 20,
        weight: str = "normal", radius: float = 10, dash: str | None = None) -> None:
    elements.append(rect(x, y, width, height, fill, stroke, 2, radius, dash))
    elements.append(text(x + width / 2, y + height / 2, label, size,
                         "middle", weight))


def tag(elements: list[str], x: float, y: float, label: str, color: str) -> None:
    elements.append(rect(x, y, 85, 28, color, color, 1, 4))
    elements.append(text(x + 42.5, y + 15, label, 16, "middle", "bold", WHITE))


def export(stem: str, width: int, height: int, elements: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    svg_path = OUT / f"{stem}.svg"
    svg_path.write_text("\n".join(elements + ["</svg>", ""]), encoding="utf-8")
    handle = Rsvg.Handle.new_from_file(str(svg_path))
    pdf_path = svg_path.with_suffix(".pdf")
    surface = cairo.PDFSurface(str(pdf_path), width, height)
    context = cairo.Context(surface)
    handle.render_cairo(context)
    surface.finish()
    scale = EXPORT_DPI / 254.0
    image = cairo.ImageSurface(cairo.FORMAT_ARGB32, round(width * scale),
                               round(height * scale))
    context = cairo.Context(image)
    context.scale(scale, scale)
    handle.render_cairo(context)
    png_path = svg_path.with_suffix(".png")
    image.write_to_png(str(png_path))
    with Image.open(png_path) as preview:
        preview.save(svg_path.with_suffix(".tiff"), dpi=(EXPORT_DPI, EXPORT_DPI),
                     compression="tiff_lzw")
    print(f"wrote {svg_path}, {pdf_path}, {png_path}")


def motivation() -> None:
    w, h = 1800, 540
    e = header(w, h)
    e += [text(30, 32, "Online Softmax Merge", 28, "start", "bold"),
          text(1770, 32, "one merge row", 18, "end", "normal", MID)]
    e += [rect(25, 75, 1000, 430, BLUE_PALE, BLUE, 2, 16),
          text(55, 112, "State-dependent scalar recurrence", 24, "start", "bold", BLUE),
          text(995, 112, "dependency-bound", 18, "end", "normal", BLUE)]
    stages = [(60, "max\nm_new"), (245, "deltas\nΔold, Δtile"),
              (430, "2× EXP\ne_old, e_tile"), (615, "scale + add\ns_old + s_tile"),
              (800, "reciprocal\nw_old, w_tile")]
    for idx, (x, label) in enumerate(stages):
        box(e, x, 185, 150, 115, label, WHITE, BLUE, 18,
            "bold" if idx in (0, 4) else "normal")
        if idx < len(stages) - 1:
            e.append(line(x + 150, 242, stages[idx + 1][0] - 8, 242,
                          BLUE, 2, arrow_end=True))
    e += [text(55, 375,
               "loop-carried state • maximum / exponential / reciprocal • low data-level parallelism",
               18, "start"),
          text(525, 456, "specialization target", 19, "middle", "bold", BLUE)]
    e += [rect(1070, 75, 705, 430, GREEN_PALE, GREEN, 2, 16),
          text(1100, 112, "Regular O[D] vector update", 24, "start", "bold", GREEN),
          text(1745, 112, "data-parallel", 18, "end", "normal", GREEN)]
    box(e, 1120, 155, 605, 58,
        "O_new[j] = w_old O_old[j] + w_tile O_tile[j]", WHITE, GREEN, 18)
    for lane, y in enumerate((235, 295, 355, 415)):
        box(e, 1180, y, 485, 42, f"j={lane}: independent multiply-add", WHITE,
            GREEN, 17, radius=5)
    e.append(text(1422, 492, "reuse existing vector datapath", 18,
                  "middle", "bold", GREEN))
    export("figure1_computation_decomposition", w, h, e)


def architecture() -> None:
    w, h = 1800, 620
    e = header(w, h)
    e += [text(30, 32, "Selective recurrence-offloading architecture", 28,
               "start", "bold"),
          text(1770, 32, "platform-independent", 18, "end", "normal", MID)]
    box(e, 650, 70, 500, 70, "Software / control plane", LIGHT, MID, 22, "bold")
    e += [rect(100, 190, 650, 230, BLUE_PALE, BLUE, 2, 16),
          rect(1050, 190, 650, 230, GREEN_PALE, GREEN, 2, 16)]
    tag(e, 125, 210, "NEW", BLUE)
    tag(e, 1075, 210, "REUSED", GREEN)
    e += [text(425, 250, "Scalar SMU", 27, "middle", "bold", BLUE),
          text(425, 300, "state-dependent recurrence", 20, "middle", "normal", BLUE),
          text(425, 355, "max → EXP rescaling → l_new → weights", 19),
          text(1375, 250, "Existing vector datapath", 27, "middle", "bold", GREEN),
          text(1375, 300, "regular O[D] update", 20, "middle", "normal", GREEN),
          text(1375, 355, "vector load / multiply-add / store", 19)]
    box(e, 320, 475, 1160, 85, "Shared scratchpad", LIGHT, MID, 23, "bold")
    e.append(text(900, 540, "recurrence state • weights • O vectors", 18,
                  "middle", "normal", MID))
    e += [line(775, 140, 500, 190, MID, 2, "8 6", True),
          line(1025, 140, 1300, 190, MID, 2, "8 6", True),
          text(565, 155, "start / completion", 17, "middle", "normal", MID),
          text(1235, 155, "invoke vector phase", 17, "middle", "normal", MID),
          line(390, 420, 520, 475, BLUE, 3, None, True, True),
          line(1410, 420, 1280, 475, GREEN, 3, None, True, True),
          text(335, 453, "state + weights", 17, "middle", "normal", BLUE),
          text(1465, 453, "weights + vectors", 17, "middle", "normal", GREEN),
          text(900, 450, "phase boundary through shared state", 19,
               "middle", "bold")]
    export("figure2_selective_architecture", w, h, e)


def datapath() -> None:
    w, h = 1800, 740
    e = header(w, h)
    e += [text(30, 30, "Scalar SMU recurrence datapath", 28, "start", "bold"),
          text(1770, 30, "RTL structure", 18, "end", "normal", MID)]
    # Inputs.
    for x, y, label in ((35, 95, "m_old"), (35, 190, "m_tile")):
        box(e, x, y, 125, 58, label, LIGHT, MID, 20)
    box(e, 230, 125, 170, 92, "FP32 max\nselection", BLUE_PALE, BLUE, 20, "bold")
    e += [line(160, 124, 230, 155, BLUE, 2, None, True),
          line(160, 219, 230, 190, BLUE, 2, None, True)]
    box(e, 455, 140, 140, 62, "m_new\nregister", LIGHT, BLUE, 18, "bold")
    e.append(line(400, 171, 455, 171, BLUE, 2, None, True))
    # Parallel deltas and EXP blocks.
    for y, source, exp_name in ((265, "m_old - m_new", "EXP LUT 0\n+ interpolation"),
                                (405, "m_tile - m_new", "EXP LUT 1\n+ interpolation")):
        box(e, 250, y, 210, 58, source, WHITE, BLUE, 18)
        box(e, 525, y, 200, 58, exp_name, BLUE_PALE, BLUE, 18, "bold")
        e.append(line(460, y + 29, 525, y + 29, BLUE, 2, None, True))
    e += [polyline([(95, 153), (195, 153), (195, 294), (250, 294)], MID, 2),
          polyline([(95, 219), (195, 219), (195, 434), (250, 434)], MID, 2),
          polyline([(525, 202), (525, 235), (355, 235), (355, 265)], BLUE, 2),
          polyline([(545, 202), (545, 370), (355, 370), (355, 405)], BLUE, 2)]
    # Scaling multipliers and scaled states.
    box(e, 790, 175, 175, 50, "l_old", LIGHT, MID, 18)
    box(e, 790, 505, 175, 50, "l_tile", LIGHT, MID, 18)
    box(e, 790, 265, 175, 58, "l_old × e_old", ORANGE_PALE, ORANGE, 18)
    box(e, 790, 405, 175, 58, "l_tile × e_tile", ORANGE_PALE, ORANGE, 18)
    e += [line(725, 294, 790, 294, BLUE, 2, None, True),
          line(725, 434, 790, 434, BLUE, 2, None, True),
          line(877, 225, 877, 265, MID, 2, None, True),
          line(877, 505, 877, 463, MID, 2, None, True)]
    box(e, 1020, 265, 120, 58, "s_old reg", LIGHT, ORANGE, 18)
    box(e, 1020, 405, 120, 58, "s_tile reg", LIGHT, ORANGE, 18)
    e += [line(965, 294, 1020, 294, ORANGE, 2, None, True),
          line(965, 434, 1020, 434, ORANGE, 2, None, True)]
    box(e, 1210, 325, 130, 82, "+\nl_new", ORANGE_PALE, ORANGE, 20, "bold")
    e += [line(1140, 294, 1210, 350, ORANGE, 2, None, True),
          line(1140, 434, 1210, 382, ORANGE, 2, None, True)]
    # Registered reciprocal stage.
    e.append(rect(1375, 150, 390, 500, "none", MID, 2, 10, "8 6"))
    e.append(text(1395, 170, "COMPUTE_WEIGHT stage", 17, "start", "normal", MID))
    box(e, 1410, 230, 150, 65, "l_new\nregister", LIGHT, BLUE, 18, "bold")
    e.append(polyline([(1340, 366), (1485, 366), (1485, 295)], BLUE, 2))
    box(e, 1410, 350, 180, 78, "reciprocal LUT\n+ interpolation", BLUE_PALE,
        BLUE, 18, "bold")
    e.append(line(1485, 295, 1485, 350, BLUE, 2, None, True))
    box(e, 1630, 300, 125, 64, "s_old / l_new\nw_old", WHITE, BLUE, 17)
    box(e, 1630, 455, 125, 64, "s_tile / l_new\nw_tile", WHITE, BLUE, 17)
    e += [line(1590, 389, 1630, 332, BLUE, 2, None, True),
          line(1590, 389, 1630, 487, BLUE, 2, None, True),
          polyline([(1080, 265), (1080, 205), (1605, 205), (1605, 332), (1630, 332)],
                   ORANGE, 2),
          polyline([(1080, 463), (1080, 575), (1605, 575), (1605, 487), (1630, 487)],
                   ORANGE, 2),
          text(900, 690, "Q1.23 LUT outputs; 48-bit Q16.32 state and weight arithmetic",
               18, "middle", "normal", MID)]
    export("figure3_scalar_smu_datapath", w, h, e)


def schedule() -> None:
    w, h = 880, 340
    e = header(w, h)
    e += [text(25, 30, "Nominal scalar-only FSM schedule", 23, "start", "bold"),
          text(855, 30, "24 busy cycles / row", 20, "end", "bold")]
    left, usable, top, bar_h = 35, 810, 135, 90
    states = [("LOAD_SCALAR", 13, BLUE), ("COMPUTE_SCALAR", 1, ORANGE),
              ("COMPUTE_WEIGHT", 1, PURPLE), ("STORE_SCALAR", 9, GREEN)]
    x = left
    centers = []
    for name, cycles, color in states:
        width = usable * cycles / 24
        e.append(rect(x, top, width, bar_h, color, WHITE, 2, 0))
        centers.append(x + width / 2)
        if cycles > 2:
            e.append(text(x + width / 2, top + bar_h / 2,
                          f"{name}\n{cycles}", 18, "middle", "bold", WHITE))
        else:
            e.append(text(x + width / 2, top + bar_h / 2, str(cycles), 17,
                          "middle", "bold", WHITE))
        x += width
    e += [text(centers[1], 82, "COMPUTE\nSCALAR", 16, "middle", "normal", ORANGE),
          line(centers[1], 112, centers[1], 135, ORANGE, 2, None, True),
          text(centers[2], 270, "COMPUTE\nWEIGHT", 16, "middle", "normal", PURPLE),
          line(centers[2], 238, centers[2], 225, PURPLE, 2, None, True),
          text(35, 315,
               "No-stall TCDM handshake; software command/polling and RVV phase excluded",
               16, "start", "normal", MID)]
    export("figure4_smu_schedule", w, h, e)


def integration() -> None:
    w, h = 1800, 880
    e = header(w, h)
    e.append(text(30, 30, "Spatz prototype integration and execution sequence",
                  28, "start", "bold"))
    e += [text(30, 95, "a", 25, "start", "bold"),
          text(75, 95, "Cluster integration", 22, "start", "bold")]
    box(e, 70, 155, 260, 135, "RISC-V core\nsoftware", LIGHT, MID, 21, "bold")
    box(e, 420, 170, 285, 105, "Cluster peripheral\nMMIO registers", LIGHT, MID,
        19, "bold")
    box(e, 810, 150, 285, 145, "Scalar SMU\nrecurrence FSM", BLUE_PALE, BLUE,
        21, "bold")
    tag(e, 825, 160, "NEW", BLUE)
    box(e, 1240, 150, 330, 145, "Spatz RVV\nVLSU + arithmetic", GREEN_PALE,
        GREEN, 21, "bold")
    tag(e, 1255, 160, "REUSED", GREEN)
    box(e, 370, 360, 1040, 70, "TCDM interconnect", WHITE, MID, 22, "bold")
    box(e, 370, 480, 1040, 70, "128 KiB shared TCDM (16 banks)", LIGHT, MID,
        21, "bold")
    e += [line(330, 220, 420, 220, MID, 2, "8 6", True), text(375, 198, "MMIO", 16),
          line(705, 220, 810, 220, MID, 2, "8 6", True),
          text(758, 198, "start / status", 16),
          line(952, 295, 820, 360, BLUE, 3, None, True, True),
          text(900, 330, "independent requester", 17, "middle", "normal", BLUE),
          line(1405, 295, 1320, 360, GREEN, 3, None, True, True),
          text(1430, 330, "existing TCDM ports", 17, "middle", "normal", GREEN),
          line(890, 430, 890, 480, MID, 3, None, True, True)]
    e += [text(30, 610, "b", 25, "start", "bold"),
          text(75, 610, "Software-hardware sequence", 22, "start", "bold")]
    lanes = [(300, "CPU / software"), (720, "Scalar SMU"),
             (1140, "Shared TCDM"), (1560, "RVV")]
    for x, label in lanes:
        e += [text(x, 655, label, 19, "middle", "bold"),
              line(x, 680, x, 855, GRID, 2, "6 5")]
    events = [
        (300, 700, 720, "configure + start", MID, "8 6"),
        (720, 730, 1140, "read scalar state", BLUE, None),
        (720, 760, 1140, "write state + weights", BLUE, None),
        (720, 790, 300, "done", MID, "8 6"),
        (300, 820, 1560, "invoke RVV update", GREEN, "8 6"),
        (1560, 850, 1140, "O[D] loads / stores", GREEN, None),
    ]
    for x1, y, x2, label, color, dash in events:
        e += [line(x1, y, x2, y, color, 2, dash, True),
              text((x1 + x2) / 2, y - 13, label, 16, "middle", "normal", color)]
    export("figure5_spatz_integration", w, h, e)


def load_scaling() -> dict[str, dict[str, float]]:
    params: dict[str, dict[str, float]] = {}
    with SCALING.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] == "parameter":
                params[row["config"]] = {
                    "Cs": float(row["Cs"]), "Cv": float(row["Cv"]),
                    "R2": float(row["R_squared"]),
                }
    required = {"B2R_RVV", "A1_SMU_SCALAR", "A2_SMU_FULL"}
    if not required <= set(params):
        raise ValueError(f"missing scaling parameters: {required - set(params)}")
    return params


def scaling_plot() -> None:
    w, h = 1800, 720
    e = header(w, h)
    params = load_scaling()
    order = ("B2R_RVV", "A1_SMU_SCALAR", "A2_SMU_FULL")
    labels = ("B2R\nmatched RVV", "Proposed\nScalar SMU + RVV",
              "Full-Offload\ndesign point")
    colors = (GREEN, BLUE, RED)
    assert all(params[cfg]["Cs"] > 0 for cfg in order), \
        "C_s must remain positive on the log axis"
    e.append(text(900, 35, "Fitted cycle-growth coefficients", 28,
                  "middle", "bold"))
    # Cs log panel.
    e += [text(35, 90, "a", 25, "start", "bold"),
          text(110, 90, "N-dependent recurrence component", 23, "start", "bold")]
    left, top, pw, ph = 130, 150, 650, 390
    e += [line(left, top, left, top + ph, DARK, 2),
          line(left, top + ph, left + pw, top + ph, DARK, 2)]
    lo, hi = 10.0, 2000.0
    ylog = lambda v: top + ph * (math.log10(hi) - math.log10(v)) / (math.log10(hi) - math.log10(lo))
    for tick in (10, 100, 1000):
        y = ylog(tick)
        e += [line(left, y, left + pw, y, GRID, 1),
              text(left - 15, y, str(tick), 17, "end", "normal", MID)]
    e.append(text(52, top + ph / 2, "Fitted C_s (cycles/row)", 18,
                  "middle", "bold", DARK, -90))
    centers = [left + pw * (i + 0.5) / 3 for i in range(3)]
    for x, cfg, label, color in zip(centers, order, labels, colors):
        value = params[cfg]["Cs"]
        if value <= 0:
            raise ValueError("C_s must remain positive on the log axis")
        y = ylog(value)
        e += [rect(x - 62, y, 124, top + ph - y, color, WHITE, 1, 2),
              text(x, y - 17, f"{value:.2f}", 18, "middle", "bold", color),
              text(x, top + ph + 45, label, 17, "middle")]
    # Cv linear panel.
    e += [text(900, 90, "b", 25, "start", "bold"),
          text(975, 90, "ND-dependent vector component", 23, "start", "bold")]
    left2 = 1030
    e += [line(left2, top, left2, top + ph, DARK, 2),
          line(left2, top + ph, left2 + pw, top + ph, DARK, 2)]
    ymax = 9.0
    ylin = lambda v: top + ph * (1 - v / ymax)
    for tick in (0, 2, 4, 6, 8):
        y = ylin(tick)
        e += [line(left2, y, left2 + pw, y, GRID, 1),
              text(left2 - 15, y, str(tick), 17, "end", "normal", MID)]
    e.append(text(952, top + ph / 2, "Fitted C_v (cycles/element)", 18,
                  "middle", "bold", DARK, -90))
    centers2 = [left2 + pw * (i + 0.5) / 3 for i in range(3)]
    for x, cfg, label, color in zip(centers2, order, labels, colors):
        value = params[cfg]["Cv"]
        y = ylin(value)
        e += [rect(x - 62, y, 124, top + ph - y, color, WHITE, 1, 2),
              text(x, y - 17, f"{value:.2f}", 18, "middle", "bold", color),
              text(x, top + ph + 45, label, 17, "middle")]
    e.append(text(900, 690, "23 measured RTL/Verilator shapes per design",
                  17, "middle", "normal", MID))
    export("figure2_scaling", w, h, e)


def tradeoff_plot() -> None:
    w, h = 889, 680
    e = header(w, h)
    ratios: dict[str, dict[str, float]] = {}
    geomean: dict[str, float] = {}
    with WORKLOAD.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["workload"] == "geomean":
                geomean = {"A1": float(row["A1_speedup_over_B2R"]),
                           "A2": float(row["A2_speedup_over_B2R"])}
            else:
                ratios[row["workload"]] = {
                    "A1": float(row["A1_speedup_over_B2R"]),
                    "A2": float(row["A2_speedup_over_B2R"]),
                }
    areas: dict[str, float] = {}
    with AREA.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            areas[row["design"]] = float(row["liberty_area"]) / 1000.0
    if set(ratios) != {"BERT", "Mistral", "Qwen14B"}:
        raise ValueError("workload rows do not match the frozen three-shape set")
    e.append(text(444, 28, "Specialization tradeoff", 24, "middle", "bold"))
    left, top, pw, ph = 95, 85, 730, 455
    xmin, xmax, ymin, ymax = -8.0, 126.0, 0.5, 5.2
    xmap = lambda value: left + pw * (value - xmin) / (xmax - xmin)
    ymap = lambda value: top + ph * (ymax - value) / (ymax - ymin)
    for tick in (0, 20, 40, 60, 80, 100, 120):
        x = xmap(tick)
        e += [line(x, top, x, top + ph, GRID, 1),
              text(x, top + ph + 24, str(tick), 16, "middle", "normal", MID)]
    for tick in (1, 2, 3, 4, 5):
        y = ymap(tick)
        e += [line(left, y, left + pw, y, GRID, 1),
              text(left - 12, y, str(tick), 16, "end", "normal", MID)]
    e += [line(left, top, left, top + ph, DARK, 2),
          line(left, top + ph, left + pw, top + ph, DARK, 2),
          text(30, top + ph / 2, "Cycle-count ratio over B2R", 18,
               "middle", "bold", DARK, -90),
          text(left + pw / 2, 632,
               "Standalone block area (10³ Nangate45 Liberty units)",
               18, "middle", "bold")]
    points = {"B2R": (0.0, 1.0, GREEN),
              "Proposed": (areas["A1"], geomean["A1"], BLUE),
              "Full-Offload": (areas["A2"], geomean["A2"], RED)}
    for label, (area, gm, color) in points.items():
        x, y = xmap(area), ymap(gm)
        e += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="{color}" '
              f'stroke="white" stroke-width="2"/>',
              text(x + (18 if label == "B2R" else -18),
                   y - 24 if label == "B2R" else y,
                   f"{gm:.2f}×", 20,
                   "start" if label == "B2R" else "end", "bold", color)]
        for workload, short, side in (("BERT", "B", "right"),
                                      ("Mistral", "M", "left"),
                                      ("Qwen14B", "Q", "right")):
            if label == "B2R":
                continue
            value = ratios[workload]["A1" if label == "Proposed" else "A2"]
            yy = ymap(value)
            e += [f'<rect x="{x - 6:.1f}" y="{yy - 6:.1f}" width="12" height="12" '
                  f'fill="{color}" stroke="white" stroke-width="1"/>',
                  text(x + (13 if side == "right" else -13), yy,
                       short, 14, "start" if side == "right" else "end",
                       "bold", color)]
    e += [text(xmap(0), top + ph + 54, "0\nB2R", 16),
          text(xmap(areas["A1"]), top + ph + 54, f"{areas['A1']:.3f}\nProposed", 16),
          text(xmap(areas["A2"]), top + ph + 54,
               f"{areas['A2']:.3f}\nFull-Offload", 16)]
    export("figure3_hardware_tradeoff", w, h, e)


def main() -> None:
    motivation()
    architecture()
    datapath()
    schedule()
    integration()
    scaling_plot()
    tradeoff_plot()


if __name__ == "__main__":
    main()
