#!/usr/bin/env python3
"""Verify preserved external experiment roots and create Git indices."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import experiment_common as common


SET_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}")
TOP_LEVEL_FILES = (
    "run_manifest.json",
    "records.json",
    "records.csv",
    "failures.json",
    "commands.json",
    "artifact_manifest.json",
)


@dataclass(frozen=True)
class VerifiedRun:
    root: Path
    run_id: str
    manifest: dict[str, Any]
    index: dict[str, Any]
    artifact_count: int
    artifact_bytes: int


def load_json(path: Path, expected_type: type) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path}: {error}") from error
    if not isinstance(payload, expected_type):
        raise ValueError(
            f"{path} must contain {expected_type.__name__}"
        )
    return payload


def artifact_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("artifact path must be a nonempty string")
    path = Path(value)
    if path.is_absolute():
        return path
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"relative artifact escapes root: {value}") from error
    return resolved


def verify_artifacts(
    root: Path, entries: list[dict[str, Any]]
) -> tuple[int, int]:
    seen: set[str] = set()
    total_bytes = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"artifact {index} is not an object")
        path = artifact_path(root, entry.get("path"))
        identity = str(path)
        if identity in seen:
            raise ValueError(f"duplicate artifact path: {path}")
        seen.add(identity)
        if not path.is_file():
            raise ValueError(f"artifact is missing: {path}")
        expected_bytes = entry.get("bytes")
        if expected_bytes != path.stat().st_size:
            raise ValueError(
                f"artifact size mismatch: {path}: "
                f"{path.stat().st_size} != {expected_bytes}"
            )
        expected_hash = entry.get("sha256")
        actual_hash = common.sha256_file(path)
        if expected_hash != actual_hash:
            raise ValueError(
                f"artifact SHA256 mismatch: {path}: "
                f"{actual_hash} != {expected_hash}"
            )
        total_bytes += int(expected_bytes)
    return len(entries), total_bytes


def verify_run(root: Path) -> VerifiedRun:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"result root is not a directory: {root}")
    for name in TOP_LEVEL_FILES:
        if not (root / name).is_file():
            raise ValueError(f"result root is missing {name}: {root}")

    manifest = load_json(root / "run_manifest.json", dict)
    records = load_json(root / "records.json", list)
    failures = load_json(root / "failures.json", list)
    commands = load_json(root / "commands.json", list)
    artifact_entries = load_json(root / "artifact_manifest.json", list)
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or SET_NAME_PATTERN.fullmatch(run_id) is None:
        raise ValueError(f"invalid run_id in {root}: {run_id!r}")
    if manifest.get("end_utc") is None:
        raise ValueError(f"run did not record end_utc: {root}")
    if manifest.get("record_count") != len(records):
        raise ValueError(f"record_count mismatch in {root}")
    if manifest.get("failure_count") != len(failures):
        raise ValueError(f"failure_count mismatch in {root}")
    if any(not isinstance(item, dict) for item in records):
        raise ValueError(f"records contain a non-object in {root}")
    if any(not isinstance(item, dict) for item in failures):
        raise ValueError(f"failures contain a non-object in {root}")
    if any(not isinstance(item, dict) for item in commands):
        raise ValueError(f"commands contain a non-object in {root}")

    artifact_count, artifact_bytes = verify_artifacts(
        root, artifact_entries
    )
    hashes = {
        name: common.sha256_file(root / name) for name in TOP_LEVEL_FILES
    }
    index = {
        "schema_version": 1,
        "run_id": run_id,
        "artifact_root": str(root),
        "run_manifest_sha256": hashes["run_manifest.json"],
        "records_sha256": hashes["records.json"],
        "records_csv_sha256": hashes["records.csv"],
        "failures_sha256": hashes["failures.json"],
        "commands_sha256": hashes["commands.json"],
        "artifact_manifest_sha256": hashes["artifact_manifest.json"],
        "record_count": len(records),
        "failure_count": len(failures),
        "artifact_count": artifact_count,
        "artifact_bytes": artifact_bytes,
        "artifact_verification": "PASS",
    }
    return VerifiedRun(
        root=root,
        run_id=run_id,
        manifest=manifest,
        index=index,
        artifact_count=artifact_count,
        artifact_bytes=artifact_bytes,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=common.REPO_ROOT
    )
    parser.add_argument(
        "--result-root", type=Path, action="append", required=True
    )
    parser.add_argument("--set-name", required=True)
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    if SET_NAME_PATTERN.fullmatch(args.set_name) is None:
        raise SystemExit("--set-name is unsafe or invalid")
    git_commit = common.git_output(repo_root, "rev-parse", "HEAD")
    git_dirty = bool(common.git_output(repo_root, "status", "--porcelain"))
    if args.require_clean and git_dirty:
        raise SystemExit("--require-clean rejected a dirty Git worktree")

    try:
        verified = [verify_run(root) for root in args.result_root]
    except ValueError as error:
        raise SystemExit(f"external run verification failed: {error}") from error
    run_ids = [run.run_id for run in verified]
    roots = [str(run.root) for run in verified]
    if len(run_ids) != len(set(run_ids)):
        raise SystemExit("external run set contains duplicate run IDs")
    if len(roots) != len(set(roots)):
        raise SystemExit("external run set contains duplicate roots")
    if any(run.manifest.get("git_commit") != git_commit for run in verified):
        raise SystemExit("external run commit does not match current HEAD")
    if any(run.manifest.get("git_dirty") is not False for run in verified):
        raise SystemExit("external run set contains dirty-worktree evidence")

    raw_dir = repo_root / "experiments/raw"
    manifest_dir = repo_root / "experiments/manifests"
    destinations: list[Path] = []
    for run in verified:
        destinations.extend(
            (raw_dir / f"{run.run_id}.json", manifest_dir / f"{run.run_id}.json")
        )
    set_path = manifest_dir / f"{args.set_name}_index_set.json"
    destinations.append(set_path)
    existing = [path for path in destinations if path.exists()]
    if existing:
        raise SystemExit(
            "refusing to overwrite index paths: "
            + ", ".join(str(path) for path in existing)
        )

    for run in verified:
        common.write_json(raw_dir / f"{run.run_id}.json", run.index)
        common.write_json(
            manifest_dir / f"{run.run_id}.json", run.manifest
        )

    index_entries = []
    for run in verified:
        index_path = raw_dir / f"{run.run_id}.json"
        snapshot_path = manifest_dir / f"{run.run_id}.json"
        index_entries.append(
            {
                "run_id": run.run_id,
                "index_path": common.relative_or_absolute(
                    index_path, repo_root
                ),
                "index_sha256": common.sha256_file(index_path),
                "manifest_snapshot_path": common.relative_or_absolute(
                    snapshot_path, repo_root
                ),
                "manifest_snapshot_sha256": common.sha256_file(
                    snapshot_path
                ),
            }
        )
    set_manifest = {
        "schema_version": 1,
        "set_name": args.set_name,
        "indexed_utc": common.utc_now(),
        "git_commit": git_commit,
        "git_dirty_before_indexing": git_dirty,
        "indexer_path": common.relative_or_absolute(
            Path(__file__).resolve(), repo_root
        ),
        "indexer_sha256": common.sha256_file(Path(__file__).resolve()),
        "run_count": len(verified),
        "record_count": sum(
            int(run.index["record_count"]) for run in verified
        ),
        "failure_count": sum(
            int(run.index["failure_count"]) for run in verified
        ),
        "artifact_count": sum(run.artifact_count for run in verified),
        "artifact_bytes": sum(run.artifact_bytes for run in verified),
        "runs": index_entries,
    }
    common.write_json(set_path, set_manifest)
    print(f"index_set={set_path}")
    print(
        f"runs={len(verified)} records={set_manifest['record_count']} "
        f"failures={set_manifest['failure_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
