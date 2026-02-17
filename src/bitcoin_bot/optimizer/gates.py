from __future__ import annotations


def evaluate_risk_guards(
    *,
    max_drawdown: float,
    daily_loss_limit: float,
    max_position_size: float,
    current_drawdown: float,
    current_daily_loss: float,
    current_position_size: float,
) -> dict:
    reason_codes: list[str] = []
    status = "success"

    if current_drawdown > max_drawdown:
        status = "abort"
        reason_codes.append("max_drawdown_exceeded")

    if current_daily_loss > daily_loss_limit:
        if status != "abort":
            status = "degraded"
        reason_codes.append("daily_loss_limit_exceeded")

    if current_position_size > max_position_size:
        if status != "abort":
            status = "degraded"
        reason_codes.append("max_position_size_exceeded")

    return {
        "status": status,
        "reason_codes": reason_codes,
        "snapshot": {
            "current_drawdown": current_drawdown,
            "current_daily_loss": current_daily_loss,
            "current_position_size": current_position_size,
        },
        "limits": {
            "max_drawdown": max_drawdown,
            "daily_loss_limit": daily_loss_limit,
            "max_position_size": max_position_size,
        },
    }


def default_gate_result() -> dict:
    return {"accept": None, "reasons": []}


def evaluate_optimization_gates(score: float | None) -> dict:
    if score is None:
        return {"accept": False, "reasons": ["score_missing"]}

    if score >= 0.0:
        return {"accept": True, "reasons": []}

    return {"accept": False, "reasons": ["score_below_threshold"]}
