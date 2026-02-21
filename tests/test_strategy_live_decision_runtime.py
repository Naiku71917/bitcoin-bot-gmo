from __future__ import annotations

from dataclasses import dataclass

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.exchange.protocol import NormalizedOrder, NormalizedOrderState
from bitcoin_bot.pipeline.live_runner import run_live


@dataclass(slots=True)
class _FakeExchangeAdapter:
    calls: int = 0

    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState:
        self.calls += 1
        return NormalizedOrderState(
            order_id=order_request.client_order_id,
            status="accepted",
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            qty=order_request.qty,
            price=order_request.price,
            product_type=order_request.product_type,
            reduce_only=order_request.reduce_only,
            raw={"exchange": "fake"},
        )


def _config(tmp_path) -> RuntimeConfig:
    config = RuntimeConfig()
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = True
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    return config


def test_live_decision_hold_boundary_skips_order(tmp_path):
    config = _config(tmp_path)
    fake = _FakeExchangeAdapter()

    pipeline = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 100.0,
            "ema_slow": 100.0,
            "rsi": 50.0,
            "atr": 1.0,
        },
        exchange_adapter=fake,
    )

    summary = pipeline["summary"]
    assert summary["decision_action"] == "hold"
    assert summary["order_attempted"] is False
    assert summary["order_status"] == "skipped_by_strategy"
    assert "no_trade_setup" in summary["reason_codes"]
    assert fake.calls == 0


def test_live_decision_buy_boundary_places_order(tmp_path):
    config = _config(tmp_path)
    fake = _FakeExchangeAdapter()

    pipeline = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 101.0,
            "ema_slow": 100.0,
            "rsi": 50.0,
            "atr": 1.0,
        },
        exchange_adapter=fake,
    )

    summary = pipeline["summary"]
    assert summary["decision_action"] == "buy"
    assert summary["order_attempted"] is True
    assert summary["order_status"] == "accepted"
    assert "ema_momentum_long" in summary["reason_codes"]
    assert fake.calls == 1


def test_live_decision_sell_boundary_places_order(tmp_path):
    config = _config(tmp_path)
    fake = _FakeExchangeAdapter()

    pipeline = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 98.0,
            "ema_slow": 100.0,
            "rsi": 40.0,
            "atr": 1.0,
        },
        exchange_adapter=fake,
    )

    summary = pipeline["summary"]
    assert summary["decision_action"] == "sell"
    assert summary["order_attempted"] is True
    assert summary["order_status"] == "accepted"
    assert "ema_momentum_short" in summary["reason_codes"]
    assert fake.calls == 1


def test_live_regime_filter_volatility_spike_suppresses_order(tmp_path):
    config = _config(tmp_path)
    fake = _FakeExchangeAdapter()

    pipeline = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 120.0,
            "ema_slow": 100.0,
            "rsi": 50.0,
            "atr": 20.0,
            "volume": 100.0,
            "volume_ma": 100.0,
        },
        exchange_adapter=fake,
    )

    summary = pipeline["summary"]
    assert summary["decision_action"] == "hold"
    assert summary["order_attempted"] is False
    assert "regime_volatility_spike" in summary["reason_codes"]
    assert fake.calls == 0


def test_live_regime_filter_thin_liquidity_suppresses_order(tmp_path):
    config = _config(tmp_path)
    fake = _FakeExchangeAdapter()

    pipeline = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 110.0,
            "ema_slow": 100.0,
            "rsi": 50.0,
            "atr": 1.0,
            "volume": 10.0,
            "volume_ma": 100.0,
        },
        exchange_adapter=fake,
    )

    summary = pipeline["summary"]
    assert summary["decision_action"] == "hold"
    assert summary["order_attempted"] is False
    assert "regime_thin_liquidity" in summary["reason_codes"]
    assert fake.calls == 0
