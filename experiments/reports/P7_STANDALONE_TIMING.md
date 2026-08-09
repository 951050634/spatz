# P7 — Standalone SMU Timing and Estimated Fmax

来源：`experiments/scripts/run_p7_timing_synthesis.py`（`--collect-only` 从
`work-p7/p7runs/` 现有 run 重建 CSV）。flow 与 P0-6 完全相同（Nangate45 typical /
Yosys / ABC、同一 Liberty、同一 hierarchy policy），唯一差别是 P7 用 ABC 的
显式 timing-driven script（`strash; if -K 6; dretime; map -D <target>; &get -n;
&st; &dch; &nf; &put`）并以 ABC 的 post-map `stime` 提取 critical delay。

**口径（重要）**：`stime` 是 pre-layout、无 clock tree、无 routing、无 output
load 的 ABC 库延迟估计，不是 signoff STA。P7 是另一种 timing-driven standalone
mapping；其 cell count/area 不得替代 P0-6 formal area。

## Standalone timing evidence

| Design | Mapped cells (P7 timing flow) | Mapped area (P7 timing flow, Liberty units) | Critical delay (pre-layout ABC) | Estimated standalone Fmax |
| --- | ---: | ---: | ---: | ---: |
| A1 — Scalar SMU + existing RVV | 59,910 | 66,264.058 | 12,342.85 ps (12.34 ns) | **81.0186 MHz** |
| A2 — Full-Offload Ablation | 91,361 | 101,978.548 | 13,202.60 ps (13.20 ns) | **75.7427 MHz** |

The critical paths are:

- A1: `pi → AOI22_X1 → NAND3_X1 → OR3_X1 → NOR3_X1`
- A2: `pi → INV_X1 → NAND2_X1 → AOI22_X1 → AND2_X1`

## Dedicated arithmetic blocks

The scope tops are pure combinational logic (`sequential_area = 0`), so
`stime` is input-to-output combinational delay, not an Fmax:

| Scope | Mapped cells (P7 timing flow) | Mapped area (P7 timing flow, Liberty units) | Combinational delay |
| --- | ---: | ---: | ---: |
| EXP LUT | 4,428 | 4,526.788 | 4,070.47 ps |
| Reciprocal LUT | 4,502 | 4,594.618 | 2,493.75 ps |
| Vector merge datapath | 44,114 | 46,019.596 | 6,930.62 ps |

## Area boundary

P7 timing-driven mapped area (66.3k / 102.0k Liberty units) is lower than the
P0-6 `abc -fast` formal standalone area (77,103.292 / 114,713.298 Liberty
units) because the ABC scripts differ.  Formal paper area uses P0-6; P7
contributes only critical delay and estimated standalone Fmax.

## Conclusion

A1's estimated standalone Fmax is 81.0186 MHz and A2's is 75.7427 MHz under
the pre-layout ABC estimate.  The A2 critical delay is about 0.86 ns higher
(+7.0%).  Both critical paths are in scalar control/datapath logic rather
than the EXP/Reciprocal LUTs.

## Data files

- CSV: `experiments/parsed/p7_timing/p7_timing.csv`
- 原始 run：`work-p7/p7runs/{C1_SCALAR,C2_FULL,SCOPE_*}_trial1/<target>ps/`
