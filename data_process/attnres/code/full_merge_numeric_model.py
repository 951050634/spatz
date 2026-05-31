#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import csv
import math
import struct
from dataclasses import dataclass
from pathlib import Path


EXP_MIN = -8.0
EXP_MAX = 0.0
EXP_SEGMENTS = 256
RECIP_SEGMENTS = 256
REL_GUARD = 1.0


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def f32_bits(value: float) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', f32(value)))[0]:08x}"


def f32_add(a: float, b: float) -> float:
    return f32(f32(a) + f32(b))


def f32_mul(a: float, b: float) -> float:
    return f32(f32(a) * f32(b))


def f32_madd(a: float, b: float, c: float) -> float:
    return f32(f32_mul(a, b) + f32(c))


@dataclass
class MergeInput:
    name: str
    n: int
    d: int
    m_old: list[float]
    l_old: list[float]
    o_old: list[list[float]]
    m_tile: list[float]
    l_tile: list[float]
    o_tile: list[list[float]]


@dataclass
class MergeOutput:
    m: list[float]
    l: list[float]
    o: list[list[float]]


class ExpLUT:
    def __init__(self, xmin: float, xmax: float, segments: int):
        self.xmin = f32(xmin)
        self.xmax = f32(xmax)
        self.segments = segments
        step = (xmax - xmin) / segments
        self.step = f32(step)
        self.inv_step = f32(1.0 / step)
        self.values = [f32(math.exp(xmin + i * step)) for i in range(segments + 1)]

    def eval(self, x: float) -> float:
        x = f32(x)
        if x < self.xmin:
            return 0.0
        if x >= self.xmax:
            return 1.0
        pos = f32_mul(f32_add(x, -self.xmin), self.inv_step)
        idx = int(pos)
        if idx >= self.segments:
            return self.values[self.segments]
        frac = f32(pos - float(idx))
        lo = self.values[idx]
        hi = self.values[idx + 1]
        return f32_madd(f32_add(hi, -lo), frac, lo)


class RecipLUT:
    def __init__(self, segments: int):
        self.segments = segments
        self.step = f32(1.0 / segments)
        self.inv_step = f32(float(segments))
        self.values = [f32(1.0 / (1.0 + i / segments)) for i in range(segments + 1)]

    def eval(self, x: float) -> float:
        x = f32(x)
        if not math.isfinite(x) or x <= 0.0:
            raise ValueError(f"reciprocal input must be positive finite: {x}")

        mant, exp = math.frexp(x)
        y = f32(2.0 * mant)
        pos = f32_mul(f32_add(y, -1.0), self.inv_step)
        idx = int(pos)
        if idx >= self.segments:
            base = self.values[self.segments]
        else:
            frac = f32(pos - float(idx))
            lo = self.values[idx]
            hi = self.values[idx + 1]
            base = f32_madd(f32_add(hi, -lo), frac, lo)

        return f32(math.ldexp(base, 1 - exp))


def make_generic_mixed_case(n: int, d: int) -> MergeInput:
    m_old = []
    l_old = []
    o_old = []
    m_tile = []
    l_tile = []
    o_tile = []
    for i in range(n):
        row = float(i)
        mode = i & 3
        if mode == 0:
            mo = f32(1.25 + 0.125 * row)
            mt = f32(mo - 0.75)
            lo = f32(0.75 + 0.03125 * row)
            lt = f32(0.25 + 0.015625 * row)
        elif mode == 1:
            mo = f32(-0.25 + 0.0625 * row)
            mt = f32(mo + 0.75)
            lo = f32(0.50 + 0.03125 * row)
            lt = f32(1.25 + 0.015625 * row)
        elif mode == 2:
            mo = f32(0.125 + 0.0625 * row)
            mt = mo
            lo = f32(0.25 + 0.03125 * row)
            lt = f32(0.75 + 0.015625 * row)
        else:
            mo = f32(-1.0 + 0.0625 * row)
            mt = f32(mo + 0.75)
            lo = f32(0.001 * (row + 1.0))
            lt = f32(0.003 * (row + 1.0))
        m_old.append(mo)
        m_tile.append(mt)
        l_old.append(lo)
        l_tile.append(lt)
        o_old.append([f32(0.01 * float(i * 11 + j * 5 - 17)) for j in range(d)])
        o_tile.append([f32(0.02 * float(i * 7 + j * 3 - 23)) for j in range(d)])

    return MergeInput("generic-mixed", n, d, m_old, l_old, o_old, m_tile, l_tile, o_tile)


def make_delta_sweep_case(n: int, d: int) -> MergeInput:
    deltas = [0.0, 0.125, 0.25, 0.5, 0.75, 1.0, 2.0, 4.0, 6.0, 8.0]
    m_old = []
    l_old = []
    o_old = []
    m_tile = []
    l_tile = []
    o_tile = []
    for i in range(n):
        row = float(i)
        delta = deltas[i % len(deltas)]
        center = f32(-1.5 + 0.1875 * row)
        if i % 3 == 0:
            mo = f32(center + 0.5 * delta)
            mt = f32(center - 0.5 * delta)
        elif i % 3 == 1:
            mo = f32(center - 0.5 * delta)
            mt = f32(center + 0.5 * delta)
        else:
            mo = center
            mt = center
        lo = f32(0.0005 * float(i + 1) if i % 5 == 0 else 0.25 + 0.0625 * row)
        lt = f32(0.0015 * float(i + 1) if i % 5 == 0 else 0.75 + 0.03125 * row)
        m_old.append(mo)
        m_tile.append(mt)
        l_old.append(lo)
        l_tile.append(lt)
        o_old.append([f32(0.0078125 * float(i * 13 - j * 7 + 9)) for j in range(d)])
        o_tile.append([f32(0.01171875 * float(j * 5 - i * 3 - 21)) for j in range(d)])

    return MergeInput("delta-sweep", n, d, m_old, l_old, o_old, m_tile, l_tile, o_tile)


def merge_reference(inp: MergeInput) -> MergeOutput:
    out_m = []
    out_l = []
    out_o = []
    for i in range(inp.n):
        m_new = f32(max(inp.m_old[i], inp.m_tile[i]))
        old_exp = math.exp(float(inp.m_old[i]) - float(m_new))
        tile_exp = math.exp(float(inp.m_tile[i]) - float(m_new))
        old_scaled_l = float(inp.l_old[i]) * old_exp
        tile_scaled_l = float(inp.l_tile[i]) * tile_exp
        l_new = old_scaled_l + tile_scaled_l
        old_weight = old_scaled_l / l_new
        tile_weight = tile_scaled_l / l_new
        out_m.append(m_new)
        out_l.append(f32(l_new))
        row_o = []
        for j in range(inp.d):
            row_o.append(
                f32(
                    float(inp.o_old[i][j]) * old_weight
                    + float(inp.o_tile[i][j]) * tile_weight
                )
            )
        out_o.append(row_o)
    return MergeOutput(out_m, out_l, out_o)


def merge_approx(inp: MergeInput, exp_lut: ExpLUT, recip_lut: RecipLUT) -> MergeOutput:
    out_m = []
    out_l = []
    out_o = []
    for i in range(inp.n):
        m_new = f32(max(inp.m_old[i], inp.m_tile[i]))
        old_exp = exp_lut.eval(f32_add(inp.m_old[i], -m_new))
        tile_exp = exp_lut.eval(f32_add(inp.m_tile[i], -m_new))
        old_scaled_l = f32_mul(inp.l_old[i], old_exp)
        tile_scaled_l = f32_mul(inp.l_tile[i], tile_exp)
        l_new = f32_add(old_scaled_l, tile_scaled_l)
        recip_l = recip_lut.eval(l_new)
        old_weight = f32_mul(old_scaled_l, recip_l)
        tile_weight = f32_mul(tile_scaled_l, recip_l)
        out_m.append(m_new)
        out_l.append(l_new)
        row_o = []
        for j in range(inp.d):
            old_term = f32_mul(inp.o_old[i][j], old_weight)
            row_o.append(f32_madd(inp.o_tile[i][j], tile_weight, old_term))
        out_o.append(row_o)
    return MergeOutput(out_m, out_l, out_o)


def iter_values(out: MergeOutput):
    for value in out.m:
        yield value
    for value in out.l:
        yield value
    for row in out.o:
        for value in row:
            yield value


def compare_outputs(ref: MergeOutput, got: MergeOutput):
    max_abs = 0.0
    max_rel = 0.0
    abs_sum = 0.0
    count = 0
    for ref_value, got_value in zip(iter_values(ref), iter_values(got)):
        abs_err = abs(f32_add(got_value, -ref_value))
        rel_err = abs_err / max(abs(ref_value), REL_GUARD)
        max_abs = max(max_abs, abs_err)
        max_rel = max(max_rel, rel_err)
        abs_sum += abs_err
        count += 1
    return max_abs, max_rel, abs_sum / count


def summarize_case(inp: MergeInput, exp_lut: ExpLUT, recip_lut: RecipLUT):
    ref = merge_reference(inp)
    approx = merge_approx(inp, exp_lut, recip_lut)
    max_abs, max_rel, mean_abs = compare_outputs(ref, approx)
    return {
        "case_name": inp.name,
        "N": inp.n,
        "D": inp.d,
        "exp_x_min": EXP_MIN,
        "exp_x_max": EXP_MAX,
        "exp_segments": EXP_SEGMENTS,
        "recip_segments": RECIP_SEGMENTS,
        "max_abs_err": f"{max_abs:.9e}",
        "guarded_max_rel_err": f"{max_rel:.9e}",
        "mean_abs_err": f"{mean_abs:.9e}",
        "ref_m0_bits": f32_bits(ref.m[0]),
        "ref_l0_bits": f32_bits(ref.l[0]),
        "ref_o00_bits": f32_bits(ref.o[0][0]),
        "approx_m0_bits": f32_bits(approx.m[0]),
        "approx_l0_bits": f32_bits(approx.l[0]),
        "approx_o00_bits": f32_bits(approx.o[0][0]),
    }


def main():
    base_dir = Path(__file__).resolve().parent.parent
    out_path = base_dir / "data" / "online_softmax_full_merge_numeric.csv"
    exp_lut = ExpLUT(EXP_MIN, EXP_MAX, EXP_SEGMENTS)
    recip_lut = RecipLUT(RECIP_SEGMENTS)
    cases = [
        make_generic_mixed_case(4, 8),
        make_generic_mixed_case(8, 16),
        make_generic_mixed_case(8, 32),
        make_generic_mixed_case(16, 64),
        make_delta_sweep_case(16, 64),
    ]
    rows = [summarize_case(case, exp_lut, recip_lut) for case in cases]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {out_path}")
    for row in rows:
        print(
            "full-merge-numeric "
            f"{row['case_name']} N={row['N']} D={row['D']} "
            f"max_abs={row['max_abs_err']} "
            f"max_rel={row['guarded_max_rel_err']} "
            f"mean_abs={row['mean_abs_err']} "
            f"ref_l0={row['ref_l0_bits']} ref_o00={row['ref_o00_bits']} "
            f"approx_l0={row['approx_l0_bits']} approx_o00={row['approx_o00_bits']}"
        )


if __name__ == "__main__":
    main()
