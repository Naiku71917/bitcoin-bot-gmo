from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bitcoin_bot.telemetry.reason_codes import (
    REASON_CODE_BELOW_MIN_CONFIDENCE,
    REASON_CODE_COOLDOWN_ACTIVE,
    REASON_CODE_EMA_MOMENTUM_LONG,
    REASON_CODE_EMA_MOMENTUM_SHORT,
    REASON_CODE_FORCED_HOLD,
    REASON_CODE_NO_TRADE_SETUP,
)


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
            reason_codes=[REASON_CODE_COOLDOWN_ACTIVE],
            risk=_build_risk("hold", indicators, applied_hooks.max_holding_bars),
        )

    volatility = max(abs(indicators.atr), 1e-9)
    normalized_gap = (indicators.ema_fast - indicators.ema_slow) / volatility
    confidence = min(1.0, abs(normalized_gap))

    if normalized_gap > 0.2 and indicators.rsi < 70:
        action: Action = "buy"
        reason_codes = [REASON_CODE_EMA_MOMENTUM_LONG]
    elif normalized_gap < -0.2 and indicators.rsi > 30:
        action = "sell"
        reason_codes = [REASON_CODE_EMA_MOMENTUM_SHORT]
    else:
        action = "hold"
        reason_codes = [REASON_CODE_NO_TRADE_SETUP]
        confidence = 0.0

    if action != "hold" and confidence < applied_hooks.min_confidence:
        return StrategyDecision(
            action="hold",
            confidence=confidence,
            reason_codes=[*reason_codes, REASON_CODE_BELOW_MIN_CONFIDENCE],
            risk=_build_risk("hold", indicators, applied_hooks.max_holding_bars),
        )

    return StrategyDecision(
        action=action,
        confidence=confidence,
        reason_codes=reason_codes,
        risk=_build_risk(action, indicators, applied_hooks.max_holding_bars),
    )


def hold_decision(
    indicators: IndicatorInput | None = None,
    hooks: DecisionHooks | None = None,
) -> StrategyDecision:
    resolved_indicators = indicators or IndicatorInput(
        close=100.0,
        ema_fast=100.0,
        ema_slow=100.0,
        rsi=50.0,
        atr=1.0,
    )
    resolved_hooks = hooks or DecisionHooks()

    decision = decide_action(resolved_indicators, resolved_hooks)
    if decision.action == "hold":
        return decision

    return StrategyDecision(
        action="hold",
        confidence=decision.confidence,
        reason_codes=[*decision.reason_codes, REASON_CODE_FORCED_HOLD],
        risk=_build_risk("hold", resolved_indicators, resolved_hooks.max_holding_bars),
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
