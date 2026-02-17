from __future__ import annotations

from bitcoin_bot.optimizer.gates import evaluate_optimization_gates


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
