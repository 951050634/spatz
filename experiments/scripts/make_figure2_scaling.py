#!/usr/bin/env python3
"""Figure 2 — online-softmax-merge scaling decomposition.

Reads the final A1/B2R/A2 scaling model and draws the two-panel bar chart
that supports the core claim: B2R high Cs / low Cv; Full low Cs / high Cv;
Proposed low Cs / low Cv.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent.parent
MODEL = ROOT / "experiments" / "parsed" / "final_scaling_model.csv"
OUT_PNG = ROOT / "experiments" / "plots" / "figure2_scaling.png"
OUT_PDF = ROOT / "experiments" / "plots" / "figure2_scaling.pdf"
OUT_SVG = ROOT / "experiments" / "plots" / "figure2_scaling.svg"

fig_width_mm = 180.0
fig_height_mm = 80.0
mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    }
)

LABELS = {"B2R_RVV": "B2R (RVV SW)",
          "A1_SMU_SCALAR": "Proposed (Scalar SMU + RVV)",
          "A2_SMU_FULL": "Full-Offload Ablation"}
DISPLAY_LABELS = {"B2R_RVV": "B2R (RVV SW)",
                  "A1_SMU_SCALAR": "Proposed (Scalar SMU\n+ RVV)",
                  "A2_SMU_FULL": "Full-Offload\nAblation"}
COLORS = {"B2R_RVV": "#55A868", "A1_SMU_SCALAR": "#4C72B0",
          "A2_SMU_FULL": "#C44E52"}
ORDER = ("B2R_RVV", "A1_SMU_SCALAR", "A2_SMU_FULL")

params = {}
with MODEL.open(encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        if r["kind"] == "parameter":
            params[r["config"]] = {
                "C0": float(r["C0"]), "Cs": float(r["Cs"]),
                "Cv": float(r["Cv"]), "R2": float(r["R_squared"]),
            }

assert set(ORDER) <= set(params), f"missing model params: {set(ORDER) - set(params)}"

fig, axes = plt.subplots(
    1,
    2,
    figsize=(fig_width_mm / 25.4, fig_height_mm / 25.4),
    dpi=600,
    facecolor="white",
)

xs = list(range(len(ORDER)))
# Panel (a): Cs per row, log scale
ax = axes[0]
cs = [params[c]["Cs"] for c in ORDER]
bars = ax.bar(xs, cs, color=[COLORS[c] for c in ORDER], width=0.6)
ax.set_yscale("log")
ax.set_xticks(xs)
ax.set_xticklabels([DISPLAY_LABELS[c] for c in ORDER], fontsize=7,
                   linespacing=1.1)
ax.set_ylabel(r"$C_s$ (cycles per row)", fontsize=8)
ax.set_title("(a) Recurrence cost per row", fontsize=9)
for b, v in zip(bars, cs):
    ax.text(b.get_x() + b.get_width() / 2, v * 1.15, f"{v:.2f}",
            ha="center", va="bottom", fontsize=7)
ax.grid(axis="y", alpha=0.3, which="both")
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(axis="y", labelsize=7)

# Panel (b): Cv per element, linear scale
ax = axes[1]
cv = [params[c]["Cv"] for c in ORDER]
bars = ax.bar(xs, cv, color=[COLORS[c] for c in ORDER], width=0.6)
ax.set_xticks(xs)
ax.set_xticklabels([DISPLAY_LABELS[c] for c in ORDER], fontsize=7,
                   linespacing=1.1)
ax.set_ylabel(r"$C_v$ (cycles per element)", fontsize=8)
ax.set_title("(b) Vector-update cost per element", fontsize=9)
for b, v in zip(bars, cv):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.12, f"{v:.2f}",
            ha="center", va="bottom", fontsize=7)
ax.grid(axis="y", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(axis="y", labelsize=7)

fig.suptitle(
    r"Online-softmax-merge scaling decomposition: $C=C_0+C_sN+C_vND$",
    fontsize=10,
    y=0.965,
)
fig.subplots_adjust(left=0.075, right=0.985, bottom=0.34, top=0.84, wspace=0.27)

# Preserve the requested canvas exactly; do not use bbox_inches="tight".
fig.savefig(OUT_SVG, facecolor="white")
svg_text = OUT_SVG.read_text(encoding="utf-8")
OUT_SVG.write_text(
    "\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n",
    encoding="utf-8",
)
fig.savefig(OUT_PDF, facecolor="white")
fig.savefig(OUT_PNG, dpi=600, facecolor="white")
plt.close(fig)
print(f"wrote {OUT_SVG}, {OUT_PDF}, {OUT_PNG}")
