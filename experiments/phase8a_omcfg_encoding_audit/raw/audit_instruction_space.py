#!/usr/bin/env python3
"""Audit OMCFG custom-opcode space against active Snitch/Spatz decoders.

The checker parses the checked-in SystemVerilog package and the top-level
instruction casez statements. It does not build or modify the design.
Generated evidence is confined to the Phase 8A audit directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


AUDIT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = AUDIT_DIR / "raw"
REPO_ROOT = AUDIT_DIR.parents[1]
PKG_PATH = REPO_ROOT / "hw/ip/snitch/src/riscv_instr.sv"
SNITCH_PATH = REPO_ROOT / "hw/ip/snitch/src/snitch.sv"
SPATZ_PATH = REPO_ROOT / "hw/ip/spatz/src/spatz_decoder.sv"

CUSTOM_OPCODES = (
    (0x0B, "custom-0"),
    (0x2B, "custom-1"),
    (0x5B, "custom-2"),
    (0x7B, "custom-3"),
)
REQUIRED_MAX = 0x009
RESERVED_MAX = 0x0FF
FULL_MAX = 0xFFF
FAMILY_MASK = 0x00007FFF
VARIABLE_MASK = 0xFFFF8000  # imm12 plus rs1


@dataclass(frozen=True)
class Pattern:
    name: str
    bits: str
    match: int
    mask: int
    source_line: int


@dataclass(frozen=True)
class DecoderLabel:
    name: str
    decoder_line: int
    guard: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_package(path: Path) -> dict[str, Pattern]:
    regex = re.compile(
        r"localparam\s+logic\s*\[31:0\]\s+([A-Z][A-Z0-9_]*)"
        r"\s*=\s*32'b([01?]{32})\s*;"
    )
    result: dict[str, Pattern] = {}
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        match = regex.search(line)
        if not match:
            continue
        name, bits = match.groups()
        value = int(bits.replace("?", "0"), 2)
        mask = int("".join("0" if bit == "?" else "1" for bit in bits), 2)
        if name in result:
            raise AssertionError(f"duplicate package pattern {name}")
        result[name] = Pattern(name, bits, value, mask, line_no)
    return result


def strip_comments(lines: Iterable[str]) -> list[str]:
    """Remove // and /* */ comments while preserving source line count."""
    cleaned: list[str] = []
    in_block = False
    for line in lines:
        out: list[str] = []
        index = 0
        while index < len(line):
            if in_block:
                end = line.find("*/", index)
                if end < 0:
                    index = len(line)
                else:
                    in_block = False
                    index = end + 2
            else:
                block = line.find("/*", index)
                slash = line.find("//", index)
                if slash >= 0 and (block < 0 or slash < block):
                    out.append(line[index:slash])
                    index = len(line)
                elif block >= 0:
                    out.append(line[index:block])
                    in_block = True
                    index = block + 2
                else:
                    out.append(line[index:])
                    index = len(line)
        cleaned.append("".join(out))
    if in_block:
        raise AssertionError("unterminated block comment")
    return cleaned


def extract_top_case_labels(
    path: Path,
    case_expression: str,
    defines: set[str],
) -> tuple[int, int, list[DecoderLabel]]:
    """Extract only labels of the first matching top-level case statement."""
    code_lines = strip_comments(path.read_text().splitlines())
    start_regex = re.compile(
        rf"\b(?:unique\s+|priority\s+)?casez?\s*\(\s*{case_expression}\s*\)"
    )
    case_open_regex = re.compile(r"\b(?:unique\s+|priority\s+)?case[zx]?\s*\(")
    case_end_regex = re.compile(r"\bendcase\b")
    label_regex = re.compile(
        r"^\s*(?:riscv_instr::)?([A-Z][A-Z0-9_]*)\s*(?:,|:)"
    )
    directive_regex = re.compile(r"^\s*`(ifdef|ifndef|else|endif)\b\s*(\w+)?")

    preproc_stack: list[dict[str, object]] = []
    active = True
    in_target_positive_branch = False
    case_depth = 0
    case_start = 0
    case_end = 0
    labels: list[DecoderLabel] = []

    for line_no, line in enumerate(code_lines, 1):
        directive = directive_regex.match(line)
        if directive:
            kind, symbol = directive.groups()
            if kind in ("ifdef", "ifndef"):
                if symbol is None:
                    raise AssertionError(f"missing preprocessor symbol at {path}:{line_no}")
                condition = symbol in defines
                if kind == "ifndef":
                    condition = not condition
                preproc_stack.append(
                    {
                        "parent_active": active,
                        "condition": condition,
                        "symbol": symbol,
                        "positive": kind == "ifdef",
                    }
                )
                active = active and condition
            elif kind == "else":
                if not preproc_stack:
                    raise AssertionError(f"unmatched `else at {path}:{line_no}")
                frame = preproc_stack[-1]
                frame["condition"] = not bool(frame["condition"])
                frame["positive"] = not bool(frame["positive"])
                active = bool(frame["parent_active"]) and bool(frame["condition"])
            else:
                if not preproc_stack:
                    raise AssertionError(f"unmatched `endif at {path}:{line_no}")
                frame = preproc_stack.pop()
                active = bool(frame["parent_active"])
            in_target_positive_branch = any(
                frame["symbol"] == "TARGET_SPATZ"
                and bool(frame["positive"])
                and bool(frame["condition"])
                for frame in preproc_stack
            )
            continue

        if not active:
            continue
        if case_depth == 0:
            if start_regex.search(line):
                case_depth = 1
                case_start = line_no
            continue
        if case_depth == 1:
            label = label_regex.match(line)
            if label:
                labels.append(
                    DecoderLabel(
                        label.group(1),
                        line_no,
                        "ifdef TARGET_SPATZ" if in_target_positive_branch else "always",
                    )
                )
        case_depth += len(case_open_regex.findall(line))
        case_depth -= len(case_end_regex.findall(line))
        if case_depth == 0:
            case_end = line_no
            break

    if not case_start or not case_end:
        raise AssertionError(f"did not find a complete case for {case_expression} in {path}")
    return case_start, case_end, labels


def matches(word: int, pattern: Pattern) -> bool:
    return (word & pattern.mask) == pattern.match


def constraints_compatible(*pairs: tuple[int, int]) -> bool:
    """Return true when all (mask, match) constraints have an intersection."""
    for index, (mask_a, match_a) in enumerate(pairs):
        for mask_b, match_b in pairs[index + 1 :]:
            if (match_a ^ match_b) & mask_a & mask_b:
                return False
    return True


def field_rule(bits: str, high: int, low: int) -> str:
    field = bits[31 - high : 32 - low]
    return "*" if set(field) == {"?"} else field


def opcode_hex(pattern: Pattern) -> str:
    if pattern.mask & 0x7F != 0x7F:
        return "wildcard"
    return f"0x{pattern.match & 0x7F:02X}"


def write_decoder_inventory(
    path: Path,
    source_path: Path,
    labels: list[DecoderLabel],
    package: dict[str, Pattern],
) -> None:
    fields = (
        "ordinal",
        "instruction_name",
        "pattern",
        "match",
        "mask",
        "pattern_source_location",
        "decoder_location",
        "guard",
        "opcode",
        "funct3_rule",
        "funct7_rule",
        "rd_rule",
        "rs1_rule",
        "rs2_rule",
    )
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for ordinal, label in enumerate(labels, 1):
            pattern = package[label.name]
            writer.writerow(
                {
                    "ordinal": ordinal,
                    "instruction_name": label.name,
                    "pattern": pattern.bits,
                    "match": f"0x{pattern.match:08X}",
                    "mask": f"0x{pattern.mask:08X}",
                    "pattern_source_location": f"{PKG_PATH.relative_to(REPO_ROOT)}:{pattern.source_line}",
                    "decoder_location": f"{source_path.relative_to(REPO_ROOT)}:{label.decoder_line}",
                    "guard": label.guard,
                    "opcode": opcode_hex(pattern),
                    "funct3_rule": field_rule(pattern.bits, 14, 12),
                    "funct7_rule": field_rule(pattern.bits, 31, 25),
                    "rd_rule": field_rule(pattern.bits, 11, 7),
                    "rs1_rule": field_rule(pattern.bits, 19, 15),
                    "rs2_rule": field_rule(pattern.bits, 24, 20),
                }
            )


def candidate_word(opcode: int, funct3: int, cfg_id: int, rs1: int, rd: int = 0) -> int:
    return (
        ((cfg_id & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | opcode
    )


def cube_assignment_count(pattern: Pattern, fixed_mask: int, fixed_match: int) -> int:
    if not constraints_compatible((pattern.mask, pattern.match), (fixed_mask, fixed_match)):
        return 0
    constrained_variables = (pattern.mask & VARIABLE_MASK).bit_count()
    return 1 << (17 - constrained_variables)


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise AssertionError(f"refusing to write empty evidence table {path}")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    package = parse_package(PKG_PATH)
    snitch_start, snitch_end, snitch_labels = extract_top_case_labels(
        SNITCH_PATH, r"inst_data_i", {"TARGET_SPATZ"}
    )
    spatz_start, spatz_end, spatz_labels = extract_top_case_labels(
        SPATZ_PATH, r"decoder_req_i\.instr", set()
    )

    unresolved_snitch = [label.name for label in snitch_labels if label.name not in package]
    unresolved_spatz = [label.name for label in spatz_labels if label.name not in package]
    if unresolved_snitch or unresolved_spatz:
        raise AssertionError(
            f"unresolved labels: Snitch={unresolved_snitch}, Spatz={unresolved_spatz}"
        )
    if len({label.name for label in snitch_labels}) != len(snitch_labels):
        raise AssertionError("duplicate active Snitch case label")
    if len({label.name for label in spatz_labels}) != len(spatz_labels):
        raise AssertionError("duplicate top-level Spatz case label")

    guard_counts = {
        guard: sum(label.guard == guard for label in snitch_labels)
        for guard in ("always", "ifdef TARGET_SPATZ")
    }
    # Frozen-snapshot census. These fail on a changed extraction rather than
    # padding or truncating it to an expected row count.
    assert len(package) == 1063
    assert (snitch_start, snitch_end) == (552, 2641)
    assert len(snitch_labels) == 441
    assert guard_counts == {"always": 199, "ifdef TARGET_SPATZ": 242}
    assert (spatz_start, spatz_end) == (55, 1774)
    assert len(spatz_labels) == 345

    active = [(label, package[label.name]) for label in snitch_labels]
    spatz_active = [(label, package[label.name]) for label in spatz_labels]
    assert all(pattern.mask & 0x7F == 0x7F for _, pattern in active)
    assert all(pattern.mask & 0x7F == 0x7F for _, pattern in spatz_active)
    write_decoder_inventory(
        RAW_DIR / "snitch_decoder_patterns.csv", SNITCH_PATH, snitch_labels, package
    )
    write_decoder_inventory(
        RAW_DIR / "spatz_decoder_patterns.csv", SPATZ_PATH, spatz_labels, package
    )

    active_custom: dict[int, list[tuple[DecoderLabel, Pattern]]] = {}
    spatz_custom: dict[int, list[tuple[DecoderLabel, Pattern]]] = {}
    for opcode, _ in CUSTOM_OPCODES:
        active_custom[opcode] = [
            item
            for item in active
            if item[1].mask & 0x7F == 0x7F and item[1].match & 0x7F == opcode
        ]
        spatz_custom[opcode] = [
            item
            for item in spatz_active
            if item[1].mask & 0x7F == 0x7F and item[1].match & 0x7F == opcode
        ]
    assert {opcode: len(rows) for opcode, rows in active_custom.items()} == {
        0x0B: 2,
        0x2B: 8,
        0x5B: 1,
        0x7B: 0,
    }
    assert all(not rows for rows in spatz_custom.values())

    custom_rows: list[dict[str, object]] = []
    for opcode, opcode_name in CUSTOM_OPCODES:
        for label, pattern in active_custom[opcode]:
            custom_rows.append(
                {
                    "opcode": f"0x{opcode:02X}",
                    "opcode_name": opcode_name,
                    "instruction_name": label.name,
                    "pattern": pattern.bits,
                    "match": f"0x{pattern.match:08X}",
                    "mask": f"0x{pattern.mask:08X}",
                    "decoder_location": f"{SNITCH_PATH.relative_to(REPO_ROOT)}:{label.decoder_line}",
                    "funct3_rule": field_rule(pattern.bits, 14, 12),
                    "funct7_rule": field_rule(pattern.bits, 31, 25),
                    "rd_rule": field_rule(pattern.bits, 11, 7),
                    "rs1_rule": field_rule(pattern.bits, 19, 15),
                    "rs2_rule": field_rule(pattern.bits, 24, 20),
                }
            )
    write_rows(RAW_DIR / "custom_opcode_inventory.csv", custom_rows)

    omerge = package["OMERGE"]
    assert any(label.name == "OMERGE" for label in snitch_labels)
    assert omerge.bits == "00000110000000000000?????1011011"
    assert (omerge.mask, omerge.match) == (0xFFFFF07F, 0x0600005B)
    omerge_rows: list[dict[str, object]] = []
    for rd in range(32):
        word = 0x0600005B | (rd << 7)
        names = [label.name for label, pattern in active if matches(word, pattern)]
        assert names == ["OMERGE"]
        omerge_rows.append(
            {
                "rd": f"x{rd}",
                "word": f"0x{word:08X}",
                "current_match_count": 1,
                "matching_active_instructions": "OMERGE",
            }
        )
    write_rows(RAW_DIR / "omerge_rd_matches.csv", omerge_rows)

    family_rows: list[dict[str, object]] = []
    rs1_rows: list[dict[str, object]] = []
    witness_rows: list[dict[str, object]] = []
    rd_rows: list[dict[str, object]] = []
    for opcode, opcode_name in CUSTOM_OPCODES:
        for funct3 in range(8):
            family_match = (funct3 << 12) | opcode
            possible = [
                (label, pattern)
                for label, pattern in active
                if constraints_compatible(
                    (FAMILY_MASK, family_match), (pattern.mask, pattern.match)
                )
            ]
            per_rs1 = {
                rs1: {"required": 0, "reserved": 0, "full": 0}
                for rs1 in range(32)
            }
            collision_labels: set[str] = set()
            first_witness: dict[str, tuple[int, int, int, int]] = {}
            required_collisions = 0
            reserved_collisions = 0
            full_collisions = 0
            omerge_cross_collisions = 0
            current_min = len(active) + 1
            current_max = -1

            # Concrete fixed-rd=x0 enumeration: 4096 cfg IDs x all 32 rs1.
            for cfg_id in range(FULL_MAX + 1):
                for rs1 in range(32):
                    word = candidate_word(opcode, funct3, cfg_id, rs1)
                    names = [
                        label.name
                        for label, pattern in possible
                        if matches(word, pattern)
                    ]
                    count = len(names)
                    current_min = min(current_min, count)
                    current_max = max(current_max, count)
                    if not count:
                        continue
                    full_collisions += 1
                    per_rs1[rs1]["full"] += 1
                    if cfg_id <= RESERVED_MAX:
                        reserved_collisions += 1
                        per_rs1[rs1]["reserved"] += 1
                    if cfg_id <= REQUIRED_MAX:
                        required_collisions += 1
                        per_rs1[rs1]["required"] += 1
                    if "OMERGE" in names:
                        omerge_cross_collisions += 1
                    collision_labels.update(names)
                    for name in names:
                        first_witness.setdefault(name, (cfg_id, rs1, 0, word))

            status = (
                "SAFE"
                if full_collisions == 0
                else "PARTIALLY_SAFE"
                if required_collisions == 0
                else "BLOCKED"
            )
            assert current_min >= 0 and current_max <= 1
            omerge_words_matching_candidate = sum(
                ((0x0600005B | (rd << 7)) & FAMILY_MASK) == family_match
                for rd in range(32)
            )
            assert omerge_words_matching_candidate == omerge_cross_collisions

            for rs1 in range(32):
                rs1_rows.append(
                    {
                        "opcode": f"0x{opcode:02X}",
                        "opcode_name": opcode_name,
                        "funct3": f"{funct3:03b}",
                        "rs1": f"x{rs1}",
                        "required_words_tested": REQUIRED_MAX + 1,
                        "required_collision_count": per_rs1[rs1]["required"],
                        "reserved_words_tested": RESERVED_MAX + 1,
                        "reserved_collision_count": per_rs1[rs1]["reserved"],
                        "full_words_tested": FULL_MAX + 1,
                        "full_collision_count": per_rs1[rs1]["full"],
                    }
                )
            for name, (cfg_id, rs1, rd, word) in sorted(first_witness.items()):
                witness_rows.append(
                    {
                        "opcode": f"0x{opcode:02X}",
                        "opcode_name": opcode_name,
                        "funct3": f"{funct3:03b}",
                        "colliding_instruction": name,
                        "cfg_id": f"0x{cfg_id:03X}",
                        "rs1": f"x{rs1}",
                        "rd": f"x{rd}",
                        "word": f"0x{word:08X}",
                    }
                )

            # Enumerate every rd. For each fixed rd, count the remaining
            # imm12/rs1 cube exactly from the real pattern mask. Pairwise
            # disjointness is checked before counts are summed.
            rd_nonzero_collisions = 0
            rd_nonzero_labels: set[str] = set()
            for rd in range(32):
                fixed_match = family_match | (rd << 7)
                rd_possible = [
                    (label, pattern)
                    for label, pattern in active
                    if constraints_compatible(
                        (FAMILY_MASK, fixed_match), (pattern.mask, pattern.match)
                    )
                ]
                for left_index, (_, left) in enumerate(rd_possible):
                    for _, right in rd_possible[left_index + 1 :]:
                        assert not constraints_compatible(
                            (FAMILY_MASK, fixed_match),
                            (left.mask, left.match),
                            (right.mask, right.match),
                        ), "overlapping existing patterns need union counting"
                rd_count = sum(
                    cube_assignment_count(pattern, FAMILY_MASK, fixed_match)
                    for _, pattern in rd_possible
                )
                names = sorted(label.name for label, _ in rd_possible)
                rd_rows.append(
                    {
                        "opcode": f"0x{opcode:02X}",
                        "opcode_name": opcode_name,
                        "funct3": f"{funct3:03b}",
                        "rd": f"x{rd}",
                        "concrete_words_covered": 1 << 17,
                        "existing_collision_count": rd_count,
                        "colliding_instructions": ";".join(names),
                    }
                )
                if rd == 0:
                    assert rd_count == full_collisions
                else:
                    rd_nonzero_collisions += rd_count
                    rd_nonzero_labels.update(names)

            family_rows.append(
                {
                    "opcode": f"0x{opcode:02X}",
                    "opcode_name": opcode_name,
                    "format": "I-type-like",
                    "funct3": f"{funct3:03b}",
                    "funct7_or_imm_rule": "imm12=cfg_id; full 0x000..0xFFF",
                    "rd_rule": "rd=x0 (bits 11:7=00000)",
                    "rs1_rule": "rs1=x0..x31; all enumerated",
                    "rs2_rule": "N/A; bits 24:20 are imm12[4:0]",
                    "cfg_id_range_tested": "required 0x000..0x009; reserved 0x000..0x0FF; full 0x000..0xFFF",
                    "concrete_words_tested": (FULL_MAX + 1) * 32,
                    "existing_collision_count": full_collisions,
                    "colliding_instructions": ";".join(sorted(collision_labels)),
                    "status": status,
                    "notes": "current active Snitch/TARGET_SPATZ decoder",
                    "required_words_tested": (REQUIRED_MAX + 1) * 32,
                    "required_collision_count": required_collisions,
                    "required_safe": "yes" if required_collisions == 0 else "no",
                    "reserved_words_tested": (RESERVED_MAX + 1) * 32,
                    "reserved_collision_count": reserved_collisions,
                    "reserved_safe": "yes" if reserved_collisions == 0 else "no",
                    "full_words_tested": (FULL_MAX + 1) * 32,
                    "full_collision_count": full_collisions,
                    "full_safe": "yes" if full_collisions == 0 else "no",
                    "candidate_mask": f"0x{FAMILY_MASK:08X}",
                    "candidate_match": f"0x{family_match:08X}",
                    "current_match_count_min": current_min,
                    "current_match_count_max": current_max,
                    "hypothetical_match_count_min": current_min + 1,
                    "hypothetical_match_count_max": current_max + 1,
                    "omerge_cross_collision_count": omerge_cross_collisions,
                    "omerge_words_matching_candidate": omerge_words_matching_candidate,
                    "rd_nonzero_words_tested": (FULL_MAX + 1) * 32 * 31,
                    "rd_nonzero_collision_count": rd_nonzero_collisions,
                    "rd_nonzero_colliding_instructions": ";".join(
                        sorted(rd_nonzero_labels)
                    ),
                }
            )

    family_fields = list(family_rows[0])
    for path in (AUDIT_DIR / "candidate_families.csv", RAW_DIR / "family_range_results.csv"):
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=family_fields, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(family_rows)
    (RAW_DIR / "family_range_results.json").write_text(
        json.dumps(family_rows, indent=2) + "\n"
    )
    write_rows(RAW_DIR / "rs1_collision_matrix.csv", rs1_rows)
    write_rows(RAW_DIR / "collision_witnesses.csv", witness_rows)
    write_rows(RAW_DIR / "rd_variation_results.csv", rd_rows)

    status_counts = {
        status: sum(row["status"] == status for row in family_rows)
        for status in ("SAFE", "PARTIALLY_SAFE", "BLOCKED")
    }
    assert status_counts == {"SAFE": 22, "PARTIALLY_SAFE": 1, "BLOCKED": 9}
    safe_rows = [row for row in family_rows if row["status"] == "SAFE"]
    assert all(row["current_match_count_min"] == 0 for row in safe_rows)
    assert all(row["current_match_count_max"] == 0 for row in safe_rows)
    assert all(row["hypothetical_match_count_min"] == 1 for row in safe_rows)
    assert all(row["hypothetical_match_count_max"] == 1 for row in safe_rows)

    expected_counts = {
        ("0x0B", f"{funct3:03b}"): (320, 8192, 131072)
        for funct3 in range(8)
    }
    expected_counts[("0x2B", "000")] = (320, 5216, 5216)
    expected_counts[("0x5B", "000")] = (0, 1, 1)
    for row in family_rows:
        expected = expected_counts.get(
            (str(row["opcode"]), str(row["funct3"])), (0, 0, 0)
        )
        actual = (
            row["required_collision_count"],
            row["reserved_collision_count"],
            row["full_collision_count"],
        )
        assert actual == expected, (row["opcode"], row["funct3"], actual, expected)

    head = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    summary = {
        "schema": "phase8a-omcfg-instruction-space-audit-v1",
        "audited_head": head,
        "checker": {
            "path": str(Path(__file__).resolve().relative_to(REPO_ROOT)),
            "sha256": sha256(Path(__file__).resolve()),
        },
        "sources": {
            str(PKG_PATH.relative_to(REPO_ROOT)): sha256(PKG_PATH),
            str(SNITCH_PATH.relative_to(REPO_ROOT)): sha256(SNITCH_PATH),
            str(SPATZ_PATH.relative_to(REPO_ROOT)): sha256(SPATZ_PATH),
        },
        "package_pattern_count": len(package),
        "snitch": {
            "case_start": snitch_start,
            "case_end": snitch_end,
            "active_label_count": len(snitch_labels),
            "unique_name_count": len({label.name for label in snitch_labels}),
            "guard_counts": guard_counts,
            "custom_opcode_active_counts": {
                f"0x{opcode:02X}": len(active_custom[opcode])
                for opcode, _ in CUSTOM_OPCODES
            },
        },
        "spatz": {
            "case_start": spatz_start,
            "case_end": spatz_end,
            "active_label_count": len(spatz_labels),
            "unique_name_count": len({label.name for label in spatz_labels}),
            "custom_opcode_active_count": sum(map(len, spatz_custom.values())),
        },
        "omerge": {
            "pattern": omerge.bits,
            "mask": f"0x{omerge.mask:08X}",
            "match": f"0x{omerge.match:08X}",
            "base_word": "0x0600005B",
            "word_rule": "0x0600005B | (rd << 7)",
            "rd_values_tested": 32,
            "all_exactly_one_active_match": True,
        },
        "candidate_search": {
            "family_count": len(family_rows),
            "fixed_rd0_concrete_words_per_family": 131072,
            "fixed_rd0_total_concrete_words": 32 * 131072,
            "rs1_values_per_family": 32,
            "required_cfg_range": "0x000..0x009",
            "reserved_cfg_range": "0x000..0x0FF",
            "full_cfg_range": "0x000..0xFFF",
            "status_counts": status_counts,
            "safe_current_match_range": [0, 0],
            "safe_hypothetical_match_range": [1, 1],
        },
        "r_type_fallback": "not run: complete SAFE I-type-like families exist",
    }
    (RAW_DIR / "audit_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    inventory_rows = [
        {
            "scope": "riscv_instr_32bit_package_patterns",
            "count": len(package),
            "notes": "declarations; only case-referenced labels are active",
        },
        {
            "scope": "snitch_TARGET_SPATZ_top_case_labels",
            "count": len(snitch_labels),
            "notes": f"case lines {snitch_start}..{snitch_end}; 199 always + 242 TARGET_SPATZ",
        },
        {
            "scope": "spatz_downstream_top_case_labels",
            "count": len(spatz_labels),
            "notes": f"case lines {spatz_start}..{spatz_end}; zero custom opcode labels",
        },
    ]
    write_rows(RAW_DIR / "decoder_inventory.csv", inventory_rows)

    result_lines = [
        f"audited_head={head}",
        f"package_32bit_patterns={len(package)}",
        f"snitch_active_labels={len(snitch_labels)}",
        f"snitch_guard_counts={guard_counts}",
        f"spatz_top_labels={len(spatz_labels)}",
        "omerge_rd_x0_x31_exactly_one=PASS",
        "families=32",
        "fixed_rd0_concrete_words_total=4194304",
        "rs1_matrix_rows=1024",
        "rd_variation_rows=1024",
        f"status_counts={status_counts}",
        "safe_current_matches=0",
        "safe_hypothetical_matches=1",
        "result=PASS",
    ]
    (RAW_DIR / "audit_results.txt").write_text("\n".join(result_lines) + "\n")
    print(
        "PASS: parsed current RTL; "
        f"package={len(package)}, Snitch={len(snitch_labels)}, Spatz={len(spatz_labels)}"
    )
    print("PASS: OMERGE rd=x0..x31 each has exactly one active match")
    print(
        "PASS: 32 I-type-like families, 4,194,304 fixed-rd0 words; "
        "SAFE=22, PARTIALLY_SAFE=1, BLOCKED=9"
    )
    print("PASS: every SAFE word has 0 current matches and 1 after hypothetical insertion")


if __name__ == "__main__":
    main()
