#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

HEALTH_URL="${SMOKE_HEALTH_URL:-http://127.0.0.1:9754/healthz}"
MAX_HEALTH_RETRIES="${SMOKE_MAX_HEALTH_RETRIES:-30}"
MAX_ARTIFACT_RETRIES="${SMOKE_MAX_ARTIFACT_RETRIES:-30}"
SLEEP_SECONDS="${SMOKE_RETRY_INTERVAL_SECONDS:-2}"
SIMULATE_FAILURE="${SMOKE_FORCE_FAIL:-0}"
REPEAT_COUNT="${SMOKE_REPEAT_COUNT:-1}"
KEEP_CONTAINER_ON_EXIT="${SMOKE_KEEP_CONTAINER_ON_EXIT:-0}"

if [[ "${1:-}" == "--simulate-failure" ]]; then
  SIMULATE_FAILURE="1"
fi

RUN_PROGRESS_PATH="var/artifacts/run_progress.json"
RUN_COMPLETE_PATH="var/artifacts/run_complete.json"

cleanup() {
  if [[ "$KEEP_CONTAINER_ON_EXIT" == "1" ]]; then
    return
  fi
  docker-compose down >/dev/null 2>&1 || true
}

collect_diagnostics() {
  local reason="$1"
  local iteration="$2"
  local total="$3"
  echo "[smoke] FAILED: ${reason}"
  echo "[smoke] failed_iteration=${iteration}/${total}"
  echo "[smoke] === docker-compose ps ==="
  docker-compose ps || true
  echo "[smoke] === docker-compose logs (tail 200) ==="
  docker-compose logs --tail=200 bot || true
  echo "[smoke] === artifacts ==="
  if [[ -f "$RUN_PROGRESS_PATH" ]]; then
    echo "[smoke] run_progress.json"
    cat "$RUN_PROGRESS_PATH" || true
  else
    echo "[smoke] run_progress.json not found"
  fi
  if [[ -f "$RUN_COMPLETE_PATH" ]]; then
    echo "[smoke] run_complete.json"
    cat "$RUN_COMPLETE_PATH" || true
  else
    echo "[smoke] run_complete.json not found"
  fi
  return 1
}

run_single_check() {
  local iteration="$1"
  local total="$2"

  echo "[smoke] starting live daemon container (${iteration}/${total})"
  docker-compose down --remove-orphans >/dev/null 2>&1 || true
  docker-compose up -d --build || collect_diagnostics "failed_to_start_container" "$iteration" "$total"

  echo "[smoke] waiting for health endpoint: ${HEALTH_URL} (${iteration}/${total})"
  health_ok=0
  for _ in $(seq 1 "$MAX_HEALTH_RETRIES"); do
    if curl -fsS "$HEALTH_URL" >/dev/null; then
      health_ok=1
      break
    fi
    sleep "$SLEEP_SECONDS"
  done

  if [[ "$health_ok" -ne 1 ]]; then
    collect_diagnostics "health_endpoint_unreachable" "$iteration" "$total"
  fi

  echo "[smoke] waiting for artifacts: ${RUN_PROGRESS_PATH}, ${RUN_COMPLETE_PATH} (${iteration}/${total})"
  artifacts_ok=0
  for _ in $(seq 1 "$MAX_ARTIFACT_RETRIES"); do
    if [[ -f "$RUN_PROGRESS_PATH" && -f "$RUN_COMPLETE_PATH" ]]; then
      artifacts_ok=1
      break
    fi
    sleep "$SLEEP_SECONDS"
  done

  if [[ "$artifacts_ok" -ne 1 ]]; then
    collect_diagnostics "required_artifacts_not_found" "$iteration" "$total"
  fi

  if [[ "$SIMULATE_FAILURE" == "1" ]]; then
    collect_diagnostics "simulated_failure" "$iteration" "$total"
  fi
}

trap cleanup EXIT

for iteration in $(seq 1 "$REPEAT_COUNT"); do
  run_single_check "$iteration" "$REPEAT_COUNT"
  echo "[smoke] iteration ${iteration}/${REPEAT_COUNT} passed"
done

echo "[smoke] SUCCESS: ${REPEAT_COUNT} iteration(s) passed (daemon startup, health, and artifact checks)"
exit 0
