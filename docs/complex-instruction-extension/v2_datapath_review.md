# vfcmacc.vv v2 数据通路评审

## 决策

暂不启动专用 complex-FMA datapath。

v1 ISA 行为已经通过 RTL ISA regressions 覆盖，但当前 v1 工程闭环还不足以支撑
v2 datapath 决策，原因是 benchmark 与工具链证据仍不完整：

- Node 6 尚未产出 `dp-cdotp` old/new `M <= 1024` correctness 或 cycles 数据。
- Node 7 尚未把 `.insn` 替换为正式 mnemonic，因为已安装 LLVM 工具链不支持
  `vfcmacc.vv`。
- v1 目前依赖 conservative serialization fence 来处理隐式 imag register
  hazards；在决定新增 datapath 或更精细 scoreboard 之前，必须先取得 cycle
  数据。

## v1 已有证据

- 编码和寄存器布局已冻结：
  `32'b111010???????????001?????1010111`。
- Snitch 和 Spatz decode 已识别 `VFCMACC_VV` / `VFCMADD`。
- VFU 将 `vfcmacc.vv` 按四阶段序列执行：
  `Cfma_RR`、`Cfma_II`、`Cfma_RI`、`Cfma_IR`。
- ISA regressions 覆盖 e32/e64/e16、mask、tail、vstart illegal、fflags、
  NaN/Inf、signed zero、rounding mode 和 serialization fence hazards。
- v1 使用固定 `.insn` bring-up，不需要 binary patching。

## v1 缺失证据

- `dp-cdotp` old/new runtime correctness。
- `dp-cdotp` old/new 在 M128 和 M1024 下的 cycle counts。
- runtime frontend/offload stall counters。
- instruction-count reduction 是否能转化为预期 benchmark frontend/offload
  pressure reduction 的直接证据。
- assembler 与 objdump mnemonic support。

## v2 待回答问题

### Bit Identity

如果 v2 引入 fused complex-FMA datapath，不能静默复用 v1 bitwise reference。
fused datapath 可能改变 rounding、NaN payload、signed-zero 和 `fflags` 行为。

v2 RTL 启动前，项目必须先选择一个数值策略：

- 通过内部顺序执行相同 operations，保留与 v1 bit-identical 的行为；或
- 定义新的 fused numerical contract，明确 ULP、NaN 和 fflags 规则。

### Datapath Location

目前尚未决定是在 fpnew 内扩展，还是新增本地 Spatz VFU block。

当前倾向是在 benchmark 证据证明 v1 瓶颈不只是 sequencing/fence overhead
之前，不新增 datapath。

### Formats

任何 v2 datapath 都必须继续覆盖 e16/e32/e64；如果要拆分 format 支持，必须
作为独立 node 记录。放弃 e16 或 e64 需要新增 ISA 文档和测试。

### Extensions

`vfcjmacc.vv` 仍是第一个命名 follow-up extension，但不应与初始 v2 datapath
决策混在一起。它需要独立 encoding、reference model 和 tests。

## 重新打开 v2 的准入条件

1. Node 6 benchmark blocker 已解决，并记录 old/new M128/M1024 数据；可行性
   验证不得依赖 M4096 这类大数据。
2. Node 7 mnemonic support 已实现，或以稳定 user-facing `.insn` policy 明确
   延后。
3. v1 性能数据证明以下至少一种情况：
   - frontend/offload pressure 是主要瓶颈，且 v1 instruction count reduction
     仍不足；或
   - VFU sequencing/fence overhead 占主导，datapath/scoreboard 变更有明确的
     预期收益。
4. RTL 变更前已经写好 v2 reference model 与 numerical policy。

## 当前结论

本分支停止在 v1 multi-phase execution。不要新增 fpnew operations、VRF ports
或专用 complex-FMA datapath。
