from __future__ import annotations

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.strategy.core import (
    IndicatorInput,
    StrategyDecision,
    build_paper_order_event,
    decide_action,
)


def run_paper(config: RuntimeConfig, decision: StrategyDecision | None = None) -> dict:
    resolved_decision = decision or decide_action(
        IndicatorInput(
            close=100.0,
            ema_fast=100.0,
            ema_slow=100.0,
            rsi=50.0,
            atr=1.0,
        )
    )
    order_event = build_paper_order_event(
        decision=resolved_decision,
        symbol=config.exchange.symbol,
        product_type=config.exchange.product_type,
    )
    order_events = [order_event] if order_event is not None else []

    return {
        "status": "success",
        "summary": {
            "mode": "paper",
            "symbol": config.exchange.symbol,
            "product_type": config.exchange.product_type,
            "action": resolved_decision.action,
            "confidence": resolved_decision.confidence,
            "order_count": len(order_events),
            "reason_codes": resolved_decision.reason_codes,
        },
        "paper_order_events": order_events,
    }
