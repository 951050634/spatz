# vfcmacc.vv Mnemonic and Toolchain Status

## Summary

`vfcmacc.vv` currently has a tracked opcode source patch and generated Snitch
decode pattern, but the installed LLVM toolchain does not accept the mnemonic
and objdump does not disassemble the encoding back to `vfcmacc.vv`.

Bring-up remains on the fixed `.insn` wrapper:

```asm
.insn r 0x57, 0x1, 0x75, vd, vs1, vs2
```

This emits the expected 32-bit instruction encoding, but objdump prints the
instruction as `<unknown>`.

## Verified State

- `sw/toolchain/riscv-opcodes/opcodes-rvv` contains:

  ```text
  vfcmacc.vv     31..26=0x3a vm vs2 vs1 14..12=0x1 vd 6..0=0x57
  ```

- The parent repository tracks the opcode change through:

  ```text
  sw/toolchain-patches/riscv-opcodes/vfcmacc-vv.patch
  ```

- The installed LLVM is:

  ```text
  clang version 14.0.6 (pulp-platform/llvm-project b494f2d8...)
  ```

- The checked-out source tree under `sw/toolchain/` only contains
  `riscv-opcodes`; `llvm-project` and `riscv-gnu-toolchain` source trees are not
  expanded in this worktree.

## Assembler Results

Mnemonic assembly is rejected:

```text
error: unrecognized instruction mnemonic, did you mean: vfmacc.vv, vfnmacc.vv, vfwmacc.vv, vmacc.vv?
  vfcmacc.vv v16, v0, v8
```

Fixed encoding assembly succeeds:

```asm
.insn r 0x57, 0x1, 0x75, v16, v0, v8
```

Objdump output for that object is:

```text
0: 57 18 80 ea   <unknown>
```

## Decision

Node 7 is blocked for formal mnemonic support in this worktree. The v1 RTL and
benchmark bring-up must continue to use `.insn` until the pinned LLVM/binutils
source trees are expanded and patched, or until a prebuilt toolchain with
`vfcmacc.vv` mnemonic support is installed.

LLVM automatic SelectionDAG lowering remains out of v1 scope.

## Follow-up Path

1. Expand `sw/toolchain/llvm-project` and, if GNU objdump support is required,
   `sw/toolchain/riscv-gnu-toolchain`.
2. Add the `vfcmacc.vv` encoding to the RISC-V vector instruction tables used
   by the assembler/disassembler.
3. Rebuild and install the pinned toolchain.
4. Replace `.insn` wrappers in ISA tests and benchmarks with `vfcmacc.vv`.
5. Verify assembler and objdump both show `vfcmacc.vv`.
