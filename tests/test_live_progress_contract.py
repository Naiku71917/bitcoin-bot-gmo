from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.main import run
from bitcoin_bot.pipeline.live_runner import run_live
from bitcoin_bot.telemetry.reporters import emit_run_progress


REQUIRED_PROGRESS_KEYS = {"status", "updated_at", "mode", "last_error"}


def test_run_progress_created_and_updated(tmp_path):
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")

    run_live(
        config,
        risk_snapshot={
            "current_drawdown": 0.0,
            "current_daily_loss": 0.0,
            "current_position_size": 0.0,
        },
    )
    first_payload = json.loads(
        (tmp_path / "artifacts" / "run_progress.json").read_text(encoding="utf-8")
    )

    run_live(
        config,
        risk_snapshot={
            "current_drawdown": 0.3,
            "current_daily_loss": 0.0,
            "current_position_size": 0.0,
        },
    )
    second_payload = json.loads(
        (tmp_path / "artifacts" / "run_progress.json").read_text(encoding="utf-8")
    )

    assert REQUIRED_PROGRESS_KEYS.issubset(first_payload.keys())
    assert REQUIRED_PROGRESS_KEYS.issubset(second_payload.keys())
    assert first_payload["mode"] == "live"
    assert second_payload["status"] == "abort"
    assert second_payload["last_error"] == "max_drawdown_exceeded"

    first_updated_at = datetime.fromisoformat(first_payload["updated_at"])
    second_updated_at = datetime.fromisoformat(second_payload["updated_at"])
    assert first_updated_at <= second_updated_at


def test_run_progress_can_store_failed_state(tmp_path):
    payload = emit_run_progress(
        artifacts_dir=str(tmp_path / "artifacts"),
        mode="live",
        status="failed",
        last_error="runtime_exception",
    )

    assert payload["status"] == "failed"
    assert payload["last_error"] == "runtime_exception"
    stored = json.loads(
        (tmp_path / "artifacts" / "run_progress.json").read_text(encoding="utf-8")
    )
    assert stored["status"] == "failed"


def test_run_complete_contract_not_broken(tmp_path):
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
runtime:
  mode: backtest
exchange:
  product_type: spot
optimizer:
  enabled: true
  opt_trials: 5
notify:
  discord:
    enabled: false
paths:
  artifacts_dir: "./var/artifacts"
  logs_dir: "./var/logs"
  cache_dir: "./var/cache"
""",
        encoding="utf-8",
    )

    run(mode="backtest", config_path=str(config_path))

    run_complete = json.loads(
        Path("var/artifacts/run_complete.json").read_text(encoding="utf-8")
    )
    required_top_level = {
        "run_id",
        "started_at",
        "completed_at",
        "pipeline",
        "pipeline_summary",
        "optimization",
        "notifications",
    }
    assert required_top_level.issubset(run_complete.keys())
