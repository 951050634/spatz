# Cluster-Local Softmax Merge Unit Paper

This directory contains an anonymous IEEE conference-format manuscript.

Build it with:

```sh
make
```

`make` regenerates the SVG, PDF, PNG, and TIFF figure bundle from the recorded
experiment artifacts before compiling the manuscript. The primary scaling and
bottleneck figure appears in the paper; the concurrency/proxy figure remains a
supplementary asset because its resource and toggle panels are nonphysical
proxies.

The manuscript draws its experimental values from the versioned CSV and JSON
artifacts under `data_process/attnres/` and `work-artifacts/`. It distinguishes
RTL cycle measurements, LUT-model accuracy, and nonphysical resource or toggle
proxies.
