# OMCFG Encoding Recommendation

## Candidate 1 — Recommended

```text
format:             I-type-like
opcode:             custom-2 / 0x5B
funct3:             001
funct7 / imm:       imm12 = cfg_id; all 0x000..0xFFF allowed
rd:                 x0
rs1:                x0..x31; configuration value source
cfg_id:             imm12[11:0]

required cfg range: 0x000..0x009 — SAFE (320/320 words, 0 collisions)
safe reserved range:0x000..0x0FF — SAFE (8,192/8,192 words)
safe full range:    0x000..0xFFF — SAFE (131,072/131,072 words)

collision result:   zero matches with all 441 current active Snitch patterns
OMERGE coexistence: disjoint; OMERGE funct3=000, OMCFG funct3=001
decoder result:     current count=0; after hypothetical insertion exactly 1
```

Family encoding:

```text
mask  = 0x00007FFF
match = 0x0000105B
word  = (cfg_id << 20) | (rs1 << 15) | 0x0000105B
```

Why recommended: it keeps CONFIG and EXEC in the same Online Merge custom-2
namespace, separates them with one clean fixed field, supports every GPR as
the value source, and reserves the complete 12-bit cfg namespace without a
hole. All 32 existing OMERGE encodings remain exactly-one matches after this
hypothetical family is added.

## Candidate 2 — Same-opcode backup

```text
format:             I-type-like
opcode:             custom-2 / 0x5B
funct3:             010
funct7 / imm:       imm12 = cfg_id; all 0x000..0xFFF allowed
rd:                 x0
rs1:                x0..x31; configuration value source
cfg_id:             imm12[11:0]

required cfg range: 0x000..0x009 — SAFE (320/320 words, 0 collisions)
safe reserved range:0x000..0x0FF — SAFE (8,192/8,192 words)
safe full range:    0x000..0xFFF — SAFE (131,072/131,072 words)

collision result:   zero matches with all 441 current active Snitch patterns
OMERGE coexistence: disjoint; OMERGE funct3=000, candidate funct3=010
decoder result:     current count=0; after hypothetical insertion exactly 1
```

Family encoding:

```text
mask  = 0x00007FFF
match = 0x0000205B
word  = (cfg_id << 20) | (rs1 << 15) | 0x0000205B
```

Why a backup: it has the same complete safety and namespace benefits as
Candidate 1. It should be used only if Sol reserves funct3 `001` for another
policy reason.

## Candidate 3 — Independent-opcode backup

```text
format:             I-type-like
opcode:             custom-3 / 0x7B
funct3:             001
funct7 / imm:       imm12 = cfg_id; all 0x000..0xFFF allowed
rd:                 x0
rs1:                x0..x31; configuration value source
cfg_id:             imm12[11:0]

required cfg range: 0x000..0x009 — SAFE (320/320 words, 0 collisions)
safe reserved range:0x000..0x0FF — SAFE (8,192/8,192 words)
safe full range:    0x000..0xFFF — SAFE (131,072/131,072 words)

collision result:   zero matches with all 441 current active Snitch patterns
OMERGE coexistence: disjoint opcodes (0x7B versus 0x5B)
decoder result:     current count=0; after hypothetical insertion exactly 1
```

Family encoding:

```text
mask  = 0x00007FFF
match = 0x0000107B
word  = (cfg_id << 20) | (rs1 << 15) | 0x0000107B
```

Why a backup: the current active custom-3 opcode is completely empty, so this
option isolates OMCFG if same-opcode pairing is later rejected. It loses the
clear custom-2 CONFIG/EXEC grouping and is therefore ranked third.

## Rejected nearby family

Do not allocate generic OMCFG to `custom-2/funct3=000`. Although required IDs
`0x000..0x009` are safe, `cfg_id=0x060, rs1=x0` is exactly OMERGE word
`0x0600005B`. Avoiding that single immediate is an unnecessary reserved-hole
workaround when seven complete custom-2 families are available.

No encoding is frozen by this document, and no implementation is authorized
or included. The R-type fallback remains unexamined because Candidate 1 is a
complete safe I-type-like family.
