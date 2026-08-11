# Final Evidence Freeze (M3)

**ACTIVE FREEZE — use only the files listed below for paper evidence.**

This freeze is anchored to HEAD `7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f`.
The source-of-truth workflow is deterministic:

```text
python3 experiments/scripts/fit_final_scaling_model.py
python3 experiments/scripts/freeze_final_evidence.py
```

The second command writes no wall-clock timestamp.  The manifest therefore
remains byte-identical across repeated runs when the inputs and scripts are
unchanged.

## Active source list

| Evidence | Active file | Status and units |
| --- | --- | --- |
| Scaling parameters, measured points, crossovers, workload model rows | `experiments/parsed/final_scaling_model.csv` | VERIFIED M2 measured cycles; cycles, cycles/row, cycles/element |
| Workload cycles and speedups | `experiments/parsed/final_workload_comparison.csv` | VERIFIED M2 measured cycles; speedup is a cycle ratio |
| Standalone area | `experiments/parsed/final_area.csv` | VERIFIED P0-6 mapped cells and Nangate45 Liberty cell-area units |
| Standalone timing | `experiments/parsed/final_timing.csv` | PARTIAL P7-R reg→reg combinational-delay proxy; synchronous Fmax UNAVAILABLE |
| Combined hardware evidence | `experiments/parsed/final_hardware_results.csv` | mapped cells, Liberty area, relative area, and PARTIAL reg→reg delay proxy only |
| Provenance and hashes | `experiments/parsed/final_evidence_manifest.json` | deterministic input/output SHA256 manifest |

Formal M2 and M2 model-source audits remain available under
`experiments/parsed/m2/` and `experiments/reports/M2_MATCHED_LUT_REVALIDATION.md`.
P7-R ownership and methodology evidence remains under
`experiments/parsed/p7r_timing/` and
`experiments/reports/P7R_SYNCHRONOUS_TIMING_AUDIT.md`.

## Current headline numbers

The active fitted model is `C(N,D) = C0 + Cs·N + Cv·N·D`:

| Design | C0 | Cs | Cv |
| --- | ---: | ---: | ---: |
| B2R_RVV | 161.35382260160452 | 1471.8187127369117 | 2.2670632230803 |
| A1_SMU_SCALAR | 1382.7702457972362 | 90.27815541344518 | 2.126010148452419 |
| A2_SMU_FULL | 1285.5770845769534 | 19.317262422475853 | 8.029464672201952 |

The A1 workload cycle rows are BERT/Mistral/Qwen14B =
`19856/4128`, `56296/12866`, and `69348/15733` for B2R/A1.  The A1
geometric-mean speedup is `4.526920018368`; A2 is `1.885765610308`.
The standalone area rows are A1 `73505` mapped cells / `77103.292`
Liberty units and A2 `107372` mapped cells / `114713.298` Liberty units;
A2/A1 area is `1.487787291884` (`+48.778729%`).
The timing rows are A1 `12.34285 ns` and A2 `13.20260 ns`, explicitly
PARTIAL reg→reg combinational proxies only.  Synchronous Fmax is
UNAVAILABLE.

## Unit and claim policy

- Cycles are measured RTL/Verilator kernel cycles, not wall-clock time.
- Speedup is baseline measured cycles divided by design measured cycles; no
  frequency assumption is needed for this ratio.
- Mapped cell count and Liberty cell-area units are separate metrics.
- P7-R delay is pre-layout Nangate45/ABC `stime` reg→reg combinational delay.
  It excludes clock-to-Q, setup/hold, skew, I/O constraints, and physical
  buffering/load semantics.
- No P7 inverse-delay value is converted to MHz.  Synchronous Fmax,
  cluster area/timing/power/energy, absolute latency, throughput, and
  end-to-end inference performance are UNAVAILABLE in the active freeze.
- A1 is the Proposed Scalar SMU + existing RVV design.  A2 is Full-Offload
  ablation only; Full is not the primary architecture.

## Superseded evidence

Historical provenance is preserved.  The explicit registry is
`experiments/parsed/SUPERSEDED_EVIDENCE.md`; its entries are **SUPERSEDED / DO
NOT USE FOR PAPER** and are not active source paths.  This includes the old
P0-4/P0-5 scaling/workload records, old P7 inverse-delay/Fmax records, old
P9-P11 derived latency/throughput tables, old P16 tables, and progressive
baseline artifacts.  No file was deleted.  A repository-wide stale-occurrence
audit is queued for M5; Figure 1/2/3 assets are intentionally not regenerated
in M3.
