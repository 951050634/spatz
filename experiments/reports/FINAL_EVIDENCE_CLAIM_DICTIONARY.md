# Final Evidence and Claim Dictionary (M3 Freeze)

**ACTIVE SOURCE OF TRUTH:** use only the final records listed here.  Historical
records remain for provenance but are **SUPERSEDED / DO NOT USE FOR PAPER**;
see `experiments/parsed/SUPERSEDED_EVIDENCE.md`.

The freeze is anchored to HEAD `7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f`.
The deterministic generation workflow is:

```text
python3 experiments/scripts/fit_final_scaling_model.py
python3 experiments/scripts/freeze_final_evidence.py
```

## Design roles

| ID | Role | Paper use |
| --- | --- | --- |
| B2R_RVV | Matched-arithmetic software scalar recurrence + existing RVV | Matched-arithmetic RVV comparison baseline |
| A1_SMU_SCALAR | Scalar SMU + existing RVV | Proposed design |
| A2_SMU_FULL | SMU recurrence + SMU vector update | Full-Offload ablation only |

Full is never treated as the proposed architecture.

## Active source map

| Evidence | Active source | Status |
| --- | --- | --- |
| Fitted scaling model and formal M2 points | `experiments/parsed/final_scaling_model.csv` | VERIFIED M2 measured cycles and deterministic fit |
| Workload cycles and cycle speedups | `experiments/parsed/final_workload_comparison.csv` | VERIFIED M2 measured cycles; speedup is a cycle ratio |
| Standalone mapped cells and area | `experiments/parsed/final_area.csv` | VERIFIED P0-6 standalone synthesis |
| Timing classification and delays | `experiments/parsed/final_timing.csv` | PARTIAL P7-R reg→reg delay proxy only |
| Combined hardware table | `experiments/parsed/final_hardware_results.csv` | Cells/area/proxy delay only |
| Provenance and hashes | `experiments/parsed/final_evidence_manifest.json` | Deterministic input/output manifest |
| M2 audit detail | `experiments/parsed/m2/`, `experiments/reports/M2_MATCHED_LUT_REVALIDATION.md` | Sol-reviewed matched-LUT evidence |
| P7-R audit detail | `experiments/parsed/p7r_timing/`, `experiments/reports/P7R_SYNCHRONOUS_TIMING_AUDIT.md` | Ownership and timing-methodology evidence |

## Evidence categories

### VERIFIED

The following claims are directly supported by active evidence:

- M2 measured RTL/Verilator kernel cycles for the three workload shapes;
- fitted `C0`, `Cs` (N-dependent cycles/row coefficient), and `Cv`
  (ND-dependent cycles/element coefficient) from M2 points;
- P0-6 standalone mapped cell counts;
- P0-6 standalone Nangate45 Liberty cell-area units; and
- the P3 nominal no-stall scalar FSM state schedule of 24 cycles/row
  (`13+1+1+9`); model-shape observers record 289/769/962 busy cycles with
  occasional TCDM waits.

Current fitted parameters are:

| Design | C0 | Cs | Cv |
| --- | ---: | ---: | ---: |
| B2R_RVV | 161.35382260160452 | 1471.8187127369117 | 2.2670632230803 |
| A1_SMU_SCALAR | 1382.7702457972362 | 90.27815541344518 | 2.126010148452419 |
| A2_SMU_FULL | 1285.5770845769534 | 19.317262422475853 | 8.029464672201952 |

The fitted R-squared values span 0.99928--0.99999. Allowed wording includes
“measured kernel cycles,” “fitted N-dependent `Cs`,” “fitted ND-dependent
`Cv`,”
“standalone mapped cells,” “standalone Liberty cell-area units,” and “FSM
busy-cycle breakdown.” Fitted coefficients are not wall time or SMU busy
cycles, and the nominal state schedule is not system latency.

### DERIVED

Only the following derived claims are active:

- cycle speedup = B2R measured cycles / design measured cycles;
- geometric means of the three workload cycle ratios;
- model crossovers from the active fitted model; and
- A2 relative area and area delta versus A1.

The A1 geometric-mean speedup is `4.526920018368`; A2 is
`1.885765610308`.  These are cycle ratios and do not assume a frequency.
Absolute latency, throughput, and area-efficiency values are not active.

### PARTIAL

P7-R classifies the A1/A2 paths as reg→reg after recovering DFF ownership:

| Design | Delay | Status |
| --- | ---: | --- |
| A1 | 12.34285 ns | PARTIAL pre-layout combinational proxy |
| A2 | 13.20260 ns | PARTIAL pre-layout combinational proxy |

The flow does not provide synchronous period semantics: clock-to-Q,
setup/hold, skew, I/O delay/loads, and physical buffering are excluded.
Synchronous F_max is **UNAVAILABLE**. Do not invert these delays or call them
cluster F_max, signoff timing, timing closure, or achievable frequency.

### UNAVAILABLE

The following claims have no active numeric evidence and must remain
UNAVAILABLE:

- synchronous $F_{max}$, cluster critical delay, or cluster frequency;
- cluster mapped area, cluster overhead, physical/layout area;
- power, energy, and end-to-end inference performance;
- absolute latency or throughput;
- measured system throughput or wall-clock latency; and
- end-to-end LLM speedup.

## Unit and wording rules

1. Keep cells and Liberty area units in separate columns and prose phrases.
2. Keep cycles distinct from wall time.
3. Use “proxy” and “PARTIAL” for P7-R delay; never infer MHz.
4. Say “Full-Offload ablation,” never “Proposed Full.”
5. Scope workload rows as merge-kernel/model-shape measurements, not complete
   LLM inference.
6. Do not use any source in the superseded registry as active evidence.
