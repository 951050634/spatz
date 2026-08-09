#!/usr/bin/env python3
"""Draw Figure 1: the proposed selective-offload architecture.

This is a schematic rather than a data plot.  The drawing keeps the scalar
recurrence and the existing RVV update visibly separate, with the shared TCDM
as the only data path between them.  Software/MMIO sequencing is dashed;
data movement is solid.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle


# Figure contract: 180 x 88 mm, editable text, and a 600 dpi review raster.
fig_width_mm = 180.0
fig_height_mm = 88.0
mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.linewidth": 0.8,
        "patch.antialiased": True,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    }
)

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "experiments" / "plots"
OUT_SVG = OUT_DIR / "figure1_proposed_architecture.svg"
OUT_PDF = OUT_DIR / "figure1_proposed_architecture.pdf"
OUT_PNG = OUT_DIR / "figure1_proposed_architecture.png"

BLUE = "#4C72B0"
BLUE_PALE = "#E4ECF7"
GREEN = "#55A868"
GREEN_PALE = "#E5F1E9"
NEUTRAL = "#4C4C4C"
NEUTRAL_MID = "#737373"
NEUTRAL_PALE = "#F3F4F5"
BOUNDARY = "#656565"
WHITE = "#FFFFFF"


def add_box(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    facecolor: str,
    edgecolor: str,
    linewidth: float = 0.9,
    linestyle: str = "-",
    radius: float = 0.012,
    zorder: int = 2,
) -> FancyBboxPatch:
    """Add a rounded box in axes-fraction coordinates."""
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0.004,rounding_size={radius}",
        transform=ax.transAxes,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        linestyle=linestyle,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def add_text(
    ax: plt.Axes,
    x: float,
    y: float,
    text: str,
    *,
    size: float = 7.0,
    color: str = NEUTRAL,
    weight: str = "normal",
    ha: str = "center",
    va: str = "center",
    zorder: int = 5,
    **kwargs: object,
) -> None:
    ax.text(
        x,
        y,
        text,
        transform=ax.transAxes,
        fontsize=size,
        color=color,
        fontweight=weight,
        ha=ha,
        va=va,
        zorder=zorder,
        **kwargs,
    )


def add_arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = NEUTRAL,
    dashed: bool = False,
    linewidth: float = 0.9,
    mutation_scale: float = 9.0,
    arrowstyle: str = "->",
    connectionstyle: str = "arc3",
    zorder: int = 3,
) -> FancyArrowPatch:
    style = (0, (3.0, 2.2)) if dashed else "-"
    arrow = FancyArrowPatch(
        start,
        end,
        transform=ax.transAxes,
        arrowstyle=arrowstyle,
        mutation_scale=mutation_scale,
        linewidth=linewidth,
        linestyle=style,
        color=color,
        connectionstyle=connectionstyle,
        zorder=zorder,
    )
    ax.add_patch(arrow)
    return arrow


def add_routed_arrow(
    ax: plt.Axes,
    points: list[tuple[float, float]],
    *,
    color: str = NEUTRAL_MID,
    dashed: bool = True,
    linewidth: float = 0.85,
    zorder: int = 3,
) -> None:
    """Draw a polyline and put one arrowhead on its final segment."""
    style = (0, (3.0, 2.2)) if dashed else "-"
    xs, ys = zip(*points)
    ax.plot(
        xs,
        ys,
        transform=ax.transAxes,
        color=color,
        linewidth=linewidth,
        linestyle=style,
        solid_capstyle="round",
        zorder=zorder,
    )
    add_arrow(
        ax,
        points[-2],
        points[-1],
        color=color,
        dashed=dashed,
        linewidth=linewidth,
        mutation_scale=8.5,
        zorder=zorder + 1,
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(
        figsize=(fig_width_mm / 25.4, fig_height_mm / 25.4),
        facecolor=WHITE,
    )
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")
    ax.set_facecolor(WHITE)

    # Header and semantic key.
    add_text(
        ax,
        0.025,
        0.955,
        "Selective Offloading",
        size=10,
        color=NEUTRAL,
        weight="bold",
        ha="left",
    )
    add_text(
        ax,
        0.025,
        0.918,
        "Scalar SMU + RVV proposed design",
        size=7.2,
        color=NEUTRAL_MID,
        ha="left",
    )

    # Keep the legend compact so the main blocks retain visual priority.
    add_box(ax, 0.615, 0.943, 0.022, 0.018, facecolor=BLUE_PALE, edgecolor=BLUE,
            linewidth=0.7, radius=0.004, zorder=4)
    add_text(ax, 0.642, 0.952, "new", size=7, color=BLUE, ha="left")
    add_box(ax, 0.690, 0.943, 0.022, 0.018, facecolor=GREEN_PALE, edgecolor=GREEN,
            linewidth=0.7, radius=0.004, zorder=4)
    add_text(ax, 0.717, 0.952, "reused", size=7, color=GREEN, ha="left")
    ax.plot([0.795, 0.820], [0.952, 0.952], transform=ax.transAxes,
            color=NEUTRAL, linewidth=0.85, zorder=4)
    add_text(ax, 0.826, 0.952, "solid=data", size=7, color=NEUTRAL, ha="left")
    ax.plot([0.795, 0.820], [0.919, 0.919], transform=ax.transAxes,
            color=NEUTRAL_MID, linewidth=0.85, linestyle=(0, (3, 2)), zorder=4)
    add_text(ax, 0.826, 0.919, "dashed=software/MMIO", size=7,
             color=NEUTRAL_MID, ha="left")
    add_text(ax, 0.826, 0.895, "sequencing", size=7, color=NEUTRAL_MID,
             ha="left")

    # Boundary containing exactly the control interface plus the two datapaths.
    boundary_x, boundary_y = 0.205, 0.245
    boundary_w, boundary_h = 0.765, 0.625
    boundary = Rectangle(
        (boundary_x, boundary_y),
        boundary_w,
        boundary_h,
        transform=ax.transAxes,
        facecolor="none",
        edgecolor=BOUNDARY,
        linewidth=0.9,
        linestyle=(0, (4.0, 3.0)),
        zorder=1,
    )
    ax.add_patch(boundary)
    add_text(
        ax,
        boundary_x + 0.018,
        boundary_y + boundary_h - 0.002,
        "Proposed Design Boundary",
        size=8,
        color=BOUNDARY,
        weight="bold",
        ha="left",
        va="bottom",
        zorder=6,
        bbox={"facecolor": WHITE, "edgecolor": "none", "pad": 1.6},
    )

    # Software/Core remains outside the hardware boundary.
    add_box(ax, 0.025, 0.492, 0.155, 0.225, facecolor=NEUTRAL_PALE,
            edgecolor=NEUTRAL_MID, linewidth=0.9, radius=0.012)
    add_text(ax, 0.1025, 0.678, "Software/Core", size=8, weight="bold")
    add_text(ax, 0.1025, 0.635, "MMIO write + start", size=7)
    add_text(ax, 0.1025, 0.600, "wait busy → done", size=7)
    add_text(ax, 0.1025, 0.558, "load weights", size=7)
    add_text(ax, 0.1025, 0.523, "issue RVV update", size=7)

    # Separate MMIO/control interface at the top of the boundary.
    add_box(ax, 0.275, 0.702, 0.600, 0.122, facecolor=NEUTRAL_PALE,
            edgecolor=NEUTRAL_MID, linewidth=0.9, radius=0.012)
    add_text(ax, 0.575, 0.795, "MMIO Register / Command Interface", size=8,
             weight="bold")
    add_text(ax, 0.575, 0.758, "TCDM offsets, N, D, mode=1 (scalar-only)", size=7.1)
    add_text(ax, 0.575, 0.723, "status: busy / done / error", size=7,
             color=NEUTRAL_MID)

    # Dashed software/MMIO command and return-status paths.
    add_arrow(ax, (0.180, 0.655), (0.275, 0.775), dashed=True,
              color=NEUTRAL_MID, linewidth=0.85)
    add_text(ax, 0.225, 0.826, "TCDM offsets, N, D, mode=1, start", size=7,
             color=NEUTRAL_MID, ha="center",
             bbox={"facecolor": WHITE, "edgecolor": "none", "pad": 1.4})
    add_arrow(ax, (0.275, 0.735), (0.180, 0.585), dashed=True,
              color=NEUTRAL_MID, linewidth=0.85)
    add_text(ax, 0.198, 0.650, "busy / done / error", size=7,
             color=NEUTRAL_MID, ha="left",
             bbox={"facecolor": WHITE, "edgecolor": "none", "pad": 1.2})

    # New Scalar SMU: state recurrence and weight production.
    smu_x, smu_y, smu_w, smu_h = 0.235, 0.340, 0.350, 0.305
    add_box(ax, smu_x, smu_y, smu_w, smu_h, facecolor=BLUE_PALE, edgecolor=BLUE,
            linewidth=1.0, radius=0.014)
    add_box(ax, smu_x + 0.014, smu_y + smu_h - 0.041, 0.040, 0.023,
            facecolor=BLUE, edgecolor=BLUE, linewidth=0.6, radius=0.004, zorder=4)
    add_text(ax, smu_x + 0.034, smu_y + smu_h - 0.029, "NEW", size=7,
             color=WHITE, weight="bold", zorder=5)
    add_text(ax, smu_x + 0.176, smu_y + smu_h - 0.029, "Scalar SMU", size=8,
             color=BLUE, weight="bold")
    add_text(ax, smu_x + smu_w / 2, smu_y + smu_h - 0.068,
             "State-dependent Scalar Recurrence", size=7.1, color=BLUE,
             weight="bold")

    # The recurrence is arranged as a compact vertical chain to preserve the
    # exact state/lookup ordering without shrinking below the 7 pt floor.
    add_box(ax, smu_x + 0.032, smu_y + 0.173, smu_w - 0.064, 0.044,
            facecolor=WHITE, edgecolor=BLUE, linewidth=0.65, radius=0.006, zorder=3)
    add_text(ax, smu_x + smu_w / 2, smu_y + 0.195,
             "(m_old,l_old,m_tile,l_tile)", size=7, color=NEUTRAL)
    add_arrow(ax, (smu_x + smu_w / 2, smu_y + 0.171),
              (smu_x + smu_w / 2, smu_y + 0.142), color=BLUE,
              linewidth=0.75, mutation_scale=7.5)
    add_box(ax, smu_x + 0.032, smu_y + 0.096, smu_w - 0.064, 0.047,
            facecolor=WHITE, edgecolor=BLUE, linewidth=0.65, radius=0.006, zorder=3)
    add_text(ax, smu_x + smu_w / 2, smu_y + 0.120,
             "max + 2× EXP LUTs", size=7, color=NEUTRAL)
    add_arrow(ax, (smu_x + smu_w / 2, smu_y + 0.094),
              (smu_x + smu_w / 2, smu_y + 0.066), color=BLUE,
              linewidth=0.75, mutation_scale=7.5)
    add_box(ax, smu_x + 0.032, smu_y + 0.016, smu_w - 0.064, 0.047,
            facecolor=WHITE, edgecolor=BLUE, linewidth=0.65, radius=0.006, zorder=3)
    add_text(ax, smu_x + smu_w / 2, smu_y + 0.040,
             "l_new → Reciprocal LUT → w_old,w_tile", size=7, color=NEUTRAL)

    # Reused RVV datapath, deliberately independent of the SMU block.
    rvv_x, rvv_y, rvv_w, rvv_h = 0.615, 0.340, 0.315, 0.305
    add_box(ax, rvv_x, rvv_y, rvv_w, rvv_h, facecolor=GREEN_PALE, edgecolor=GREEN,
            linewidth=1.0, radius=0.014)
    add_box(ax, rvv_x + 0.014, rvv_y + rvv_h - 0.041, 0.055, 0.023,
            facecolor=GREEN, edgecolor=GREEN, linewidth=0.6, radius=0.004, zorder=4)
    add_text(ax, rvv_x + 0.0415, rvv_y + rvv_h - 0.029, "REUSED", size=7,
             color=WHITE, weight="bold", zorder=5)
    add_text(ax, rvv_x + 0.215, rvv_y + rvv_h - 0.029,
             "Reuse Existing RVV Datapath", size=7.5, color=GREEN, weight="bold")
    add_text(ax, rvv_x + rvv_w / 2, rvv_y + rvv_h - 0.078,
             "Regular O[D] Vector Update", size=7.1, color=GREEN, weight="bold")
    add_box(ax, rvv_x + 0.007, rvv_y + 0.143, rvv_w - 0.014, 0.050,
            facecolor=WHITE, edgecolor=GREEN, linewidth=0.65, radius=0.006, zorder=3)
    add_text(ax, rvv_x + rvv_w / 2, rvv_y + 0.168,
             "O_new[j]=w_old×O_old[j]+w_tile×O_tile[j]", size=7,
             color=NEUTRAL)
    add_box(ax, rvv_x + 0.007, rvv_y + 0.057, rvv_w - 0.014, 0.050,
            facecolor=WHITE, edgecolor=GREEN, linewidth=0.65, radius=0.006, zorder=3)
    add_text(ax, rvv_x + rvv_w / 2, rvv_y + 0.082,
             "VLSU load → vector multiply/FMA → store", size=7,
             color=NEUTRAL)

    # Shared software-visible TCDM is deliberately below/outside the boundary.
    tcdm_x, tcdm_y, tcdm_w, tcdm_h = 0.270, 0.047, 0.565, 0.112
    add_box(ax, tcdm_x, tcdm_y, tcdm_w, tcdm_h, facecolor=NEUTRAL_PALE,
            edgecolor=NEUTRAL_MID, linewidth=0.9, radius=0.012)
    add_text(ax, tcdm_x + tcdm_w / 2, tcdm_y + 0.077,
             "Shared TCDM (software-visible state)", size=8, weight="bold")
    add_text(ax, tcdm_x + tcdm_w / 2, tcdm_y + 0.031,
             "m/l + w_old,w_tile + O vectors", size=7, color=NEUTRAL_MID)

    # Solid, two-way data paths.  There is intentionally no SMU → RVV arrow.
    add_arrow(ax, (0.405, tcdm_y + tcdm_h), (0.405, smu_y),
              color=BLUE, linewidth=0.95, mutation_scale=8.5, arrowstyle="<->")
    add_text(ax, 0.365, 0.205, "m/l + weights", size=7, color=BLUE,
             ha="right", bbox={"facecolor": WHITE, "edgecolor": "none", "pad": 1.0})
    add_arrow(ax, (0.770, tcdm_y + tcdm_h), (0.770, rvv_y),
              color=GREEN, linewidth=0.95, mutation_scale=8.5, arrowstyle="<->")
    add_text(ax, 0.805, 0.205, "O vectors", size=7, color=GREEN,
             ha="left", bbox={"facecolor": WHITE, "edgecolor": "none", "pad": 1.0})

    # After completion, software reads weights from TCDM and launches RVV.  The
    # route is dashed and originates at Software/Core, not at the SMU.
    add_routed_arrow(
        ax,
        [(0.180, 0.520), (0.195, 0.286), (0.745, 0.286), (0.745, 0.340)],
        color=NEUTRAL_MID,
        dashed=True,
        linewidth=0.8,
    )
    add_text(
        ax,
        0.470,
        0.305,
        "after done: software loads weights from TCDM; issues RVV update",
        size=7,
        color=NEUTRAL_MID,
        bbox={"facecolor": WHITE, "edgecolor": "none", "pad": 1.4},
    )

    # No tight bounding box: preserving the figure canvas is part of the export
    # contract, so the saved page remains exactly 180 x 88 mm.
    fig.savefig(OUT_SVG, facecolor=WHITE)
    fig.savefig(OUT_PDF, facecolor=WHITE)
    fig.savefig(OUT_PNG, dpi=600, facecolor=WHITE)
    plt.close(fig)
    print(f"wrote {OUT_SVG}")
    print(f"wrote {OUT_PDF}")
    print(f"wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
