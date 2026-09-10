# Runtime configurability

## Frozen implementation

- Phase 8B implementation-freeze commit:
  `7786820821102d34e32e9517a7630b028693f25a`.
- Formal Git HEAD: the same commit.
- Frozen simulator SHA-256:
  `002161e3e88edd6fa6392dbe79a6a89796477282d5ff951037a211676785a51a`.
- RTL diff from the freeze during and after all four formal runs: empty.
- SMU arithmetic and RVV datapath changes during Phase 8C: none.

For each shape, both targets were compiled from the same source with only one
initialized runtime selector word differing. Their executable `.text` sections
were byte-identical:

| Case | MMIO `.text` SHA-256 | OMCFG `.text` SHA-256 | Equal |
|---|---|---|---:|
| N8/D32 | `07d31ec89d8e8f3f94b3584132c18afcdfbf75d6576083c38b7b6437e55d9df7` | `07d31ec89d8e8f3f94b3584132c18afcdfbf75d6576083c38b7b6437e55d9df7` | yes |
| N16/D64 | `337a39eceacd74049b12cc818e1218c7366c585fa291ba999ae4697e589f7bd0` | `337a39eceacd74049b12cc818e1218c7366c585fa291ba999ae4697e589f7bd0` | yes |

## Persistent-state equivalence

The values below were read back through the canonical MMIO register view after
setup. Adapter traces independently reported `cfg_valid=1` and selector 0
after INIT.

| Case/path | A_M | A_L | B_M | B_L | TILE_M | TILE_L | WEIGHT_OLD | WEIGHT_TILE | N | cfg_valid | selector |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N8 MMIO | 3200 | 3232 | 5376 | 5408 | 4288 | 4320 | 6464 | 6496 | 8 | 1 | 0 |
| N8 OMCFG | 3200 | 3232 | 5376 | 5408 | 4288 | 4320 | 6464 | 6496 | 8 | 1 | 0 |
| N16 MMIO | 12544 | 12608 | 20992 | 21056 | 16768 | 16832 | 25216 | 25280 | 16 | 1 | 0 |
| N16 OMCFG | 12544 | 12608 | 20992 | 21056 | 16768 | 16832 | 25216 | 25280 | 16 | 1 | 0 |

This demonstrates that MMIO and OMCFG update the same persistent accelerator
context. The same frozen RTL accepts different runtime-issued `N` and address
values for the two anchors; no Verilog parameter or accelerator implementation
was changed between them.

`D=32/64` remains a software/RVV loop parameter. It is intentionally absent
from frozen OMCFG v1. The unchanged Scalar SMU recurrence consumes the runtime
`N` and scalar-state addresses; the adapter supplies its frozen validation-safe
internal `D=1`, while the RVV kernel performs the D-wide O update.
