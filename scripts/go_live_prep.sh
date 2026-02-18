#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

LOG_PATH="${GO_LIVE_PREP_LOG_PATH:-var/artifacts/go_live_prep.log}"
SUMMARY_PATH="${GO_LIVE_PREP_SUMMARY_PATH:-var/artifacts/go_live_prep_summary.json}"
SOAK_TOTAL_ITERATIONS_VALUE="${GO_LIVE_SOAK_TOTAL_ITERATIONS:-2}"
SOAK_INTERVAL_SECONDS_VALUE="${GO_LIVE_SOAK_INTERVAL_SECONDS:-1}"

mkdir -p "$(dirname "$LOG_PATH")"
: > "$LOG_PATH"

log_line() {
  local message="$1"
  echo "$message" | tee -a "$LOG_PATH"
}

write_summary() {
  local decision="$1"
  local failed_stage="$2"
  local next_action="$3"

  cat >"$SUMMARY_PATH" <<JSON
{
  "decision": "${decision}",
  "failed_stage": "${failed_stage}",
  "next_action": "${next_action}",
  "soak_total_iterations": ${SOAK_TOTAL_ITERATIONS_VALUE},
  "soak_interval_seconds": ${SOAK_INTERVAL_SECONDS_VALUE},
  "log_path": "${LOG_PATH}"
}
JSON
}

next_action_for_stage() {
  local stage="$1"
  case "$stage" in
    go_nogo_gate)
      echo "docs/operations.md の Go/No-Go 判定と最小ロールバック手順を実施"
      ;;
    soak_24h_gate)
      echo "scripts/soak_24h_gate.sh の failed_iteration と health/artifacts を確認し再実行"
      ;;
    monthly_report)
      echo "bash scripts/go_nogo_gate.sh 実行後に bash scripts/monthly_report.sh を再実行"
      ;;
    live_connectivity_drill)
      echo "GMO API認証情報とネットワークを確認し bash scripts/live_connectivity_drill.sh を再実行"
      ;;
    *)
      echo "docs/operations.md を参照して原因切り分けを実施"
      ;;
  esac
}

run_stage() {
  local stage="$1"
  shift

  log_line "[go-live-prep] START: ${stage}"
  if "$@" >>"$LOG_PATH" 2>&1; then
    log_line "[go-live-prep] PASS: ${stage}"
    return 0
  fi

  local next_action
  next_action="$(next_action_for_stage "$stage")"
  log_line "[go-live-prep] FAIL: ${stage}"
  log_line "[go-live-prep] NEXT_ACTION: ${next_action}"
  write_summary "NO-GO" "$stage" "$next_action"
  log_line "[go-live-prep] DECISION: NO-GO stage=${stage} next_action=${next_action}"
  exit 1
}

run_stage "go_nogo_gate" bash scripts/go_nogo_gate.sh
run_stage "soak_24h_gate" env SOAK_TOTAL_ITERATIONS="$SOAK_TOTAL_ITERATIONS_VALUE" SOAK_INTERVAL_SECONDS="$SOAK_INTERVAL_SECONDS_VALUE" bash scripts/soak_24h_gate.sh
run_stage "monthly_report" bash scripts/monthly_report.sh
run_stage "live_connectivity_drill" bash scripts/live_connectivity_drill.sh

write_summary "GO" "" "none"
log_line "[go-live-prep] DECISION: GO"
exit 0
