# Figure Spec: Selective Recurrence-Offloading Architecture

- Section: Selective Recurrence-Offloading Architecture
- Archetype: architecture overview
- Backend: Python (matplotlib)
- Final size: 180 x 62 mm
- Claim: The architecture adds a recurrence engine and reuses the existing
  vector datapath, with shared scratchpad state separating the two phases.
- Components: control/software, NEW Scalar SMU, REUSED vector datapath,
  shared scratchpad.
- Connections: control starts and observes the recurrence engine; the Scalar
  SMU reads recurrence state and commits state/weights; the vector datapath
  later reads weights and vectors and writes `O_new`.
- Exclusions: no Spatz name, TCDM name, MMIO offsets, or concrete mode value.

