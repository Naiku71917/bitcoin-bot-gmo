from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Action = Literal["buy", "sell", "hold"]


@dataclass(slots=True)
class StrategyRisk:
    sl: float
    tp: float
    max_holding_bars: int


@dataclass(slots=True)
class IndicatorInput:
    close: float
    ema_fast: float
    ema_slow: float
    rsi: float
    atr: float


@dataclass(slots=True)
class DecisionHooks:
    min_confidence: float = 0.55
    cooldown_bars_remaining: int = 0
    max_holding_bars: int = 12


@dataclass(slots=True)
class StrategyDecision:
    action: Action
    confidence: float
    reason_codes: list[str]
    risk: StrategyRisk

    def __post_init__(self) -> None:
        if self.action not in {"buy", "sell", "hold"}:
            raise ValueError(f"Invalid action: {self.action}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be within [0.0, 1.0], got {self.confidence}"
            )


@dataclass(slots=True)
class PaperOrderEvent:
    symbol: str
    product_type: str
    action: Action
    confidence: float
    reason_codes: list[str]
    qty: float
    order_type: str


def _build_risk(
    action: Action, indicators: IndicatorInput, max_holding_bars: int
) -> StrategyRisk:
    atr = max(indicators.atr, 0.0)
    if action == "buy":
        return StrategyRisk(
            sl=indicators.close - atr,
            tp=indicators.close + (atr * 2.0),
            max_holding_bars=max_holding_bars,
        )
    if action == "sell":
        return StrategyRisk(
            sl=indicators.close + atr,
            tp=indicators.close - (atr * 2.0),
            max_holding_bars=max_holding_bars,
        )
    return StrategyRisk(
        sl=indicators.close - atr,
        tp=indicators.close + atr,
        max_holding_bars=max_holding_bars,
    )


def decide_action(
    indicators: IndicatorInput,
    hooks: DecisionHooks | None = None,
) -> StrategyDecision:
    applied_hooks = hooks or DecisionHooks()

    if applied_hooks.cooldown_bars_remaining > 0:
        return StrategyDecision(
            action="hold",
            confidence=0.0,
            reason_codes=["cooldown_active"],
            risk=_build_risk("hold", indicators, applied_hooks.max_holding_bars),
        )

    volatility = max(abs(indicators.atr), 1e-9)
    normalized_gap = (indicators.ema_fast - indicators.ema_slow) / volatility
    confidence = min(1.0, abs(normalized_gap))

    if normalized_gap > 0.2 and indicators.rsi < 70:
        action: Action = "buy"
        reason_codes = ["ema_momentum_long"]
    elif normalized_gap < -0.2 and indicators.rsi > 30:
        action = "sell"
        reason_codes = ["ema_momentum_short"]
    else:
        action = "hold"
        reason_codes = ["no_trade_setup"]
        confidence = 0.0

    if action != "hold" and confidence < applied_hooks.min_confidence:
        return StrategyDecision(
            action="hold",
            confidence=confidence,
            reason_codes=[*reason_codes, "below_min_confidence"],
            risk=_build_risk("hold", indicators, applied_hooks.max_holding_bars),
        )

    return StrategyDecision(
        action=action,
        confidence=confidence,
        reason_codes=reason_codes,
        risk=_build_risk(action, indicators, applied_hooks.max_holding_bars),
    )


def hold_decision() -> StrategyDecision:
    indicators = IndicatorInput(
        close=0.0, ema_fast=0.0, ema_slow=0.0, rsi=50.0, atr=0.0
    )
    return StrategyDecision(
        action="hold",
        confidence=0.0,
        reason_codes=["not_implemented"],
        risk=_build_risk("hold", indicators, max_holding_bars=0),
    )


def build_paper_order_event(
    *,
    decision: StrategyDecision,
    symbol: str,
    product_type: str,
    qty: float = 0.01,
) -> PaperOrderEvent | None:
    if decision.action == "hold":
        return None

    return PaperOrderEvent(
        symbol=symbol,
        product_type=product_type,
        action=decision.action,
        confidence=decision.confidence,
        reason_codes=list(decision.reason_codes),
        qty=qty,
        order_type="market",
    )
