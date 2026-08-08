#!/usr/bin/env python3
"""P4/P5 standalone area bar chart (Scalar vs Full + module composition)."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "experiments" / "plots" / "p4_p5_standalone_area.png"

exp = 5978.882
recip = 7516.096
scalar_ctrl = 63608.314
scalar_total = 77103.292
full_total = 114713.298
vector_inc = full_total - scalar_total

fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=150)

# Stacked bar for Scalar: EXP / RECIP / scalar control
ax.bar([0], [exp], color="#4C72B0", label=f"EXP LUT ({exp:,.0f})")
ax.bar([0], [recip], bottom=[exp], color="#DD8452",
       label=f"Reciprocal LUT ({recip:,.0f})")
ax.bar([0], [scalar_ctrl], bottom=[exp + recip], color="#55A868",
       label=f"Scalar control+datapath+interface ({scalar_ctrl:,.0f})")
# Full = Scalar + vector increment
ax.bar([1], [scalar_total], color="#C44E52", alpha=0.85,
       label=f"Scalar SMU total ({scalar_total:,.0f})")
ax.bar([1], [vector_inc], bottom=[scalar_total], color="#8172B3",
       hatch="//", label=f"Full vector path incr. ({vector_inc:,.0f})")

ax.set_xticks([0, 1])
ax.set_xticklabels(["Scalar SMU (C1)", "Full SMU (C2)"])
ax.set_ylabel("Mapped area (Nangate45 Liberty units)")
ax.set_title("P4/P5 — Standalone Online-Merge SMU area decomposition")
ax.legend(fontsize=8, loc="upper right")
ax.grid(axis="y", alpha=0.3)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)

fig.tight_layout()
fig.savefig(OUT, bbox_inches="tight")
print(f"wrote {OUT}")
