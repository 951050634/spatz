#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generate deterministic FP32 inputs and host-double golden outputs."""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path
from typing import Iterable

TCDM_CAPACITY_BYTES = 128 * 1024
TCDM_WORKING_SET_NUMERATOR = 7
TCDM_WORKING_SET_DENOMINATOR = 10
ALLOCATION_ALIGNMENT_BYTES = 256
UINT32_MAX = (1 << 32) - 1

CASE_KINDS = (
    "main",
    "equal-m",
    "delta-neg8",
    "delta-below-neg8",
    "l-old-zero",
    "l-tile-zero",
    "small-l",
    "signed-o",
    "both-zero-l",
)


def layout_bytes(n: int, d: int) -> tuple[int, int]:
    footprint = n * (32 + 16 * d)
    allocation = (
        (footprint + ALLOCATION_ALIGNMENT_BYTES - 1)
        // ALLOCATION_ALIGNMENT_BYTES
        * ALLOCATION_ALIGNMENT_BYTES
    )
    return footprint, allocation


def fits_main_capacity(n: int, d: int) -> bool:
    _, allocation = layout_bytes(n, d)
    limit = (
        TCDM_CAPACITY_BYTES
        * TCDM_WORKING_SET_NUMERATOR
        // TCDM_WORKING_SET_DENOMINATOR
    )
    return allocation <= limit


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def f32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", f32(value)))[0]


class XorShift32:
    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF
        if self.state == 0:
            self.state = 0x6D2B79F5

    def next_u32(self) -> int:
        value = self.state
        value ^= (value << 13) & 0xFFFFFFFF
        value ^= value >> 17
        value ^= (value << 5) & 0xFFFFFFFF
        self.state = value & 0xFFFFFFFF
        return self.state

    def unit(self) -> float:
        return float(self.next_u32() >> 8) / float(1 << 24)

    def uniform(self, low: float, high: float) -> float:
        return f32(low + (high - low) * self.unit())


def make_inputs(
    n: int, d: int, seed: int, case_kind: str
) -> tuple[list[float], ...]:
    rng = XorShift32(seed)
    m_old: list[float] = []
    l_old: list[float] = []
    o_old: list[float] = []
    m_tile: list[float] = []
    l_tile: list[float] = []
    o_tile: list[float] = []
    min_l = 2.0**-8

    for row in range(n):
        old_m = rng.uniform(-4.0, 4.0)
        tile_m = rng.uniform(-4.0, 4.0)
        old_l = rng.uniform(min_l, 8.0)
        tile_l = rng.uniform(min_l, 8.0)

        if row % 11 == 0:
            old_l = 0.0
        if row % 13 == 1:
            tile_l = 0.0
        if old_l == 0.0 and tile_l == 0.0:
            tile_l = f32(min_l)

        if case_kind == "equal-m":
            tile_m = old_m
        elif case_kind == "delta-neg8":
            old_m, tile_m = ((-4.0, 4.0) if row % 2 == 0 else (4.0, -4.0))
        elif case_kind == "delta-below-neg8":
            old_m, tile_m = ((-5.0, 4.0) if row % 2 == 0 else (4.0, -5.0))
        elif case_kind == "l-old-zero":
            old_l = 0.0
            tile_l = max(tile_l, f32(min_l))
        elif case_kind == "l-tile-zero":
            tile_l = 0.0
            old_l = max(old_l, f32(min_l))
        elif case_kind == "small-l":
            old_l = f32(min_l)
            tile_l = f32(min_l * (1.0 + (row % 3)))
        elif case_kind == "both-zero-l":
            old_l = 0.0
            tile_l = 0.0

        m_old.append(f32(old_m))
        m_tile.append(f32(tile_m))
        l_old.append(f32(old_l))
        l_tile.append(f32(tile_l))

        for col in range(d):
            old_o = rng.uniform(-1.0, 1.0)
            tile_o = rng.uniform(-1.0, 1.0)
            if case_kind == "signed-o":
                sign = -1.0 if (row + col) % 2 else 1.0
                old_o = f32(sign * (0.125 + 0.75 * rng.unit()))
                tile_o = f32(-sign * (0.0625 + 0.875 * rng.unit()))
            o_old.append(f32(old_o))
            o_tile.append(f32(tile_o))

    return m_old, l_old, o_old, m_tile, l_tile, o_tile


def make_golden(
    n: int,
    d: int,
    inputs: tuple[list[float], ...],
) -> tuple[list[float], list[float], list[float], bool]:
    m_old, l_old, o_old, m_tile, l_tile, o_tile = inputs
    m_out: list[float] = []
    l_out: list[float] = []
    o_out: list[float] = []
    unsupported = False

    for row in range(n):
        merged_m = max(float(m_old[row]), float(m_tile[row]))
        old_scaled = float(l_old[row]) * math.exp(float(m_old[row]) - merged_m)
        tile_scaled = (
            float(l_tile[row]) * math.exp(float(m_tile[row]) - merged_m)
        )
        merged_l = old_scaled + tile_scaled
        m_out.append(f32(merged_m))
        l_out.append(f32(merged_l))

        if merged_l == 0.0 or not math.isfinite(merged_l):
            unsupported = True
            o_out.extend([0.0] * d)
            continue

        old_weight = old_scaled / merged_l
        tile_weight = tile_scaled / merged_l
        base = row * d
        for col in range(d):
            value = (
                old_weight * float(o_old[base + col])
                + tile_weight * float(o_tile[base + col])
            )
            o_out.append(f32(value))

    return m_out, l_out, o_out, unsupported


def format_u32_array(name: str, values: Iterable[float]) -> str:
    bits = [f"0x{f32_bits(value):08x}u" for value in values]
    lines = [f"static const uint32_t {name}[{len(bits)}] = {{"]
    for offset in range(0, len(bits), 6):
        lines.append("    " + ", ".join(bits[offset : offset + 6]) + ",")
    lines.append("};")
    return "\n".join(lines)


def generate_header(
    n: int, d: int, seed: int, case_kind: str, repeats: int
) -> str:
    if case_kind not in CASE_KINDS:
        raise ValueError(f"unsupported case kind: {case_kind}")
    capacity_skip = not fits_main_capacity(n, d)
    if capacity_skip:
        inputs = tuple([0.0] for _ in range(6))
        golden_m, golden_l, golden_o, unsupported = [0.0], [0.0], [0.0], False
    else:
        inputs = make_inputs(n, d, seed, case_kind)
        golden_m, golden_l, golden_o, unsupported = make_golden(n, d, inputs)
    names = (
        "online_merge_m_old_bits",
        "online_merge_l_old_bits",
        "online_merge_o_old_bits",
        "online_merge_m_tile_bits",
        "online_merge_l_tile_bits",
        "online_merge_o_tile_bits",
    )
    arrays = [
        format_u32_array(name, values)
        for name, values in zip(names, inputs, strict=True)
    ]
    arrays.extend(
        (
            format_u32_array("online_merge_golden_m_bits", golden_m),
            format_u32_array("online_merge_golden_l_bits", golden_l),
            format_u32_array("online_merge_golden_o_bits", golden_o),
        )
    )
    if capacity_skip:
        case_class = "capacity"
    elif unsupported:
        case_class = "unsupported"
    else:
        case_class = "main" if case_kind == "main" else "boundary"
    footprint, allocation = layout_bytes(n, d)
    return "\n".join(
        (
            "// Generated by generate_case.py; do not edit.",
            "#pragma once",
            "#include <stdint.h>",
            "",
            f"#define ONLINE_MERGE_CASE_N {n}u",
            f"#define ONLINE_MERGE_CASE_D {d}u",
            f"#define ONLINE_MERGE_CASE_SEED {seed & 0xFFFFFFFF}u",
            f"#define ONLINE_MERGE_CASE_REPEATS {repeats}u",
            f'#define ONLINE_MERGE_CASE_KIND "{case_kind}"',
            f'#define ONLINE_MERGE_CASE_CLASS "{case_class}"',
            f"#define ONLINE_MERGE_CASE_UNSUPPORTED {int(unsupported)}u",
            f"#define ONLINE_MERGE_CASE_CAPACITY_SKIP {int(capacity_skip)}u",
            f"#define ONLINE_MERGE_CASE_FOOTPRINT_BYTES {footprint}ull",
            f"#define ONLINE_MERGE_CASE_ALLOCATION_BYTES {allocation}ull",
            "",
            *arrays,
            "",
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--d", type=int, required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--case-kind", choices=CASE_KINDS, default="main")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.n <= 0 or args.d <= 0:
        raise SystemExit("N and D must be positive")
    if args.n > UINT32_MAX or args.d > UINT32_MAX:
        raise SystemExit("N and D must fit in uint32_t")
    if not 3 <= args.repeats <= 16:
        raise SystemExit("repeats must be in [3, 16]")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        generate_header(
            args.n, args.d, args.seed, args.case_kind, args.repeats
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
