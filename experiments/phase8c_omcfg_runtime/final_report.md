# Phase 8C final report

Status: **PASS**

## 1. Implementation freeze

Phase 8B was reviewed and committed before formal execution at
`7786820821102d34e32e9517a7630b028693f25a`. The formal simulator was built
from that RTL and has SHA-256
`002161e3e88edd6fa6392dbe79a6a89796477282d5ff951037a211676785a51a`.
No RTL changed during Phase 8C.

## 2. Frozen ISA

OMERGE remains opcode `0x5b`, funct3 `000`, funct7 `0000011`, rs1/rs2 `x0`,
with status in rd. OMCFG remains I-type-like custom-2 opcode `0x5b`, funct3
`001`, rd `x0`, rs1 carrying the value, imm12 carrying cfg_id, mask
`0x00007fff`, and match `0x0000105b`.

## 3. Final cfg mapping

| cfg_id | Field | Persistent RTL state | MMIO equivalent |
|---:|---|---|---|
| `0x000` | A_M | `merge_isa_state_a_m` | `0xf0` |
| `0x001` | A_L | `merge_isa_state_a_l` | `0xf8` |
| `0x002` | B_M | `merge_isa_state_b_m` | `0x100` |
| `0x003` | B_L | `merge_isa_state_b_l` | `0x108` |
| `0x004` | TILE_M | `merge_src_m_tile` | `0x80` |
| `0x005` | TILE_L | `merge_src_l_tile` | `0x88` |
| `0x006` | WEIGHT_OLD | `merge_dst_weight_old` | `0xd0` |
| `0x007` | WEIGHT_TILE | `merge_dst_weight_tile` | `0xd8` |
| `0x008` | N | `merge_n` | `0xb0` |
| `0x009` | CTRL/INIT | adapter control | `MERGE_CTRL.CLEAR_DONE` |

No cfg_id was added in Phase 8C.

## 4. Exact execution order

1. N8/D32 MMIO-config + OMERGE
2. N8/D32 OMCFG-config + OMERGE
3. N16/D64 MMIO-config + OMERGE
4. N16/D64 OMCFG-config + OMERGE

All four formal runs were executed once in this order.

## 5–8. Formal results

| Case | Path | Setup | Native Core | Setup + Core | OMERGE | SMU start/done | Final hash | Exit |
|---|---|---:|---:|---:|---:|---:|---|---:|
| N8/D32 | MMIO | 991 | 72,636 | 73,627 | 1 | 1/1 | `0x9c7cdedc` | 0 |
| N8/D32 | OMCFG | 659 | 72,636 | 73,295 | 1 | 1/1 | `0x9c7cdedc` | 0 |
| N16/D64 | MMIO | 986 | 507,464 | 508,450 | 3 | 3/3 | `0xfd0d2cff` | 0 |
| N16/D64 | OMCFG | 632 | 507,476 | 508,108 | 3 | 3/3 | `0xfd0d2cff` | 0 |

## 9. Configuration-state equivalence

PASS for both shapes. All nine persistent values, `cfg_valid=1`, and selector
0 after INIT matched between MMIO and OMCFG. The per-shape configuration-state
SHA-256 values are reported in `correctness.md`.

## 10. Final-O equivalence

PASS for both shapes. N8 compared 256 FP32 words and N16 compared 1,024 FP32
words. Both comparisons were bit-identical with the same target hash,
pairwise MAE 0, stable relative error 0, cosine 1, and zero non-finite values.

## 11. Setup-cycle comparison

OMCFG reduced the measured one-time setup window by 332 cycles (33.50%) for
N8/D32 and 354 cycles (35.90%) for N16/D64. This is workload-level setup
overhead and is not claimed as a major Attention speedup.

## 12. Steady-state Native Core

N8 was exactly 72,636 cycles on both paths. N16 was 507,464 cycles for MMIO
and 507,476 for OMCFG, a +12-cycle (+0.0024%) observation. No steady-state
performance benefit is claimed.

## 13. Command and selector counts

N8 used one OMERGE, one SMU start/done pair, and one selector toggle on each
path. N16 used three of each. Selector transitions were `0->1` for N8 and
`0->1->0->1` for N16. Each setup used nine fields plus one INIT: nine ordinary
MMIO writes plus one MMIO INIT, or ten OMCFG instructions including CTRL/INIT.

## 14. Runtime configurability

PASS. The same frozen RTL, simulator, ISA encodings, configuration API, and
per-shape byte-identical executable `.text` accepted different runtime address
and `N` values for N8/D32 and N16/D64. D remains a software/RVV workload
parameter and was not added to OMCFG.

## 15. Errors and timeouts

All four runs reported zero SMU errors, zero timeouts, zero non-finite outputs,
and exit code 0. A postprocessing-only cosine rounding issue was corrected
without changing or rerunning the four raw logs; provenance is in
`correctness.md` and `manifest.json`.

## 16. Phase 8C modified files

- `sw/spatzBenchmarks/CMakeLists.txt`: two matched test targets.
- `sw/spatzBenchmarks/native-online-attention/main.c`: shared runtime config
  API selection, nine-field setup, setup timer, and state/count diagnostics.
- `experiments/phase8c_omcfg_runtime/`: runner, raw evidence, tables, manifest,
  and reports.

No hardware file was modified in Phase 8C.

## 17. Final Git HEAD

`7786820821102d34e32e9517a7630b028693f25a`

## 18. Working tree

The Phase 8C software harness and report artifacts are intentionally
uncommitted. The unrelated, pre-existing untracked
`experiments/phase8a_omcfg_encoding_audit/` directory was preserved and not
modified as part of Phase 8C. Generated `work-phase8c*` builds and `raw/*.log`
are ignored by repository rules but retained locally.

## 19. Paper-safe claims

OMCFG exposes workload-level Online Merge context through the same custom
RISC-V namespace as OMERGE. Across N8/D32 and N16/D64 Native Online Attention,
OMCFG and MMIO configuration established equivalent accelerator state and
produced identical final outputs while reusing the same frozen hardware.
OMCFG also reduced the measured one-time configuration setup overhead; this
cost is amortized at workload level and did not change OMERGE, SMU, or RVV
semantics.

## 20. Unsupported claims and limitations

- No recurring-interface, end-to-end major-speedup, or statistical timing
  claim follows from these single matched runs.
- No B2R, extra shape, random regression, multi-hart, or full-model run was
  performed.
- D, precision, tile size, modes, O-vector addresses, and strides remain
  outside OMCFG v1.
- No synthesis, place-and-route, power, compiler-backend, descriptor, SMU
  arithmetic, or RVV datapath work was performed.

Phase 8C stops here pending Sol review; no Phase 8D action was started.
