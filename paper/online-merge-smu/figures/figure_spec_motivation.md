# Figure Spec: Motivation and Computation Decomposition

- Section: Background and Motivation
- Archetype: concept illustration / computation decomposition
- Backend: Python (matplotlib)
- Final size: 180 x 54 mm
- Claim: Online Softmax Merge combines a dependency-bound scalar recurrence
  with an element-independent `O[D]` vector update.
- Content: `(m_old,l_old,O_old)` and tile state enter a scalar chain
  `max -> deltas -> two EXP paths -> scaled lengths -> accumulation ->
  reciprocal -> weights`; ready weights fan out to independent `j` updates.
- Exclusions: no Spatz, TCDM, MMIO, address, or mode detail.
- Grayscale encoding: serial chain versus parallel lanes remains visible
  through layout, arrows, and labels without relying on color.

