from __future__ import annotations

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.pipeline.paper_runner import run_paper
from bitcoin_bot.strategy.core import IndicatorInput, decide_action


def test_paper_runner_hold_does_not_emit_orders():
    config = RuntimeConfig()
    hold_decision = decide_action(
        IndicatorInput(
            close=100.0,
            ema_fast=100.0,
            ema_slow=100.0,
            rsi=50.0,
            atr=1.0,
        )
    )

    result = run_paper(config, decision=hold_decision)
    assert result["summary"]["action"] == "hold"
    assert result["summary"]["order_count"] == 0
    assert result["paper_order_events"] == []


def test_paper_runner_buy_emits_single_order_event():
    config = RuntimeConfig()
    buy_decision = decide_action(
        IndicatorInput(
            close=100.0,
            ema_fast=110.0,
            ema_slow=100.0,
            rsi=55.0,
            atr=2.0,
        )
    )

    result = run_paper(config, decision=buy_decision)
    assert result["summary"]["action"] == "buy"
    assert result["summary"]["order_count"] == 1
    assert result["paper_order_events"][0].action == "buy"


def test_paper_runner_sell_emits_single_order_event_and_summary_contract():
    config = RuntimeConfig()
    sell_decision = decide_action(
        IndicatorInput(
            close=100.0,
            ema_fast=90.0,
            ema_slow=100.0,
            rsi=45.0,
            atr=2.0,
        )
    )

    result = run_paper(config, decision=sell_decision)
    summary = result["summary"]

    assert summary["action"] == "sell"
    assert isinstance(summary["confidence"], float)
    assert summary["order_count"] == 1
    assert isinstance(summary["reason_codes"], list)
