#!/usr/bin/env python3
"""Bounded bit-level equivalence check for the RTL FP16 divider.

The software reference in Phase 1 is the pre-narrowing 64-bit expression.  A
second implementation below mirrors the 35-bit quotient, 12-bit divisor and
52-bit comparison carrier used by ``online_merge_fp16_divider``.  The sweep is
deliberately bounded: it covers the historical 523,776 subnormal pair cases
and 600,000 deterministic finite normal/subnormal cases, but never attempts a
65k-by-65k Cartesian product.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
PHASE1 = ROOT / "experiments" / "phase1_online_softmax" / "run_validation.py"
spec = importlib.util.spec_from_file_location("phase1_validation", PHASE1)
if spec is None or spec.loader is None:  # pragma: no cover
    raise RuntimeError(f"cannot load {PHASE1}")
phase1 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = phase1
spec.loader.exec_module(phase1)


NUM_WIDTH = 35
RATIO_WIDTH = 52


def narrow_round_ratio(
    quotient: int, remainder: int, denominator: int, shift: int
) -> int:
    """The narrowed RTL round_ratio, with its legal FP16 shift bounds."""

    quotient = int(quotient)
    remainder = int(remainder)
    denominator = int(denominator)
    shift = int(shift)
    if shift == 0:
        return quotient
    if shift >= NUM_WIDTH:
        low_quotient = quotient
        base = 0
    else:
        low_quotient = quotient & ((1 << shift) - 1)
        base = quotient >> shift
    discarded = low_quotient * denominator + remainder
    # ``shift >= RATIO_WIDTH`` is unreachable for finite binary16 inputs;
    # match the RTL's saturated defensive carrier for that invalid path.
    denominator_scaled = (
        (1 << RATIO_WIDTH) - 1
        if shift >= RATIO_WIDTH
        else denominator << shift
    )
    half = denominator_scaled >> 1
    round_up = discarded > half
    if not round_up and denominator_scaled & 1 == 0:
        round_up = discarded == half and (base & 1) != 0
    if not round_up and denominator_scaled & 1 == 1:
        round_up = (discarded << 1) == denominator_scaled and (base & 1) != 0
    return base + int(round_up)


def _significand_exponent(bits: int) -> tuple[int, int]:
    exp = (bits >> 10) & 0x1F
    frac = bits & 0x3FF
    if exp == 0:
        msb = frac.bit_length() - 1
        return frac << (10 - msb), msb - 34
    return 1024 + frac, exp - 25


def fp16_div_with(
    numerator_bits: int,
    denominator_bits: int,
    round_ratio: Callable[[int, int, int, int], int],
) -> int:
    """Run the Phase-1 divider reference with a selected ratio rounder."""

    if (numerator_bits & 0x7FFF) == 0 or (denominator_bits & 0x7FFF) == 0:
        return 0
    if ((numerator_bits >> 10) & 0x1F) == 0x1F or (
        (denominator_bits >> 10) & 0x1F
    ) == 0x1F:
        return 0
    numerator_sig, numerator_exp = _significand_exponent(numerator_bits)
    denominator_sig, denominator_exp = _significand_exponent(denominator_bits)
    exponent_diff = numerator_exp - denominator_exp
    quotient, remainder = divmod(numerator_sig << 24, denominator_sig)
    if quotient >= (1 << 24):
        significand = round_ratio(quotient, remainder, denominator_sig, 14)
        normalized_exponent = exponent_diff - 10
    else:
        significand = round_ratio(quotient, remainder, denominator_sig, 13)
        normalized_exponent = exponent_diff - 11
    if significand >= 2048:
        significand >>= 1
        normalized_exponent += 1
    sign = ((numerator_bits >> 15) ^ (denominator_bits >> 15)) & 1
    if normalized_exponent > 5:
        return (sign << 15) | 0x7C00
    if normalized_exponent >= -24:
        return (sign << 15) | ((normalized_exponent + 25) << 10) | (
            significand & 0x3FF
        )
    rounded = round_ratio(
        quotient, remainder, denominator_sig, -exponent_diff
    )
    if rounded >= 1024:
        return (sign << 15) | 0x0400
    return (sign << 15) | (rounded & 0x3FF)


def finite_normal(state: int) -> tuple[int, int]:
    state = (1664525 * state + 1013904223) & 0xFFFFFFFF
    return state, 0x0400 + (state % 0x7800)


def finite_subnormal(state: int) -> tuple[int, int]:
    state = (1664525 * state + 1013904223) & 0xFFFFFFFF
    return state, 1 + (state % 0x03FF)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    mismatches = []
    subnormal_pairs = 0

    # 1024 choose 2 is the historical 523,776 bounded sub/sub sweep.  Zero
    # is retained as the first subnormal endpoint because the RTL has an
    # explicit zero fast path and the original count included it.
    for numerator in range(1024):
        for denominator in range(numerator + 1, 1024):
            expected = phase1._fp16_div_bits(numerator, denominator)
            got = fp16_div_with(numerator, denominator, narrow_round_ratio)
            subnormal_pairs += 1
            if got != expected:
                mismatches.append((numerator, denominator, got, expected))
                break
        if mismatches:
            break

    # Cover all four normal/subnormal strata and both signs with a bounded
    # deterministic stream.  This is intentionally not an exhaustive sweep.
    finite_pairs = 600_000
    state = 0x20260823
    for index in range(finite_pairs):
        if index & 3 == 0:
            state, numerator = finite_normal(state)
            state, denominator = finite_normal(state)
        elif index & 3 == 1:
            state, numerator = finite_normal(state)
            state, denominator = finite_subnormal(state)
        elif index & 3 == 2:
            state, numerator = finite_subnormal(state)
            state, denominator = finite_normal(state)
        else:
            state, numerator = finite_subnormal(state)
            state, denominator = finite_subnormal(state)
        if state & 1:
            numerator |= 0x8000
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        if state & 1:
            denominator |= 0x8000
        expected = phase1._fp16_div_bits(numerator, denominator)
        got = fp16_div_with(numerator, denominator, narrow_round_ratio)
        if got != expected:
            mismatches.append((numerator, denominator, got, expected))
            break

    # Exercise shift 0 and the largest legal subnormal shift directly.  For
    # finite binary16 the minimum normalized exponent is -34 and the maximum
    # finite exponent is +5, hence the legal maximum is 39.
    max_legal_shift = (
        (0x0001 & 0x3FF).bit_length() - 1 - 34
        - ((0x7BFF >> 10) & 0x1F) + 25
    )
    if max_legal_shift != -39:
        raise AssertionError(max_legal_shift)
    for shift in (0, 1, 13, 14, 34, 35, 39):
        quotient = (0x1ABCDE + 17 * shift) & ((1 << NUM_WIDTH) - 1)
        remainder = (0x155 + shift) & 0x7FF
        denominator = 1 + ((0x2A5 + shift) & 0x7FF)
        expected = phase1._round_ratio_rne(
            quotient, remainder, denominator, shift
        )
        got = narrow_round_ratio(quotient, remainder, denominator, shift)
        if got != expected:
            mismatches.append((quotient, remainder, got, expected))

    result = {
        "subnormal_pair_cases": subnormal_pairs,
        "finite_normal_subnormal_cases": finite_pairs,
        "max_legal_subnormal_shift": -max_legal_shift,
        "mismatches": mismatches,
        "status": "pass" if not mismatches else "fail",
        "elapsed_seconds": time.monotonic() - started,
    }
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
