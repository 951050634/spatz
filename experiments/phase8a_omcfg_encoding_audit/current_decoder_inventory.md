# Current Decoder Inventory

## Scope and counting rule

The audited revision is
`c32c99c90b11831f46d8d79372d38bede8ea3c3b`. The checker parses 32-bit
ternary declarations from `hw/ip/snitch/src/riscv_instr.sv`, then resolves
only labels present in active top-level instruction decode cases.

| Decode scope | Case location | Active labels | Unique names/patterns | Custom-opcode labels |
|---|---|---:|---:|---:|
| Snitch with `TARGET_SPATZ` | `hw/ip/snitch/src/snitch.sv:552` | 441 | 441 | 11 |
| Spatz downstream | `hw/ip/spatz/src/spatz_decoder.sv:55` | 345 | 345 | 0 |

The Snitch count is 199 unconditional labels plus 242 labels under
`TARGET_SPATZ`. Its top-level case closes at line 2641. The Spatz case closes
at line 1774. Nested field-decode cases are not counted again.

The package contains 1,063 32-bit localparam patterns. Declarations such as
`CUSTOM2`, `CUSTOM2_RS1`, and the generated IPU patterns do not collide merely
by existing: neither active top-level decoder references them. The raw
inventories retain the package and decoder source locations for every active
label, so this distinction is explicit rather than name-based.

## Active custom-opcode patterns

`*` below means the real pattern is wildcarded over the entire field. A field
containing `?` is only partially constrained.

| Opcode | Instruction | funct3 | funct7 | rd | rs1 | rs2 | Match | Mask |
|---|---|---|---|---|---|---|---|---|
| `0x0B` | FREP_O | `*` | `*` | `????1` | `*` | `*` | `0x0000008B` | `0x000000FF` |
| `0x0B` | FREP_I | `*` | `*` | `????0` | `*` | `*` | `0x0000000B` | `0x000000FF` |
| `0x2B` | DMSRC | `000` | `0000000` | `00000` | `*` | `*` | `0x0000002B` | `0xFE007FFF` |
| `0x2B` | DMDST | `000` | `0000001` | `00000` | `*` | `*` | `0x0200002B` | `0xFE007FFF` |
| `0x2B` | DMSTR | `000` | `0000110` | `00000` | `*` | `*` | `0x0C00002B` | `0xFE007FFF` |
| `0x2B` | DMCPYI | `000` | `0000010` | `*` | `*` | `*` | `0x0400002B` | `0xFE00707F` |
| `0x2B` | DMCPY | `000` | `0000011` | `*` | `*` | `*` | `0x0600002B` | `0xFE00707F` |
| `0x2B` | DMSTATI | `000` | `0000100` | `*` | `00000` | `*` | `0x0800002B` | `0xFE0FF07F` |
| `0x2B` | DMSTAT | `000` | `0000101` | `*` | `00000` | `*` | `0x0A00002B` | `0xFE0FF07F` |
| `0x2B` | DMREP | `000` | `0000111` | `00000` | `*` | `00000` | `0x0E00002B` | `0xFFF07FFF` |
| `0x5B` | OMERGE | `000` | `0000011` | `*` | `00000` | `00000` | `0x0600005B` | `0xFFFFF07F` |

There is no active `0x7B` pattern. FREP is the only opcode-only-like masked
region: it fixes the 7-bit opcode and instruction bit 7, but ignores funct3
and every higher bit. DMA fixes funct3 `000` and then applies the distinct
funct7/rd/rs1/rs2 constraints shown above. OMERGE fixes every bit except rd.

The machine-readable version is `raw/custom_opcode_inventory.csv`; the full
sets are `raw/snitch_decoder_patterns.csv` and
`raw/spatz_decoder_patterns.csv`.

## Frozen OMERGE verification

The repository definition is exactly:

```text
pattern = 0000011 00000 00000 000 ????? 1011011
opcode  = custom-2 = 0x5B
funct3  = 000
funct7  = 0000011
rs1     = x0
rs2     = x0
rd      = completion/status destination
mask    = 0xFFFFF07F
match   = 0x0600005B
```

Thus:

```text
base word = 0x0600005B
word      = 0x0600005B | (rd << 7)
```

All 32 words for `rd=x0..x31` were matched against the 441 active Snitch
patterns. Each has match count exactly one, and the sole matching label is
OMERGE. `raw/omerge_rd_matches.csv` records every word and match count.

## Candidate pattern shape

For an I-type-like OMCFG family with arbitrary cfg and rs1 but fixed rd=x0:

```text
pattern = ????????????????? funct3 00000 opcode
mask    = 0x00007FFF
match   = (funct3 << 12) | opcode
word    = (cfg_id << 20) | (rs1 << 15) | match
```

The checker evaluates this pattern using the same mask/match relation as the
current `casez` decoder.
