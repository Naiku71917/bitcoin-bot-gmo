from __future__ import annotations

import json
from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.pipeline.live_runner import run_live
from bitcoin_bot.strategy.core import IndicatorInput, decide_action
from bitcoin_bot.telemetry.reason_codes import REASON_CODES


def _build_config(tmp_path) -> RuntimeConfig:
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    return config


def test_strategy_reason_codes_are_defined_in_dictionary():
    decision = decide_action(
        IndicatorInput(
            close=100.0,
            ema_fast=101.0,
            ema_slow=100.0,
            rsi=50.0,
            atr=1.0,
        )
    )
    assert decision.reason_codes
    assert set(decision.reason_codes).issubset(REASON_CODES)


def test_live_summary_reason_codes_are_defined_in_dictionary(tmp_path):
    config = _build_config(tmp_path)
    config.runtime.execute_orders = False

    result = run_live(config)
    summary = result["summary"]

    assert set(summary["reason_codes"]).issubset(REASON_CODES)
    assert set(summary["stop_reason_codes"]).issubset(REASON_CODES)


def test_audit_risk_stop_reason_codes_are_defined_in_dictionary(tmp_path):
    config = _build_config(tmp_path)
    config.runtime.execute_orders = True

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

    path = Path(config.paths.logs_dir) / "audit_events.jsonl"
    events = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    risk_events = [event for event in events if event["event_type"] == "risk_stop"]

    assert risk_events
    assert set(risk_events[-1]["payload"]["reason_codes"]).issubset(REASON_CODES)
