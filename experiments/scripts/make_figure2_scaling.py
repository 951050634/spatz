#!/usr/bin/env python3
"""P17 Figure 2 — scaling mechanism: Cs (cycles/row) and Cv (cycles/element).

Reads the final A1/B2R/A2 scaling model and draws the two-panel bar chart
that supports the core claim: B2R high Cs / low Cv; Full low Cs / high Cv;
Proposed low Cs / low Cv.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent.parent
MODEL = ROOT / "experiments" / "parsed" / "final_scaling_model.csv"
OUT_PNG = ROOT / "experiments" / "plots" / "figure2_scaling.png"
OUT_PDF = ROOT / "experiments" / "plots" / "figure2_scaling.pdf"

LABELS = {"B2R_RVV": "B2R (RVV SW)", "A1_SMU_SCALAR": "Proposed (Scalar SMU)",
          "A2_SMU_FULL": "Full SMU"}
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

fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.8), dpi=150)

xs = list(range(len(ORDER)))
# Panel (a): Cs per row, log scale
ax = axes[0]
cs = [params[c]["Cs"] for c in ORDER]
bars = ax.bar(xs, cs, color=[COLORS[c] for c in ORDER], width=0.6)
ax.set_yscale("log")
ax.set_xticks(xs)
ax.set_xticklabels([LABELS[c] for c in ORDER], fontsize=8)
ax.set_ylabel("Cs (cycles / row)", fontsize=9)
ax.set_title("(a) Recurrence cost per row", fontsize=9)
for b, v in zip(bars, cs):
    ax.text(b.get_x() + b.get_width() / 2, v * 1.15, f"{v:.0f}",
            ha="center", va="bottom", fontsize=8)
ax.grid(axis="y", alpha=0.3, which="both")
ax.spines[["top", "right"]].set_visible(False)

# Panel (b): Cv per element, linear scale
ax = axes[1]
cv = [params[c]["Cv"] for c in ORDER]
bars = ax.bar(xs, cv, color=[COLORS[c] for c in ORDER], width=0.6)
ax.set_xticks(xs)
ax.set_xticklabels([LABELS[c] for c in ORDER], fontsize=8)
ax.set_ylabel("Cv (cycles / element)", fontsize=9)
ax.set_title("(b) Vector-update cost per element", fontsize=9)
for b, v in zip(bars, cv):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.12, f"{v:.2f}",
            ha="center", va="bottom", fontsize=8)
ax.grid(axis="y", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)

fig.suptitle("P17 Figure 2 — Online-Softmax-Merge scaling mechanism "
             "(C = C0 + Cs·N + Cv·N·D)", fontsize=10)
fig.tight_layout(rect=(0, 0, 1, 0.94))
for p in (OUT_PNG, OUT_PDF):
    fig.savefig(p, bbox_inches="tight")
print(f"wrote {OUT_PNG}, {OUT_PDF}")
