#!/usr/bin/env python3
"""Hardware performance-area trade-off figure.

x-axis: standalone SMU mapped area in 10^3 Liberty units (P0-6 exact;
B2R = 0 since it adds no SMU).  y-axis: cycle speedup over B2R at
iso-frequency.  Points per design are geometric means over BERT/Mistral/Qwen,
with per-workload markers.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent.parent
MODEL = ROOT / "experiments" / "parsed" / "final_scaling_model.csv"
P06 = ROOT / "experiments" / "parsed" / "p0_6" / "p0_6_synthesis_summary.csv"
OUT_PNG = ROOT / "experiments" / "plots" / "figure3_hardware_tradeoff.png"
OUT_PDF = ROOT / "experiments" / "plots" / "figure3_hardware_tradeoff.pdf"

CONFIGS = ("B2R_RVV", "A1_SMU_SCALAR", "A2_SMU_FULL")
LABELS = {"B2R_RVV": "B2R (RVV SW)",
          "A1_SMU_SCALAR": "Proposed (Scalar SMU + RVV)",
          "A2_SMU_FULL": "Full-Offload Ablation"}
COLORS = {"B2R_RVV": "#55A868", "A1_SMU_SCALAR": "#4C72B0",
          "A2_SMU_FULL": "#C44E52"}
WORKLOADS = ("BERT", "Mistral", "Qwen14B")

cycles = {}
with MODEL.open(encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        if r["kind"] == "workload":
            cycles.setdefault(r["workload"], {})[r["config"]] = int(r["measured_cycles"])

area = {}
with P06.open(encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        area[r["config_id"]] = float(r["mapped_cell_area"])

x = {"B2R_RVV": 0.0,
     "A1_SMU_SCALAR": area["C1_SCALAR"] / 1000.0,
     "A2_SMU_FULL": area["C2_FULL"] / 1000.0}

fig, ax = plt.subplots(figsize=(6.6, 4.4), dpi=150)
gms = {"B2R_RVV": 1.0}
for cfg in CONFIGS:
    if cfg == "B2R_RVV":
        continue
    per_wl = [cycles[w]["B2R_RVV"] / cycles[w][cfg] for w in WORKLOADS]
    gm = math.prod(per_wl) ** (1.0 / len(per_wl))
    gms[cfg] = gm
    ax.scatter([x[cfg]], [gm], s=110, color=COLORS[cfg], zorder=3,
               label=LABELS[cfg])
    for wl, v in zip(WORKLOADS, per_wl):
        ax.scatter([x[cfg]], [v], s=58, color="white", linewidths=2.4,
                   marker="x", zorder=4)
        ax.scatter([x[cfg]], [v], s=34, color=COLORS[cfg], alpha=0.45,
                   marker="x", zorder=5)
# B2R reference point
ax.scatter([x["B2R_RVV"]], [1.0], s=110, color=COLORS["B2R_RVV"], zorder=3,
           label=LABELS["B2R_RVV"])

for cfg in CONFIGS:
    xx, yy = x[cfg], gms[cfg]
    ha = "left" if cfg == "B2R_RVV" else "center"
    ax.annotate(f"{yy:.2f}×", (xx, yy), textcoords="offset points",
                xytext=(8, 6) if ha == "left" else
                (28, 8) if cfg == "A1_SMU_SCALAR" else (0, 8),
                ha="center", fontsize=9, color=COLORS[cfg], fontweight="bold")

ax.set_xlabel("Standalone SMU mapped area (10^3 Liberty units)")
ax.set_ylabel("Cycle speedup over B2R (iso-frequency)")
ax.set_title("Performance–area trade-off\n"
             "(×=per workload: BERT / Mistral / Qwen14B; ●=geomean)",
             fontsize=10)
ax.grid(alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(fontsize=8, loc="upper left")
fig.tight_layout()
for p in (OUT_PNG, OUT_PDF):
    fig.savefig(p, bbox_inches="tight")
print(f"wrote {OUT_PNG}, {OUT_PDF}")
