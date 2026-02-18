#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

SMOKE_REPEAT_COUNT_VALUE="${SMOKE_REPEAT_COUNT:-3}"
HEALTH_URL="${SMOKE_HEALTH_URL:-http://127.0.0.1:9754/healthz}"
METRICS_URL="${SMOKE_METRICS_URL:-http://127.0.0.1:9754/metrics}"
LOG_PATH="${GO_NOGO_LOG_PATH:-var/artifacts/go_nogo_gate.log}"
RETRY_COUNT="${GO_NOGO_RETRY_COUNT:-30}"
RETRY_INTERVAL="${GO_NOGO_RETRY_INTERVAL_SECONDS:-2}"

mkdir -p "$(dirname "$LOG_PATH")"
: > "$LOG_PATH"

log_line() {
  local message="$1"
  echo "$message" | tee -a "$LOG_PATH"
}

fail_with_stage() {
  local stage="$1"
  local reason="$2"
  log_line "[go-nogo] FAIL: ${stage} (${reason})"
  log_line "[go-nogo] NEXT_ACTION: docs/operations.md の『最小ロールバック手順』を実施"
  log_line "[go-nogo] DECISION: NO-GO stage=${stage} reason=${reason} next=rollback_runbook"
  exit 1
}

run_stage() {
  local stage="$1"
  shift

  log_line "[go-nogo] START: ${stage}"
  if "$@" >>"$LOG_PATH" 2>&1; then
    log_line "[go-nogo] PASS: ${stage}"
  else
    fail_with_stage "$stage" "command_failed"
  fi
}

wait_for_endpoint() {
  local url="$1"
  for _ in $(seq 1 "$RETRY_COUNT"); do
    if curl -fsS "$url" >/dev/null; then
      return 0
    fi
    sleep "$RETRY_INTERVAL"
  done
  return 1
}

run_stage "release_check" bash scripts/release_check.sh
run_stage "replay_check" bash scripts/replay_check.sh
run_stage "smoke_repeat" env SMOKE_REPEAT_COUNT="$SMOKE_REPEAT_COUNT_VALUE" bash scripts/smoke_live_daemon.sh
run_stage "restart_for_health_metrics" docker-compose up -d --build bot
run_stage "health_check" wait_for_endpoint "$HEALTH_URL"
run_stage "metrics_check" wait_for_endpoint "$METRICS_URL"

log_line "[go-nogo] DECISION: GO"
exit 0
