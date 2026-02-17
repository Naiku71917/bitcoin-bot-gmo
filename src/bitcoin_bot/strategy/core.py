from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StrategyDecision:
    action: str
    confidence: float
    reason_codes: list[str]


def hold_decision() -> StrategyDecision:
    return StrategyDecision(action="hold", confidence=0.0, reason_codes=["not_implemented"])
