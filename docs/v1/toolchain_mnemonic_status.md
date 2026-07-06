# 工具链助记符支持状态

## 1. v1 结论

v1 不把完整 LLVM/GNU 助记符支持作为硬门槛。当前软件路径以 inline assembly 或编码宏方式使用 `vfcmacc.vv`，足以支撑 RTL/ISA regression。

## 2. 当前边界

已完成：

- 指令 encoding 和 RTL decode 路径可用；
- ISA 测试可以覆盖 `vfcmacc` 行为；
- benchmark/测试代码可以通过受控方式发出该指令。

未完整关闭：

- assembler 原生 `vfcmacc.vv` mnemonic；
- objdump 反汇编显示；
- LLVM 自动指令选择；
- register allocator 对 paired real/imag group 的完整理解。

## 3. v2 建议

在 dedicated datapath correctness 完成前，不建议把主要精力投入完整工具链支持。更合理的顺序是：

1. 保持 inline assembly/encoding macro 可用；
2. 完成 v2 datapath correctness；
3. 完成 benchmark closure；
4. 再补 mnemonic、objdump 和编译器选择支持。
