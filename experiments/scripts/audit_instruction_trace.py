#!/usr/bin/env python3
"""Audit retired instructions inside online-merge DASM markers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import experiment_common as common


SYMBOL_HEADER = re.compile(r"^([0-9a-fA-F]+) <([^>]+)>:$")
INSTRUCTION = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+([A-Za-z0-9_.]+)(?:\s+(.*))?$"
)
TRACE_LINE = re.compile(
    r"^\s*\d+\s+(\d+)\s+\d+\s+0x([0-9a-fA-F]+)\s+DASM"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--disassembly", type=Path, required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--D", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def decode_disassembly(
    text: str,
) -> tuple[dict[int, str], list[tuple[int, int, str]]]:
    instructions: dict[int, str] = {}
    starts: list[tuple[int, str]] = []
    for line in text.splitlines():
        header = SYMBOL_HEADER.match(line)
        if header:
            starts.append((int(header.group(1), 16), header.group(2)))
            continue
        instruction = INSTRUCTION.match(line)
        if instruction:
            instructions[int(instruction.group(1), 16)] = (
                instruction.group(2)
            )
    starts.sort()
    ranges: list[tuple[int, int, str]] = []
    for index, (start, name) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else 1 << 64
        ranges.append((start, end, name))
    return instructions, ranges


def symbol_for(pc: int, ranges: list[tuple[int, int, str]]) -> str | None:
    for start, end, name in ranges:
        if start <= pc < end:
            return name
    return None


def symbol_range(
    ranges: list[tuple[int, int, str]], name: str
) -> tuple[int, int]:
    matches = [(start, end) for start, end, symbol in ranges if symbol == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {name} symbol, got {len(matches)}")
    return matches[0]


def category(mnemonic: str, symbol: str | None) -> str:
    if mnemonic.startswith("v"):
        return "rvv"
    if mnemonic.startswith(("b", "j")) or mnemonic in {
        "ret",
        "call",
        "tail",
    }:
        return "loop_control"
    if mnemonic.startswith(("fence", "csr")):
        return "synchronization"
    load_store_prefixes = (
        "lb",
        "lh",
        "lw",
        "ld",
        "lbu",
        "lhu",
        "sb",
        "sh",
        "sw",
        "sd",
        "fl",
        "fs",
    )
    if mnemonic.startswith(load_store_prefixes):
        return "load_store"
    if symbol and (
        symbol.startswith("online_merge_b2_r")
        or symbol.startswith("online_merge_rtl_reference")
        or "rtl_row_weights" in symbol
    ):
        return "software_scalar"
    return "other"


def audit_trace(
    trace_path: Path,
    disassembly_path: Path,
    config: str,
    n: int,
    d: int,
) -> dict[str, Any]:
    trace_path = trace_path.resolve()
    disassembly_path = disassembly_path.resolve()
    instructions, ranges = decode_disassembly(
        disassembly_path.read_text(encoding="utf-8")
    )
    begin_start, begin_end = symbol_range(
        ranges, "online_merge_trace_begin"
    )
    end_start, end_end = symbol_range(ranges, "online_merge_trace_end")

    inside = False
    saw_begin = False
    saw_end = False
    first_tick: int | None = None
    last_tick: int | None = None
    category_counts: Counter[str] = Counter()
    category_cycle_spans: Counter[str] = Counter()
    mnemonic_counts: Counter[str] = Counter()
    symbol_counts: Counter[str] = Counter()
    undecoded = 0
    previous_tick: int | None = None
    previous_category: str | None = None

    with trace_path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            match = TRACE_LINE.match(line)
            if not match:
                continue
            tick = int(match.group(1))
            pc = int(match.group(2), 16)
            if begin_start <= pc < begin_end:
                saw_begin = True
                continue
            if saw_begin and not inside:
                inside = True
                first_tick = tick
            if inside and end_start <= pc < end_end:
                saw_end = True
                last_tick = tick
                if previous_tick is not None and previous_category is not None:
                    category_cycle_spans[previous_category] += max(
                        0, tick - previous_tick
                    )
                break
            if not inside:
                continue
            if previous_tick is not None and previous_category is not None:
                category_cycle_spans[previous_category] += max(
                    0, tick - previous_tick
                )
            mnemonic = instructions.get(pc)
            symbol = symbol_for(pc, ranges)
            if mnemonic is None:
                undecoded += 1
                instruction_category = "undecoded"
            else:
                mnemonic_counts[mnemonic] += 1
                instruction_category = category(mnemonic, symbol)
            category_counts[instruction_category] += 1
            symbol_counts[symbol or "<unknown>"] += 1
            previous_tick = tick
            previous_category = instruction_category
            last_tick = tick

    errors: list[str] = []
    if not saw_begin:
        errors.append("begin marker not observed")
    if not saw_end:
        errors.append("end marker not observed")
    retired = sum(category_counts.values())
    vector_retired = category_counts["rvv"]
    expected_rvv = config in {"B2R_RVV", "A1_SMU_SCALAR"}
    if expected_rvv and vector_retired == 0:
        errors.append("no retired RVV instruction in marker envelope")
    if config == "B1_SCALAR" and vector_retired != 0:
        errors.append("B1 marker envelope contains retired RVV instructions")
    return {
        "schema_version": 1,
        "config": config,
        "N": n,
        "D": d,
        "trace_path": str(trace_path),
        "trace_sha256": common.sha256_file(trace_path),
        "disassembly_path": str(disassembly_path),
        "disassembly_sha256": common.sha256_file(disassembly_path),
        "marker_begin_observed": saw_begin,
        "marker_end_observed": saw_end,
        "first_tick": first_tick,
        "last_tick": last_tick,
        "marker_tick_span": (
            last_tick - first_tick
            if first_tick is not None and last_tick is not None
            else None
        ),
        "retired_instructions_in_envelope": retired,
        "retired_rvv_instructions": vector_retired,
        "undecoded_instructions": undecoded,
        "category_counts": dict(sorted(category_counts.items())),
        "category_cycle_spans": dict(
            sorted(category_cycle_spans.items())
        ),
        "cycle_attribution_method": (
            "each interval between adjacent retire timestamps is assigned "
            "to the preceding retired instruction category"
        ),
        "mnemonic_counts": dict(sorted(mnemonic_counts.items())),
        "symbol_counts": dict(sorted(symbol_counts.items())),
        "errors": errors,
        "dynamic_rvv_trace_verified": not errors,
        "window_note": (
            "DASM marker envelope includes the target cycle-counter boundary "
            "instructions; target kernel_cycles remain authoritative"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = audit_trace(
            args.trace,
            args.disassembly,
            args.config,
            args.N,
            args.D,
        )
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    common.write_json(args.output.resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not payload["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
