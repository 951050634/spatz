# Node 7: Toolchain Mnemonic 支持状态

## 已完成

### ✅ riscv-opcodes 更新
- **文件**: `sw/toolchain/riscv-opcodes/opcodes-rvv`
- **patch**: `sw/toolchain-patches/riscv-opcodes/vfcmacc-vv.patch` 已应用
- **定义**: `vfcmacc.vv 31..26=0x3a vm vs2 vs1 14..12=0x1 vd 6..0=0x57`
- **状态**: ✅ 完成

### ✅ riscv_instr.sv 生成
- **文件**: `hw/ip/snitch/src/riscv_instr.sv`
- **常量**: `VFCMACC_VV = 32'b111010???????????001?????1010111`
- **状态**: ✅ 完成

## 未完成

### ❌ binutils assembler 支持
- **现象**: assembler 不识别 `vfcmacc.vv` mnemonic
- **错误**: `error: unrecognized instruction mnemonic`
- **原因**: riscv-gnu-toolchain/binutils 未更新
- **影响**: 必须继续使用 `.insn` 临时方案

### ❌ objdump 支持
- **状态**: 未验证（assembler 失败阻塞）
- **预期**: 也需要 binutils 更新

## 补救路径

根据 PLAN.md Node 7 建议修改文件列表，需要更新：

```
sw/toolchain/riscv-gnu-toolchain/riscv-binutils/include/opcode/riscv-opc.h
sw/toolchain/riscv-gnu-toolchain/riscv-binutils/opcodes/riscv-opc.c
```

但这需要：
1. 展开 riscv-gnu-toolchain 源码（当前未展开）
2. 修改 binutils 源码
3. 重新编译整个 toolchain

**时间成本**: 预计数小时

## Node 7 验收状态

根据 PLAN.md 验收标准：

| 标准 | 状态 | 说明 |
|------|------|------|
| inline asm 可写 `vfcmacc.vv` | ❌ | assembler 不识别 |
| benchmark 不需要 binary patch | ✅ | 使用 `.insn` 可编译 |
| objdump 能显示 `vfcmacc.vv` | ❌ | 待验证 |
| 记录原因和补救路径 | ✅ | 本文档 |

**结论**: Node 7 部分完成。RTL 和 opcodes 定义就绪，toolchain 编译支持待完成。

## 当前workaround

继续使用 `.insn` 格式：

```c
#define VFCMACC_VV_VM1(vd, vs1, vs2) \
    asm volatile(".insn r 0x57, 0x1, 0x75, " vd ", " vs1 ", " vs2 ::: "memory")
```

所有功能正常，只是没有 mnemonic 语法糖。
