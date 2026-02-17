from __future__ import annotations

from bitcoin_bot.optimizer.gates import evaluate_optimization_gates


def score_from_backtest_metrics(metrics: dict[str, float]) -> float:
    return_value = metrics.get("return", 0.0)
    max_drawdown = metrics.get("max_drawdown", 0.0)
    win_rate = metrics.get("win_rate", 0.0)
    profit_factor = metrics.get("profit_factor", 0.0)
    trade_count = metrics.get("trade_count", 0.0)

    raw_score = (
        (return_value * 2.0)
        - (max_drawdown * 1.5)
        + win_rate
        + (profit_factor * 0.2)
        + (trade_count * 0.01)
    )
    return round(raw_score, 6)


def build_optimization_snapshot(
    *,
    enabled: bool,
    opt_trials: int,
    score: float | None = None,
    salvage: dict | None = None,
) -> dict:
    if not enabled:
        return {
            "enabled": False,
            "trials": opt_trials,
            "score": None,
            "gates": {"accept": False, "reasons": ["optimizer_disabled"]},
            "salvage": salvage,
        }

    gates = evaluate_optimization_gates(score)
    return {
        "enabled": True,
        "trials": opt_trials,
        "score": score,
        "gates": gates,
        "salvage": salvage,
    }
