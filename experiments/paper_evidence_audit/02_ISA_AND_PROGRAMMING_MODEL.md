# ISA and Programming Model Audit

## OMERGE

| Field | Frozen value |
|---|---|
| Format | R-type custom |
| opcode | custom-2, `0x5B` (`1011011`) |
| funct3 | `000` |
| funct7 | `0000011` (numeric `3`) |
| rs1 / rs2 | `x0` / `x0` |
| rd | `x0..x31`, completion/status destination |
| pattern | `0000011 00000 00000 000 ????? 1011011` |
| mask / match | `0xFFFFF07F` / `0x0600005B` |
| machine word | `0x0600005B \| (rd << 7)` |
| software form | `.insn r 0x5b, 0, 3, rd, x0, x0` |

Examples archived in the formal manifest: x0=`0x0600005b`, a0=`0x0600055b`,
a1=`0x060005db`, x31=`0x06000fdb`.

### Completion semantics

OMERGE reads no architectural source operands. Decode marks `rd` as the pending
destination, routes the request to the SMU accelerator path, and returns only after
the existing engine reports DONE or ERROR and the response is accepted. `rd=0`
means success; nonzero means error. The timed ISA recurrence/control window includes
issue, **SMU execution/busy**, response commit, and status consumption.

## OMCFG

| Field | Frozen value |
|---|---|
| Shape | I-type-like custom instruction |
| opcode | custom-2, `0x5B` |
| funct3 | `001` |
| rd | fixed `x0`; no result and no destination scoreboard entry |
| rs1 | value source register; all x0..x31 encodings are collision-safe |
| imm12 / cfg_id | bits 31:20, `0x000..0xFFF` namespace |
| pattern | `???????????? ????? 001 00000 1011011` |
| mask / match | `0x00007FFF` / `0x0000105B` |
| machine word | `(cfg_id << 20) \| (rs1 << 15) \| 0x0000105B` |
| software helper | `sw/snRuntime/include/online_merge_omcfg.h` |

OMCFG uses the same scalar accelerator issue path, carries X[rs1] in `data_arga`,
and updates the same generated physical registers as MMIO. It is accepted in the
adapter IDLE state and does not start the recurrence engine or return a completion
payload.

## Frozen cfg_id mapping

| cfg_id | Final name | Meaning | MMIO-equivalent offset |
|---:|---|---|---:|
| `0x000` | A_M | state-A max address | `0xF0` |
| `0x001` | A_L | state-A normalization address | `0xF8` |
| `0x002` | B_M | state-B max address | `0x100` |
| `0x003` | B_L | state-B normalization address | `0x108` |
| `0x004` | TILE_M | tile max address | `0x80` |
| `0x005` | TILE_L | tile normalization address | `0x88` |
| `0x006` | WEIGHT_OLD | old-state weight destination | `0xD0` |
| `0x007` | WEIGHT_TILE | tile weight destination | `0xD8` |
| `0x008` | N | row count | `0xB0` |
| `0x009` | CTRL/INIT | commit required mask and reset selector | `MERGE_CTRL.CLEAR_DONE` |
| `0x00A..0xFFF` | reserved | no register write; deterministically invalidates context | — |

The required mask is `9'h1FF`. A complete field set plus CTRL value bit 0=`1`
establishes `cfg_valid=1` and selector 0. Any required-field rewrite makes the
context dirty. CTRL bit 0=`0` does not commit INIT.

Not represented in v1 cfg IDs: D, precision/mode, tile size, O addresses, stride,
or selector. These are fixed in the adapter or remain software/RVV concerns.

## Final programming model

```text
OMCFG        → workload-persistent configuration plane (nine fields + INIT)
OMERGE       → one state-dependent recurrence invocation per non-first tile
HW selector  → deterministic dynamic m/l A/B state
RVV/software → D-dimensional O update and software O-buffer pointer swap
```

The separation matters when reporting results: OMERGE measures recurring invocation/
control benefit; OMCFG measures configuration-plane, one-time setup benefit.

## Phase 8A decoder audit

Audit revision: `c32c99c90b11831f46d8d79372d38bede8ea3c3b` (before OMCFG
insertion).

| Scope | Active patterns |
|---|---:|
| `riscv_instr.sv` package declarations | 1,063 |
| Snitch top-level decode with `TARGET_SPATZ` | 441 = 199 unconditional + 242 guarded |
| downstream Spatz decode | 345 |

Active custom-opcode pattern counts were: custom-0 `2` (FREP), custom-1 `8`
(DMA), custom-2 `1` (OMERGE), custom-3 `0`. Across 32 opcode/funct3 families,
22 were SAFE, one PARTIALLY_SAFE, and nine BLOCKED.

The exhaustive fixed-rd0 search checked `4 × 8 × 4096 × 32 = 4,194,304`
concrete words. For the selected custom-2/funct3=001 family it found:

- zero collisions for the 320 required words (`10 cfg_id × 32 rs1`);
- zero collisions for the 8,192-word reserved 8-bit namespace;
- zero collisions for all 131,072 words in its full imm12/rs1 domain;
- empty intersection with every OMERGE rd variant.

After OMCFG insertion, the Phase 8B static checker reports 442 active Snitch
labels. Do not mix that post-insertion count with the Phase 8A candidate audit's
441 pre-insertion count. Likewise, Phase 7's 440/1,062 counts are an earlier
pre-OMERGE epoch.

## Why `0x5B/funct3=001`?

- It keeps OMCFG beside OMERGE in custom-2 while the fixed funct3 bits make their
  concrete sets disjoint.
- It provides a clean full 12-bit cfg namespace for every rs1 and fixed rd=x0.
- custom-0 is unusable because FREP's low-eight-bit mask covers every funct3 and
  every higher-field assignment.
- custom-1/funct3=000 collides with DMA required IDs; other funct3 values were safe
  but would separate the interface from OMERGE.
- custom-3 was empty and safe, but was retained only as an independent-opcode backup.
- custom-2/funct3=000 was rejected despite required IDs being clear: cfg_id `0x060`,
  rs1=x0, rd=x0 produces `0x0600005B`, exactly OMERGE. A namespace with this hole
  was not accepted as a clean family.

Primary sources: `experiments/phase7_omerge_instruction/formal/instruction_manifest.json`,
`experiments/phase8a_omcfg_encoding_audit/README.md`,
`experiments/phase8a_omcfg_encoding_audit/current_decoder_inventory.md`,
`experiments/phase8a_omcfg_encoding_audit/collision_details.md`,
`experiments/phase8a_omcfg_encoding_audit/raw/audit_summary.json`,
`experiments/phase8b_omcfg_impl/implementation_summary.md`,
`experiments/phase8b_omcfg_impl/cfg_mapping.md`,
`experiments/phase8b_omcfg_impl/functional_validation.md`,
`hw/ip/snitch/src/riscv_instr.sv`, `hw/ip/snitch/src/snitch.sv`, and
`hw/ip/online_merge/src/online_merge_omerge_adapter.sv`.
