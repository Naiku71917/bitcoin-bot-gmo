from __future__ import annotations

from bitcoin_bot.telemetry.reason_codes import (
    REASON_CODE_DAILY_LOSS_LIMIT_EXCEEDED,
    REASON_CODE_MAX_DRAWDOWN_EXCEEDED,
    REASON_CODE_MAX_LEVERAGE_EXCEEDED,
    REASON_CODE_MAX_POSITION_SIZE_EXCEEDED,
    REASON_CODE_MAX_TRADE_LOSS_EXCEEDED,
    REASON_CODE_WALLET_DRIFT_EXCEEDED,
    normalize_reason_codes,
)


RISK_CONDITION_MATRIX = {
    "max_drawdown": {
        "status": "abort",
        "reason_code": REASON_CODE_MAX_DRAWDOWN_EXCEEDED,
    },
    "daily_loss_limit": {
        "status": "degraded",
        "reason_code": REASON_CODE_DAILY_LOSS_LIMIT_EXCEEDED,
    },
    "max_position_size": {
        "status": "degraded",
        "reason_code": REASON_CODE_MAX_POSITION_SIZE_EXCEEDED,
    },
    "max_trade_loss": {
        "status": "abort",
        "reason_code": REASON_CODE_MAX_TRADE_LOSS_EXCEEDED,
    },
    "max_leverage": {
        "status": "degraded",
        "reason_code": REASON_CODE_MAX_LEVERAGE_EXCEEDED,
    },
    "max_wallet_drift": {
        "status": "degraded",
        "reason_code": REASON_CODE_WALLET_DRIFT_EXCEEDED,
    },
}

_STATUS_SEVERITY = {
    "success": 0,
    "degraded": 1,
    "abort": 2,
}


def evaluate_risk_guards(
    *,
    max_drawdown: float,
    daily_loss_limit: float,
    max_position_size: float,
    max_trade_loss: float,
    max_leverage: float,
    max_wallet_drift: float,
    current_drawdown: float,
    current_daily_loss: float,
    current_position_size: float,
    current_trade_loss: float,
    current_leverage: float,
    current_wallet_drift: float,
) -> dict:
    reason_codes: list[str] = []
    status = "success"

    checks = (
        ("max_drawdown", current_drawdown > max_drawdown),
        ("daily_loss_limit", current_daily_loss > daily_loss_limit),
        ("max_position_size", current_position_size > max_position_size),
        ("max_trade_loss", current_trade_loss > max_trade_loss),
        ("max_leverage", current_leverage > max_leverage),
        ("max_wallet_drift", current_wallet_drift > max_wallet_drift),
    )

    for condition_name, triggered in checks:
        if not triggered:
            continue

        condition = RISK_CONDITION_MATRIX[condition_name]
        reason_codes.append(condition["reason_code"])

        candidate_status = condition["status"]
        if _STATUS_SEVERITY[candidate_status] > _STATUS_SEVERITY[status]:
            status = candidate_status

    reason_codes = normalize_reason_codes(reason_codes)

    return {
        "status": status,
        "reason_codes": reason_codes,
        "snapshot": {
            "current_drawdown": current_drawdown,
            "current_daily_loss": current_daily_loss,
            "current_position_size": current_position_size,
            "current_trade_loss": current_trade_loss,
            "current_leverage": current_leverage,
            "current_wallet_drift": current_wallet_drift,
        },
        "limits": {
            "max_drawdown": max_drawdown,
            "daily_loss_limit": daily_loss_limit,
            "max_position_size": max_position_size,
            "max_trade_loss": max_trade_loss,
            "max_leverage": max_leverage,
            "max_wallet_drift": max_wallet_drift,
        },
        "reason_matrix": RISK_CONDITION_MATRIX,
    }


def default_gate_result() -> dict:
    return {"accept": None, "reasons": []}


def evaluate_optimization_gates(score: float | None) -> dict:
    if score is None:
        return {"accept": False, "reasons": ["score_missing"]}

    if score >= 0.0:
        return {"accept": True, "reasons": []}

    return {"accept": False, "reasons": ["score_below_threshold"]}
