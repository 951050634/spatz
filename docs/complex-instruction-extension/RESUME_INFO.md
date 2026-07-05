# 会话恢复信息

**最后更新**: 2026-07-06
**工作树**: `/home/wxt/spatz-cfma`
**分支**: `feature/cfma-instruction-extension`
**最新提交**: `0de3f7f [cfma] Implement split VRF read logic for 6 complex FMA operands`

---

## 快速状态

- 当前工程目标：在 Spatz 上完成 `vfcmacc.vv` / CFMA 指令扩展的 RTL、软件和验证闭环。
- 当前进度口径：18 步硬件实施计划中，步骤 1-11 已完成，步骤 15 曾提前完成过一次
  全系统编译验证。
- 当前工作区：存在 1 个未提交 RTL 修改，文件为
  `hw/ip/spatz/src/spatz_vfu.sv`。
- 未提交修改内容：Step 12 的 CFMA split VRF write-back 草稿，新增两拍写回 FSM，
  将 `result.real` 写回 `vd`，将 `result.imag` 写回 `vd + LMUL`。
- 当前风险：Step 12 写回输出尚未接入现有 VRF 写仲裁/控制路径，也尚未针对本轮
  未提交修改运行编译验证。

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
sed -n '1,160p' docs/complex-instruction-extension/README.md
sed -n '1,180p' docs/complex-instruction-extension/PHASE_RESULTS.md
sed -n '780,880p' docs/complex-instruction-extension/complex_fma_hardware_design.md
```

---

## 关键文件

- `hw/ip/spatz/src/fpnew_complex_fma.sv`：CFMA 硬件单元。
- `hw/ip/spatz/src/spatz_vfu.sv`：VFU 集成点；当前未提交 Step 12 写回草稿位于此文件。
- `Bender.yml`：硬件编译配置，已包含 CFMA 模块。
- `docs/complex-instruction-extension/complex_fma_hardware_design.md`：18 步硬件实施计划。
- `docs/complex-instruction-extension/PHASE_RESULTS.md`：验收证据与风险记录。
- `docs/complex-instruction-extension/GIT_NOTES.md`：提交与验证命令记录。

---

## 下一步建议

1. 检查当前 `spatz_vfu.sv` 中 Step 12 写回 FSM 的时序：确认 `cfma_result_valid`、
   pending 标志和 `spatz_req` 生命周期不会在两拍写回期间失配。
2. 将 `cfma_wb_addr`、`cfma_wb_data`、`cfma_wb_we`、`cfma_wb_be` 接入现有 VRF
   写回仲裁，而不是只停留在局部信号。
3. 处理 CFMA 写回与普通 FPU/vector pipeline 写回的优先级和互斥关系。
4. 运行文档要求的验证命令，至少包括：

   ```bash
   git diff --check
   make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
   ```

5. 将验证结果写入 `PHASE_RESULTS.md` 和 `GIT_NOTES.md`。

---

## 长时间编译验证规则

允许进行长时间编译工作以验证指令集修改的合理性。涉及 RTL、opcode、decode、
benchmark 或 ISA 行为的修改时，可以运行完整 Verilator 构建、软件构建和目标 CTest；
编译耗时长不是跳过验证的理由。每次验证必须记录命令、开始/结束时间、退出码和关键
输出摘要。如果长时间编译失败或超时，只能记录为失败证据，不能把对应步骤标为完成。

---

## 当前不要误判的事项

- 不要把 Step 12 标记为完成；当前只有未提交写回草稿，尚未完成仲裁接入和编译验证。
- 重复且过期的旧状态报告已删除；当前状态以本文和 `PHASE_RESULTS.md` 为准。
- 不要声称 benchmark correctness 或 speedup 已完成；后续仍需 Step 16-17 验证。
