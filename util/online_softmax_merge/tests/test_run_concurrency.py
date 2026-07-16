# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import json
import struct
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

import run_concurrency as runner  # noqa: E402
import run_experiments as common  # noqa: E402


def bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def command(
    status: str = "pass", returncode: int | None = 0
) -> common.CommandRecord:
    return common.CommandRecord(
        argv=["sim", "test.elf"],
        command="sim test.elf",
        start_utc="start",
        end_utc="end",
        returncode=returncode,
        status=status,
        timeout_seconds=30,
        log_path="simulator.log",
    )


def raw_meta(case: common.Case) -> dict[str, object]:
    layout = runner.layout_bytes(case.n, case.d)
    return {
        "schema_version": 1,
        "N": case.n,
        "D": case.d,
        "repeats": case.repeats,
        "include_baselines": 1,
        "phase_start": 0,
        "phase_count": 16,
        "phase_step_bytes": 8,
        "phase_period_bytes": 128,
        "smu_phase_base_offset": 256,
        "stream_elements": runner.STREAM_ELEMENTS,
        "stream_array_bytes": runner.STREAM_ARRAY_BYTES,
        "stream_bytes_per_workload": runner.STREAM_BYTES,
        "stream_source_destination_spacing": runner.STREAM_SPACING_BYTES,
        "stream_avl_cap": runner.STREAM_AVL_CAP,
        "stream_tail_elements": runner.STREAM_TAIL_ELEMENTS,
        "register_iterations": 100,
        "register_target_cycles_hi": 0,
        "register_target_cycles_lo": 100,
        "poll_backoff_iterations": runner.POLL_BACKOFF_ITERATIONS,
        "poll_backoff_cycles_hi": 0,
        "poll_backoff_cycles_lo": 10,
        "max_status_reads": 4096,
        "merge_footprint_bytes": layout["merge_footprint_bytes"],
        "merge_allocation_bytes": layout["merge_allocation_bytes"],
        "stream_allocation_bytes": layout["stream_allocation_bytes"],
        "tcdm_capacity_bytes": runner.TCDM_CAPACITY_BYTES,
    }


def raw_record(
    case: common.Case,
    scenario: str,
    phase: int,
    repeat: int,
    invocation: int = -1,
) -> dict[str, object]:
    has_stream = scenario in {"C0_STREAM", "C2", "C3_CORE", "C3"}
    has_register = scenario in {"C0_REG", "C1"}
    is_smu = scenario in runner.SMU_SCENARIOS
    smu_phase = 3
    core_phase = (smu_phase + phase // 8) % 16 if has_stream else runner.UINT32_MAX
    total_cycles = 100 if not has_stream else 220
    core_cycles = 100 if not has_stream else 200
    if scenario == "C0_STREAM" or scenario == "C3_CORE":
        total_cycles = core_cycles
    return {
        "schema_version": 1,
        "scenario": scenario,
        "repeat": repeat,
        "N": case.n,
        "D": case.d,
        "phase_bytes": phase,
        "relative_phase_bytes": phase if has_stream else runner.UINT32_MAX,
        "destination_relative_phase_bytes": (
            phase if has_stream else runner.UINT32_MAX
        ),
        "smu_bank_phase": smu_phase,
        "core_source_bank_phase": core_phase,
        "core_destination_bank_phase": core_phase,
        "smu_invocation": invocation,
        "total_cycles_hi": total_cycles >> 32,
        "total_cycles_lo": total_cycles,
        "core_cycles_hi": core_cycles >> 32,
        "core_cycles_lo": core_cycles,
        "tcdm_accessed": 100,
        "tcdm_congested": 10,
        "status_after_core": 1 if is_smu else 0,
        "status_reads": 2 if is_smu else 0,
        "busy_status_reads": 1 if is_smu else 0,
        "poll_backoff_calls": 1 if is_smu else 0,
        "poll_backoff_iterations": runner.POLL_BACKOFF_ITERATIONS,
        "poll_checksum": 1 if is_smu else 0,
        "core_checksum": 1 if has_register else 0,
        "status_reads_during_core": 0,
        "counter_reads_inside_window": 0,
        "register_iterations": 100 if has_register else 0,
        "core_elements": runner.STREAM_ELEMENTS if has_stream else 0,
        "core_bytes": runner.STREAM_BYTES if has_stream else 0,
        "stream_array_bytes": (
            runner.STREAM_ARRAY_BYTES if has_stream else 0
        ),
        "stream_tail_elements": (
            runner.STREAM_TAIL_ELEMENTS if has_stream else 0
        ),
        "merge_checked": case.n * (case.d + 2) if is_smu else 0,
        "merge_mismatches": 0,
        "merge_max_abs_bits": bits(0.0),
        "core_checked": (
            runner.STREAM_ELEMENTS if has_stream else 1 if has_register else 0
        ),
        "core_mismatches": 0,
        "failure_index": 0,
        "expected_bits": 0,
        "actual_bits": 0,
        "status": "pass",
    }


def raw_fsm(case: common.Case, invocation: int) -> dict[str, object]:
    return {
        "schema_version": 1,
        "invocation": invocation,
        "N": case.n,
        "D": case.d,
        "terminal_state": "DONE",
        "load_scalar_cycles": 10,
        "compute_scalar_cycles": 10,
        "compute_weight_cycles": 10,
        "store_scalar_cycles": 10,
        "update_vector_cycles": 60,
        "busy_cycles": 100,
    }


def raw_terminal(
    case: common.Case, status: str
) -> dict[str, object]:
    record = raw_record(case, "ALL", runner.UINT32_MAX, -1)
    record["status"] = status
    return record


def full_schedule(
    case: common.Case,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    invocation = 0
    for scenario in ("C0_SMU", "C0_REG", "C0_STREAM", "C1", "C2"):
        phase = (
            0
            if scenario in {"C0_STREAM", "C2"}
            else runner.UINT32_MAX
        )
        for repeat in range(-1, case.repeats):
            is_smu = scenario in runner.SMU_SCENARIOS
            records.append(
                raw_record(
                    case,
                    scenario,
                    phase,
                    repeat,
                    invocation if is_smu else -1,
                )
            )
            if is_smu:
                invocation += 1
    for phase in runner.PHASES:
        for scenario in ("C3_CORE", "C3"):
            for repeat in range(-1, case.repeats):
                is_smu = scenario == "C3"
                records.append(
                    raw_record(
                        case,
                        scenario,
                        phase,
                        repeat,
                        invocation if is_smu else -1,
                    )
                )
                if is_smu:
                    invocation += 1
    fsm = [raw_fsm(case, item) for item in range(invocation)]
    return records, fsm


class RunConcurrencyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.case = common.Case(8, 32, 1, "main", 3, 30)

    def test_layout_includes_stream_workspace(self) -> None:
        layout = runner.layout_bytes(8, 32)
        self.assertEqual(layout["merge_footprint_bytes"], 4352)
        self.assertEqual(layout["merge_allocation_bytes"], 4352)
        self.assertEqual(layout["stream_allocation_bytes"], 16772)
        self.assertEqual(layout["combined_allocation_bytes"], 21124)

    def test_low_perturbation_simulator_configuration_passes(self) -> None:
        configuration = {
            "schema_version": 1,
            "profile": "low_perturbation",
            "dasm_trace_enabled": False,
            "fsm_observer_enabled": True,
        }
        records, errors = runner.parse_simulator_configuration(
            runner.SIM_CONFIG_PREFIX + json.dumps(configuration)
        )
        self.assertEqual(records, [configuration])
        self.assertEqual(errors, [])

    def test_default_simulator_configuration_is_rejected(self) -> None:
        configuration = {
            "schema_version": 1,
            "profile": "default",
            "dasm_trace_enabled": True,
            "fsm_observer_enabled": True,
        }
        _, errors = runner.parse_simulator_configuration(
            runner.SIM_CONFIG_PREFIX + json.dumps(configuration)
        )
        self.assertEqual(
            {error["kind"] for error in errors},
            {"simulator_configuration_profile", "simulator_dasm_gate"},
        )

    def test_parse_three_structured_record_types_and_malformed(self) -> None:
        record = raw_record(self.case, "C0_SMU", 0, -1, 0)
        meta = raw_meta(self.case)
        fsm = raw_fsm(self.case, 0)
        output = "\n".join(
            (
                runner.RECORD_PREFIX + json.dumps(record),
                runner.META_PREFIX + json.dumps(meta),
                runner.FSM_PREFIX + json.dumps(fsm),
                runner.RECORD_PREFIX + "{bad",
            )
        )
        records, metadata, fsms, errors = runner.parse_prefixed_json(output)
        self.assertEqual(records, [record])
        self.assertEqual(metadata, [meta])
        self.assertEqual(fsms, [fsm])
        self.assertEqual(errors[0]["kind"], "malformed_structured_json")

    def test_complete_schedule_and_pairing_pass(self) -> None:
        records, fsms = full_schedule(self.case)
        output = runner.PASS_BANNER
        errors = runner.validate_complete_schedule(
            records, [raw_meta(self.case)], fsms, self.case, output
        )
        self.assertEqual(errors, [])
        normalized, metadata, normalized_fsm, failures = runner.normalize_run(
            records,
            [raw_meta(self.case)],
            fsms,
            self.case,
            command(),
            output,
            [],
        )
        self.assertEqual(failures, [])
        self.assertEqual(len(normalized), 148)
        self.assertEqual(len(metadata), 1)
        self.assertEqual(len(normalized_fsm), 76)
        self.assertTrue(all(item["status"] == "pass" for item in normalized))
        self.assertEqual(metadata[0]["register_target_cycles"], 100)

    def test_missing_phase_is_tool_error_and_retained(self) -> None:
        records, fsms = full_schedule(self.case)
        records.pop()
        normalized, _, _, failures = runner.normalize_run(
            records,
            [raw_meta(self.case)],
            fsms,
            self.case,
            command(),
            runner.PASS_BANNER,
            [],
        )
        self.assertTrue(failures)
        self.assertTrue(all(item["status"] == "tool_error" for item in normalized))
        self.assertEqual(normalized[-1]["scenario"], "ALL")

    def test_host_timeout_keeps_partial_records_and_adds_terminal(self) -> None:
        partial = [raw_record(self.case, "C0_SMU", 0, -1, 0)]
        normalized, _, normalized_fsm, failures = runner.normalize_run(
            partial,
            [raw_meta(self.case)],
            [raw_fsm(self.case, 0)],
            self.case,
            command("timeout", -15),
            "HOST_TIMEOUT seconds=30",
            [],
        )
        self.assertTrue(failures)
        self.assertEqual(len(normalized_fsm), 1)
        self.assertEqual(normalized[0]["target_status"], "pass")
        self.assertEqual(normalized[0]["status"], "timeout")
        self.assertEqual(normalized[-1]["scenario"], "ALL")
        self.assertEqual(normalized[-1]["status"], "timeout")

    def test_malformed_empty_output_becomes_tool_error(self) -> None:
        normalized, metadata, fsms, failures = runner.normalize_run(
            [],
            [],
            [],
            self.case,
            command(),
            "",
            [{"kind": "malformed_structured_json"}],
        )
        self.assertEqual(metadata, [])
        self.assertEqual(fsms, [])
        self.assertTrue(failures)
        self.assertEqual(normalized[0]["scenario"], "ALL")
        self.assertEqual(normalized[0]["status"], "tool_error")

    def test_synthetic_capacity_and_unsupported_are_explicit(self) -> None:
        for status in ("capacity_skip", "unsupported"):
            with self.subTest(status=status):
                record = runner.synthetic_record(self.case, status, "reason")
                self.assertEqual(record["scenario"], "ALL")
                self.assertEqual(record["status"], status)
                self.assertEqual(record["failure_reason"], "reason")
                self.assertIsNone(record["total_cycles"])

    def test_target_terminal_status_skips_full_schedule_validation(self) -> None:
        for status in ("capacity_skip", "unsupported"):
            with self.subTest(status=status):
                normalized, metadata, fsms, failures = runner.normalize_run(
                    [raw_terminal(self.case, status)],
                    [],
                    [],
                    self.case,
                    command(),
                    "",
                    [],
                )
                self.assertEqual(failures, [])
                self.assertEqual(metadata, [])
                self.assertEqual(fsms, [])
                self.assertEqual(len(normalized), 1)
                self.assertEqual(normalized[0]["scenario"], "ALL")
                self.assertEqual(normalized[0]["status"], status)

    def test_invalid_terminal_or_numeric_output_becomes_tool_error(self) -> None:
        terminal = raw_terminal(self.case, "capacity_skip")
        normalized, _, _, failures = runner.normalize_run(
            [terminal],
            [raw_meta(self.case)],
            [],
            self.case,
            command(),
            "",
            [],
        )
        self.assertTrue(failures)
        self.assertEqual(normalized[0]["status"], "tool_error")

        records, fsms = full_schedule(self.case)
        records[0]["phase_bytes"] = "not-an-integer"
        records[1]["total_cycles_lo"] = "not-an-integer"
        normalized, _, _, failures = runner.normalize_run(
            records,
            [raw_meta(self.case)],
            fsms,
            self.case,
            command(),
            runner.PASS_BANNER,
            [],
        )
        self.assertTrue(failures)
        self.assertTrue(
            all(record["status"] == "tool_error" for record in normalized)
        )

    def test_disassembly_gate_accepts_register_only_and_rvv_tail_loop(self) -> None:
        disassembly = """
00000100 <online_merge_register_workload>:
 100: mv a0,a1
 104: addi a0,a0,-1
 108: bnez a0,100 <online_merge_register_workload>
 10c: ret
00000200 <online_merge_concurrency_stream>:
 200: vsetvli t0,a2,e32,m8,ta,ma
 204: vle32.v v8,(a0)
 208: vse32.v v8,(a1)
 20c: addi a2,a2,-1
 210: bnez a2,200 <online_merge_concurrency_stream>
 214: ret
"""
        snippets, errors = runner.inspect_concurrency_disassembly(disassembly)
        self.assertEqual(errors, [])
        self.assertEqual(set(snippets), {runner.REGISTER_SYMBOL, runner.STREAM_SYMBOL})

    def test_disassembly_gate_rejects_register_memory_and_unknown_rvv(self) -> None:
        disassembly = """
00000100 <online_merge_register_workload>:
 100: lw a0,0(sp)
 104: bnez a0,100 <online_merge_register_workload>
00000200 <online_merge_concurrency_stream>:
 200: <unknown>
 204: bnez a2,200 <online_merge_concurrency_stream>
"""
        _, errors = runner.inspect_concurrency_disassembly(disassembly)
        joined = "\n".join(errors)
        self.assertIn("memory instructions", joined)
        self.assertIn("stack pointer", joined)
        self.assertIn("lacks vsetvli", joined)
        self.assertIn("undecoded", joined)

    def test_output_root_is_external_named_and_empty(self) -> None:
        repo = Path("/tmp/repository").resolve()
        with self.assertRaises(ValueError):
            runner.validate_output_root(repo / "work-online-merge-x", repo)
        with self.assertRaises(ValueError):
            runner.validate_output_root(Path("/tmp/results"), repo)
        with tempfile.TemporaryDirectory(prefix="work-online-merge-test-") as temp:
            root = Path(temp)
            runner.validate_output_root(root, repo)
            (root / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.validate_output_root(root, repo)

    def test_options_and_case_validation(self) -> None:
        args = Namespace(
            timeout_seconds=1,
            configure_timeout_seconds=1,
            build_timeout_seconds=1,
            disassembly_timeout_seconds=1,
            jobs=1,
            include_baselines=True,
            phase_start=0,
            phase_count=16,
        )
        runner.validate_options(args)
        args.jobs = 0
        with self.assertRaises(ValueError):
            runner.validate_options(args)

    def test_phase_shard_schedule_is_exact(self) -> None:
        phases = runner.selected_phases(4, 3)
        self.assertEqual(phases, (32, 40, 48))
        keys = runner.expected_record_keys(
            self.case.repeats, False, phases
        )
        self.assertEqual(len(keys), 24)
        self.assertEqual(
            runner.expected_smu_invocations(
                self.case.repeats, False, phases
            ),
            12,
        )
        self.assertEqual(
            {key[0] for key in keys}, {"C3_CORE", "C3"}
        )
        with self.assertRaises(ValueError):
            runner.selected_phases(15, 2)

    def test_phase_only_complete_schedule_passes(self) -> None:
        phases = runner.selected_phases(4, 3)
        records = []
        invocation = 0
        for phase in phases:
            for scenario in ("C3_CORE", "C3"):
                for repeat in range(-1, self.case.repeats):
                    is_smu = scenario == "C3"
                    records.append(
                        raw_record(
                            self.case,
                            scenario,
                            phase,
                            repeat,
                            invocation if is_smu else -1,
                        )
                    )
                    if is_smu:
                        invocation += 1
        meta = raw_meta(self.case)
        meta.update(
            {
                "include_baselines": 0,
                "phase_start": 4,
                "phase_count": 3,
                "register_iterations": 0,
                "register_target_cycles_hi": 0,
                "register_target_cycles_lo": 0,
            }
        )
        fsms = [raw_fsm(self.case, item) for item in range(invocation)]
        errors = runner.validate_complete_schedule(
            records,
            [meta],
            fsms,
            self.case,
            runner.PASS_BANNER,
            False,
            4,
            phases,
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
