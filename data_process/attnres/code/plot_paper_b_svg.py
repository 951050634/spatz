#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import csv
import math
from pathlib import Path


BLUE = "#4c78a8"
RED = "#e45756"
GREEN = "#59a14f"
PURPLE = "#b07aa1"
TEAL = "#72b7b2"
GRAY = "#444444"


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def svg_header(width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#222} .axis{stroke:#333;stroke-width:1.2}'
        '.grid{stroke:#ddd;stroke-width:1}</style>',
    ]


def write_svg(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines + ["</svg>\n"]))


def text(x, y, s, size=12, anchor="middle", rotate=None):
    r = f' transform="rotate({rotate} {x} {y})"' if rotate else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}"{r}>{s}</text>'


def line(x1, y1, x2, y2, cls="axis", dash=False):
    dash_attr = ' stroke-dasharray="5 4"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{cls}"{dash_attr}/>'


def rect(x, y, w, h, fill):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"/>'


def bar_chart(path, title, labels, series, ylabel, log=False):
    width, height = 980, 520
    left, right, top, bottom = 85, 30, 58, 110
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [v for _, vals, _ in series for v in vals]
    if log:
        min_v = max(min(v for v in values if v > 0), 1.0)
        max_v = max(values)
        ymap = lambda v: top + plot_h * (1.0 - (math.log10(max(v, min_v)) - math.log10(min_v)) /
                                         (math.log10(max_v) - math.log10(min_v)))
        ticks = [10 ** p for p in range(int(math.floor(math.log10(min_v))),
                                        int(math.ceil(math.log10(max_v))) + 1)]
    else:
        max_v = max(values) * 1.12
        ymap = lambda v: top + plot_h * (1.0 - v / max_v)
        ticks = [max_v * i / 5.0 for i in range(6)]

    lines = svg_header(width, height)
    lines += [text(width / 2, 30, title, 18), text(22, height / 2, ylabel, 13, rotate=-90)]
    for tick in ticks:
        if tick <= 0:
            continue
        y = ymap(tick)
        lines += [line(left, y, width - right, y, "grid"), text(left - 10, y + 4, f"{tick:.0f}", 10, "end")]
    lines += [line(left, top, left, top + plot_h), line(left, top + plot_h, width - right, top + plot_h)]

    group_w = plot_w / len(labels)
    bar_w = group_w / (len(series) + 1.2)
    for si, (name, vals, color) in enumerate(series):
        for i, val in enumerate(vals):
            x = left + i * group_w + (si + 0.55) * bar_w
            y = ymap(val)
            lines.append(rect(x, y, bar_w * 0.86, top + plot_h - y, color))
    for i, label in enumerate(labels):
        x = left + i * group_w + group_w / 2
        lines.append(text(x, top + plot_h + 24, label, 11, rotate=-25))
    for si, (name, _, color) in enumerate(series):
        lx = left + si * 240
        lines += [rect(lx, height - 30, 14, 14, color), text(lx + 20, height - 18, name, 12, "start")]
    write_svg(path, lines)


def line_chart(path, title, xs, ys, labels, ylabel):
    width, height = 920, 500
    left, right, top, bottom = 85, 35, 58, 80
    plot_w, plot_h = width - left - right, height - top - bottom
    max_x, max_y = max(xs), max(ys) * 1.18
    xmap = lambda v: left + plot_w * v / max_x
    ymap = lambda v: top + plot_h * (1.0 - v / max_y)
    lines = svg_header(width, height)
    lines += [text(width / 2, 30, title, 18), text(24, height / 2, ylabel, 13, rotate=-90)]
    lines += [line(left, top, left, top + plot_h), line(left, top + plot_h, width - right, top + plot_h)]
    lines.append(line(left, ymap(1.0), width - right, ymap(1.0), "axis", True))
    pts = " ".join(f"{xmap(x):.1f},{ymap(y):.1f}" for x, y in zip(xs, ys))
    lines.append(f'<polyline points="{pts}" fill="none" stroke="{TEAL}" stroke-width="2.5"/>')
    for x, y, label in zip(xs, ys, labels):
        lines.append(f'<circle cx="{xmap(x):.1f}" cy="{ymap(y):.1f}" r="4" fill="{TEAL}"/>')
        lines.append(text(xmap(x), ymap(y) - 10, f"{label} {y:.1f}x", 10))
    write_svg(path, lines)


def main():
    base = Path(__file__).resolve().parent.parent
    data = base / "data"
    out = base / "pic"
    full = read_rows(data / "online_softmax_full_mixed_bypass.csv")
    attn = read_rows(data / "online_softmax_attention_like_smu.csv")
    numeric = read_rows(data / "online_softmax_full_merge_numeric.csv")

    labels = [f"N{r['N']} D{r['D']}" for r in full]
    bar_chart(out / "paper_b_full_mixed_cycles.svg", "Paper B Full Mixed-Scalar Merge: CPU vs Engine Cycles",
              labels,
              [("software", [int(r["cpu_cycles"]) for r in full], BLUE),
               ("engine", [int(r["engine_cycles"]) for r in full], RED)],
              "Cycles", log=True)
    line_chart(out / "paper_b_full_mixed_speedup.svg", "Paper B Full Mixed-Scalar Merge: Speedup vs Workload Size",
               [int(r["workload_elems"]) for r in full], [float(r["speedup"]) for r in full], labels,
               "Speedup")
    bar_chart(out / "paper_b_full_mixed_tcdm.svg", "Paper B Full Mixed-Scalar Merge: TCDM Counters",
              labels,
              [("accessed", [int(r["tcdm_accessed"]) for r in full], GREEN),
               ("congested", [int(r["tcdm_congested"]) for r in full], PURPLE)],
              "Counter value")
    err_labels = [f"{r['case_name']} N{r['N']} D{r['D']}" for r in numeric]
    bar_chart(out / "paper_b_numeric_error.svg", "Paper B Full Merge: Numeric Approximation Error",
              err_labels,
              [("max abs", [float(r["max_abs_err"]) for r in numeric], RED),
               ("guarded rel", [float(r["guarded_max_rel_err"]) for r in numeric], TEAL),
               ("mean abs", [float(r["mean_abs_err"]) for r in numeric], GREEN)],
              "Error", log=True)
    attn_labels = [f"rows={r['rows']} blocks={r['blocks']} D={r['D']}" for r in attn]
    bar_chart(out / "paper_b_attention_like_smu.svg", "Paper B Attention-Like SMU Merge Chain",
              attn_labels,
              [("software", [int(r["cpu_cycles"]) for r in attn], BLUE),
               ("SMU chain", [int(r["engine_cycles"]) for r in attn], RED)],
              "Cycles", log=True)
    print(f"Generated Paper B SVG plots in: {out}")


if __name__ == "__main__":
    main()
