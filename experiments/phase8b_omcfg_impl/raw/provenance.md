# Phase 8B validation provenance

- Validation date: 2026-09-09 (Asia/Shanghai)
- Baseline Git HEAD: `c32c99c90b11831f46d8d79372d38bede8ea3c3b`
- Baseline commit: `[phase7b] Finalize formal schema provenance`
- Simulator profile reported at runtime: `default`
- Pre-implementation working tree: only the pre-existing untracked
  `experiments/phase8a_omcfg_encoding_audit/` directory

## Generated-register consistency

The repository-pinned `register_interface` regtool was run from checkout
`register_interface-e63646ed5fd78e93` against
`spatz_cluster_peripheral_reg.hjson`.  Fresh temporary outputs were bytewise
compared with:

```text
spatz_cluster_peripheral_reg_pkg.sv  MATCH
spatz_cluster_peripheral_reg_top.sv  MATCH
sw/snRuntime/include/spatz_cluster_peripheral.h  MATCH (no content change)
```

The C header is unchanged because register offsets and fields did not change;
only hardware access/write-event properties changed.

## Build and registration

```text
make VLT_BIN=work-phase8b/spatz_cluster.vlt \
  work-phase8b/spatz_cluster.vlt
PASS: target is up to date after the completed Verilator build

cmake --build hw/system/spatz_cluster/sw/build \
  --target test-riscvTests-omcfg-directed -j8
PASS: target linked successfully

ctest --test-dir hw/system/spatz_cluster/sw/build -N -R omcfg-directed
PASS: exactly one directed test registered
```

The software build emits a non-fatal llvm-objdump warning about unavailable
libgcc source annotations.  It does not affect compilation, linking,
instruction bytes, or execution.

## Checks and immutable artifacts

```text
git diff --check
PASS

python3 experiments/phase8b_omcfg_impl/raw/check_decode.py
PASS: 442 active labels, zero OMCFG symbolic overlaps

./hw/system/spatz_cluster/work-phase8b/spatz_cluster.vlt \
  hw/system/spatz_cluster/sw/build/riscvTests/\
test-riscvTests-omcfg-directed
PASS: exit 0, PHASE8B_RESULT SUCCESS failures=0
```

SHA-256 values at final validation:

```text
923d0a9299b243de5cb43cc05a0e2a4ae26c17ae71a077a041a3e8954cc19264  spatz_cluster.vlt
82bb1f1e6df27cff15beb2731b7e24cf8549d440dc6be542d42027033e1d2658  test-riscvTests-omcfg-directed
94583d4bad41a75037b19a9e0f0fe30fff74d6c102b845e50f36cb62818dfd1c  decode_check.log
0800d8acc2b67055152360b68cd55fadfb526fa65969ad895dcdec88237301ec  omcfg_directed.log
2eff8f51c912c60a64816ef2685ba04ce4e7c1c4c3583e45b58528d7ce9442d2  instruction_words.log
```

## Scope proof

`git diff --name-only HEAD -- hw/ip/online_merge` reports only
`online_merge_omerge_adapter.sv`; the update engine and arithmetic modules are
unchanged.  `git diff --name-only HEAD -- hw/ip/spatz` is empty, proving the RVV
datapath subtree is unchanged.  The two Snitch changes are limited to
`riscv_instr.sv` and `snitch.sv` decode/routing.

No synthesis or workload/performance run was performed.

## Validation-time working tree

Branch `exp/online-softmax-supplement` remains 15 commits ahead of its tracked
remote.  At the time of final functional validation, Phase 8B had not yet been
committed and its implementation delta comprised:

```text
M  hw/ip/online_merge/src/online_merge_omerge_adapter.sv
M  hw/ip/snitch/src/riscv_instr.sv
M  hw/ip/snitch/src/snitch.sv
M  hw/system/spatz_cluster/src/spatz_cluster.sv
M  hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral.sv
M  hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg.hjson
M  hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg_pkg.sv
M  hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg_top.sv
M  sw/riscvTests/CMakeLists.txt
?? sw/riscvTests/isa/omcfg-directed.c
?? sw/snRuntime/include/online_merge_omcfg.h
?? experiments/phase8b_omcfg_impl/
```

The separate untracked `experiments/phase8a_omcfg_encoding_audit/` directory
predated this phase and was preserved unchanged.

This section intentionally records the pre-commit validation state.  The
resulting Phase 8B commit identity is reported in the submission handoff,
because a commit cannot contain its own final object ID.
