# vfcmacc.vv 助记符与工具链状态

## 概要

`vfcmacc.vv` 当前已经有受版本管理的 opcode source patch，也已经生成 Snitch
decode pattern；但本工作树安装的 LLVM 工具链仍不接受该 mnemonic，objdump 也
无法把对应编码反汇编回 `vfcmacc.vv`。

正式 mnemonic 支持完成前，bring-up 继续使用固定 `.insn` wrapper：

```asm
.insn r 0x57, 0x1, 0x75, vd, vs1, vs2
```

该写法会生成预期的 32-bit 指令编码，但 objdump 仍把该指令显示为
`<unknown>`。

## 已验证状态

- `sw/toolchain/riscv-opcodes/opcodes-rvv` 已包含：

  ```text
  vfcmacc.vv     31..26=0x3a vm vs2 vs1 14..12=0x1 vd 6..0=0x57
  ```

- 父仓库通过以下 patch 追踪 opcode 变更：

  ```text
  sw/toolchain-patches/riscv-opcodes/vfcmacc-vv.patch
  ```

- 当前安装的 LLVM 为：

  ```text
  clang version 14.0.6 (pulp-platform/llvm-project b494f2d8...)
  ```

- 当前工作树的 `sw/toolchain/` 下只展开了 `riscv-opcodes`；
  `llvm-project` 与 `riscv-gnu-toolchain` source tree 尚未展开。

## 汇编器结果

直接使用 mnemonic 会被拒绝：

```text
error: unrecognized instruction mnemonic, did you mean: vfmacc.vv, vfnmacc.vv, vfwmacc.vv, vmacc.vv?
  vfcmacc.vv v16, v0, v8
```

使用固定编码可以汇编成功：

```asm
.insn r 0x57, 0x1, 0x75, v16, v0, v8
```

该 object 的 objdump 输出为：

```text
0: 57 18 80 ea   <unknown>
```

## 决策

Node 7 在当前工作树内阻塞于正式 mnemonic 支持。v1 RTL 与 benchmark
bring-up 继续使用 `.insn`，直到 pinned LLVM/binutils source tree 展开并完成
patch，或安装了已经支持 `vfcmacc.vv` mnemonic 的预构建工具链。

LLVM 自动 SelectionDAG lowering 仍不纳入 v1 范围。

## 后续解锁路径

1. 展开 `sw/toolchain/llvm-project`；如果需要 GNU objdump 支持，也展开
   `sw/toolchain/riscv-gnu-toolchain`。
2. 将 `vfcmacc.vv` 编码加入 assembler/disassembler 使用的 RISC-V vector
   instruction tables。
3. 重新构建并安装 pinned toolchain。
4. 将 ISA tests 与 benchmarks 中的 `.insn` wrapper 替换为 `vfcmacc.vv`。
5. 验证 assembler 与 objdump 都能显示 `vfcmacc.vv`。
