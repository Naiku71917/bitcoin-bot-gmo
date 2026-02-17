from __future__ import annotations


def build_optimization_snapshot(enabled: bool, opt_trials: int) -> dict:
    if not enabled:
        return {"enabled": False}
    return {
        "enabled": True,
        "trials": opt_trials,
        "score": None,
        "gates": {"accept": None, "reasons": []},
        "salvage": None,
    }
