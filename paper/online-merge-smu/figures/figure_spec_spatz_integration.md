# Figure Spec: Spatz Prototype Integration and Execution Sequence

- Section: Spatz-Based Prototype Integration
- Archetype: two-panel system integration and sequence diagram
- Backend: Python (matplotlib)
- Final size: 180 x 88 mm
- Claim: Spatz instantiates selective recurrence offloading with an MMIO
  cluster peripheral, an independent SMU TCDM requester, and the unchanged RVV
  path; software sequences the two phases through completion and shared state.
- Panel a: RISC-V core/software, cluster peripheral/MMIO, Scalar SMU,
  interconnect, shared TCDM, and Spatz RVV with its existing TCDM ports.
- Panel b lanes: CPU/software, Scalar SMU, shared TCDM, RVV. Events are
  configure/start, recurrence reads/computation/writes, done, weight load, and
  RVV `O[D]` update.
- Grayscale encoding: new/reused tags, solid data paths, and dashed control
  paths supplement color.
