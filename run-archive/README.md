# run-archive — work-online-merge 运行产物归档

本目录集中收纳 **Online Softmax Merge 实验各批次运行的结果数据**（原位于
`/home/wxt` 顶层的 `work-online-merge-*` 目录），于 2026-08-25 归档。

`records.csv / records.json`、各 `*_manifest.json`、`instruction_trace_audit.json`、
`simulator.log`、合成 `mapped-stat.* / mapped-netlist.v / yosys.log` 等**均完整保留**。
所有批次已确认无 `.dasm`、`*.elf`、`objdump` 及 build 中间产物残留。

## 目录映射（原名 → 归档名）

| 原路径 | 归档后 | 原大小 → 现大小 | 内容 |
|---|---|---|---|
| `work-online-merge-20260823T101418Z_4d92e822_p0-6-synthesis` | `<本目录>/同名` | 320K → 320K | P0-6 C0/C1/C2 SMU 标准单元合成 |
| `work-online-merge-phase2a-synth-20260823` | `<本目录>/同名` | 154M → 27M | 同上（裁掉 2 个 66MB `mapped-netlist.json` dump，`.v`+stat 保留） |
| `work-online-merge-phase2-matched-20260823` | `<本目录>/同名` | 861M → 828K | 匹配标量性能矩阵 18 条记录 |
| `work-online-merge-phase3-division-correct` | `<本目录>/同名` | 1.9M → 340K | phase3 除法版正确性 |
| `work-online-merge-phase3-div-performance` | `<本目录>/同名` | 1.5M → 236K | phase3 除法版性能（含 B1_SCALAR 基线 100691 cycles） |
| `work-online-merge-phase3-reciprocal-correct` | `<本目录>/同名` | 992K → 212K | phase3 倒数-LUT 版正确性/性能（2622/5024 cycles） |
| `work-online-merge-runs/work-online-merge-m1-matched-lut-20260810` | `<本目录>/同名` | 53M → 460K | m1 matched-LUT 套件 |
| `work-online-merge-runs/work-online-merge-m2-7225d41-scaling` | `<本目录>/同名` | 1.1G → 11M | m2 scaling 扫描（records 1.7M+.8M 为大头） |
| `work-online-merge-runs/work-online-merge-m2-complete-7225d41-models` | `<本目录>/同名` | 681M → 2.3M | m2 models 完整版 |
| `work-online-merge-runs/work-online-merge-m2-7225d41-models` | `<本目录>/同名` | 361M → 1.9M | m2 models 早期版（被 complete 取代，已确认无脚本引用） |
| `work-online-merge-runs/README.md` | `README-m2-m1-index.md` | — | 原批次索引（含 run_id/提交对照表） |

## 已删除（全部可重建，理由见下）

| 项 | 体积 |
|---|---|
| `phase3-div/recip-build`（Verilator CMake 中间产物，`.o/.gch/.a/lib`） | 约 1.0G |
| `phase3-*-performance-build / *-correct-build / phase2-matched-build`（5 个 CMake 目录） | 约 70M |
| `phase3-div-sim / recip-sim` 的 `spatz_cluster.vlt` 仿真器 | 36M |
| 各运行目录内 `trace_hart_*.dasm`（单文件 40–80M）×47 | 约 2.5G |
| 各运行目录内 `*.elf / objdump.txt / *.disasm / symbols.txt / sections.txt / build.log / compile_commands.json / link_command.txt` | 约 300M |
| `mapped-netlist.json`（66M×2 合成器 netlist dump，`.v` 等价物已保留） | 132M |

**可重建依据**：所有运行在 `run_manifest.json` 中 pin 了源码提交
（`4d92e822` / `7225d41a` / `05547a1b`）、工具链版本（clang 14.0.6、Verilator 5.034、
yosys 0.66+4）、配置与库 SHA-256（`*.hjson` / `policy*.json` / `Nangate45_typ.lib`）。
`simulator` 二进制可经 `*-build` + 对应 `-D` 宏重建；`trace_hart_*.dasm` 可在
精简 run 目录重建（records 已固化全部测得的 cycle/error 指标与各文件 hash）。

## 正式证据位置

论文正式 frozen 证据在 `../experiments/parsed/`（p0_4/p0_5/p0_6/optional_capabilities/
p7r_timing 等冻结 CSV）；本目录仅存运行原始产出。未触碰的活跃工作区：
`/home/wxt/m1-matched-lut.7wqexi`（repo/ + artifacts/，当时进行中）。