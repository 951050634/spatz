# Experimental Methodology Audit

This file records what the frozen experiments actually measure. It is not polished
paper prose and it does not authorize combining different timing windows.

## Evidence hierarchy used in this audit

1. Phase 8C matched results/raw logs and Phase 8A/8B frozen reports;
2. Phase 7B formal recovery CSV/raw logs and implementation freeze;
3. Phase 5/6 formal native-attention CSVs and manifests;
4. Phase 3 frozen mixed-reciprocal numerics and standalone PPA;
5. Phase 4 explicit-P negative control;
6. M2/TCAS-II final matched-LUT files only as a separate historical microkernel
   evidence family.

Superseded CSVs listed in `experiments/parsed/SUPERSEDED_EVIDENCE.md` are excluded.

## Simulation environment

| Item | Frozen value / role | Source |
|---|---|---|
| Functional/performance simulator | cycle-level Verilated `spatz_cluster.vlt` | phase manifests |
| Verilator version | 5.034 | `experiments/PROJECT_STATE.md` |
| Phase 5/6 simulator SHA-256 | `8f85b204d064f1ced29d2fc27518754f8b018db0530cf2328a3a1062687c9138` | Phase 5/6 manifests |
| Phase 7 simulator SHA-256 | `483ca72c2cebb6959620a3ec5bdc3bee891c294ef99f91cd1587aaf9c44c9aff` | Phase 7 audit |
| Phase 8C simulator SHA-256 | `002161e3e88edd6fa6392dbe79a6a89796477282d5ff951037a211676785a51a` | Phase 8C manifest |
| Compiler | Clang 14.0.6, PULP toolchain commit `b494f2d8` | `experiments/PROJECT_STATE.md`; manifests |
| GCC support toolchain | GCC 7.1.1 | same |
| Common target flags | includes `-DPRINTF_DISABLE_SUPPORT_FLOAT`; target metrics are emitted as bit fields and host-collected | Phase 5 manifest/collector |
| Cluster config | `spatz_cluster.default.dram.hjson` | build manifests |
| Cycle counter | `benchmark_get_cycle64()` around explicit stage boundaries | native benchmark |
| HW/SW interface | MMIO control, or scalar accelerator issue/response through OMERGE; TCDM carries state; RVV performs O update | RTL + benchmark |

Simulator paths stored in older manifests may reference the relocated
`/home/wxt/spatz-archive/...` tree. HEAD `809805d…` updates artifact paths after
relocation; hashes, formal CSVs, and raw data were not recomputed by this audit.

## Workload definitions

- `N`: query/sequence rows in the native benchmark and number of per-tile row
  recurrences executed by the SMU.
- `D`: output/head dimension handled by the software/RVV `O[D]` update.
- tile size (`tile_keys`): number of keys per local tile; fixed at `4` for all
  Phase 5–8 formal native-attention cases.
- tile count: `N / 4` for the measured divisible shapes.
- first tile: computes local state and copies it into the running state; it does
  not invoke recurrence hardware.
- merge count: `tile_count - 1`; one OMERGE/SMU invocation per merge.

### Primary formal anchors

| Shape | Seed | Tile size | Tiles | Merges | Role |
|---|---:|---:|---:|---:|---|
| N8/D32 | 1 | 4 | 2 | 1 | Phase 5, 7, 8 anchor |
| N16/D64 | 1 | 4 | 4 | 3 | Phase 5, 7, 8 anchor |

### Additional formal native shapes

| Shape | Seed | Tile size | Tiles | Merges | Status |
|---|---:|---:|---:|---:|---|
| N24/D64 | 1 | 4 | 6 | 5 | `FROZEN_NEW_SHAPE`, Phase 6 |
| N16/D128 | 1 | 4 | 4 | 3 | `FROZEN_NEW_SHAPE`, Phase 6 |

N32/D64 was considered and rejected before formal collection under the declared
host-completion criterion; there is no matched result. Status: **NOT MEASURED**.

### Numerical/stress workloads

- Phase 3 model matrix: sequence lengths 128/256/512/1024 × D=64/128, both
  random-score and single-head QKᵀV cases, plus an extended stress sweep.
- reciprocal exhaustive domain: all 31,743 positive finite FP16 denominators;
  independent 257-point mantissa probe.
- Phase 4 explicit-P negative control: N8/D32 and N16/D64, seed 1.

### Earlier separate workload evidence

The M2 final matched-LUT workload CSV contains BERT N12/D64, Mistral N32/D128,
and Qwen14B N40/D128. It measures an older standalone/microkernel evidence epoch.
It is not part of the Phase 5–8 native-attention timing table and must not be pooled
with the current Mixed OMERGE data.

## Timing windows

| Metric | Exact inclusion | Important exclusion / warning |
|---|---|---|
| `recurrence` — B2R software | scalar recurrence producing `m/l/weights` for every non-first tile | excludes RVV O update |
| `recurrence` — Phase 5 MMIO SMU | all per-merge register programming, clear/start, BUSY/DONE polling, and SMU execution | **includes SMU busy**; not pure control |
| `recurrence/control` — Phase 7 MMIO | config + clear + start + poll + SMU completion | **includes engine busy** |
| `recurrence/control` — Phase 7 ISA | instruction issue + SMU execution/busy + response commit + status consumption | **includes engine busy**; not pure dispatch |
| `engine_busy_cycles` | observer-reported accelerator busy interval | diagnostic subwindow, not the recurrence total |
| `RVV update` | existing per-row `O[D]` weighted output update | excludes recurrence |
| `merge` / `merge_window` | outer window around recurrence + RVV update + small pointer-swap/orchestration remainder, only non-first tiles | not whole attention |
| `Native Core` | score-tile compute + local-state construction + all merge windows + first-tile/residual work + final output copy | excludes allocation, input generation, diagnostics, and Q/K/V loading/linear projection |
| Phase 7 `workload_setup` | ISA persistent-context setup before `core_start` | MMIO row is zero because its legacy configuration is charged per merge, not because MMIO is free |
| Phase 7 `setup-inclusive` | `workload_setup + Native Core` | compare this when including OMERGE's one-time setup |
| Phase 8C `setup` | nine configuration fields plus one INIT, either MMIO or OMCFG | one-time configuration plane only |
| Phase 8C `Native Core` | both variants subsequently use OMERGE and the same core path | setup excluded |
| Phase 8C `setup-inclusive` | setup + Native Core | correct configuration-plane total |
| Phase 4 `Softmax` | software complete explicit-P Softmax, or Mixed initialization + SMU launch/poll + RVV P update + swap/clear | explicit-P dataflow; not native recurrence |
| Phase 4 `Attention Total` | arithmetic sum of QKV Linear + QKᵀ + scaling + Softmax + P×V | not an independently timed counter |
| Phase 4 `raw_total` | full measured Phase 4 window including quantization/requantization/rescaling boundaries | not a full Transformer |

Cycle speedup is baseline cycles divided by design cycles. Cycle reduction is
`100 × (baseline-design)/baseline`. A recurrence speedup is never a whole-attention
speedup.

## Phase-specific comparison controls

### Phase 5/6: B2R versus Mixed Scalar SMU

Both paths share tile construction and the existing RVV output update. The software
path executes `online_merge_b2_r_scalar`; the SMU path executes mode-3 Mixed Scalar
recurrence through MMIO. Phase 6 imports Phase 5 anchor CSVs without rerunning them
and adds two selected shapes. One interrupted N16/D128 SMU run was recovered under
the guarded r2 recovery; the provenance identifies it explicitly.

### Phase 7B: A1-MMIO versus A1-ISA

Four fixed-order recovery runs use the same two anchors, seed, tile size, arithmetic,
RVV routine, simulator, and output protocol. The initial continuation lacked formal
raw transcripts and failed Gate 2; a complete fresh fixed-order recovery produced
the active evidence. Reconstructed legacy logs are invalidated. This comparison
isolates recurring invocation/control-path effects, subject to small cold-run noise
in shared components.

### Phase 8C: MMIO-config versus OMCFG-config

Fixed order: N8 MMIO, N8 OMCFG, N16 MMIO, N16 OMCFG; one run each. Both binaries
have byte-identical `.text` within each shape and use OMERGE after setup. The only
intended difference is nine MMIO writes + MMIO INIT versus ten OMCFG instructions
(nine fields + INIT). This comparison isolates one-time setup/config transport.

## Correctness metrics

| Metric | Definition / authority |
|---|---|
| MAE | mean absolute error over output words |
| stable relative error | `sum(abs(actual-reference)) / max(sum(abs(reference)), 1e-12)` |
| cosine | host float64 recomputation for formal comparisons where archived; target-side approximate cosine is diagnostic only in Phase 4 |
| nonfinite | count of FP32 output words with exponent `0xff`; required zero |
| word-for-word equality | exact FP32 bit-vector comparison between matched paths |
| output hash | FNV-1a-like 32-bit digest emitted by benchmark; used with exact dumps, not as a substitute for them |

Phase 8C initially reported failure only because exact N16 bit vectors produced host
float64 cosine `1.0000000000000002`. Post-processing now maps exact vector identity
to cosine `1.0`. **No formal case was rerun and no raw log was modified**; raw hashes
are unchanged. This is a derived post-processing correction.

Phase 7 component-level m/l/weight hashes and MAEs are absent from recovery records:
status **NOT MEASURED**, not zero. Final-O pairwise arrays are present and exact.

## Synthesis methodology

### Standalone SMU

- tool: Yosys 0.66+4 with ABC;
- library: Nangate45 typical Liberty;
- scope: standalone mapped tops for Legacy Scalar, Mixed+Division, and
  Mixed+Reciprocal;
- area: mapped cell count and summed Liberty cell-area units, three identical
  trials per design;
- timing: a separate timing-constrained mapping and longest reg-to-reg combinational
  path proxy; the area values from this timing run are not the formal area table;
- timing status: pre-layout proxy only, target 1.5 ns not met; no synchronous Fmax.

### Cluster-level matched attempt

- top: `spatz_cluster_wrapper`;
- configurations: Spatz Baseline and Spatz + Mixed SMU;
- SRAMs black-boxed; same source overlay and Nangate45/Yosys/Slang flow;
- planned area scope: instance-weighted hierarchical top;
- planned timing proxy: local ABC `stime` after `abc -D 50000`;
- r3: 4 GiB RAM + 4 GiB swap, OOM at techmap;
- r4: 6 GiB RAM + 4 GiB swap, OOM at techmap (swap almost exhausted);
- no `mapped-hier-stat` and no numeric baseline/SMU rows were emitted.

Status is **BLOCKED_RESOURCE**. The earlier `p6-stop` diagnostic reached a different
flatten-stage failure and emitted only generic pre-mapped counts; it is provenance,
not a matched cluster PPA result.
