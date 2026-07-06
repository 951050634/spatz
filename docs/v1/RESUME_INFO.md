# 会话恢复信息

**最后更新**: 2026-07-06
**工作树**: `/home/wxt/spatz-cfma`
**分支**: `feature/cfma-instruction-extension`
**最新提交**: 本轮稳定化提交；准确 hash 以 `git log --oneline -1` 为准。

---

## 快速状态

- 当前工程目标：在 Spatz 上完成 `vfcmacc.vv` / CFMA 指令扩展的 v1 RTL、软件和验证闭环。
- 当前 v1 功能路径：`vfcmacc` 使用已验证的现有四阶段 FPU CFMA 路径。
- 专用 CFMA 写回路径：仍通过 `CfmaDedicatedWritebackEn = 1'b0` 默认禁用；不得作为
  dedicated hardware correctness 证据。
- Step 13-18 收尾：已补齐 v1 架构决策、build/ISA RTL regression 证据、性能证据
  文档和实施总结。
- 当前验证：`git diff --check`、`bin/spatz_cluster.vlt`、`sw.vlt`、
  `riscvTests-rtl-(vfmacc|vfcmacc|vfnmsac)` 均在 2026-07-06 通过。
- benchmark 状态：`dp-caxpy_M256` 和 `dp-caxpy_vfcmacc_M256` probes 通过；
  `dp-cdotp_old_M128` 在观察到的 17 分钟窗口内未完成，因此不声明完整 benchmark
  correctness 或 speedup。

---

## 恢复命令

```bash
cd /home/wxt/spatz-cfma
git status --short --branch
git log --oneline -5
git diff -- hw/ip/spatz/src/spatz_vfu.sv
```

继续实施前优先阅读：

```bash
sed -n '1,160p' docs/v1/README.md
sed -n '1,180p' docs/v1/PHASE_RESULTS.md
sed -n '780,880p' docs/v1/complex_fma_hardware_design.md
```

---

## 关键文件

- `hw/ip/spatz/src/fpnew_complex_fma.sv`：CFMA 硬件单元。
- `hw/ip/spatz/src/spatz_vfu.sv`：VFU 集成点；当前未提交 Step 12 写回草稿位于此文件。
- `Bender.yml`：硬件编译配置，已包含 CFMA 模块。
- `docs/v1/complex_fma_hardware_design.md`：18 步硬件实施计划。
- `docs/v1/PHASE_RESULTS.md`：验收证据与风险记录。
- `docs/v1/GIT_NOTES.md`：提交与验证命令记录。

---

## 下一步建议

1. 推荐 Option A：保留 v1 四阶段 FPU path，清理或继续 guard unused dedicated
   prototype，避免后续误启用未验证路径。
2. 若继续追 Step 17，先调查 `dp-cdotp_old_M128` 在 RTL benchmark probe 中超过
   17 分钟未完成的问题；完成前不要声明完整 benchmark correctness 或 speedup。
3. 若选择 dedicated hardware 路线，必须先补 `fpnew_complex_fma` 独立 reference/testbench，
   再重新设计动态 FP format、packed e16/e32 lanes、complex arithmetic/status flags、
   mask/tail byte enable、response timing 和 VRF 写回仲裁。

---

## 长时间编译验证规则

允许进行长时间编译工作以验证指令集修改的合理性。涉及 RTL、opcode、decode、
benchmark 或 ISA 行为的修改时，可以运行完整 Verilator 构建、软件构建和目标 CTest；
编译耗时长不是跳过验证的理由。每次验证必须记录命令、开始/结束时间、退出码和关键
输出摘要。如果长时间编译失败或超时，只能记录为失败证据，不能把对应步骤标为完成。

---

## 当前不要误判的事项

- 不要把 Step 12 标记为完成；当前专用写回草稿虽然可编译，但默认禁用，且
  dedicated hardware result path 尚未满足功能语义。
- 重复且过期的旧状态报告已删除；当前状态以本文和 `PHASE_RESULTS.md` 为准。
- 不要声称 benchmark correctness 或 speedup 已完成；后续仍需 Step 16-17 验证。
