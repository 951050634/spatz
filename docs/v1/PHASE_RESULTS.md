# CFMA v1 阶段结果总览

本文件是 v1 归档版阶段结果摘要。详细 Git 操作可参考 [GIT_NOTES.md](GIT_NOTES.md)，最终实现边界可参考 [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)。

## 1. 阶段结果表

| 阶段 | 目标 | v1 结果 |
| --- | --- | --- |
| Node 0 | 建立工作树、文档和阶段记录框架 | 完成 |
| Node 1 | 确定 paired register layout 与 encoding 决策 | 完成 |
| Node 2 | 生成/接入 `VFCMACC_VV` opcode pattern | 完成 |
| Node 3 | 接入 Snitch/Spatz decode、配置开关和非法路径 | 完成 |
| Node 4 | 实现 e32 unmasked 多拍执行 | 完成 |
| Node 5a | 支持 e64/e16 format | 完成 |
| Node 5b | 支持 mask/tail，冻结 `vstart` 策略 | 完成 |
| Node 5c | 覆盖特殊数值、rounding 与 fflags | 完成 |
| Node 5d | 覆盖 serialization fence 与 imag group hazard | 完成 |
| Node 6 | 软件/工具链 mnemonic 整理 | 部分完成：inline asm 可用，完整 mnemonic/objdump 支持未闭环 |
| Node 7 | v2 datapath 评审门 | 结论为 v1 不启用 dedicated datapath，v2 另开 |
| Step 12 | dedicated split writeback | 有草稿但默认禁用，不能标记完成 |
| Step 13-18 | v1 收尾、验证和文档交接 | 按 v1 范围完成；性能闭环未完成 |

## 2. v1 功能闭环

v1 功能闭环包括：

- `vfcmacc.vv` 指令识别；
- paired register layout 合法性检查；
- e16/e32/e64 行为；
- mask/tail 行为；
- `vstart != 0` illegal 行为；
- fflags 累积；
- 保守 serialization/fence；
- 邻近 FMA 指令回归不被破坏。

## 3. 验证证据摘要

2026-07-06 记录：

```text
git diff --check: PASS
bin/spatz_cluster.vlt build: PASS
sw.vlt build: PASS
riscvTests-rtl-vfmacc: PASS
riscvTests-rtl-vfcmacc: PASS
riscvTests-rtl-vfnmsac: PASS
```

benchmark probe：

```text
dp-caxpy_M256: PASS
dp-caxpy_vfcmacc_M256: PASS
dp-cdotp_old_M128: 观察窗口超过 17 分钟未完成
dp-cdotp_vfcmacc_M128: 该轮未执行到
```

## 4. 不关闭的内容

以下内容不在 v1 中关闭：

- dedicated hardware correctness；
- dedicated split writeback correctness；
- full benchmark correctness；
- cycle speedup；
- area/power/timing；
- 完整 LLVM mnemonic/objdump 工具链支持。

## 5. v2 入口

v2 规划已迁移到：

```text
docs/v2/README.md
```

v2 应重新建立 dedicated datapath 的 reference/testbench、request/response contract、VRF read/write sequencing 和 benchmark closure。
