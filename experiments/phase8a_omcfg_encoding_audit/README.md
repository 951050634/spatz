# Phase 8A — OMCFG Instruction-Space Audit

This is an analysis-only audit of repository HEAD
`c32c99c90b11831f46d8d79372d38bede8ea3c3b`. It changed no RTL, decoder,
SMU, OMERGE, RVV, software, or build configuration. It ran no workload,
simulation, performance experiment, or synthesis.

The collision authority is the current `TARGET_SPATZ` Snitch top-level
`unique casez (inst_data_i)`. The downstream Spatz decoder was also scanned;
it contains no active pattern in any of the four custom opcodes. Pattern
matching uses the actual `casez` mask/match semantics, including every `?`
wildcard.

## Direct answers

### Q1 — What custom-opcode space is actually available?

| Opcode | Active instructions | I-type-like availability with `rd=x0` |
|---|---|---|
| `0x0B` custom-0 | `FREP_I`, `FREP_O`; low-eight-bit masked decode | No family: every funct3 and every cfg/rs1 word collides |
| `0x2B` custom-1 | Eight DMA instructions, all funct3 `000` | funct3 `001..111` are full SAFE; `000` is BLOCKED |
| `0x5B` custom-2 | OMERGE at funct3 `000` | funct3 `001..111` are full SAFE; `000` is PARTIALLY_SAFE and rejected |
| `0x7B` custom-3 | None | funct3 `000..111` are full SAFE in the active decoder |

Across all 32 opcode/funct3 families, the result is 22 `SAFE`, one
`PARTIALLY_SAFE`, and nine `BLOCKED`.

### Q2 — Is there a complete safe I-type OMCFG family?

Yes. The recommended `0x5B/funct3=001` family has zero current matches for
all `4096 cfg_id × 32 rs1 = 131,072` fixed-`rd=x0` words.

### Q3 — Can OMERGE and OMCFG share custom-2?

Yes. OMERGE remains at `0x5B/funct3=000`; OMCFG can use
`0x5B/funct3=001`. Their fixed funct3 bits conflict, so their concrete-set
intersection is empty.

### Q4 — Are all 32 rs1 and required cfg IDs safe?

Yes for every recommended candidate. The checker explicitly enumerated all
`32 rs1` values for every cfg ID. Candidate 1 has zero collisions among the
`10 × 32 = 320` required words for cfg IDs `0x000..0x009`.

### Q5 — Can an 8-bit or full 12-bit cfg namespace be reserved?

Yes for Candidate 1: both `0x000..0x0FF` (8,192 concrete words) and the full
`0x000..0xFFF` range (131,072 words) have zero active-decoder collisions.

### Q6 — Which encodings are recommended?

1. `custom-2 / 0x5B / funct3=001` — recommended.
2. `custom-2 / 0x5B / funct3=010` — same-opcode backup.
3. `custom-3 / 0x7B / funct3=001` — independent-opcode backup.

This report does not freeze an encoding. That decision remains with Sol.
Because complete I-type-like families exist, the conditional R-type fallback
audit was not run.

## Evidence

| File | Purpose |
|---|---|
| `current_decoder_inventory.md` | Active Snitch/Spatz census and exact custom patterns |
| `candidate_families.csv` | All 32 families, required columns, range counts, and rd audit |
| `collision_details.md` | Wildcard interpretation, DMA regions, witnesses, and cross-checks |
| `recommendation.md` | One primary and two backup encodings |
| `raw/audit_instruction_space.py` | Source parser and exhaustive fixed-rd checker |
| `raw/snitch_decoder_patterns.csv` | 441 active Snitch patterns |
| `raw/spatz_decoder_patterns.csv` | 345 downstream Spatz patterns |
| `raw/omerge_rd_matches.csv` | Exactly-one proof for OMERGE x0..x31 |
| `raw/rs1_collision_matrix.csv` | Per-family, per-rs1 range results (1,024 rows) |
| `raw/rd_variation_results.csv` | Per-family, per-rd full-domain results (1,024 rows) |
| `raw/collision_witnesses.csv` | Concrete witness for every colliding active instruction |
| `raw/audit_summary.json` | Machine-readable snapshot, source hashes, and totals |

Reproduce the analysis from the repository root with:

```sh
python3 experiments/phase8a_omcfg_encoding_audit/raw/audit_instruction_space.py
```
