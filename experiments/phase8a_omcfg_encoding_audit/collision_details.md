# Collision Details

## Match method and enumerated domains

A concrete word matches a decoder pattern when:

```text
(word & pattern_mask) == pattern_match
```

The checker derives mask and match from every `0`, `1`, and `?` in the
current `riscv_instr.sv` pattern, rather than comparing only opcode/funct3 or
assuming an R-type interpretation.

For each of four opcodes and eight funct3 values, it concretely enumerates:

| Range | cfg IDs | rs1 values | rd | Words per family |
|---|---|---|---|---:|
| Required-safe | `0x000..0x009` | `x0..x31` | `x0` | 320 |
| Reserved-safe | `0x000..0x0FF` | `x0..x31` | `x0` | 8,192 |
| Full-safe | `0x000..0xFFF` | `x0..x31` | `x0` | 131,072 |

The full fixed-rd search therefore covers 4,194,304 concrete words. The raw
per-rs1 matrix contains 1,024 rows. A separate mask-cardinality audit fixes
each `rd=x0..x31` in turn and covers the same 131,072 cfg/rs1 assignments per
rd; pairwise disjointness is asserted before individual pattern counts are
summed.

Before hypothetical insertion, a `SAFE` family has current match count zero
for every legal word. Its proposed family mask matches every legal word once,
so after insertion the count is exactly one. Collision words in non-SAFE
families would instead have count two.

## custom-0 / 0x0B

FREP_I has mask/match `0x000000FF/0x0000000B`; FREP_O has
`0x000000FF/0x0000008B`. The mask ignores funct3 and all higher fields.
With rd=x0, bit 7 is zero, so every candidate word matches FREP_I:

| funct3 families | Required collisions | Reserved collisions | Full collisions | Status |
|---|---:|---:|---:|---|
| `000..111` (each) | 320 | 8,192 | 131,072 | BLOCKED |

There is no rd escape. Any even rd, including x0, selects FREP_I; any odd rd
selects FREP_O. Over the additional `rd=x1..x31` domain, every family has
4,063,232 more collision words.

## custom-1 / 0x2B

All eight active DMA patterns use funct3 `000`. Interpreting bits 31:20 as
the proposed I-like cfg ID gives these exact collision regions:

| Instruction | Match / mask | cfg_id values | rs1 condition | rd condition | Fixed-rd0 collisions |
|---|---|---|---|---|---:|
| DMSRC | `0x0000002B / 0xFE007FFF` | `0x000..0x01F` | any | x0 | 1,024 |
| DMDST | `0x0200002B / 0xFE007FFF` | `0x020..0x03F` | any | x0 | 1,024 |
| DMCPYI | `0x0400002B / 0xFE00707F` | `0x040..0x05F` | any | any | 1,024 |
| DMCPY | `0x0600002B / 0xFE00707F` | `0x060..0x07F` | any | any | 1,024 |
| DMSTATI | `0x0800002B / 0xFE0FF07F` | `0x080..0x09F` | x0 | any | 32 |
| DMSTAT | `0x0A00002B / 0xFE0FF07F` | `0x0A0..0x0BF` | x0 | any | 32 |
| DMSTR | `0x0C00002B / 0xFE007FFF` | `0x0C0..0x0DF` | any | x0 | 1,024 |
| DMREP | `0x0E00002B / 0xFFF07FFF` | exactly `0x0E0` | any | x0 | 32 |

The total is 5,216 unique fixed-rd0 words. Required cfg IDs `0x000..0x009`
all fall in DMSRC, so all 320 required words collide and funct3 `000` is
BLOCKED. The reserved and full collision totals are both 5,216. Funct3
`001..111` each has zero collisions across the full range and is SAFE.

For `rd=x1..x31`, the fixed-rd DMA patterns disappear, but DMCPYI, DMCPY,
DMSTATI, and DMSTAT remain. They contribute 65,472 collision words, so using
rd as a workaround would still leave a restricted family and is unnecessary.

## custom-2 / 0x5B

| funct3 | Required collisions | Reserved collisions | Full collisions | OMERGE intersection | Status |
|---|---:|---:|---:|---:|---|
| `000` | 0 | 1 | 1 | 1 | PARTIALLY_SAFE |
| `001` | 0 | 0 | 0 | 0 | SAFE |
| `010` | 0 | 0 | 0 | 0 | SAFE |
| `011` | 0 | 0 | 0 | 0 | SAFE |
| `100` | 0 | 0 | 0 | 0 | SAFE |
| `101` | 0 | 0 | 0 | 0 | SAFE |
| `110` | 0 | 0 | 0 | 0 | SAFE |
| `111` | 0 | 0 | 0 | 0 | SAFE |

The sole funct3 `000` witness is:

```text
cfg_id = 0x060
rs1    = x0
rd     = x0
word   = 0x0600005B
match  = OMERGE
```

The required range happens to avoid this word, but the 8-bit reserved range
does not. Depending on a hole at cfg `0x060` violates the clean-family rule,
so this family is not recommended. OMERGE wildcards rd; changing rd would
produce the corresponding collision for every other rd, not remove it.

For any funct3 `001..111`, the funct3 constraint conflicts with OMERGE's
fixed `000`. Thus all 131,072 candidate words are disjoint from OMERGE, and
all 32 existing OMERGE words are disjoint from a newly inserted candidate.

## custom-3 / 0x7B

Neither the active Snitch decoder nor the downstream Spatz decoder contains a
custom-3 pattern. Every funct3 `000..111` family has zero required, reserved,
and full collisions. All eight are SAFE against the current frozen decoder.

## Required configuration IDs

For each recommended candidate, every rs1 is safe for all required IDs:

| ID | Configuration |
|---|---|
| `0x000` | `STATE_A_M_ADDR` |
| `0x001` | `STATE_A_L_ADDR` |
| `0x002` | `STATE_B_M_ADDR` |
| `0x003` | `STATE_B_L_ADDR` |
| `0x004` | `TILE_M_ADDR` |
| `0x005` | `TILE_L_ADDR` |
| `0x006` | `WEIGHT_OLD_ADDR` |
| `0x007` | `WEIGHT_TILE_ADDR` |
| `0x008` | `N` |
| `0x009` | `CTRL` |

## rd conclusion

For every recommended family, `rd=x1..x31` is also collision-free, so fixing
rd=x0 does not create the safety result. It remains the clean v1 architectural
constraint and leaves no implied return value. Since a full family already
exists, there is no reason to expand OMCFG semantics to use rd.

Concrete aggregate results are in `candidate_families.csv`; witnesses are in
`raw/collision_witnesses.csv`; per-rs1 and per-rd evidence is in
`raw/rs1_collision_matrix.csv` and `raw/rd_variation_results.csv`.
