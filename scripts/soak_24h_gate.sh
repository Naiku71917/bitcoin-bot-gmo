#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

SOAK_TOTAL_ITERATIONS="${SOAK_TOTAL_ITERATIONS:-288}"
SOAK_INTERVAL_SECONDS="${SOAK_INTERVAL_SECONDS:-300}"
HEALTH_URL="${SMOKE_HEALTH_URL:-http://127.0.0.1:9754/healthz}"
RUN_PROGRESS_PATH="var/artifacts/run_progress.json"
RUN_COMPLETE_PATH="var/artifacts/run_complete.json"

started_at="$(date +%s)"
success_count=0

print_final_state() {
  local failed_iteration="$1"
  local total_iterations="$2"

  echo "[soak] failed_iteration=${failed_iteration}/${total_iterations}"

  health_status="$(curl -sS -o /dev/null -w "%{http_code}" "$HEALTH_URL" || true)"
  if [[ -z "$health_status" ]]; then
    health_status="unreachable"
  fi
  echo "[soak] final_health_status=${health_status}"

  echo "[soak] latest_artifacts"
  if [[ -f "$RUN_PROGRESS_PATH" ]]; then
    echo "[soak] run_progress.json"
    cat "$RUN_PROGRESS_PATH" || true
  else
    echo "[soak] run_progress.json not found"
  fi

  if [[ -f "$RUN_COMPLETE_PATH" ]]; then
    echo "[soak] run_complete.json"
    cat "$RUN_COMPLETE_PATH" || true
  else
    echo "[soak] run_complete.json not found"
  fi
}

for iteration in $(seq 1 "$SOAK_TOTAL_ITERATIONS"); do
  echo "[soak] START iteration=${iteration}/${SOAK_TOTAL_ITERATIONS}"

  if ! SMOKE_REPEAT_COUNT=1 SMOKE_KEEP_CONTAINER_ON_EXIT=1 bash scripts/smoke_live_daemon.sh; then
    print_final_state "$iteration" "$SOAK_TOTAL_ITERATIONS"
    echo "[soak] FAIL: smoke_iteration_failed"
    exit 1
  fi

  success_count=$((success_count + 1))

  if [[ "$iteration" -lt "$SOAK_TOTAL_ITERATIONS" ]]; then
    echo "[soak] WAIT interval_seconds=${SOAK_INTERVAL_SECONDS}"
    sleep "$SOAK_INTERVAL_SECONDS"
  fi

done

elapsed_seconds="$(( $(date +%s) - started_at ))"
echo "[soak] SUCCESS: passed_iterations=${success_count}/${SOAK_TOTAL_ITERATIONS} elapsed_seconds=${elapsed_seconds}"
exit 0
