# Optional Experiment Capability Audit

This audit records executable scope and blockers without installing or updating any tool, package, PDK, or submodule.

| Capability | Status | Paper eligible | Reason |
| --- | --- | --- | --- |
| `EXP_ONLY` | `BLOCKED_NOT_IMPLEMENTED` | `NO` | EXP_ONLY_NOT_IMPLEMENTED; software exp() and zero-cost substitutes are forbidden |
| `TILE_SCAN` | `NOT_APPLICABLE` | `NO` | NO_INDEPENDENT_TILE_PARAMETER |
| `INPUT_PATTERN` | `COMPLETE_SUPPORTING` | `NO` | P0_4_BOUNDARY_COVERAGE_PASS |
| `OPENROAD` | `BLOCKED_TOOLCHAIN` | `NO` | OPENROAD_NOT_FOUND |
| `WORKLOAD_POWER_ENERGY` | `BLOCKED_EXTERNAL` | `NO` | MISSING_TOOLS=openroad,sta,vcd2saif; MISSING_GATE_OR_POSTLAYOUT_ACTIVITY_PARASITICS_CLOCK_TREE_AND_CHARACTERIZED_POWER_FLOW |
| `FIGURE_RENDERING` | `BLOCKED_PYTHON_PACKAGES` | `NO` | MISSING_PACKAGES=matplotlib |

RTL toggle counts remain a zero-delay activity proxy. This audit does not convert them into mW, pJ, or physical energy.
