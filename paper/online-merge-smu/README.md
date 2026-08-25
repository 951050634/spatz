# Selective Recurrence Offloading Paper

This directory contains an anonymous IEEE conference-format manuscript.

Build it with:

```sh
make
```

`make` regenerates the platform-independent architecture figures, the
RTL-grounded Scalar SMU diagrams, and the quantitative scaling/tradeoff plots
before compiling the manuscript. The quantitative plots read only the frozen
CSV evidence under `experiments/parsed/`; the architecture scripts do not run
simulation or synthesis.

The manuscript draws its experimental values from the active final evidence
listed in `experiments/reports/FINAL_EVIDENCE_FREEZE.md`. It distinguishes
RTL/Verilator cycle measurements, standalone mapped area, and the pre-layout
register-to-register timing proxy.
