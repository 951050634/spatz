#!/usr/bin/env python3
"""P9-P11: cycles -> derived iso-frequency latency/throughput/efficiency.

Derived latency = cycles / f_iso.  Derived throughput = N*D / latency
(MElements/s).  These are not measured wall time or system throughput.
Area efficiency = Throughput / normalized mapped area.

Frequency policy (see P8 report): cluster-level timing is unavailable, so the
common iso-frequency assumption uses the A1 estimated standalone Fmax
(pre-layout ABC), 81.0186 MHz, for all three designs.  This isolates the
architecture (cycle) effect.  Area metric = standalone incremental SMU mapped
area (P0-6, exact); B2R has no SMU increment, so AE is n/a.
"""

from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL = REPO_ROOT / "experiments" / "parsed" / "final_scaling_model.csv"
P06 = REPO_ROOT / "experiments" / "parsed" / "p0_6" / "p0_6_synthesis_summary.csv"
P7 = REPO_ROOT / "experiments" / "parsed" / "p7_timing" / "p7_timing.csv"
OUT_DIR = REPO_ROOT / "experiments" / "parsed" / "p9_p11"
OUT_LAT = OUT_DIR / "p9_latency.csv"
OUT_THRU = OUT_DIR / "p10_throughput.csv"
OUT_AE = OUT_DIR / "p11_area_efficiency.csv"

CONFIG_TO_MODEL = {"B2R_RVV": "baseline", "A1_SMU_SCALAR": "proposed",
                   "A2_SMU_FULL": "full"}
WORKLOADS = [("BERT", 12, 64), ("Mistral", 32, 128), ("Qwen14B", 40, 128)]


def load_model() -> dict[tuple[str, str], int]:
    cycles = {}
    with MODEL.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] == "workload":
                cycles[(r["config"], r["workload"])] = int(r["measured_cycles"])
    return cycles


def load_fmax() -> dict[str, float]:
    fmax = {}
    with P7.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            label = r["label"].split("/")[0]
            if label in ("C1_SCALAR", "C2_FULL") and r["fmax_mhz"]:
                fmax[label] = float(r["fmax_mhz"])
    return fmax


def load_area() -> dict[str, float]:
    area = {}
    with P06.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            area[r["config_id"]] = float(r["mapped_cell_area"])
    return area


def main() -> int:
    cycles = load_model()
    fmax = load_fmax()
    area = load_area()
    f_iso = fmax["C1_SCALAR"]
    f_full = fmax["C2_FULL"]
    a_proposed, a_full = area["C1_SCALAR"], area["C2_FULL"]
    norm_full = a_full / a_proposed

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lat_rows = [["workload", "config", "N", "D", "elements", "cycles",
                 "freq_mhz", "freq_source", "latency_us"]]
    thr_rows = [["workload", "config", "elements", "cycles", "latency_us",
                 "throughput_MElements_per_s"]]
    ae_rows = [["workload", "config", "throughput_MElements_per_s",
                "normalized_area", "area_efficiency_MElements_per_s_per_area"]]
    summary = {}
    for wl, n, d in WORKLOADS:
        elems = n * d
        for cfg, role in CONFIG_TO_MODEL.items():
            c = cycles[(cfg, wl)]
            # iso-frequency latency (main table)
            lat_iso = c / (f_iso * 1e6) * 1e6  # us
            thr_iso = elems / (lat_iso * 1e-6) / 1e6  # MElements/s
            lat_rows.append([wl, cfg, n, d, elems, c, f"{f_iso:.4f}",
                             "derived iso-frequency (A1 estimated standalone Fmax)",
                             f"{lat_iso:.3f}"])
            thr_rows.append([wl, cfg, elems, c, f"{lat_iso:.3f}",
                             f"{thr_iso:.3f}"])
            if role == "proposed":
                na = 1.0
            elif role == "full":
                na = norm_full
            else:
                na = float("nan")
            ae = thr_iso / na if role != "baseline" else float("nan")
            ae_rows.append([wl, cfg, f"{thr_iso:.3f}",
                            f"{na:.4f}" if role != "baseline" else "n/a",
                            f"{ae:.3f}" if role != "baseline" else "n/a"])
        # speedup over B2R (iso-frequency == cycle ratio)
        c_b = cycles[("B2R_RVV", wl)]
        c_p = cycles[("A1_SMU_SCALAR", wl)]
        c_f = cycles[("A2_SMU_FULL", wl)]
        summary[wl] = {"speedup_proposed": c_b / c_p, "speedup_full": c_b / c_f}

    with OUT_LAT.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(lat_rows)
    with OUT_THRU.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(thr_rows)
    with OUT_AE.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(ae_rows)

    print(f"f_iso={f_iso:.4f} MHz  f_full={f_full:.4f} MHz  "
          f"norm_full_area={norm_full:.4f}")
    for wl, s in summary.items():
        print(f"{wl}: speedup Proposed={s['speedup_proposed']:.2f}x  "
              f"Full={s['speedup_full']:.2f}x")
    print(f"wrote {OUT_LAT}, {OUT_THRU}, {OUT_AE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
