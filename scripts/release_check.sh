#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

run_stage() {
  local stage_name="$1"
  shift

  echo "[release-check] START: ${stage_name}"
  if "$@"; then
    echo "[release-check] PASS: ${stage_name}"
  else
    echo "[release-check] FAIL: ${stage_name}"
    return 1
  fi
}

run_stage "pre-commit" /home/truen/projects/bitcoin-bot-gmo/.venv/bin/pre-commit run --all-files
run_stage "pytest-quick" /home/truen/projects/bitcoin-bot-gmo/.venv/bin/python -m pytest -q
run_stage "pytest-live-failover" /home/truen/projects/bitcoin-bot-gmo/.venv/bin/python -m pytest -q tests/test_live_failover_scenarios.py
run_stage "pytest-coverage" /home/truen/projects/bitcoin-bot-gmo/.venv/bin/python -m pytest -q --cov=src/bitcoin_bot --cov-report=term-missing --cov-report=xml --cov-report=html
run_stage "smoke-live-daemon" bash scripts/smoke_live_daemon.sh

echo "[release-check] SUCCESS: all stages passed"
exit 0
