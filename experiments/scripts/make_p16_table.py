#!/usr/bin/env python3
"""Fail-closed compatibility entry point for the superseded P16 table.

The former generator could reintroduce withdrawn Fmax, absolute latency, and
throughput rows from P7/P9-P11.  M3 intentionally blocks that path; consume
``experiments/parsed/final_hardware_results.csv`` and the other final records
instead.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P16 legacy table generation is disabled by the M3 freeze."
    )
    parser.parse_args()
    print(
        "P16 legacy generator disabled: use "
        "experiments/parsed/final_hardware_results.csv"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
