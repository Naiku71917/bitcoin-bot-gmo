from __future__ import annotations

import json
from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.pipeline.live_runner import run_live
from bitcoin_bot.telemetry.reporters import emit_run_progress


def _read_audit_events(logs_dir: Path) -> list[dict]:
    path = logs_dir / "audit_events.jsonl"
    assert path.exists()
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_order_attempt_and_result_events_are_written(tmp_path):
    config = RuntimeConfig()
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = True
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")

    run_live(config)

    events = _read_audit_events(tmp_path / "logs")
    event_types = [event["event_type"] for event in events]
    assert "order_attempt" in event_types
    assert "order_result" in event_types


def test_risk_stop_event_is_written(tmp_path):
    config = RuntimeConfig()
    config.runtime.execute_orders = True
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")

    run_live(
        config,
        risk_snapshot={
            "current_drawdown": 0.5,
            "current_daily_loss": 0.0,
            "current_position_size": 0.0,
            "current_trade_loss": 0.0,
            "current_leverage": 0.0,
            "current_wallet_drift": 0.0,
        },
    )

    events = _read_audit_events(tmp_path / "logs")
    risk_events = [event for event in events if event["event_type"] == "risk_stop"]
    assert risk_events
    assert "max_drawdown_exceeded" in risk_events[-1]["payload"]["reason_codes"]


def test_startup_validation_event_and_secret_redaction(tmp_path):
    artifacts_dir = tmp_path / "artifacts"

    emit_run_progress(
        artifacts_dir=str(artifacts_dir),
        mode="live",
        status="running",
        last_error=None,
        monitor_status="active",
        validation={
            "fatal_errors": [],
            "warnings": ["discord_webhook_missing"],
            "api_secret": "super-secret",
            "discord": {
                "status": "failed",
                "webhook_url": "https://example.com/hook",
            },
        },
    )

    events = _read_audit_events(tmp_path / "logs")
    startup_events = [
        event for event in events if event["event_type"] == "startup_validation"
    ]
    assert startup_events

    payload = startup_events[-1]["payload"]
    assert payload["validation"]["api_secret"] == "***"
    assert payload["validation"]["discord"]["webhook_url"] == "***"
