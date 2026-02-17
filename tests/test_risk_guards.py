from __future__ import annotations

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.optimizer.gates import evaluate_risk_guards
from bitcoin_bot.pipeline.live_runner import run_live


def test_risk_guards_abort_on_max_drawdown_exceeded():
    result = evaluate_risk_guards(
        max_drawdown=0.2,
        daily_loss_limit=0.05,
        max_position_size=0.1,
        max_trade_loss=0.02,
        max_leverage=2.0,
        max_wallet_drift=0.02,
        current_drawdown=0.25,
        current_daily_loss=0.01,
        current_position_size=0.05,
        current_trade_loss=0.01,
        current_leverage=1.0,
        current_wallet_drift=0.0,
    )

    assert result["status"] == "abort"
    assert "max_drawdown_exceeded" in result["reason_codes"]


def test_risk_guards_degraded_on_daily_loss_or_position_size_exceeded():
    result = evaluate_risk_guards(
        max_drawdown=0.2,
        daily_loss_limit=0.05,
        max_position_size=0.1,
        max_trade_loss=0.02,
        max_leverage=2.0,
        max_wallet_drift=0.02,
        current_drawdown=0.1,
        current_daily_loss=0.06,
        current_position_size=0.11,
        current_trade_loss=0.01,
        current_leverage=1.0,
        current_wallet_drift=0.0,
    )

    assert result["status"] == "degraded"
    assert "daily_loss_limit_exceeded" in result["reason_codes"]
    assert "max_position_size_exceeded" in result["reason_codes"]


def test_risk_guards_cover_trade_loss_leverage_wallet_drift():
    result = evaluate_risk_guards(
        max_drawdown=0.2,
        daily_loss_limit=0.05,
        max_position_size=0.1,
        max_trade_loss=0.02,
        max_leverage=2.0,
        max_wallet_drift=0.02,
        current_drawdown=0.1,
        current_daily_loss=0.01,
        current_position_size=0.08,
        current_trade_loss=0.03,
        current_leverage=2.5,
        current_wallet_drift=0.03,
    )

    assert result["status"] == "abort"
    assert "max_trade_loss_exceeded" in result["reason_codes"]
    assert "max_leverage_exceeded" in result["reason_codes"]
    assert "wallet_drift_exceeded" in result["reason_codes"]


def test_live_runner_passes_stop_reason_codes(tmp_path):
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")

    config.risk.max_drawdown = 0.2
    config.risk.daily_loss_limit = 0.05
    config.risk.max_position_size = 0.1

    pipeline = run_live(
        config,
        risk_snapshot={
            "current_drawdown": 0.1,
            "current_daily_loss": 0.06,
            "current_position_size": 0.08,
            "current_trade_loss": 0.0,
            "current_leverage": 1.0,
            "current_wallet_drift": 0.0,
        },
    )

    assert pipeline["status"] == "degraded"
    reasons = pipeline["summary"]["stop_reason_codes"]
    assert reasons
    assert "daily_loss_limit_exceeded" in reasons
