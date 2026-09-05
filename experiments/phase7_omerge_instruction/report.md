# Phase 7B OMERGE Instruction Results

## 1. Motivation

Phase 7B tests whether the frozen Scalar SMU recurrence can be reached by a
single scalar OMERGE instruction while preserving the existing RVV output
update. The proposed design remains Scalar SMU + RVV. The measured questions
are RQ1, safe instruction mapping; RQ2, functional and control agreement with
the MMIO path; and RQ3, cycle impact in a matched native workload.

## 2. Frozen Baselines

The implementation freeze is commit `eac2851cbb60754a2e63f64780901ab6fd12a9c0`
with tree `fabf72c186506588a1d9352354ce35af57b2b20e`. The two deterministic
anchors are N=8, D=32, seed=1 and N=16, D=64, seed=1, with four keys per tile.
The MMIO path is the existing Scalar SMU control path. Full SMU is retained
only for ablation and historical comparison. B2R is used only for mapping and
historical context, not as an OMERGE pairwise baseline.

## 3. Phase7A Encoding Re-Freeze

Phase 7A selected custom-2 Candidate A after checking the active TARGET_SPATZ
decoder and all `opcodes-*` source definitions. The selected family has zero
existing and generator intersections for all 32 rd values. The rejected
custom-0 regression remains recorded in `BLOCKED_ENCODING.md`; it overlaps
FREP_I and FREP_O and was not deleted.

## 4. RISC-V Execution Mapping

| Field | Frozen value | Role |
|---|---|---|
| format | R-type custom | scalar instruction |
| opcode | custom-2, `0x5b` | instruction family |
| funct7/funct3 | `0000011` / `000` | selected Candidate A |
| rs1/rs2 | x0 / x0 | no dynamic source operands |
| rd | x0..x31 | completion/status destination |
| machine word | `0x0600005b \| (rd << 7)` | encoded instruction |

The assembler spelling is `.insn r 0x5b, 0, 3, rd, x0, x0`.

## 5. OMERGE ISA Definition

OMERGE is a scalar-side, stateful command. It reads no register operands,
issues to the SMU accelerator interface, and returns zero for a successful
completion or a nonzero error status. The adapter fixes the arithmetic mode to
mode 3, Mixed Scalar. The A/B state selector is committed only when the
response is accepted.

## 6. Snitch Decode and Offload Path

`riscv_instr.sv` defines the frozen pattern. The top-level Snitch decoder in
`snitch.sv` recognizes OMERGE, suppresses ordinary writeback, marks the
destination as used, and emits an accelerator request with the SMU address.
The Spatz core wrapper forwards the request to the cluster arbiter. The
cluster records the accepting core and demultiplexes the asynchronous response
back to that core.

## 7. SMU Instruction Adapter

`online_merge_omerge_adapter.sv` is a four-state control adapter: IDLE,
START, WAIT, and RESP. It supplies persistent addresses and dimensions,
clears the previous terminal status, starts the existing update engine, waits
for DONE or ERROR, and toggles the selector only after response acceptance.
The adapter contains no SMU arithmetic and no RVV datapath.

## 8. Persistent Workload Configuration

The ISA benchmark writes the A/B m and l addresses, tile addresses, weight
addresses, N, D, stride, and mode once through the generated cluster registers.
`smu_isa_setup` runs before the native-core timer. The mode is 3 for every
OMERGE launch. Q/K/V loading and allocation are outside the native-core timer
for both paths.

## 9. Ping-Pong State Management

The adapter owns one selector bit. State A is the source and B is the
destination on the first merge, then the roles reverse after a successful
response. The N8 sequence is A->B. The N16 sequence is A->B->A->B. Each real
merge has one ACCEPT, START, DONE, and RESPONSE event, with zero errors.

## 10. Software Integration

The benchmark adds the OMERGE target and uses the inline `.insn` form. The
existing RVV output update remains common to MMIO and ISA paths. The ISA path
consumes the instruction status before ending its recurrence timing sample.
The setup timing is emitted separately as `workload_setup`.

## 11. Encoding and Decoder Verification

The archived smoke evidence records exact words and little-endian bytes for
x0, a0, a1, and x31. Phase 7A inventory has 440 existing decoder labels,
440 unique instruction names, and zero unresolved labels. The selected family
has exactly one OMERGE match after addition for each rd in x0..x31. The
uniqueness proof reuses the 96-row A/B/C proof artifact and does not execute a
complete 2048-family search in Phase 7B.

## 12. Functional Correctness

Both paths returned `status=pass`, `native-online-attention PASS`, and zero
nonfinite outputs. Final O hashes match within each anchor: 2625429212 for
N8/D32 and 4245499135 for N16/D64. Each path's reported metrics are against
the generated FP32 reference. The recovery raw transcripts also contain
complete final-O word dumps. The MMIO-versus-ISA dumps are bit-identical at
each anchor, so their pairwise MAE and stable relative error are 0.0 and their
pairwise cosine is 1.0. The retained reference metrics are:

| Case | MAE bits / float | Stable-relative-error bits / float | Cosine bits / float |
|---|---|---|---|
| N8/D32 | 965841751 / 0.00027766331913881004 | 1000282788 / 0.004855470731854439 | 1065352977 / 0.9999857544898987 |
| N16/D64 | 972444283 / 0.00046982229105196893 | 1005107881 / 0.007102329749614 | 1065352699 / 0.9999691843986511 |

The recovery `PHASE5_RESULT` records do not emit component hashes. Component
hash match and component MAE are therefore `NA`; the old reconstructed logs
are invalidated and are not evidence for these fields.

## 13. MMIO vs ISA Matched Methodology

The four fresh runs use the same simulator, deterministic anchor, tile shape,
compiler configuration, and output protocol. MMIO means existing Scalar SMU
register control. ISA means OMERGE issue plus the same Scalar SMU engine and
RVV update. The main measured table is:

| Case | Path | Inclusive control window | Engine busy total | RVV update | Merge window | Native core | Setup | Setup-inclusive core |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| N8/D32 | MMIO | 2069 | 808 | 808 | 2926 | 74392 | 0 | 74392 |
| N8/D32 | ISA | 848 | 808 | 800 | 1706 | 72897 | 869 | 73766 |
| N16/D64 | MMIO | 8429 | 4852 | 7942 | 16548 | 510991 | 0 | 510991 |
| N16/D64 | ISA | 4929 | 4848 | 7813 | 12915 | 507795 | 907 | 508702 |

The inclusive control window is not pure dispatch. For MMIO it is
config+clear+start+poll+SMU. For ISA it is issue+SMU+completion/status.

## 14. Control / Recurrence Cycles

The ISA control window reduces recurrence cycles from 2069 to 848 at N8 and
from 8429 to 4929 at N16. The reductions are 59.014% and 41.523%, with
window speedups of 2.440x and 1.710x. Engine busy totals are 808 versus 808
cycles at N8 and 4852 versus 4848 cycles at N16. The remaining window is
control and instruction-path overhead, not a claim of zero-latency SMU
arithmetic.

## 15. Merge-Kernel Performance

Merge-window reduction, using MMIO as the denominator, is 41.695% at N8
(2926 to 1706 cycles) and 21.954% at N16 (16548 to 12915 cycles). The RVV
portion changes from 808 to 800 cycles at N8 and from 7942 to 7813 cycles at
N16. These values keep the common RVV update in the inclusive merge window.

## 16. Native Attention Core Performance

The native-core timer excludes ISA setup because `smu_isa_setup` completes
before `core_start` in `main.c`. Core-cycle reduction is 2.010% at N8
(74392 to 72897) and 0.625% at N16 (510991 to 507795). Adding the measured
869 and 907 setup cycles gives setup-inclusive reductions of 0.841% and
0.448% (74392 to 73766 and 510991 to 508702). These are two-anchor cycle
measurements, not a broad end-to-end gain claim.

## 17. Instruction-Level Evidence

The ISA logs show one OMERGE adapter handshake for N8 and three for N16. The
N8 selector audit is A->B with mode 3 and `busy_cycles=808`. The N16 ISA
audit is A->B->A->B with mode 3 and `busy_cycles=1616` for each merge; the
N16 MMIO busy records are 1616, 1618, and 1618. MMIO has `omerge_count=0`;
ISA has one and three OMERGE commands for N8 and N16 respectively. All
command and completion counts are 1/1 and 3/3, with errors and timeouts equal
to zero.

## 18. Hardware / Software Modification Scope

The freeze contains 14 modified files covering decoder and routing, the
cluster issue/response path, the OMERGE adapter, generated register wrapper,
runtime register definitions, CMake target registration, and benchmark timing.
SMU arithmetic, RVV datapath, and Phase 1-6 implementation files are outside
the change scope. The exact list is in `formal/implementation_manifest.json`.

## 19. Limitations

The evidence covers two anchors and one fresh recovery run per path. Area,
synthesis timing, frequency, flush, interrupt, concurrent MMIO/ISA, and
multihart owner stress are not measured here. The optional no-trace Gate 1
check is deferred. All four recovery raw transcripts are trace-enabled and
retain the simulator `.rtlbinary` warning, including the required N8 MMIO
warning. Pairwise final-O agreement is measured from the raw word dumps;
component-level hash pairings remain `NA` because recovery records do not
emit component hashes.

## 20. Supported Claims

RQ1 is supported by the Phase 7A decoder/source proof and the exact-word
smoke evidence. RQ2 is supported by pass status, zero nonfinite outputs,
matching final-O hashes, and the selector audit. RQ3 is supported for these
two matched anchors by the inclusive recurrence, merge-window, and native-core
cycle tables. The instruction path reduces control-window cycles in both
anchors and preserves bit-identical final-O arrays in the raw pairwise
comparison.

## 21. Unsupported Claims

These results do not establish a universal workload speedup, an area or
frequency result, concurrent multi-core correctness, interrupt or flush
semantics, or a no-trace result. They do not establish component-level hash
agreement because those hashes are absent from the recovery records. They do
not claim that Full SMU is the proposed architecture. B2R numbers are not
used as MMIO-vs-ISA numerical evidence.

## 22. Provenance

The four raw source paths, fixed run order, allowlisted command template,
freeze commit and tree, simulator path and SHA256, ELF paths and SHA256,
redaction status, and `OM_SIM_CONFIG` are recorded in each provenance file
and `formal/audit.json`. The first continuation's formal source was
unavailable, which caused the initial Gate 2 FAIL with P1 raw loss. Gate 2
then required this full recovery. Re-review passes with P0=0, P1=0, and P2=0.
The final data comes only from this second fixed-order single-run recovery; it
is not cherry-picked.
The simulator hash is
`483ca72c2cebb6959620a3ec5bdc3bee891c294ef99f91cd1587aaf9c44c9aff`.
The formal result commit is
`f72e73d897d8b9f4791a555b4d45be3b5a0a5f66`. The subsequent commit only
finalizes provenance metadata; it does not change raw transcripts, CSV values,
or performance conclusions. No environment secrets or unallowlisted
overrides are archived.
