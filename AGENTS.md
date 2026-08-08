本阶段目标是量化和强化 Scalar SMU 加速器本身，而不是继续扩展实验基础设施。优先复用现有脚本、RTL 和结果格式。除非直接阻塞目标实验，否则不要进行大规模重构、兼容性封装、异常处理扩展、额外 runner gate 或防御性检查。每项任务应首先完成最短可工作的实现，然后直接生成论文需要的性能、面积、时序或结构数据。Proposed Design 固定为 Scalar SMU + RVV，Full SMU 仅用于消融比较，不继续作为主要架构开发方向。

# Repository Guidelines

## Project Structure & Module Organization

`hw/` holds the RTL and system integration code, with the main top-level cluster in `hw/system/spatz_cluster/`. `sw/` contains the software stack: `snRuntime/` for runtime support, `riscvTests/` for ISA-style tests, and `spatzBenchmarks/` for benchmark programs. Shared build helpers live in `util/`, while generated or local build outputs should stay under `sw/build/`, `hw/system/spatz_cluster/bin/`, or `work-*` directories.

## Build, Test, and Development Commands

Use the root `Makefile` to bootstrap the toolchain and generated sources:

- `make all` installs the pinned toolchain pieces and updates opcodes.
- `make init` is the lighter setup path for IIS-managed environments.
- `make -C hw/system/spatz_cluster help` lists simulator and software targets.
- `make -C hw/system/spatz_cluster bin/spatz_cluster.vlt` builds the Verilator system binary.
- `make -C hw/system/spatz_cluster sw.vlt` configures and builds the software against the Verilator simulator.
- `make -C hw/system/spatz_cluster sw.test.vlt` runs the software test suite through CTest.

## Coding Style & Naming Conventions

Follow the existing `.editorconfig`: 2-space indentation by default, 4 spaces for Python, tabs for Makefiles, LF line endings, and 80-column wrapping unless a file type overrides it. SystemVerilog files may use up to 100 columns. Keep names descriptive and local to the domain: hardware under `hw/ip/<block>/`, software tests under `sw/riscvTests/isa/`, and benchmark directories grouped by kernel and precision. Prefer the repository’s current naming patterns for generated artifacts and Make targets.

## Testing Guidelines

The software test flow is CMake- and CTest-based. Add new ISA tests in `sw/riscvTests/CMakeLists.txt` using the existing `add_snitch_test(...)` pattern, and run the relevant subset with `ctest -R <name>` from `sw/build/`. For simulator-integrated validation, use `sw.test.vlt`, `sw.test.vsim`, or `sw.test.vcs` from `hw/system/spatz_cluster/`.

## Commit & Pull Request Guidelines

Keep commits atomic, rebased, and free of merge commits. Subject lines should be imperative, capitalized, under 100 characters, and may start with a scoped tag like `[uart]`. Reference related issues in the commit body or PR description when relevant. Pull requests should include a clear summary, the validation you ran, and screenshots or waveforms when the change affects hardware behavior.

## Configuration Notes

Cluster configuration comes from `hw/system/spatz_cluster/cfg/*.hjson`. When changing simulator behavior, prefer passing `CFG=...` on the make command line rather than editing the default file in place.
