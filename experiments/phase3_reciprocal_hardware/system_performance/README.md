# Phase 3 system-level performance

This directory contains the same-input Verilator measurements for the
normalization comparison.  The Division binary was built with
`-DSPATZ_DISABLE_DASM`; the Reciprocal binary was built with
`-DSPATZ_DISABLE_DASM -DONLINE_MERGE_MIXED_RECIPROCAL`.  Both binaries emit

```text
OM_SIM_CONFIG {"schema_version":1,"profile":"low_perturbation","dasm_trace_enabled":false,"fsm_observer_enabled":true}
```

The measured command used `run_performance_matrix.py`, `--profiles memory`,
`--trials 1`, `--jobs 1`, and cases
`N8_D32_S1_main,N16_D64_S1_main`.  The runner's minimum-trial check was
lowered from three to one so that this explicitly requested single-trial
measurement is accepted; reproducibility and all existing output/FSM gates
are unchanged.

## Results

| Case | Legacy A1 / Division (kernel, busy, weight) | Mixed / Division (kernel, busy, weight) | Mixed / Reciprocal (kernel, busy, weight) | Reciprocal kernel delta |
| --- | ---: | ---: | ---: | ---: |
| N8, D32 | 2625, 192, 8 | 3171, 737, 552 | 2622, 208, 24 | -549 (-17.31%) |
| N16, D64 | 5067, 384, 16 | 6061, 1474, 1104 | 5024, 417, 48 | -1037 (-17.11%) |

All six records are `PASS`; all four Division and both Reciprocal records
have `fsm_gate=PASS`, `reproducible=YES`, and no runner failures.  The FSM
records report mode 1 for Legacy A1 and mode 3 for both Mixed implementations.
The Reciprocal runs retain the same functional status and checked-element
counts as Division: 272 (N8) and 1056 (N16).  Mixed Reciprocal maximum
absolute/relative errors versus the software reference are 0.00758553 /
0.00379625 (N8) and 0.00629747 / 0.00605114 (N16), within the declared mixed
tolerance.

The Reciprocal datapath reduces Mixed normalization busy cycles by 71.8%:
737 to 208 for N8 and 1474 to 417 for N16.  Its end-to-end kernel cycles are
within 1% of Legacy A1 in these two cases, and remove the Division-mode
Mixed penalty.  This is a system-level cycle result, not a claim that the
post-layout timing proxy improved: the separate Phase 3 timing result is
15,539.55 ps for Reciprocal versus 14,619.73 ps for Division.

Raw runner artifacts are in `division/` and `reciprocal/` (`records.json`,
`records.csv`, `run_manifest.json`, logs, and command manifests).  The
reproducibility manifests record the simulator hashes, input hashes, compiler
commands, and external simulator paths:

* Division simulator: `/home/wxt/work-online-merge-phase3-div-sim/spatz_cluster.vlt`
  (SHA-256
  `6c8f2a3efe7fd588cbb10f038c0c756889b9dbfcebe309673d90ac9daada8151`).
* Reciprocal simulator: `/home/wxt/work-online-merge-phase3-recip-sim/spatz_cluster.vlt`
  (SHA-256
  `8f85b204d064f1ced29d2fc27518754f8b018db0530cf2328a3a1062687c9138`).

The runner marks the records paper-ineligible only because this checkout is
dirty while the broader Phase 3 changes are being developed; this does not
indicate a functional or reproducibility failure.
