#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

RUN_COMPLETE_PATH="${RUN_COMPLETE_PATH:-var/artifacts/run_complete.json}"
RUN_PROGRESS_PATH="${RUN_PROGRESS_PATH:-var/artifacts/run_progress.json}"
GO_NOGO_LOG_PATH="${GO_NOGO_LOG_PATH:-var/artifacts/go_nogo_gate.log}"
OUTPUT_DIR="${MONTHLY_OUTPUT_DIR:-var/artifacts/monthly}"

resolve_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "$PYTHON_BIN"
    return 0
  fi

  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  return 1
}

PYTHON_BIN="$(resolve_python_bin || true)"
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "[monthly-report] FAIL: python_not_found"
  echo "[monthly-report] NEXT_ACTION: set PYTHON_BIN or prepare python3/python"
  exit 1
fi

missing=()
for path in "$RUN_COMPLETE_PATH" "$RUN_PROGRESS_PATH" "$GO_NOGO_LOG_PATH"; do
  if [[ ! -f "$path" ]]; then
    missing+=("$path")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "[monthly-report] FAIL: missing_required_data"
  for path in "${missing[@]}"; do
    echo "[monthly-report] missing=${path}"
  done
  echo "[monthly-report] NEXT_ACTION: run 'bash scripts/go_nogo_gate.sh' to regenerate artifacts/logs"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "[monthly-report] START: generating monthly report"
"$PYTHON_BIN" - <<'PY' "$RUN_COMPLETE_PATH" "$RUN_PROGRESS_PATH" "$GO_NOGO_LOG_PATH" "$OUTPUT_DIR"
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

run_complete_path = Path(sys.argv[1])
run_progress_path = Path(sys.argv[2])
go_nogo_log_path = Path(sys.argv[3])
output_dir = Path(sys.argv[4])

run_complete = json.loads(run_complete_path.read_text(encoding="utf-8"))
run_progress = json.loads(run_progress_path.read_text(encoding="utf-8"))
go_nogo_lines = go_nogo_log_path.read_text(encoding="utf-8").splitlines()

decision_lines = [line for line in go_nogo_lines if "[go-nogo] DECISION:" in line]
last_decision = decision_lines[-1] if decision_lines else "[go-nogo] DECISION: unknown"

go_count = sum(1 for line in decision_lines if "DECISION: GO" in line)
no_go_count = sum(1 for line in decision_lines if "DECISION: NO-GO" in line)

completed_at = str(run_complete.get("completed_at", ""))
period_token_match = re.match(r"(\d{4})-(\d{2})", completed_at)
if period_token_match:
    period_token = f"{period_token_match.group(1)}{period_token_match.group(2)}"
    period_label = f"{period_token_match.group(1)}-{period_token_match.group(2)}"
else:
    now = datetime.now(UTC)
    period_token = now.strftime("%Y%m")
    period_label = now.strftime("%Y-%m")

summary = {
    "generated_at": datetime.now(UTC).isoformat(),
    "period": period_label,
    "schema_version": run_complete.get("schema_version"),
    "pipeline_mode": run_complete.get("pipeline", {}).get("mode"),
    "pipeline_status": run_complete.get("pipeline", {}).get("status"),
    "monitor_status": run_progress.get("monitor_status"),
    "reconnect_count": run_progress.get("reconnect_count"),
    "last_error": run_progress.get("last_error"),
    "go_nogo_last_decision": last_decision,
    "go_nogo_go_count": go_count,
    "go_nogo_no_go_count": no_go_count,
    "discord_status": run_complete.get("notifications", {}).get("discord", {}).get("status"),
    "discord_reason": run_complete.get("notifications", {}).get("discord", {}).get("reason"),
    "reason_codes": run_complete.get("pipeline_summary", {}).get("reason_codes", []),
    "stop_reason_codes": run_complete.get("pipeline_summary", {}).get("stop_reason_codes", []),
}

json_path = output_dir / f"monthly_report_{period_token}.json"
md_path = output_dir / f"monthly_report_{period_token}.md"

json_path.write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
    encoding="utf-8",
)

markdown = "\n".join(
    [
        f"# Monthly Report ({summary['period']})",
        "",
        f"- generated_at: {summary['generated_at']}",
        f"- schema_version: {summary['schema_version']}",
        f"- pipeline_mode: {summary['pipeline_mode']}",
        f"- pipeline_status: {summary['pipeline_status']}",
        f"- monitor_status: {summary['monitor_status']}",
        f"- reconnect_count: {summary['reconnect_count']}",
        f"- last_error: {summary['last_error']}",
        f"- go_nogo_last_decision: {summary['go_nogo_last_decision']}",
        f"- go_nogo_go_count: {summary['go_nogo_go_count']}",
        f"- go_nogo_no_go_count: {summary['go_nogo_no_go_count']}",
        f"- discord_status: {summary['discord_status']}",
        f"- discord_reason: {summary['discord_reason']}",
        f"- reason_codes: {summary['reason_codes']}",
        f"- stop_reason_codes: {summary['stop_reason_codes']}",
    ]
)
md_path.write_text(markdown + "\n", encoding="utf-8")

print(
    f"[monthly-report] SUCCESS: period={summary['period']} json={json_path} markdown={md_path}"
)
PY
