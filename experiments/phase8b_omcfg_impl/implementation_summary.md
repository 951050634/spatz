# Phase 8B implementation summary

## Result

The frozen OMCFG instruction is integrated through the existing Snitch SMU
accelerator issue path.  It updates the same generated registers used by the
legacy MMIO configuration path, and the unchanged OMERGE launch path consumes
that state after a successful INIT.

Frozen encodings:

```text
OMCFG:  opcode=0x5b, funct3=001, rd=x0, imm12=cfg_id
        mask=0x00007fff, match=0x0000105b
OMERGE: mask=0xfffff07f, match=0x0600005b (unchanged)
```

## Implementation

1. **Files changed.**

   - Decode/routing: `hw/ip/snitch/src/riscv_instr.sv`,
     `hw/ip/snitch/src/snitch.sv`.
   - Adapter/control: `hw/ip/online_merge/src/online_merge_omerge_adapter.sv`.
   - Cluster wiring and canonical shared registers:
     `hw/system/spatz_cluster/src/spatz_cluster.sv`,
     `hw/system/spatz_cluster/src/spatz_cluster_peripheral/`
     `spatz_cluster_peripheral.sv`, its `.hjson`, and the two regenerated
     SystemVerilog register files.
   - Software/test: `sw/snRuntime/include/online_merge_omcfg.h`,
     `sw/riscvTests/isa/omcfg-directed.c`, and
     `sw/riscvTests/CMakeLists.txt`.

2. **Decode location.**  `riscv_instr.sv` contains the exact frozen OMCFG
   pattern.  Its `snitch.sv` decode case selects scalar register operand A,
   routes the request to the existing `SMU` accelerator address, fixes the
   architectural destination to x0, and creates no destination scoreboard
   entry.  OMERGE's pattern and case are unchanged.

3. **Field transport.**  The existing issue request transports the complete
   instruction in `data_op` and X[rs1] in `data_arga`.  The adapter extracts
   `cfg_id = data_op[31:20]`, the encoded rs1 index from `data_op[19:15]` for
   test evidence, and the 32-bit value from `data_arga[31:0]`.

4. **Persistent-state write.**  For cfg IDs `0x000..0x008`, the adapter emits
   one hardware write strobe, ID, and value.  The peripheral connects these to
   the `d/de` ports of the existing generated MMIO registers.  No second
   configuration bank was introduced.

5. **MMIO/OMCFG relationship.**  Both paths update the same nine physical
   register instances listed in `cfg_mapping.md`.  MMIO reads directly observe
   OMCFG writes.  MMIO write-enable pulses and OMCFG accepts also feed the same
   adapter-local validity tracking.  The legacy direct-MMIO engine launch path
   and all existing MMIO addresses remain present.

6. **Validity.**  Reset initializes `cfg_written_mask=0` and `cfg_valid=0`.
   Each required-field write sets its bit and makes the context dirty
   (`cfg_valid=0`).  The required mask is `9'h1ff`.  A reserved cfg ID writes no
   register and deterministically invalidates the context.

7. **INIT.**  `OMCFG CTRL` with value bit 0 set clears stale engine terminal
   state and tests the required mask.  A complete mask sets `cfg_valid=1` and
   selector 0; an incomplete mask leaves `cfg_valid=0`.  The existing MMIO
   `MERGE_CTRL.CLEAR_DONE` pulse is the MMIO-side INIT equivalent, preserving
   the current setup sequence without adding a commit state machine.

8. **Selector.**  The selector remains adapter-owned.  Successful INIT resets
   it to 0.  Only acceptance of a successful OMERGE response toggles it; an
   invalid configuration or engine error leaves it unchanged.  No selector
   cfg ID exists.

9. **OMERGE delta.**  The existing `IDLE -> START -> WAIT -> RESP` execution is
   retained.  The only functional gate added is: when `cfg_valid=0`, return
   nonzero status/error without asserting SMU start.  Valid OMERGE behavior,
   completion status, and success-toggle rule remain intact.

10. **SMU/RVV boundary.**  No update-engine arithmetic file and no RVV
    datapath file was modified.  OMERGE remains fixed to Mixed Scalar mode.
    Because the current generic engine validator checks D and stride although
    scalar recurrence does not consume them, the adapter supplies legal
    constants D=1 and stride=0.  The existing arithmetic and validator are
    unchanged.

## Completion, exclusion, and busy behavior

OMCFG is a short issue handshake: it neither starts the engine nor returns an
architectural value.  No long-latency response state is allocated.  The shared
adapter accepts a command only while its state is IDLE and the engine is not
busy, so an OMCFG cannot change active OMERGE state.  MMIO and OMCFG write
pulses are also mutually excluded at the adapter acceptance point.

The implemented namespace is `0x000..0x009`; `0x00a..0xfff` is reserved.
Reserved IDs have no register side effect and invalidate readiness.  For CTRL,
only bit 0 is implemented; bits 31:1 are ignored.

## Deliberate limits

- The small C wrapper emits only the ten implemented immediate IDs; it is not
  a compiler backend or general custom-instruction runtime.
- Existing software must not perform legacy MMIO reconfiguration during an
  active OMERGE.  Phase 8B adds accelerator backpressure for OMCFG, not a new
  transaction protocol around the legacy MMIO bus.
- Validation is the requested minimal directed path.  It does not include
  exhaustive cfg IDs/GPRs, random streams, multi-hart stress, Native Attention
  workloads, performance comparison, or synthesis.
