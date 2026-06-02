# Claude Code 使用指南

## 避免读取的文件和目录

以下文件/目录包含大量生成内容或与代码逻辑无关，请 Claude Code 避免直接读取：

### 工具链（最重要 - 体积巨大）
- `sw/toolchain/`
- `install/`

### Python 环境
- `.venv/`, `venv/`, `__pycache__/`, `*.pyc`, `*.pyo`

### 构建输出
- `build/`, `dist/`, `out/`, `target/`, `generated/`, `gen/`, `obj/`, `obj_dir/`

### 硬件仿真波形（可能很大）
- `*.vcd`, `*.fst`, `*.wlf`, `*.fsdb`, `*.vpd`

### 编译产物
- `*.o`, `*.a`, `*.so`, `*.dylib`, `*.dll`, `*.elf`, `*.bin`, `*.hex`, `*.map`

### 临时/缓存
- `.cache/`, `tmp/`, `*.tmp`, `*.log`

### Git 内部
- `.git/`

### IDE 和依赖
- `.vscode/`, `.idea/`, `node_modules/`

### CMake
- `CMakeFiles/`, `CMakeCache.txt`

### 基准测试输出
- `benchmark_results/`, `perf_logs/`

### 大型数据集
- `datasets/`, `checkpoints/`

### RTL 生成目录
- `hw/**/generated/`, `hw/**/build/`, `hw/**/sim/`

### Verilator
- `verilator/`

## 内存和上下文管理

- 不要将上述目录的内容保存到 memory/
- 遇到大文件时使用 limit/offset 参数分段读取
- 优先使用 grep 而非直接 Read 大文件
- 代码结构、已知目录布局等信息不应重复保存到 memory

## 引用

本文件内容来源于 `.codexignore`，转换为 Claude Code 适用的格式。
