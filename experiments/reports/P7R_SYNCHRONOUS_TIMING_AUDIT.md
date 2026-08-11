# P7-R Synchronous Timing Methodology Audit

Status: **Outcome B** for both standalone designs.

The existing ABC `stime` paths are reproducibly reg→reg boundary paths after ownership recovery. They remain library-delay proxies; this audit does not report synchronous Fmax.

## Scope and reproducibility

- Analysis HEAD: `7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f`.
- Expected HEAD: `7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f`.
- Liberty: `/home/wxt/yosys-sta/pdk/nangate45/lib/Nangate45_typ.lib` (SHA256 `2efd0b32eb580e4e60e72fc0575bb3bc69aac907c91d908442e4ae6d7fe55895`).
- Yosys: `/home/wxt/yosys-sta/oss-cad-suite/bin/yosys` (`Yosys 0.66+4 (git sha1 8125af88d, clang++ 18.1.8 -fPIC -O3)`, SHA256 `7c3e3396b38c129dd7485be5a0a0f0da8e495a94c8fd486059e3bea043a588d6`).
- P7 front-end: `read_liberty; read_slang; hierarchy -check; proc; opt; memory_collect; opt_clean; flatten; setattr; fsm; opt; techmap; opt; dfflibmap`; P7 back-end then runs `abc -D <target> ... stime -p 5; clean; check -assert`.
- The exact front-end script is regenerated under `work-p7r/` and stops at `dfflibmap; write_json`; source bytes match the expected HEAD.

P7 RTL input SHA256 audit:

| Input | SHA256 | Byte-identical to expected HEAD |
| --- | --- | --- |
| `hw/ip/online_merge/src/online_merge_fp32_helpers.sv` | `5214724007affc041efe6b01950e44c60808e84898b62ca095bd1ea525e6e786` | `True` |
| `hw/ip/online_merge/src/online_merge_exp_approx.sv` | `8890918192d6659057967193f4f2d1197cdd16899217c919388a931464f5babe` | `True` |
| `hw/ip/online_merge/src/online_merge_recip_approx.sv` | `13590b295a4c567e0fa69179b2c11969ab46debd22f8e7b86107a77d58b2ff1f` | `True` |
| `hw/ip/online_merge/src/online_merge_update_engine.sv` | `defd7887bcf89e8462a2045aabdea87f9d7a251d444e429413b91aefb73bfc82` | `True` |
| `hw/ip/online_merge/synth/online_merge_resource_wrapper.sv` | `53f464891016a2cd6f4e137648e8ce52a09f2007ff4c2fb11311fd8cfd2e4754` | `True` |
| `hw/ip/online_merge/synth/online_merge_mapped_wrapper.sv` | `40594f9565ff8de4919571e5e2f0f046bc79b77d397cbf48a0cfd19c3bec0904` | `True` |

All six inputs are byte-identical to `7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f`: `True`.
- Full source and artifact hashes are in `/home/wxt/work-online-merge-supplement/experiments/parsed/p7r_timing/p7r_path_details.json`.

## Clock and timing-constraint audit

Both `flow.ys` files have top-level `clk_i` and asynchronous `rst_ni` connections, and every mapped DFF CK pin resolves to `clk_i`. Neither flow contains `create_clock`, `set_clock`, input/output delay, driver, load, or `-constr` constraints. The `-D` value is an ABC mapping target, not a clock period.

The ABC script uses `dretime; map -D ...; ...; stime -p 5`, but does not use `buffer`, `upsize`, or `dnsize`. ABC reports `lat = 0`, so clock-to-Q, setup/hold, and clock skew are not represented. No input driver or output load is supplied; the `-D` target is not a clock period constraint.

The selected Liberty declares DFFR/DFFS `next_state=D`, `clocked_on=CK`, D-pin setup/hold arcs, and Q/QN clock-to-Q arcs. Those declarations do not make this ABC `stime` run synchronous STA: the printed path consists of combinational gates between ABC `pi`/`po` boundaries, with no capture required time or clock network.

## Path-category results

| Design | Category | Longest delay (ps) | Status |
| --- | --- | ---: | --- |
| A1 | reg→reg | 12342.85 | verified |
| A1 | PI→reg | N/A | unavailable |
| A1 | reg→PO | N/A | unavailable |
| A1 | PI→PO | N/A | unavailable |
| A2 | reg→reg | 13202.60 | verified |
| A2 | PI→reg | N/A | unavailable |
| A2 | reg→PO | N/A | unavailable |
| A2 | PI→PO | N/A | unavailable |

The reg→reg row is the longest path emitted by `stime`; its ABC `pi`/`po` labels are not treated as physical primary ports. The other rows are N/A because this P7 flow emits no category-specific path enumeration.

## Design evidence

### A1 (online_merge_c1_scalar_mapped_top)

- Pre-ABC JSON: `/home/wxt/work-online-merge-supplement/work-p7r/preabc/C1_SCALAR/preabc.json` (SHA256 `c94fbc822a9681d46f1f481a51a9b102981a2216852d3da687de66f882832485`); front-end script: `/home/wxt/work-online-merge-supplement/work-p7r/preabc/C1_SCALAR/frontend.ys`.
- Sequential cells: 520 ({'DFFR_X1': 519, 'DFFS_X1': 1}); recognized clock: `clk_i`; all CK matches: `True`.
- All P7 targets: 1000 ps: unmet, 1500 ps: unmet, 3000 ps: unmet, 5000 ps: unmet; each log and CSV row is unmet (`all_targets_unmet=True`).
- Path: `pi581 ($auto$dfflibmap.cc:539:dfflibmap$334459)` → `po353 ($auto$rtlil.cc:3501:MuxGate$333741)`; delay `12342.85 ps`; category `reg→reg`.
- Launch ownership: `['i_variant.gen_engine.i_engine.m_tile_q[22]']` in `online_merge_c1_scalar_mapped_top / i_variant.gen_engine.i_engine` via `DFFR_X1 QN`; capture ownership: `['i_variant.gen_engine.i_engine.i_recip_approx.frac[12]', 'i_variant.gen_engine.i_engine.i_recip_approx.x_i[12]', 'i_variant.gen_engine.i_engine.l_new_q[12]', 'i_variant.gen_engine.i_engine.recip_input_bits[12]', 'i_variant.gen_engine.i_engine.recip_input_q[12]']` in `online_merge_c1_scalar_mapped_top / i_variant.gen_engine.i_engine` via `DFFR_X1 D`; both CK pins resolve to `clk_i` bits `[2]`/`[2]`; source `hw/ip/online_merge/src/online_merge_update_engine.sv:312.3` → `hw/ip/online_merge/src/online_merge_update_engine.sv:312.3`.
- Maximum path Cout: `173.9 ff` versus Cmax `25.3 ff` at `AOI21_X1` (path 53); gate Cout>Cmax rows: `12` (ABC boundary row adds `1`).
- Timing semantics: target_met `False` (failure `1000.0 ps`); FF arcs `not evaluated by stime; DFFs are sequential boundaries`; clk→Q `excluded; ABC path starts at pi/registered boundary`; setup `excluded; no required-time check against capture DFF setup arc`; skew `excluded; no clock tree or skew constraint`; I/O `excluded; no input/output delay, driver, or load`; buffer/upsize/dnsize =`False/False/False`.
- Ordered ABC chain (the complete machine-readable chain is also in `p7r_path_details.json`):

```text
0:pi -> 1:AOI22_X1 -> 2:NAND3_X1 -> 3:OR3_X1 -> 4:NOR3_X1 -> 5:AOI21_X1 -> 6:OAI21_X1 -> 7:NOR2_X1 -> 8:OAI21_X1 -> 9:OAI21_X1 -> 10:NAND3_X1 -> 11:NAND4_X1 -> 12:AOI21_X1 -> 13:NAND3_X1 -> 14:NAND3_X1 -> 15:NAND3_X1 -> 16:NAND3_X1 -> 17:OAI211_X1 -> 18:NAND2_X1 -> 19:AOI21_X1 -> 20:NAND3_X1 -> 21:NAND2_X1 -> 22:NAND2_X1 -> 23:NAND3_X1 -> 24:OAI21_X1 -> 25:NAND3_X1 -> 26:NAND3_X1 -> 27:NAND3_X1 -> 28:NAND3_X1 -> 29:NAND3_X1 -> 30:NAND3_X1 -> 31:NAND3_X1 -> 32:NAND2_X1 -> 33:NAND3_X1 -> 34:AOI22_X1 -> 35:NAND2_X1 -> 36:AND2_X1 -> 37:AOI21_X1 -> 38:AOI21_X1 -> 39:XNOR2_X1 -> 40:INV_X1 -> 41:NAND3_X1 -> 42:NOR2_X1 -> 43:NOR2_X1 -> 44:NAND3_X1 -> 45:XNOR2_X1 -> 46:NOR2_X1 -> 47:NOR2_X1 -> 48:NAND4_X1 -> 49:NAND2_X1 -> 50:XNOR2_X1 -> 51:NOR2_X1 -> 52:NAND3_X1 -> 53:AOI21_X1 -> 54:NAND4_X1 -> 55:AOI22_X1 -> 56:NAND3_X1 -> 57:AOI21_X1 -> 58:OAI21_X1 -> 59:NAND3_X1 -> 60:NAND3_X1 -> 61:AND3_X1 -> 62:AOI21_X1 -> 63:OAI21_X1 -> 64:AOI21_X1 -> 65:OAI21_X1 -> 66:AOI211_X1 -> 67:NOR2_X1 -> 68:OAI211_X1 -> 69:NAND4_X1 -> 70:NAND3_X1 -> 71:NAND3_X1 -> 72:NAND3_X1 -> 73:NAND3_X1 -> 74:INV_X1 -> 75:NAND3_X1 -> 76:INV_X1 -> 77:NAND3_X1 -> 78:NAND3_X1 -> 79:NAND3_X1 -> 80:AOI22_X1 -> 81:AOI21_X1 -> 82:OAI21_X1 -> 83:AOI21_X1 -> 84:OAI21_X1 -> 85:NAND2_X1 -> 86:NAND3_X1 -> 87:NAND2_X1 -> 88:NAND4_X1 -> 89:NAND4_X1 -> 90:NAND2_X1 -> 91:AOI21_X1 -> 92:OAI21_X1 -> 93:NAND3_X1 -> 94:OAI22_X1 -> 95:AOI21_X1 -> 96:NOR3_X1 -> 97:OAI21_X1 -> 98:AND3_X1 -> 99:OAI21_X1 -> 100:NAND4_X1 -> 101:AND3_X1 -> 102:OAI22_X1 -> 103:AND3_X1 -> 104:OAI21_X1 -> 105:AND3_X1 -> 106:OAI21_X1 -> 107:AND3_X1 -> 108:AND3_X1 -> 109:OAI21_X1 -> 110:NAND3_X1 -> 111:NAND2_X1 -> 112:OR2_X1 -> 113:NAND2_X1 -> 114:XOR2_X1 -> 115:NAND3_X1 -> 116:NAND2_X1 -> 117:NAND3_X1 -> 118:NAND2_X1 -> 119:NAND4_X1 -> 120:AOI21_X1 -> 121:AOI21_X1 -> 122:OAI21_X1 -> 123:AOI21_X1 -> 124:OAI21_X1 -> 125:XNOR2_X1 -> 126:OAI21_X1 -> 127:NAND4_X1 -> 128:OAI21_X1 -> 129:AOI21_X1 -> 130:OAI211_X1 -> 131:NAND4_X1 -> 132:AOI22_X1 -> 133:AOI21_X1 -> 134:OAI21_X1 -> 135:AOI21_X1 -> 136:OAI21_X1 -> 137:NAND4_X1 -> 138:AOI21_X1 -> 139:OAI211_X1 -> 140:AOI21_X1 -> 141:OAI21_X1 -> 142:NOR2_X1 -> 143:AND3_X1 -> 144:NAND3_X1 -> 145:NOR2_X1 -> 146:INV_X1 -> 147:AOI21_X1 -> 148:NAND2_X1 -> 149:NAND2_X1 -> 150:NAND2_X1 -> 151:INV_X1 -> 152:NAND3_X1 -> 153:OAI33_X1 -> 154:AOI21_X1 -> 155:OAI22_X1 -> po353
```


### A2 (online_merge_c2_full_mapped_top)

- Pre-ABC JSON: `/home/wxt/work-online-merge-supplement/work-p7r/preabc/C2_FULL/preabc.json` (SHA256 `4723498076920d534ee0799e9bea2b6b6292604b9ca5762cb202e010bf1efcef`); front-end script: `/home/wxt/work-online-merge-supplement/work-p7r/preabc/C2_FULL/frontend.ys`.
- Sequential cells: 619 ({'DFFR_X1': 618, 'DFFS_X1': 1}); recognized clock: `clk_i`; all CK matches: `True`.
- All P7 targets: 1000 ps: unmet, 1500 ps: unmet, 3000 ps: unmet, 5000 ps: unmet; each log and CSV row is unmet (`all_targets_unmet=True`).
- Path: `pi611 (\i_variant.gen_engine.i_engine.m_old_q [31])` → `po491 ($auto$rtlil.cc:3501:MuxGate$476330)`; delay `13202.60 ps`; category `reg→reg`.
- Launch ownership: `['i_variant.gen_engine.i_engine.m_old_q[31]']` in `online_merge_c2_full_mapped_top / i_variant.gen_engine.i_engine` via `DFFR_X1 Q`; capture ownership: `['i_variant.gen_engine.i_engine.i_recip_approx.frac[1]', 'i_variant.gen_engine.i_engine.i_recip_approx.x_i[1]', 'i_variant.gen_engine.i_engine.l_new_q[1]', 'i_variant.gen_engine.i_engine.recip_input_bits[1]', 'i_variant.gen_engine.i_engine.recip_input_q[1]']` in `online_merge_c2_full_mapped_top / i_variant.gen_engine.i_engine` via `DFFR_X1 D`; both CK pins resolve to `clk_i` bits `[2]`/`[2]`; source `hw/ip/online_merge/src/online_merge_update_engine.sv:312.3` → `hw/ip/online_merge/src/online_merge_update_engine.sv:312.3`.
- Maximum path Cout: `232.4 ff` versus Cmax `25.3 ff` at `AOI21_X1` (path 56); gate Cout>Cmax rows: `10` (ABC boundary row adds `1`).
- Timing semantics: target_met `False` (failure `1000.0 ps`); FF arcs `not evaluated by stime; DFFs are sequential boundaries`; clk→Q `excluded; ABC path starts at pi/registered boundary`; setup `excluded; no required-time check against capture DFF setup arc`; skew `excluded; no clock tree or skew constraint`; I/O `excluded; no input/output delay, driver, or load`; buffer/upsize/dnsize =`False/False/False`.
- Ordered ABC chain (the complete machine-readable chain is also in `p7r_path_details.json`):

```text
0:pi -> 1:INV_X1 -> 2:NAND2_X1 -> 3:AOI22_X1 -> 4:AND2_X1 -> 5:AND4_X1 -> 6:OAI21_X1 -> 7:AOI21_X1 -> 8:OAI211_X1 -> 9:OAI21_X1 -> 10:AND4_X1 -> 11:NAND3_X1 -> 12:OAI21_X1 -> 13:NAND2_X1 -> 14:OAI211_X1 -> 15:NAND2_X1 -> 16:OAI21_X1 -> 17:AOI21_X1 -> 18:OAI22_X1 -> 19:OAI211_X1 -> 20:AND3_X1 -> 21:OAI21_X1 -> 22:NAND3_X1 -> 23:OAI21_X1 -> 24:NAND4_X1 -> 25:NAND3_X1 -> 26:NAND2_X1 -> 27:NAND2_X1 -> 28:NAND3_X1 -> 29:NOR3_X1 -> 30:NAND4_X1 -> 31:NOR2_X1 -> 32:NAND4_X1 -> 33:NOR3_X1 -> 34:NAND3_X1 -> 35:NOR3_X1 -> 36:NAND4_X1 -> 37:OR2_X1 -> 38:XNOR2_X1 -> 39:AOI21_X1 -> 40:OAI21_X1 -> 41:AOI21_X1 -> 42:OAI21_X1 -> 43:AOI21_X1 -> 44:OAI21_X1 -> 45:NAND2_X1 -> 46:NAND2_X1 -> 47:AOI21_X1 -> 48:NOR2_X1 -> 49:OAI211_X1 -> 50:XOR2_X1 -> 51:XOR2_X1 -> 52:NAND2_X1 -> 53:INV_X1 -> 54:NAND2_X1 -> 55:NAND2_X1 -> 56:AOI21_X1 -> 57:NAND3_X1 -> 59:NAND2_X1 -> 60:OAI211_X1 -> 61:OAI211_X1 -> 62:NAND3_X1 -> 63:NAND3_X1 -> 64:NOR3_X1 -> 65:OAI21_X1 -> 66:NAND2_X1 -> 67:AOI21_X1 -> 68:OAI21_X1 -> 69:NAND2_X1 -> 70:NOR2_X1 -> 71:NAND3_X1 -> 72:NAND3_X1 -> 73:OAI211_X1 -> 74:NAND4_X1 -> 75:NAND3_X1 -> 76:NAND3_X1 -> 77:NAND3_X1 -> 78:NAND2_X1 -> 79:NAND2_X1 -> 80:NAND2_X1 -> 81:NOR2_X1 -> 82:OAI21_X1 -> 83:NAND3_X1 -> 84:AOI22_X1 -> 85:AOI21_X1 -> 86:OAI21_X1 -> 87:NAND4_X1 -> 88:AOI21_X1 -> 89:OAI22_X1 -> 90:AND3_X1 -> 91:OAI21_X1 -> 92:NAND3_X1 -> 93:NAND2_X1 -> 94:OAI211_X1 -> 95:NAND3_X1 -> 96:NAND2_X1 -> 97:NOR2_X1 -> 98:NAND3_X1 -> 99:AND3_X1 -> 100:NOR3_X1 -> 101:OAI22_X1 -> 102:AND3_X1 -> 103:OAI22_X1 -> 104:NAND4_X1 -> 105:AND3_X1 -> 106:NOR3_X1 -> 107:OAI21_X1 -> 108:AND3_X1 -> 109:OAI21_X1 -> 110:AND3_X1 -> 111:OAI21_X1 -> 112:AOI21_X1 -> 113:OAI21_X1 -> 114:AND3_X1 -> 115:OAI21_X1 -> 116:INV_X1 -> 117:OR3_X1 -> 118:AND2_X1 -> 119:NAND3_X1 -> 120:INV_X1 -> 121:NOR2_X1 -> 122:AOI21_X1 -> 123:OAI21_X1 -> 124:AOI21_X1 -> 125:AOI21_X1 -> 126:AOI21_X1 -> 127:OAI21_X1 -> 128:NAND3_X1 -> 129:OAI211_X1 -> 130:NAND3_X1 -> 131:AOI211_X1 -> 132:OAI211_X1 -> 133:NAND2_X1 -> 134:NAND3_X1 -> 135:AOI21_X1 -> 136:OAI211_X1 -> 137:AOI21_X1 -> 138:AOI21_X1 -> 139:OAI21_X1 -> 140:NAND4_X1 -> 141:NOR2_X1 -> 142:OAI21_X1 -> 143:AOI21_X1 -> 144:OAI21_X1 -> 145:AOI21_X1 -> 146:OAI211_X1 -> 147:NAND2_X1 -> 148:NAND4_X1 -> 149:AOI21_X1 -> 150:AOI21_X1 -> 151:NAND3_X1 -> 152:OAI21_X1 -> 153:MUX2_X1 -> 154:OAI21_X1 -> 155:AOI21_X1 -> 156:AOI21_X1 -> 157:OAI22_X1 -> po491
```

## Classification of the old P7 numbers

The old `pi`/`po` labels are ABC's sequential boundary abstraction. A1's start net resolves to the `DFFR_X1` QN associated with `m_tile_q[22]` in the scalar mapped top, and its endpoint net is the D input of the `DFFR_X1` whose Q is `l_new_q[12]`. A2 resolves analogously from `m_old_q[31]` Q to the D input of the register whose Q is `l_new_q[1]`. Thus both old paths are reg→reg combinational boundary delays, not PI→PO paths.

The old inverses, 81.0186 MHz (A1) and 75.7427 MHz (A2), are withdrawn as synchronous Fmax. They must not be described as cluster Fmax, signoff frequency, or achievable frequency. The 12.34285 ns and 13.20260 ns values may only be called pre-layout Nangate45/ABC reg→reg combinational delay proxies under this unconstrained flow.

## Final outcome

**Outcome B.** The recovered longest paths are real reg→reg paths and remain near 12–13 ns, but the flow lacks the timing constraints and sequential timing terms required for a defensible synchronous Fmax. All four category rows, clock assumptions, and limitations are encoded in the JSON/CSV outputs.
