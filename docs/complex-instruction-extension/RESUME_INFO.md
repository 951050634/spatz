# 会话恢复信息

**最后更新**: 2026-07-06
**工作树**: `/home/wxt/spatz-cfma`
**分支**: `feature/cfma-instruction-extension`
**最新提交**: 本轮稳定化提交；准确 hash 以 `git log --oneline -1` 为准。

---

## 快速状态

- 当前工程目标：在 Spatz 上完成 `vfcmacc.vv` / CFMA 指令扩展的 RTL、软件和验证闭环。
- 当前进度口径：18 步硬件实施计划中，步骤 1-11 已完成；步骤 12 有 RTL 草稿，
  但不能标记完成。
- 当前工作区：存在未提交修改，包含 1 个 RTL 文件和 4 个文档文件：
  `hw/ip/spatz/src/spatz_vfu.sv`、`RESUME_INFO.md`、`PHASE_RESULTS.md`、
  `GIT_NOTES.md` 和 `complex_fma_hardware_design.md`。
- 未提交修改内容：Step 12 的 CFMA split VRF write-back 草稿，新增两拍写回 FSM，
  并把该路径接入 VRF 写回 mux；但该专用写回路径通过
  `CfmaDedicatedWritebackEn = 1'b0` 默认禁用。
- 当前功能路径：`vfcmacc` 仍使用已验证的现有四阶段 FPU CFMA 路径。专用 CFMA
  硬件结果不会覆盖该路径。
- 当前风险：专用 CFMA 硬件路径尚未具备可启用条件。已知问题包括固定
  `FP64` 实例化、只锁存 `operand*[ELEN-1:0]`、缺少 e16/e32 packed lane 语义，
  以及 `fpnew_complex_fma.sv` 中 imag 计算语义未完成。
- 当前验证：已针对默认禁用专用写回后的 RTL 运行 whitespace、Verilator build
  和 `vfcmacc/vfmacc/vfnmsac` RTL 回归；结果记录在 `PHASE_RESULTS.md` 和
  `GIT_NOTES.md`。

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

1. 不要继续把当前 Step 12 草稿推进为完成态；它只应作为 disabled prototype
   保留，避免破坏已通过的 ISA 行为。
2. 做 Step 13 控制架构决策：
   - v1 保守路线：明确保留现有四阶段 FPU 路径作为功能实现，删除或继续 guard
     未完成的专用写回路径。
   - 专用硬件路线：重新设计完整 dedicated CFMA path，包括动态 FP format、
     packed e16/e32 lanes、正确 complex arithmetic、status flags、mask/tail byte
     enable、response timing 和 VRF 写回仲裁。
3. 若选择专用硬件路线，先补 `fpnew_complex_fma` 的独立 reference/testbench，
   再重新打开 `CfmaDedicatedWritebackEn`，不能直接启用当前草稿。

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
