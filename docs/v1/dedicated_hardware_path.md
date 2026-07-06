# CFMA 专用硬件路线归档

本文件记录 v1 阶段对 dedicated complex-FMA datapath 的路线评估。它不是 v1 完成声明。

## 1. 当前 v1 现状

v1 `vfcmacc.vv` 使用四阶段 FPU 复用路径：

```text
1. RR: real_acc += xr * yr
2. II: real_acc -= xi * yi
3. RI: imag_acc += xi * yr
4. IR: imag_acc += xr * yi
```

优点：

- 风险低；
- 复用已有 FPU 和 VRF 机制；
- 已有 ISA regression 证据。

缺点：

- 内部仍是 4 个 FPU phase；
- 不能提供 dedicated datapath 级别吞吐；
- performance speedup 未证明。

## 2. 专用数据通路的预期收益

目标 dedicated datapath 应一次处理：

```text
real_out = c.real + a.real * b.real - a.imag * b.imag
imag_out = c.imag + a.real * b.imag + a.imag * b.real
```

预期收益是目标而非当前结果：

| 方案 | 预期收益 | 状态 |
| --- | --- | --- |
| 移除/优化 conservative fence | 约 1.5-2x | 未作为 v1 完成项 |
| dedicated complex-FMA datapath | 保守 2x+，理想 3-4x | v2 目标 |
| 完整优化含面积/功耗/调度 | 4x+ 可能性 | 长期研究方向 |

## 3. 关键挑战

- 需要 6 个源操作数：`a.real/a.imag/b.real/b.imag/c.real/c.imag`。
- 需要写回 2 个 destination group：`vd` 与 `vd+LMUL`。
- 需要处理 e16/e32/e64 格式。
- 需要处理 mask/tail byte enable。
- 需要精确定义 rounding 和 fflags。
- 需要与现有 FPU writeback 仲裁。
- 需要处理 backpressure、flush、exception 和 completion timing。

## 4. 推荐 v2 顺序

1. 独立 reference/testbench。
2. request/response timing 文档。
3. 六操作数读取。
4. dedicated compute 接入。
5. split writeback 验证。
6. ISA regression。
7. benchmark closure。

v2 的正式计划见 `docs/v2/README.md`。
