# OMCFG v1 configuration mapping

Frozen instruction family:

```text
OMCFG cfg_id, rs1
word  = (cfg_id << 20) | (rs1 << 15) | 0x0000105b
mask  = 0x00007fff
match = 0x0000105b
rd    = x0
```

## Final mapping

| cfg_id | Symbolic name | Actual RTL register/state | Width | Consumer | MMIO equivalent | Required |
|---:|---|---|---:|---|---|---:|
| `0x000` | `STATE_A_M_ADDR` | `reg2hw.merge_isa_state_a_m.q` | 32 (low `TCDMAddrWidth` consumed) | adapter A/B m mux -> SMU `src_m_old`/`dst_m` | `MERGE_ISA_STATE_A_M` (`0xf0`) | yes |
| `0x001` | `STATE_A_L_ADDR` | `reg2hw.merge_isa_state_a_l.q` | 32 (low `TCDMAddrWidth` consumed) | adapter A/B l mux -> SMU `src_l_old`/`dst_l` | `MERGE_ISA_STATE_A_L` (`0xf8`) | yes |
| `0x002` | `STATE_B_M_ADDR` | `reg2hw.merge_isa_state_b_m.q` | 32 (low `TCDMAddrWidth` consumed) | adapter A/B m mux -> SMU `src_m_old`/`dst_m` | `MERGE_ISA_STATE_B_M` (`0x100`) | yes |
| `0x003` | `STATE_B_L_ADDR` | `reg2hw.merge_isa_state_b_l.q` | 32 (low `TCDMAddrWidth` consumed) | adapter A/B l mux -> SMU `src_l_old`/`dst_l` | `MERGE_ISA_STATE_B_L` (`0x108`) | yes |
| `0x004` | `TILE_M_ADDR` | `reg2hw.merge_src_m_tile.q` | 32 (low `TCDMAddrWidth` consumed) | SMU `src_m_tile` | `MERGE_SRC_M_TILE` (`0x80`) | yes |
| `0x005` | `TILE_L_ADDR` | `reg2hw.merge_src_l_tile.q` | 32 (low `TCDMAddrWidth` consumed) | SMU `src_l_tile` | `MERGE_SRC_L_TILE` (`0x88`) | yes |
| `0x006` | `WEIGHT_OLD_ADDR` | `reg2hw.merge_dst_weight_old.q` | 32 (low `TCDMAddrWidth` consumed) | SMU old-weight store | `MERGE_DST_WEIGHT_OLD` (`0xd0`) | yes |
| `0x007` | `WEIGHT_TILE_ADDR` | `reg2hw.merge_dst_weight_tile.q` | 32 (low `TCDMAddrWidth` consumed) | SMU tile-weight store | `MERGE_DST_WEIGHT_TILE` (`0xd8`) | yes |
| `0x008` | `N` | `reg2hw.merge_n.q` | 32 | SMU scalar row bound | `MERGE_N` (`0xb0`) | yes |
| `0x009` | `CTRL` | adapter control (no value register) | bit 0 | `INIT`: validate mask, set `cfg_valid`, reset selector on success | existing `MERGE_CTRL.CLEAR_DONE` setup terminator | no |

`REQUIRED_MASK = 9'h1ff`, covering cfg IDs `0x000..0x008`.

For `CTRL`, bit 0 is `INIT`; bits 31:1 are reserved and ignored.  An INIT
with an incomplete required mask leaves `cfg_valid=0`.  A successful INIT
sets `cfg_valid=1` and `selector=0`.

## Reserved namespace

`0x00a..0xfff` is reserved.  A reserved OMCFG is accepted as a short command,
does not write any configuration register, and deterministically invalidates
the context.  Software must issue a valid INIT before a later OMERGE can run.

OMCFG v1 intentionally has no D, precision, tile-size, EXP/reciprocal mode,
O-vector address, selector, or stride entry.  OMERGE remains fixed to Mixed
Scalar mode; the adapter supplies validation-safe `D=1`, `stride=0`, and
aligned zero O-vector addresses to the unchanged engine.
