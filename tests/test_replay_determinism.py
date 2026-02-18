from __future__ import annotations

import os
import subprocess

from bitcoin_bot.config.loader import load_runtime_config
from bitcoin_bot.config.validator import validate_config
from bitcoin_bot.pipeline.backtest_runner import extract_replay_summary, run_backtest


def test_backtest_replay_summary_is_deterministic():
    config = validate_config(load_runtime_config("configs/runtime.example.yaml"))
    config.runtime.mode = "backtest"

    first = extract_replay_summary(run_backtest(config))
    second = extract_replay_summary(run_backtest(config))

    assert first == second


def test_replay_check_script_detects_mismatch():
    env = os.environ.copy()
    env["REPLAY_FORCE_DRIFT"] = "1"

    completed = subprocess.run(
        ["bash", "scripts/replay_check.sh"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode != 0
    assert "[replay-check] FAIL: summaries_mismatch" in completed.stdout
    assert "--- first" in completed.stdout
    assert "+++ second" in completed.stdout
