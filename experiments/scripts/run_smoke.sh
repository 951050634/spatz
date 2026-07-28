#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"

default_simulator="${repo_root}/hw/system/spatz_cluster/bin/spatz_cluster.vlt"
simulator="${ONLINE_MERGE_SIMULATOR:-${default_simulator}}"
jobs="${ONLINE_MERGE_JOBS:-8}"

PYTHONDONTWRITEBYTECODE=1 python3 \
  "${script_dir}/run_performance_matrix.py" \
  --repo-root "${repo_root}" \
  --case-file "${repo_root}/experiments/configs/p0_smoke_cases.json" \
  --simulator "${simulator}" \
  --profiles memory \
  --trials 3 \
  --jobs "${jobs}" \
  --suite smoke
