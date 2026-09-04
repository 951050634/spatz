# Phase 7 OMERGE Encoding Blocker

Status: `BLOCKED_ENCODING`

Date: 2026-09-04

Audited commit: `b5fe69b3f249c55b3b5e0e88b668ab9f2f6d5806`

## Problem

The frozen OMERGE encoding conflicts with the existing Snitch FREP encoding:

```text
OMERGE rd:
0000000_00000_00000_000_?????_0001011
```

The repository generates `FREP_I` and `FREP_O` from
`opcodes-frep_CUSTOM`. Both instructions use custom-0. They use instruction
bit 7 to distinguish the two forms:

```text
FREP_I: bit 7 = 0, bits 6:0 = 0001011
FREP_O: bit 7 = 1, bits 6:0 = 0001011
```

For OMERGE, instruction bit 7 is `rd[0]`. Every legal OMERGE word therefore
matches an existing FREP pattern:

| OMERGE destination | Existing match |
|---|---|
| even `rd` (`x0`, `x2`, ..., `x30`) | `FREP_I` |
| odd `rd` (`x1`, `x3`, ..., `x31`) | `FREP_O` |

No `rd` value avoids the collision.

## Evidence

- `Makefile:16` includes `opcodes-frep_CUSTOM` in the opcode generation set.
- `Makefile:144-150` regenerates both the Snitch SystemVerilog patterns and
  the toolchain encoding header from that set.
- `sw/toolchain/riscv-opcodes/opcodes-frep_CUSTOM:17-18` defines `frep.o`
  with bit 7 equal to 1 and `frep.i` with bit 7 equal to 0. Both definitions
  set bits 6:2 to `0x02` and bits 1:0 to `3`, which gives custom-0 opcode
  `0001011`.
- `hw/ip/snitch/src/riscv_instr.sv:35-36` contains the generated patterns
  `????????????????????????10001011` and
  `????????????????????????00001011`.
- `hw/ip/snitch/src/snitch.sv:552` uses `unique casez` for instruction decode.
  The active FREP decode appears at `hw/ip/snitch/src/snitch.sv:2065-2074`.
- A development-only assembly check emitted `0x0000040B` for the frozen
  encoding with `rd=x8`. The repository toolchain disassembled this exact
  machine word as `frep.i`, reproducing the collision.

The generic `CUSTOM0` declaration also overlaps by construction, but Snitch
does not use that declaration as an active named decode. The FREP overlap is
an active instruction collision.

## Impact

Adding OMERGE to the same `unique casez` decoder creates multiple active
matches and aliases every FREP encoding whose upper fields satisfy OMERGE.
Decode priority can make a smoke test execute the OMERGE path, but priority
does not remove the ISA collision. Such a run cannot support Phase 7
correctness or performance claims.

## Likely Cause

The pre-implementation audit treated custom-0 as unused. It missed that FREP
uses bit 7 as part of an eight-bit encoding while bits 6:0 still select the
custom-0 major opcode.

## Gate 1 Review

Sol Max independently reported:

```text
P0 = 1
P1 = 0
P2 = 0
Verdict = BLOCKED_ENCODING
Affected destinations = x0-x31
```

## Current State

`BLOCKED_ENCODING`

The uncommitted OMERGE integration was removed. No alternate opcode was
selected. Formal N8/D32 and N16/D64 data collection, performance CSVs, and
Phase 7 claims were not produced. The frozen Phase 1-6 RTL and formal results
remain unchanged.
