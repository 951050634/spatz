#!/usr/bin/env python3
"""P16 — final hardware results table (CSV) compiled from parsed evidence.

Baseline (B2R) has no SMU increment: mapped cells/area and standalone timing
are n/a.  Latency and throughput are derived at a common iso-frequency so the
cycle effect is isolated (see P8/P9-P11 reports).
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
P06 = REPO_ROOT / "experiments" / "parsed" / "p0_6" / "p0_6_synthesis_summary.csv"
P7 = REPO_ROOT / "experiments" / "parsed" / "p7_timing" / "p7_timing.csv"
P9 = REPO_ROOT / "experiments" / "parsed" / "p9_p11" / "p9_latency.csv"
P10 = REPO_ROOT / "experiments" / "parsed" / "p9_p11" / "p10_throughput.csv"
OUT_DIR = REPO_ROOT / "experiments" / "parsed" / "p16"
OUT_CSV = OUT_DIR / "p16_hardware_results.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    p06 = {r["config_id"]: r for r in read_csv(P06)}
    p7 = {}
    for r in read_csv(P7):
        p7.setdefault(r["label"].split("/")[0], r)
    lat = read_csv(P9)
    thr = read_csv(P10)

    cells = {"baseline": "n/a", "proposed": p06["C1_SCALAR"]["mapped_cell_count"],
             "full": p06["C2_FULL"]["mapped_cell_count"]}
    area = {"baseline": "n/a", "proposed": f"{float(p06['C1_SCALAR']['mapped_cell_area']):,.1f}",
            "full": f"{float(p06['C2_FULL']['mapped_cell_area']):,.1f}"}
    crit = {"baseline": "n/a", "proposed": p7["C1_SCALAR"]["critical_delay_ps"],
            "full": p7["C2_FULL"]["critical_delay_ps"]}
    fmax = {"baseline": "n/a", "proposed": p7["C1_SCALAR"]["fmax_mhz"],
            "full": p7["C2_FULL"]["fmax_mhz"]}

    # geomean latency/throughput over the 3 workloads per design
    gmean = {}
    for role, cfg in (("baseline", "B2R_RVV"), ("proposed", "A1_SMU_SCALAR"),
                      ("full", "A2_SMU_FULL")):
        lat_us = [float(r["latency_us"]) for r in lat if r["config"] == cfg]
        thr_m = [float(r["throughput_MElements_per_s"]) for r in thr
                 if r["config"] == cfg]
        gmean[role] = {
            "latency_us": math.prod(lat_us) ** (1.0 / len(lat_us)),
            "throughput": math.prod(thr_m) ** (1.0 / len(thr_m)),
        }

    norm_area = {"baseline": None, "proposed": 1.0,
                 "full": float(p06["C2_FULL"]["mapped_cell_area"]) / float(
                     p06["C1_SCALAR"]["mapped_cell_area"])}
    ae = {role: (gmean[role]["throughput"] / norm_area[role]
                 if norm_area[role] else None) for role in gmean}

    lat_by_wl = {}
    for r in lat:
        lat_by_wl.setdefault(r["workload"], {})[r["config"]] = float(r["latency_us"])
    wl_order = ("BERT", "Mistral", "Qwen14B")

    rows = [
        ("metric", "baseline", "proposed", "full"),
        *[
            (f"{wl} derived iso-frequency latency (us)",
             f"{lat_by_wl[wl]['B2R_RVV']:.1f}",
             f"{lat_by_wl[wl]['A1_SMU_SCALAR']:.1f}",
             f"{lat_by_wl[wl]['A2_SMU_FULL']:.1f}")
            for wl in wl_order
        ],
        ("Standalone mapped cells (P0-6, SMU increment)",
         cells["baseline"], cells["proposed"], cells["full"]),
        ("Standalone mapped area (P0-6, Liberty units, SMU increment)",
         area["baseline"], area["proposed"], area["full"]),
        ("Standalone critical delay (P7, pre-layout ABC, ps)", crit["baseline"],
         f"{float(crit['proposed']):,.1f}", f"{float(crit['full']):,.1f}"),
        ("Estimated standalone Fmax (P7, pre-layout ABC, MHz)",
         fmax["baseline"], f"{float(fmax['proposed']):.2f}",
         f"{float(fmax['full']):.2f}"),
        ("Derived iso-frequency throughput geomean (MElements/s)",
         f"{gmean['baseline']['throughput']:.2f}",
         f"{gmean['proposed']['throughput']:.2f}",
         f"{gmean['full']['throughput']:.2f}"),
        ("Incremental-SMU area efficiency geomean (ME/s / norm-area)",
         "n/a", f"{ae['proposed']:.2f}", f"{ae['full']:.2f}"),
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)

    print(f"geomean throughput: baseline={gmean['baseline']['throughput']:.2f} "
          f"proposed={gmean['proposed']['throughput']:.2f} "
          f"full={gmean['full']['throughput']:.2f}")
    print(f"AE: proposed={ae['proposed']:.2f} full={ae['full']:.2f} "
          f"ratio={ae['proposed'] / ae['full']:.2f}x")
    print(f"wrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
