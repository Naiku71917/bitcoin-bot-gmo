from __future__ import annotations

from dataclasses import asdict

from bitcoin_bot.strategy.core import DecisionHooks, IndicatorInput, decide_action


def test_strategy_output_schema_contract():
    indicators = IndicatorInput(
        close=100.0,
        ema_fast=110.0,
        ema_slow=100.0,
        rsi=55.0,
        atr=2.0,
    )
    decision = decide_action(indicators)
    payload = asdict(decision)

    assert payload["action"] in {"buy", "sell", "hold"}
    assert 0.0 <= payload["confidence"] <= 1.0
    assert isinstance(payload["reason_codes"], list)
    assert "risk" in payload
    assert {"sl", "tp", "max_holding_bars"}.issubset(payload["risk"].keys())


def test_confidence_boundaries_zero_and_one():
    hold_indicators = IndicatorInput(
        close=100.0,
        ema_fast=100.0,
        ema_slow=100.0,
        rsi=50.0,
        atr=2.0,
    )
    hold_decision = decide_action(hold_indicators)
    assert hold_decision.action == "hold"
    assert hold_decision.confidence == 0.0

    max_indicators = IndicatorInput(
        close=100.0,
        ema_fast=200.0,
        ema_slow=100.0,
        rsi=50.0,
        atr=1.0,
    )
    high_confidence_decision = decide_action(
        max_indicators,
        hooks=DecisionHooks(min_confidence=0.0),
    )
    assert high_confidence_decision.action == "buy"
    assert high_confidence_decision.confidence == 1.0


def test_hold_decision_by_hooks():
    indicators = IndicatorInput(
        close=100.0,
        ema_fast=103.0,
        ema_slow=100.0,
        rsi=40.0,
        atr=10.0,
    )

    cooldown_decision = decide_action(
        indicators,
        hooks=DecisionHooks(cooldown_bars_remaining=2),
    )
    assert cooldown_decision.action == "hold"
    assert "cooldown_active" in cooldown_decision.reason_codes

    min_confidence_decision = decide_action(
        indicators,
        hooks=DecisionHooks(min_confidence=0.95),
    )
    assert min_confidence_decision.action == "hold"
    assert "below_min_confidence" in min_confidence_decision.reason_codes
