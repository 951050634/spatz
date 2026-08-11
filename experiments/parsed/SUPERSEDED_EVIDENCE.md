# SUPERSEDED EVIDENCE REGISTRY

**SUPERSEDED / DO NOT USE FOR PAPER.** Historical files remain in place for
provenance and are not active evidence.  The only active machine-readable
records are listed in `experiments/reports/FINAL_EVIDENCE_FREEZE.md` and
`experiments/parsed/final_evidence_manifest.json`.

| Legacy path or set | Reason superseded | Replacement / policy |
| --- | --- | --- |
| `experiments/parsed/p0_4/p0_4_scaling_points.csv` and related `p0_4_*` scaling CSV/JSON | Pre-M1/P0-4 workload and scaling anchor; not code-matched to the M2 matched-LUT HEAD | Use `experiments/parsed/m2/m2_scaling.csv` through `final_scaling_model.csv` |
| `experiments/parsed/p0_5/p0_5_workload_comparison.csv` and related `p0_5_*` CSV/JSON | Pre-M1 workload anchor | Use `experiments/parsed/m2/m2_workloads.csv` through `final_workload_comparison.csv` |
| `experiments/parsed/p7_timing/p7_timing.csv` | Old P7 global ABC inverse-delay/Fmax field; ABC `pi`/`po` boundaries were not synchronous timing semantics | Use `experiments/parsed/p7r_timing/p7r_path_summary.csv`; report delay as PARTIAL reg→reg proxy and Fmax UNAVAILABLE |
| `experiments/reports/P7_STANDALONE_TIMING.md` | Old standalone timing report containing withdrawn inverse-delay MHz values | Retained with SUPERSEDED banner; use P7-R audit and `final_timing.csv` |
| `experiments/parsed/p9_p11/p9_latency.csv`, `p10_throughput.csv`, `p11_area_efficiency.csv` | Derived absolute latency/throughput depended on withdrawn 81.0186 MHz assumption | No active replacement; cycles and speedup remain in final workload/model records |
| `experiments/reports/P9_P11_LATENCY_THROUGHPUT_AE.md` | Historical derived-performance report | Retained with SUPERSEDED banner; do not cite |
| `experiments/parsed/p16/p16_hardware_results.csv` | Old mixed hardware table containing Fmax, absolute latency, and throughput | Use `experiments/parsed/final_hardware_results.csv` |
| `experiments/reports/P16_HARDWARE_RESULTS.md` | Old mixed P16 table | Updated to active cells/area/timing-proxy-only policy |
| `experiments/parsed/progressive_baseline.csv`, `progressive_breakdown.csv` | Old progressive baseline/workload evidence | Retained for provenance; do not use as final evidence |
| `experiments/reports/progressive_baseline.md` | Old progressive baseline report | Retained with SUPERSEDED banner |
| `experiments/plots/figure2_scaling.{png,pdf,svg}` | Generated before the M3 source freeze; M4 must regenerate from active final model | Do not cite current assets; M4 regeneration only |
| `experiments/plots/figure3_hardware_tradeoff.{png,pdf,svg}` | Generated before the M3 source freeze; M4 must regenerate from active final model | Do not cite current assets; M4 regeneration only |
| `paper/online-merge-smu/figures/smu_concurrency_proxies.svg` (contains the `94,713` generic proxy) | LEGACY / UNREFERENCED / DO NOT USE FOR PAPER | SUPERSEDED; do not cite or edit/delete; never use as active evidence |

CSV files are intentionally not modified with comments, so their parsers remain
usable.  The registry and report banners carry the superseded status instead.
