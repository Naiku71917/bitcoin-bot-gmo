from __future__ import annotations

import json

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.main import run
from bitcoin_bot.pipeline.live_runner import run_live
from bitcoin_bot.telemetry.reporters import emit_run_progress


def test_monitor_status_transitions_and_progress_fields(tmp_path):
    artifacts_dir = tmp_path / "artifacts"

    active = emit_run_progress(
        artifacts_dir=str(artifacts_dir),
        mode="live",
        status="running",
        last_error=None,
        monitor_status="active",
        reconnect_count=0,
    )
    reconnecting = emit_run_progress(
        artifacts_dir=str(artifacts_dir),
        mode="live",
        status="degraded",
        last_error="reconnecting_after_error",
        monitor_status="reconnecting",
        reconnect_count=1,
    )
    degraded = emit_run_progress(
        artifacts_dir=str(artifacts_dir),
        mode="live",
        status="degraded",
        last_error="shutdown_signal",
        monitor_status="degraded",
        reconnect_count=1,
    )

    assert active["monitor_status"] == "active"
    assert reconnecting["monitor_status"] == "reconnecting"
    assert degraded["monitor_status"] == "degraded"

    stored = json.loads(
        (artifacts_dir / "run_progress.json").read_text(encoding="utf-8")
    )
    assert "monitor_status" in stored
    assert "reconnect_count" in stored
    assert stored["monitor_status"] == "degraded"


def test_live_run_summary_contains_monitor_summary(tmp_path):
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")

    result = run_live(
        config,
        risk_snapshot={
            "current_drawdown": 0.0,
            "current_daily_loss": 0.0,
            "current_position_size": 0.0,
            "current_trade_loss": 0.0,
            "current_leverage": 0.0,
            "current_wallet_drift": 0.0,
        },
    )

    monitor_summary = result["summary"]["monitor_summary"]
    assert monitor_summary["status"] in {"active", "degraded"}
    assert "reconnect_count" in monitor_summary


def test_run_complete_contract_still_includes_markers_and_pipeline_summary(
    tmp_path, capsys
):
    artifacts_dir = tmp_path / "artifacts"
    logs_dir = tmp_path / "logs"
    cache_dir = tmp_path / "cache"

    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        f"""
runtime:
  mode: live
exchange:
  product_type: spot
optimizer:
  enabled: true
  opt_trials: 5
notify:
  discord:
    enabled: false
paths:
  artifacts_dir: "{artifacts_dir}"
  logs_dir: "{logs_dir}"
  cache_dir: "{cache_dir}"
""",
        encoding="utf-8",
    )

    run(mode="live", config_path=str(config_path))
    out = capsys.readouterr().out

    assert "BEGIN_RUN_COMPLETE_JSON" in out
    assert "END_RUN_COMPLETE_JSON" in out

    payload = json.loads(
        (artifacts_dir / "run_complete.json").read_text(encoding="utf-8")
    )
    assert "pipeline_summary" in payload
    assert "monitor_summary" in payload["pipeline_summary"]
