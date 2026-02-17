#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

HEALTH_URL="${SMOKE_HEALTH_URL:-http://127.0.0.1:9754/healthz}"
MAX_HEALTH_RETRIES="${SMOKE_MAX_HEALTH_RETRIES:-30}"
MAX_ARTIFACT_RETRIES="${SMOKE_MAX_ARTIFACT_RETRIES:-30}"
SLEEP_SECONDS="${SMOKE_RETRY_INTERVAL_SECONDS:-2}"
SIMULATE_FAILURE="${SMOKE_FORCE_FAIL:-0}"

if [[ "${1:-}" == "--simulate-failure" ]]; then
  SIMULATE_FAILURE="1"
fi

RUN_PROGRESS_PATH="var/artifacts/run_progress.json"
RUN_COMPLETE_PATH="var/artifacts/run_complete.json"

cleanup() {
  docker-compose down >/dev/null 2>&1 || true
}

collect_diagnostics() {
  local reason="$1"
  echo "[smoke] FAILED: ${reason}"
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

trap cleanup EXIT

echo "[smoke] starting live daemon container"
docker-compose down --remove-orphans >/dev/null 2>&1 || true
docker-compose up -d --build || collect_diagnostics "failed_to_start_container"

echo "[smoke] waiting for health endpoint: ${HEALTH_URL}"
health_ok=0
for _ in $(seq 1 "$MAX_HEALTH_RETRIES"); do
  if curl -fsS "$HEALTH_URL" >/dev/null; then
    health_ok=1
    break
  fi
  sleep "$SLEEP_SECONDS"
done

if [[ "$health_ok" -ne 1 ]]; then
  collect_diagnostics "health_endpoint_unreachable"
fi

echo "[smoke] waiting for artifacts: ${RUN_PROGRESS_PATH}, ${RUN_COMPLETE_PATH}"
artifacts_ok=0
for _ in $(seq 1 "$MAX_ARTIFACT_RETRIES"); do
  if [[ -f "$RUN_PROGRESS_PATH" && -f "$RUN_COMPLETE_PATH" ]]; then
    artifacts_ok=1
    break
  fi
  sleep "$SLEEP_SECONDS"
done

if [[ "$artifacts_ok" -ne 1 ]]; then
  collect_diagnostics "required_artifacts_not_found"
fi

if [[ "$SIMULATE_FAILURE" == "1" ]]; then
  collect_diagnostics "simulated_failure"
fi

echo "[smoke] SUCCESS: daemon startup, health, and artifact checks passed"
exit 0
