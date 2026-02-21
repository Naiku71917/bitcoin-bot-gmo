#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

METRICS_URL="${ALERTS_METRICS_URL:-http://127.0.0.1:9754/metrics}"
ARTIFACT_PATH="${ALERTS_SANITY_ARTIFACT_PATH:-var/artifacts/alerts_sanity_check.json}"
FAILURES_THRESHOLD="${ALERTS_RUN_LOOP_FAILURES_THRESHOLD:-3}"
DEGRADED_THRESHOLD="${ALERTS_MONITOR_DEGRADED_THRESHOLD:-0}"
RECONNECTING_THRESHOLD="${ALERTS_MONITOR_RECONNECTING_THRESHOLD:-2}"

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
  echo "[alerts-sanity] FAIL: python_not_found"
  exit 1
fi

mkdir -p "$(dirname "$ARTIFACT_PATH")"

METRICS_RAW=""
if ! METRICS_RAW="$(curl -fsS "$METRICS_URL")"; then
  cat >"$ARTIFACT_PATH" <<JSON
{
  "passed": false,
  "cause": "endpoint_unreachable",
  "detail": "metrics_endpoint_unreachable",
  "metrics_url": "${METRICS_URL}"
}
JSON
  echo "[alerts-sanity] FAIL: endpoint_unreachable"
  echo "[alerts-sanity] artifact=${ARTIFACT_PATH}"
  exit 1
fi

"$PYTHON_BIN" - <<'PY' "$ARTIFACT_PATH" "$FAILURES_THRESHOLD" "$DEGRADED_THRESHOLD" "$RECONNECTING_THRESHOLD" "$METRICS_URL" "$METRICS_RAW"
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

artifact_path = Path(sys.argv[1])
failures_threshold = float(sys.argv[2])
degraded_threshold = float(sys.argv[3])
reconnecting_threshold = float(sys.argv[4])
metrics_url = sys.argv[5]
metrics_raw = sys.argv[6]

lines = [line.strip() for line in metrics_raw.splitlines() if line.strip() and not line.startswith("#")]

run_loop_failures_value: float | None = None
degraded_value: float | None = None
reconnecting_value: float | None = None
active_value: float | None = None

for line in lines:
    if line.startswith("run_loop_failures_total"):
        parts = line.split()
        if len(parts) >= 2:
            try:
                run_loop_failures_value = float(parts[-1])
            except ValueError:
                run_loop_failures_value = None

    monitor_match = re.match(r'^monitor_status\{([^}]*)\}\s+([-+]?[0-9]*\.?[0-9]+)$', line)
    if monitor_match:
        labels_text = monitor_match.group(1)
        value = float(monitor_match.group(2))
        labels = {}
        for chunk in labels_text.split(","):
            if "=" not in chunk:
                continue
            k, v = chunk.split("=", 1)
            labels[k.strip()] = v.strip().strip('"')
        status = labels.get("status")
        if status == "degraded":
            degraded_value = value
        elif status == "reconnecting":
            reconnecting_value = value
        elif status == "active":
            active_value = value

if active_value is not None:
    if degraded_value is None:
        degraded_value = 0.0
    if reconnecting_value is None:
        reconnecting_value = 0.0

checks = []

if run_loop_failures_value is None:
    checks.append({"metric": "run_loop_failures_total", "ok": False, "cause": "metric_missing", "detail": "run_loop_failures_total_not_found"})
else:
    ok = run_loop_failures_value < failures_threshold
    checks.append({
        "metric": "run_loop_failures_total",
        "ok": ok,
        "value": run_loop_failures_value,
        "threshold": failures_threshold,
        "cause": None if ok else "threshold_exceeded",
        "detail": None if ok else "run_loop_failures_total_threshold_exceeded",
    })

if degraded_value is None:
    checks.append({"metric": "monitor_status_degraded", "ok": False, "cause": "metric_missing", "detail": "monitor_status_degraded_not_found"})
else:
    ok = degraded_value <= degraded_threshold
    checks.append({
        "metric": "monitor_status_degraded",
        "ok": ok,
        "value": degraded_value,
        "threshold": degraded_threshold,
        "cause": None if ok else "threshold_exceeded",
        "detail": None if ok else "monitor_status_degraded_threshold_exceeded",
    })

if reconnecting_value is None:
    checks.append({"metric": "monitor_status_reconnecting", "ok": False, "cause": "metric_missing", "detail": "monitor_status_reconnecting_not_found"})
else:
    ok = reconnecting_value <= reconnecting_threshold
    checks.append({
        "metric": "monitor_status_reconnecting",
        "ok": ok,
        "value": reconnecting_value,
        "threshold": reconnecting_threshold,
        "cause": None if ok else "threshold_exceeded",
        "detail": None if ok else "monitor_status_reconnecting_threshold_exceeded",
    })

failed = [item for item in checks if not bool(item.get("ok"))]
passed = not failed

report = {
    "generated_at": datetime.now(UTC).isoformat(),
    "passed": passed,
    "metrics_url": metrics_url,
    "checks": checks,
}

if failed:
    categories = sorted({str(item.get("cause") or "threshold_exceeded") for item in failed})
    report["cause"] = categories[0] if len(categories) == 1 else ",".join(categories)

artifact_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

if passed:
    print("[alerts-sanity] PASS: thresholds_ok")
    print(f"[alerts-sanity] artifact={artifact_path}")
    sys.exit(0)

for item in failed:
    print(
        "[alerts-sanity] FAIL: "
        + str(item.get("metric"))
        + " cause="
        + str(item.get("cause"))
        + " detail="
        + str(item.get("detail"))
    )
print(f"[alerts-sanity] artifact={artifact_path}")
sys.exit(1)
PY
