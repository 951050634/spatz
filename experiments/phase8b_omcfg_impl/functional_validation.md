# Phase 8B functional validation

## Outcome

**PASS.**  OMCFG correctly configures the existing OMERGE execution context.
All required T1--T8 checks pass in the system Verilator model, with a separate
static check of the implemented instruction patterns.

Validation baseline: repository HEAD
`c32c99c90b11831f46d8d79372d38bede8ea3c3b` plus the Phase 8B working-tree
changes.  The directed program is a one-row scalar merge and is not an
Attention workload.

## Commands

```text
python3 experiments/phase8b_omcfg_impl/raw/check_decode.py

cmake --build hw/system/spatz_cluster/sw/build \
  --target test-riscvTests-omcfg-directed -j8

cd hw/system/spatz_cluster
./work-phase8b/spatz_cluster.vlt \
  sw/build/riscvTests/test-riscvTests-omcfg-directed
```

The software target built successfully.  The simulator exited with status 0
and printed `PHASE8B_RESULT SUCCESS failures=0` and `[SUCCESS] Program finished
successfully`.

Raw evidence:

- `raw/decode_check.log`: exact decode mask/match and symbolic overlap check.
- `raw/instruction_words.log`: emitted x0, a0/x10, x31, and reserved-ID words.
- `raw/omcfg_directed.log`: test markers plus adapter/engine event trace.

## T1--T8

| Test | Result | Key evidence |
|---|---|---|
| T1 -- Decode | **PASS** | Static extraction reports OMCFG `0x0000105b/0x00007fff`, unchanged OMERGE `0x0600005b/0xfffff07f`, one active case for each, and zero overlap with all 441 other active Snitch labels. Samples are cfg 0/x0, cfg 1/x10, cfg 2/x31, and reserved cfg 10/x31. Runtime adapter events report the same cfg IDs and rs1 indices, while no OMERGE accept occurs for those OMCFG words. |
| T2 -- Individual writes | **PASS** | After every one of the nine required-field writes, the C test reads all nine canonical registers through MMIO and checks the target value plus unchanged peers. The adapter reports exactly one write event per instruction. |
| T3 -- `cfg_written_mask` | **PASS** | Adapter trace advances `000 -> 001 -> 003 -> 007`, then `00f -> 01f -> 03f -> 07f -> 0ff -> 1ff`, matching cfg IDs 0--8. |
| T4 -- Early INIT | **PASS** | INIT at mask `0x007` reports `complete=0`, `cfg_valid_after=0`, selector 0. The next OMERGE produces error status 1 with no intervening `OMERGE_ADAPTER_START`; both state buffers remain unchanged. |
| T5 -- Full INIT | **PASS** | INIT at mask `0x1ff` reports `complete=1`, `cfg_valid_after=1`, and `selector_after=0`. |
| T6 -- Consume OMCFG state | **PASS** | The first valid OMERGE starts in selector 0 using the OMCFG/MMIO-visible addresses. With A `(m=1,l=2)` and tile `(m=1,l=3)`, it writes B `(m=1,l=5)` and returns status 0. The engine event reports the configured `N=1`, fixed scalar mode 3, and validation constant D=1. |
| T7 -- Selector | **PASS** | First successful response logs selector `0 -> 1` (A to B). The second starts at selector 1, writes A normalization `5+3=8`, and logs `1 -> 0`. |
| T8 -- Reconfiguration | **PASS** | Writing cfg ID 5 after READY makes the next OMERGE return status 1 without start or toggle. Re-INIT restores valid state and selector 0; the next A-to-B merge succeeds and writes the expected normalization 9. |

The additional `PHASE8B_RESERVED PASS` check confirms cfg ID `0x00a`
modifies none of the nine registers and invalidates the context.  The
`PHASE8B_MMIO_SHARED PASS` check then writes cfg field 5 through its legacy
MMIO address, observes dirty rejection, commits through
`MERGE_CTRL.CLEAR_DONE`, and successfully runs OMERGE from selector 0.  This
directly demonstrates that MMIO and OMCFG share both value storage and
validity/INIT semantics.

## Research questions

| RQ | Answer |
|---|---|
| RQ1 | **Yes.** OMCFG uses the existing Snitch SMU issue path; neither SMU arithmetic nor RVV datapath changed. |
| RQ2 | **Yes.** OMCFG drives the hardware-write ports of the same generated registers written through MMIO. |
| RQ3 | **Yes.** The minimal one-row execution consumes OMCFG-established A/B, tile, weight, and N context and produces the expected scalar result. |
| RQ4 | **Yes.** Incomplete/dirty configurations are rejected, INIT establishes readiness and selector 0, and only successful OMERGE responses toggle the selector. |

No Native Attention configuration, performance comparison, setup-cycle claim,
or synthesis was run.
