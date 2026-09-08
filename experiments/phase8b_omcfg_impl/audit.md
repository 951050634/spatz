# Phase 8B implementation audit

Audit point: repository HEAD `c32c99c90b11831f46d8d79372d38bede8ea3c3b`
before Phase 8B implementation.  The only pre-existing working-tree item was
the untracked `experiments/phase8a_omcfg_encoding_audit/` evidence directory.
This audit was read-only; no workload, simulation, synthesis, or source edit
was performed before recording the findings below.

## Existing path inventory

| Item | Current implementation | Audit finding |
|---|---|---|
| OMERGE decoder | `hw/ip/snitch/src/riscv_instr.sv`, label `OMERGE`; `hw/ip/snitch/src/snitch.sv`, OMERGE case | Pattern is `0x0600005b/0xfffff07f`; the decoder registers `rd`, routes to `SMU`, and leaves rs1/rs2 unused. |
| Snitch accelerator issue path | `snitch.sv` -> `hw/ip/spatz_cc/src/spatz_cc.sv` -> cluster SMU issue arbiter | `data_op` carries the complete instruction, `data_arga` carries selected rs1 data, and the SMU route is accelerator address 2. |
| OMERGE adapter | `hw/ip/online_merge/src/online_merge_omerge_adapter.sv` | Four states (`IDLE/START/WAIT/RESP`), one outstanding operation, delayed one-cycle start, response status, and success-only selector toggle. |
| Persistent configuration | Generated cluster peripheral registers consumed directly by the adapter | A/B m/l use `MERGE_ISA_STATE_*`; tile m/l, weights, N, D, and stride use the existing generic merge registers.  The adapter itself initially stores only selector and response state. |
| MMIO path | `spatz_cluster_peripheral_reg.hjson` and generated package/top, exported by `spatz_cluster_peripheral.sv` | MMIO remains the sole configuration writer before Phase 8B.  Direct-MMIO engine launch and OMERGE share the physical engine but use different source/destination selection. |
| Configuration-valid logic | `online_merge_update_engine.sv::valid_cfg()` only | There is no persistent OMERGE `cfg_valid`.  Engine validation occurs only after `start_i`, so a completely unconfigured OMERGE reaches the engine and fails there. |
| A/B selector | `online_merge_omerge_adapter.sv::selector_q` | MMIO writes to any A/B ISA-state register reset it to zero while idle.  A successful accepted OMERGE response toggles it; error responses do not. |
| SMU interface | Adapter `start_o/clear_done_o`; engine `busy_o/done_o/error_o` | Requests are accepted only when adapter IDLE and engine not busy.  START is exactly one cycle; WAIT observes done/error. |
| Software configuration | `sw/spatzBenchmarks/native-online-attention/main.c::smu_isa_setup()` | Writes A/B m/l, tile m/l, N, D, stride, mode, two weight addresses, then `MERGE_CTRL.CLEAR_DONE`; `omerge()` uses `.insn r 0x5b, 0, 3`. |
| Directed-test infrastructure | Phase 7 system-integrated native-attention target plus adapter `$display` observers | There is no standalone adapter test.  The existing CMake/CTest simulator path can host one small non-workload directed executable, and adapter observers already provide handshake/selector evidence. |

## What MMIO stores, and what frozen OMERGE actually uses

The direct MMIO engine interface exposes the full historical engine context:
old/tile/destination m, l and O addresses; N; D; stride; mode; two weight
destinations; and start/clear pulses.  OMERGE does not consume that entire
context.  Its adapter selects A/B state registers for old/destination m/l,
fixes mode to Mixed Scalar (`3`), fixes all O addresses to zero, and uses the
generic tile, weight and N registers.

| MMIO field | Current OMERGE connection | Used by Mixed Scalar recurrence? | OMCFG v1 |
|---|---|---:|---:|
| `MERGE_ISA_STATE_A_M` | A-side old/destination max | yes | required |
| `MERGE_ISA_STATE_A_L` | A-side old/destination normalization | yes | required |
| `MERGE_ISA_STATE_B_M` | B-side destination/old max | yes | required |
| `MERGE_ISA_STATE_B_L` | B-side destination/old normalization | yes | required |
| `MERGE_SRC_M_TILE` | tile max input | yes | required |
| `MERGE_SRC_L_TILE` | tile normalization input | yes | required |
| `MERGE_DST_WEIGHT_OLD` | old-weight output | yes | required |
| `MERGE_DST_WEIGHT_TILE` | tile-weight output | yes | required |
| `MERGE_N` | scalar row bound | yes | required |
| `MERGE_D` | passed to engine; only checked nonzero in mode 3 | no scalar recurrence data dependency | excluded |
| `MERGE_STRIDE` | passed to engine; only alignment-checked in mode 3 | no scalar recurrence data dependency | excluded |
| `MERGE_MODE` | ignored by adapter; adapter emits constant `3` | no (already fixed) | excluded |
| `MERGE_SRC_O_OLD/TILE`, `MERGE_DST_O` | adapter emits aligned zero instead | no | excluded |
| `MERGE_SRC_M/L_OLD`, `MERGE_DST_M/L` | used only by direct-MMIO launch, bypassed by OMERGE A/B selection | no | excluded |

The engine's generic `valid_cfg()` requires nonzero D even in scalar mode,
although the scalar state machine never uses D or stride.  Phase 8B can keep
the engine unchanged and provide legal constants (`D=1`, `stride=0`) from the
OMERGE adapter.  This removes validation-only legacy fields from the v1
architectural context without changing arithmetic.

## Minimal integration decision

The nine existing generated MMIO registers listed as required remain the one
canonical value bank.  OMCFG will use the hardware-write side of those same
registers, so OMCFG updates are also visible through their existing MMIO
addresses.  MMIO write-enable pulses and OMCFG accepts feed one adapter-local
`cfg_written_mask`; normal writes make the context invalid.  OMCFG CTRL/INIT
commits a complete mask.  The existing MMIO setup terminator,
`MERGE_CTRL.CLEAR_DONE`, supplies the equivalent legacy-MMIO INIT pulse so the
Phase 7 setup sequence remains available.

No SMU arithmetic or RVV datapath change is required.
