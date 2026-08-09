# P4/P5 — Standalone SMU Area 与模块分解

来源：P0-6 正式 C1/C2 mapped synthesis（3 trial 完全一致，`abc -fast`，Nangate45
typical）作为总面积；模块分解采用规划 P5-4 允许的 **scope synthesis proxy**：
EXP / Reciprocal / Vector merge 各自作为独立 top，用与 P0-6 完全相同的
`nangate45_area.ys.in` flow（同一 Liberty、同一 ABC script）综合 3 次，均完全可复现。
Scalar control/datapath/interface 由 `C1 − EXP − RECIP` 推得；Full vector path 由
`C2 − C1` 推得。这些是结构性分解参考（non-additive），非精确 hierarchy 账目。

## Standalone 总面积（P0-6 正式值）

| Config | Mapped cells (P0-6 standalone) | Mapped area (P0-6 Liberty units) | Full/Scalar |
| --- | ---: | ---: | ---: |
| C1 — Scalar SMU | 73,505 | 77,103.292 | 1.000 |
| C2 — Full SMU | 107,372 | 114,713.298 | 1.488 |

## 模块面积分解（scope synthesis proxy）

| Module | Basis | Area | % of Scalar | Cells |
| --- | ---: | ---: | ---: | ---: |
| EXP (exp LUT) | standalone top | 5,978.882 | 7.8% | 6,156 |
| Reciprocal (recip LUT) | standalone top | 7,516.096 | 9.7% | 7,852 |
| Scalar control + datapath + interface | C1 − EXP − RECIP | 63,608.314 | 82.5% | – |
| Full vector path（增量） | C2 − C1 | 37,610.006 | +48.8% of Scalar | – |
| Vector merge datapath（standalone proxy） | standalone top | 46,726.890 | 60.6% of Scalar | 47,696 |

## 结论

- EXP 与 Reciprocal 都是 LUT 近似，只占 Scalar SMU 约 18%；Scalar 主体是
  command/control、scalar recurrence datapath、TCDM 接口寄存器与握手逻辑。
- Full SMU 的 vector update datapath 带来约 +37.6k area（+48.8% standalone
  overhead），与 P0-6 的 1.488× 总面积比一致。standalone vector proxy
  (46.7k) 大于增量 (37.6k)，说明 Full 内部 scalar/vector 有资源共享，增量是
  更合理的 overhead 估计。
- 论文口径：Full vector path ≈ +49% standalone mapped area。

## 数据文件
- CSV：`experiments/parsed/p4_p5/p4_p5_module_area.csv`
- 原始 manifest（含 yosys/liberty/flow hash）：`work-module-area/manifest.json`
