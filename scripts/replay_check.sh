#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

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
CONFIG_PATH="${REPLAY_CONFIG_PATH:-configs/runtime.example.yaml}"
FORCE_DRIFT="${REPLAY_FORCE_DRIFT:-0}"

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "[replay-check] FAIL: python_not_found ($PYTHON_BIN)"
  exit 1
fi

tmp_dir="$(mktemp -d)"
first_json="$tmp_dir/summary_first.json"
second_json="$tmp_dir/summary_second.json"

cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

echo "[replay-check] START: run backtest twice with same input"
"$PYTHON_BIN" - <<'PY' "$CONFIG_PATH" "$first_json" "$second_json" "$FORCE_DRIFT"
import json
import sys
from pathlib import Path

from bitcoin_bot.config.loader import load_runtime_config
from bitcoin_bot.config.validator import validate_config
from bitcoin_bot.pipeline.backtest_runner import extract_replay_summary, run_backtest

config_path = sys.argv[1]
out_first = Path(sys.argv[2])
out_second = Path(sys.argv[3])
force_drift = sys.argv[4] == "1"

config = validate_config(load_runtime_config(config_path))
config.runtime.mode = "backtest"

first = extract_replay_summary(run_backtest(config))
second = extract_replay_summary(run_backtest(config))

if force_drift:
    second["return"] = (second.get("return") or 0.0) + 0.0001

out_first.write_text(json.dumps(first, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
out_second.write_text(json.dumps(second, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
PY

echo "[replay-check] START: compare summaries"
if cmp -s "$first_json" "$second_json"; then
  echo "[replay-check] PASS: summaries_match"
  exit 0
fi

echo "[replay-check] FAIL: summaries_mismatch"
"$PYTHON_BIN" - <<'PY' "$first_json" "$second_json"
import difflib
import sys
from pathlib import Path

first = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
second = Path(sys.argv[2]).read_text(encoding="utf-8").splitlines()

for line in difflib.unified_diff(first, second, fromfile="first", tofile="second", lineterm=""):
    print(line)
PY
exit 1
