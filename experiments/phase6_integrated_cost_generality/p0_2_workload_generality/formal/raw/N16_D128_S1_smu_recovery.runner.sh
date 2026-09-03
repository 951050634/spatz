#!/usr/bin/env bash
set -u

RECOVERY_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="/home/wxt/work-online-merge-supplement"
ELF="/home/wxt/work-phase6-native-formal-117caff-r1/N16_D128_S1/spatzBenchmarks/test-spatzBenchmarks-native-online-attention-smu"
SIMULATOR="/home/wxt/spatz-archive/phase4/work-phase4-recip-sim/spatz_cluster.vlt"
PARTIAL_MANIFEST="/home/wxt/work-phase6-formal-117caff-r1/p0_2/formal/manifest.json"
META="${RECOVERY_DIR}/runner.meta"
STDOUT_LOG="${RECOVERY_DIR}/N16_D128_S1_smu.log"
STDERR_LOG="${RECOVERY_DIR}/N16_D128_S1_smu.stderr.log"

EXPECTED_COMMIT="117caff8109c0f6c32cf07a8322a3397307c8e14"
EXPECTED_ELF_SHA256="653ed7cccbe845e9f448b63313b6f654666a84d4edb037ca85e826fa8c5ea927"
EXPECTED_SIM_SHA256="8f85b204d064f1ced29d2fc27518754f8b018db0530cf2328a3a1062687c9138"

START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUNNER_PID="$$"
SESSION_ID="$(ps -o sid= -p "$$" 2>/dev/null | tr -d '[:space:]')"
[ -n "$SESSION_ID" ] || SESSION_ID="unknown"
COMMAND="${SIMULATOR} ${ELF}"

actual_commit="$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || true)"
git_status="$(git -C "$REPO_DIR" status --porcelain=v1 2>/dev/null || true)"
if [ -z "$git_status" ]; then
  git_status="clean"
fi
actual_elf_sha256="$(sha256sum "$ELF" 2>/dev/null | awk '{print $1}' || true)"
actual_sim_sha256="$(sha256sum "$SIMULATOR" 2>/dev/null | awk '{print $1}' || true)"

{
  printf 'RECOVERY_KIND phase6-p0-2-single-run-recovery\n'
  printf 'CASE N16_D128_S1\n'
  printf 'IMPLEMENTATION smu\n'
  printf 'WRAPPER_START_UTC %s\n' "$START_UTC"
  printf 'WRAPPER_PID %s\n' "$RUNNER_PID"
  printf 'SESSION_ID %s\n' "$SESSION_ID"
  printf 'CWD %s\n' "$REPO_DIR"
  printf 'COMMAND %s\n' "$COMMAND"
  printf 'GIT_COMMIT_EXPECTED %s\n' "$EXPECTED_COMMIT"
  printf 'GIT_COMMIT_ACTUAL %s\n' "$actual_commit"
  printf 'GIT_STATUS_BEFORE %s\n' "$git_status"
  printf 'PARTIAL_MANIFEST_READONLY %s\n' "$PARTIAL_MANIFEST"
  printf 'ELF_PATH %s\n' "$ELF"
  printf 'ELF_SHA256_EXPECTED %s\n' "$EXPECTED_ELF_SHA256"
  printf 'ELF_SHA256_ACTUAL %s\n' "$actual_elf_sha256"
  printf 'SIMULATOR_PATH %s\n' "$SIMULATOR"
  printf 'SIMULATOR_SHA256_EXPECTED %s\n' "$EXPECTED_SIM_SHA256"
  printf 'SIMULATOR_SHA256_ACTUAL %s\n' "$actual_sim_sha256"
  printf 'STDOUT_LOG %s\n' "$STDOUT_LOG"
  printf 'STDERR_LOG %s\n' "$STDERR_LOG"
  printf 'VALIDATION_STATUS pending\n'
} > "$META"

: > "$STDOUT_LOG"
: > "$STDERR_LOG"

validation_error=0
if [ "$actual_commit" != "$EXPECTED_COMMIT" ]; then
  printf 'validation failure: git commit expected=%s actual=%s\n' \
    "$EXPECTED_COMMIT" "$actual_commit" >> "$STDERR_LOG"
  validation_error=1
fi
if [ "$git_status" != "clean" ]; then
  printf 'validation failure: repository is not clean: %s\n' "$git_status" \
    >> "$STDERR_LOG"
  validation_error=1
fi
if [ "$actual_elf_sha256" != "$EXPECTED_ELF_SHA256" ]; then
  printf 'validation failure: ELF sha256 expected=%s actual=%s\n' \
    "$EXPECTED_ELF_SHA256" "$actual_elf_sha256" >> "$STDERR_LOG"
  validation_error=1
fi
if [ "$actual_sim_sha256" != "$EXPECTED_SIM_SHA256" ]; then
  printf 'validation failure: simulator sha256 expected=%s actual=%s\n' \
    "$EXPECTED_SIM_SHA256" "$actual_sim_sha256" >> "$STDERR_LOG"
  validation_error=1
fi
if [ ! -x "$ELF" ]; then
  printf 'validation failure: ELF is not executable: %s\n' "$ELF" >> "$STDERR_LOG"
  validation_error=1
fi
if [ ! -x "$SIMULATOR" ]; then
  printf 'validation failure: simulator is not executable: %s\n' "$SIMULATOR" \
    >> "$STDERR_LOG"
  validation_error=1
fi

if [ "$validation_error" -ne 0 ]; then
  RC=2
  validation_status="fail"
else
  validation_status="pass"
  printf 'VALIDATION_STATUS %s\n' "$validation_status" >> "$META"
  if ! cd "$REPO_DIR"; then
    printf 'run failure: cannot cd to %s\n' "$REPO_DIR" >> "$STDERR_LOG"
    RC=126
  else
    "$SIMULATOR" "$ELF" > "$STDOUT_LOG" 2> "$STDERR_LOG"
    RC=$?
  fi
fi

END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
STDOUT_SHA256="$(sha256sum "$STDOUT_LOG" | awk '{print $1}')"
STDERR_SHA256="$(sha256sum "$STDERR_LOG" | awk '{print $1}')"
{
  printf 'RETURN_CODE %s\n' "$RC"
  printf 'WRAPPER_END_UTC %s\n' "$END_UTC"
  printf 'STDOUT_SHA256 %s\n' "$STDOUT_SHA256"
  printf 'STDERR_SHA256 %s\n' "$STDERR_SHA256"
} >> "$META"
exit "$RC"
