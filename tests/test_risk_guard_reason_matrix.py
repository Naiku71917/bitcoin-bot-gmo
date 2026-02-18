from __future__ import annotations

from bitcoin_bot.optimizer.gates import RISK_CONDITION_MATRIX, evaluate_risk_guards
from bitcoin_bot.telemetry.reason_codes import REASON_CODES


def _base_kwargs() -> dict[str, float]:
    return {
        "max_drawdown": 0.2,
        "daily_loss_limit": 0.05,
        "max_position_size": 0.1,
        "max_trade_loss": 0.02,
        "max_leverage": 2.0,
        "max_wallet_drift": 0.02,
        "current_drawdown": 0.1,
        "current_daily_loss": 0.01,
        "current_position_size": 0.05,
        "current_trade_loss": 0.01,
        "current_leverage": 1.0,
        "current_wallet_drift": 0.01,
    }


def test_risk_matrix_definitions_use_dictionary_reason_codes():
    for _, condition in RISK_CONDITION_MATRIX.items():
        assert condition["status"] in {"degraded", "abort"}
        assert condition["reason_code"] in REASON_CODES


def test_risk_matrix_single_condition_status_mapping():
    checks = [
        ("max_drawdown", {"current_drawdown": 0.25}, "abort", "max_drawdown_exceeded"),
        (
            "daily_loss_limit",
            {"current_daily_loss": 0.06},
            "degraded",
            "daily_loss_limit_exceeded",
        ),
        (
            "max_position_size",
            {"current_position_size": 0.11},
            "degraded",
            "max_position_size_exceeded",
        ),
        (
            "max_trade_loss",
            {"current_trade_loss": 0.03},
            "abort",
            "max_trade_loss_exceeded",
        ),
        (
            "max_leverage",
            {"current_leverage": 2.5},
            "degraded",
            "max_leverage_exceeded",
        ),
        (
            "max_wallet_drift",
            {"current_wallet_drift": 0.03},
            "degraded",
            "wallet_drift_exceeded",
        ),
    ]

    for _, override, expected_status, expected_reason in checks:
        kwargs = _base_kwargs()
        kwargs.update(override)
        result = evaluate_risk_guards(**kwargs)
        assert result["status"] == expected_status
        assert expected_reason in result["reason_codes"]


def test_abort_has_higher_priority_than_degraded():
    kwargs = _base_kwargs()
    kwargs.update(
        {
            "current_daily_loss": 0.08,
            "current_trade_loss": 0.03,
        }
    )
    result = evaluate_risk_guards(**kwargs)
    assert result["status"] == "abort"
    assert "daily_loss_limit_exceeded" in result["reason_codes"]
    assert "max_trade_loss_exceeded" in result["reason_codes"]
