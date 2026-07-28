#!/usr/bin/env python3
"""Generate P0 progressive-cycle figures from parsed CSV evidence."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
from pathlib import Path
from typing import Any, Sequence


CONFIGS = (
    "B1_SCALAR",
    "B2R_RVV",
    "A1_SMU_SCALAR",
    "A2_SMU_FULL",
)
COLORS = ("#6b7280", "#2563eb", "#ea580c", "#059669")


def require_plot_runtime() -> None:
    missing = [
        package
        for package in ("matplotlib", "numpy")
        if importlib.util.find_spec(package) is None
    ]
    if missing:
        raise SystemExit(
            "Python plotting backend unavailable; missing package(s): "
            + ", ".join(missing)
            + ". No cross-backend fallback was used."
        )


def configure_matplotlib() -> None:
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Arial",
                "Helvetica",
                "DejaVu Sans",
                "sans-serif",
            ],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 7,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
        }
    )


def save_figure_bundle(figure: Any, output: Path) -> None:
    stem = output.with_suffix("")
    figure.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    figure.savefig(output, bbox_inches="tight")
    figure.savefig(
        stem.with_suffix(".png"), dpi=600, bbox_inches="tight"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--progressive-csv",
        type=Path,
        default=root / "experiments/parsed/progressive_baseline.csv",
    )
    parser.add_argument(
        "--breakdown-csv",
        type=Path,
        default=root / "experiments/parsed/progressive_breakdown.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "experiments/plots",
    )
    parser.add_argument("--allow-ineligible", action="store_true")
    return parser.parse_args(argv)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def number(value: str | None) -> float:
    if value in (None, "", "NA"):
        return math.nan
    return float(value)


def require_eligible(rows: list[dict[str, str]], allow: bool) -> None:
    if allow:
        return
    ineligible = [
        row
        for row in rows
        if row.get("paper_eligible") not in (None, "", "YES")
    ]
    if ineligible:
        raise SystemExit(
            "refusing to plot paper-ineligible rows; use "
            "--allow-ineligible only for diagnostic figures"
        )


def require_complete_matrix(rows: list[dict[str, str]]) -> None:
    by_coordinate: dict[tuple[int, int], set[str]] = {}
    for row in rows:
        coordinate = (int(row["N"]), int(row["D"]))
        by_coordinate.setdefault(coordinate, set()).add(row["config"])
    expected = set(CONFIGS)
    incomplete = {
        coordinate: sorted(expected - configs)
        for coordinate, configs in by_coordinate.items()
        if configs != expected
    }
    if incomplete:
        raise SystemExit(f"incomplete progressive matrix: {incomplete}")


def progressive_plot(
    rows: list[dict[str, str]], output: Path, diagnostic: bool
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    coordinates = sorted(
        {(int(row["N"]), int(row["D"])) for row in rows}
    )
    index: dict[tuple[int, int, str], dict[str, str]] = {
        (int(row["N"]), int(row["D"]), row["config"]): row
        for row in rows
    }
    x = np.arange(len(coordinates))
    width = 0.19
    figure, axis = plt.subplots(figsize=(7.2, 4.0))
    for config_index, config in enumerate(CONFIGS):
        values = [
            number(index.get((*coordinate, config), {}).get("kernel_cycles"))
            for coordinate in coordinates
        ]
        axis.bar(
            x + (config_index - 1.5) * width,
            values,
            width,
            color=COLORS[config_index],
            label=config,
        )
    axis.set_xticks(x, [f"({n},{d})" for n, d in coordinates])
    axis.set_xlabel("Merge shape (N,D)")
    axis.set_ylabel("Kernel cycles")
    title = "Progressive Online-Merge Baselines"
    axis.set_title(title + (" [DIAGNOSTIC]" if diagnostic else ""))
    axis.grid(axis="y", alpha=0.25)
    axis.legend(frameon=False, ncol=2)
    figure.tight_layout()
    save_figure_bundle(figure, output)
    plt.close(figure)


def breakdown_plot(
    rows: list[dict[str, str]], output: Path, diagnostic: bool
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    ordered = sorted(
        rows,
        key=lambda row: (
            int(row["N"]),
            int(row["D"]),
            CONFIGS.index(row["config"]),
        ),
    )
    labels = [
        f"{row['config']}\n({row['N']},{row['D']})" for row in ordered
    ]
    components = (
        ("software_scalar_cycles", "Software scalar", "#6b7280"),
        ("rvv_cycles", "RVV", "#2563eb"),
        ("smu_scalar_compute_cycles", "SMU scalar", "#ea580c"),
        ("smu_vector_compute_cycles", "SMU vector", "#059669"),
        ("memory_fsm_cycles", "Memory/FSM", "#7c3aed"),
        ("command_and_sync_cycles", "Command/sync", "#db2777"),
        ("loop_control_cycles", "Loop/control", "#0891b2"),
        ("other_cycles", "Other", "#a16207"),
        ("stall_or_other_cycles", "Unclassified/stall", "#d1d5db"),
    )
    x = np.arange(len(ordered))
    bottom = np.zeros(len(ordered))
    figure, axis = plt.subplots(figsize=(7.2, 4.6))
    for field, label, color in components:
        values = np.array(
            [
                0.0
                if math.isnan(number(row.get(field)))
                else number(row.get(field))
                for row in ordered
            ]
        )
        axis.bar(x, values, bottom=bottom, label=label, color=color)
        bottom += values
    axis.set_xticks(x, labels, rotation=35, ha="right")
    axis.set_ylabel("Kernel cycles")
    title = "Cycle Decomposition (Trace Estimates / FSM Counters)"
    axis.set_title(title + (" [DIAGNOSTIC]" if diagnostic else ""))
    axis.grid(axis="y", alpha=0.25)
    axis.legend(frameon=False, ncol=4, fontsize=8)
    figure.tight_layout()
    save_figure_bundle(figure, output)
    plt.close(figure)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    progressive = read_csv(args.progressive_csv.resolve())
    breakdown = read_csv(args.breakdown_csv.resolve())
    if not progressive or not breakdown:
        raise SystemExit("parsed CSV files contain no rows")
    require_complete_matrix(progressive)
    require_complete_matrix(breakdown)
    require_eligible(progressive, args.allow_ineligible)
    diagnostic = any(
        row.get("paper_eligible") not in (None, "", "YES")
        for row in progressive
    )
    require_plot_runtime()
    configure_matplotlib()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    progressive_plot(
        progressive,
        output_dir / "progressive_cycles.pdf",
        diagnostic,
    )
    breakdown_plot(
        breakdown,
        output_dir / "progressive_breakdown.pdf",
        diagnostic,
    )
    print(output_dir / "progressive_cycles.pdf")
    print(output_dir / "progressive_breakdown.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
