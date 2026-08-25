#!/usr/bin/env python3
"""Merge-kernel cycle-count ratio versus standalone block area.

x-axis: standalone accelerator-block area in 10^3 Nangate45 Liberty units;
B2R = 0 because it adds no incremental Scalar SMU block, not because cluster
area is zero. The y-axis is the measured merge-kernel cycle-count ratio over
B2R, with B/M/Q workload markers and a geomean marker.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent.parent
WORKLOAD_CSV = ROOT / "experiments" / "parsed" / "final_workload_comparison.csv"
AREA_CSV = ROOT / "experiments" / "parsed" / "final_area.csv"
OUT_PNG = ROOT / "experiments" / "plots" / "figure3_hardware_tradeoff.png"
OUT_PDF = ROOT / "experiments" / "plots" / "figure3_hardware_tradeoff.pdf"
OUT_SVG = ROOT / "experiments" / "plots" / "figure3_hardware_tradeoff.svg"
SVG_METADATA = {"Creator": "M8 Python/matplotlib figure freeze", "Date": None}
PDF_METADATA = {
    "Creator": "M8 Python/matplotlib figure freeze",
    "Producer": "M8 Python/matplotlib figure freeze",
    "CreationDate": None,
    "ModDate": None,
}

# The manuscript places Figure 3 in one IEEE column.  Keep the export compact
# enough for that placement while retaining editable vector text.
fig_width_mm = 88.9
fig_height_mm = 68.0
mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "svg.fonttype": "none",
        "svg.hashsalt": "m4-figure3",
        "pdf.fonttype": 42,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.facecolor": "white",
        "figure.facecolor": "white",
        "legend.frameon": False,
        "savefig.facecolor": "white",
    }
)

CONFIGS = ("B2R_RVV", "A1_SMU_SCALAR", "A2_SMU_FULL")
LABELS = {"B2R_RVV": "B2R (matched RVV)",
          "A1_SMU_SCALAR": "Proposed",
          "A2_SMU_FULL": "Full-Offload design point"}
COLORS = {"B2R_RVV": "#55A868", "A1_SMU_SCALAR": "#4C72B0",
          "A2_SMU_FULL": "#C44E52"}
WORKLOADS = ("BERT", "Mistral", "Qwen14B")
WORKLOAD_SHORT = {"BERT": "B", "Mistral": "M", "Qwen14B": "Q"}
WORKLOAD_MARKERS = {"BERT": "s", "Mistral": "^", "Qwen14B": "D"}

ratios = {}
geomean = {}
with WORKLOAD_CSV.open(encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        if r["workload"] == "geomean":
            geomean = {
                "A1_SMU_SCALAR": float(r["A1_speedup_over_B2R"]),
                "A2_SMU_FULL": float(r["A2_speedup_over_B2R"]),
            }
        else:
            assert r["status"].startswith("VERIFIED_M2"), r["status"]
            ratios[r["workload"]] = {
                "A1_SMU_SCALAR": float(r["A1_speedup_over_B2R"]),
                "A2_SMU_FULL": float(r["A2_speedup_over_B2R"]),
            }

assert set(ratios) == set(WORKLOADS), set(ratios)
assert set(geomean) == {"A1_SMU_SCALAR", "A2_SMU_FULL"}

area = {}
with AREA_CSV.open(encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        area[r["design"]] = float(r["liberty_area"])

x = {"B2R_RVV": 0.0,
     "A1_SMU_SCALAR": area["A1"] / 1000.0,
     "A2_SMU_FULL": area["A2"] / 1000.0}
assert x["A1_SMU_SCALAR"] > 0 and x["A2_SMU_FULL"] > x["A1_SMU_SCALAR"]

fig, ax = plt.subplots(
    figsize=(fig_width_mm / 25.4, fig_height_mm / 25.4),
    dpi=600,
    facecolor="white",
)
gms = {"B2R_RVV": 1.0}
for cfg in CONFIGS:
    if cfg == "B2R_RVV":
        continue
    per_wl = [ratios[w][cfg] for w in WORKLOADS]
    gm = geomean[cfg]
    derived_gm = math.prod(per_wl) ** (1.0 / len(per_wl))
    assert abs(gm - derived_gm) < 1e-9, (cfg, gm, derived_gm)
    gms[cfg] = gm
    ax.scatter([x[cfg]], [gm], s=110, color=COLORS[cfg], zorder=3,
               label=LABELS[cfg])
    for wl, v in zip(WORKLOADS, per_wl):
        ax.scatter([x[cfg]], [v], s=54, color=COLORS[cfg],
                   edgecolors="white", linewidths=1.0,
                   marker=WORKLOAD_MARKERS[wl], zorder=4)
        ax.annotate(WORKLOAD_SHORT[wl], (x[cfg], v),
                    textcoords="offset points",
                    xytext=(7, 0) if wl == "BERT" else
                    (-10, 5) if wl == "Mistral" else (-10, -10),
                    ha="left" if wl == "BERT" else "right",
                    va="center", fontsize=6.5, color=COLORS[cfg],
                    fontweight="bold", zorder=6)
# B2R reference point
ax.scatter([x["B2R_RVV"]], [1.0], s=110, color=COLORS["B2R_RVV"], zorder=3,
           label=LABELS["B2R_RVV"])

for cfg in CONFIGS:
    xx, yy = x[cfg], gms[cfg]
    ha = "left" if cfg == "B2R_RVV" else "center"
    ax.annotate(f"{yy:.2f}×", (xx, yy), textcoords="offset points",
                xytext=(8, 6) if ha == "left" else
                (28, 8) if cfg == "A1_SMU_SCALAR" else (0, 8),
                ha=ha, fontsize=9, color=COLORS[cfg], fontweight="bold")

ax.set_xticks([x[cfg] for cfg in CONFIGS])
ax.set_xticklabels([
    "0\nB2R",
    f"{x['A1_SMU_SCALAR']:.3f}\nProposed",
    f"{x['A2_SMU_FULL']:.3f}\nFull-Offload",
], fontsize=7, linespacing=1.1)
ax.set_xlabel(r"Standalone block area "
              r"($10^3$ Nangate45 Liberty units)", fontsize=8)
ax.set_ylabel("Merge-kernel cycle-count ratio over B2R", fontsize=8)
ax.set_title("Specialization tradeoff", fontsize=8.5, pad=2)
ax.grid(alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(labelsize=7)
ax.set_xlim(-8, max(x.values()) + 12)
fig.tight_layout()
# Preserve the requested canvas exactly; do not use bbox_inches="tight".
fig.savefig(OUT_SVG, facecolor="white", metadata=SVG_METADATA)
svg_text = OUT_SVG.read_text(encoding="utf-8")
OUT_SVG.write_text(
    "\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n",
    encoding="utf-8",
)
fig.savefig(OUT_PDF, facecolor="white", metadata=PDF_METADATA)
fig.savefig(OUT_PNG, dpi=600, facecolor="white")
plt.close(fig)
print(f"wrote {OUT_SVG}, {OUT_PDF}, {OUT_PNG}")
