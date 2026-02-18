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


def _build_config(tmp_path) -> RuntimeConfig:
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    return config


def test_execute_orders_false_does_not_place_order(tmp_path):
    config = _build_config(tmp_path)
    config.runtime.execute_orders = False

    fake = _FakeExchangeAdapter()
    result = run_live(config, exchange_adapter=fake)

    assert fake.calls == 0
    summary = result["summary"]
    assert summary["execute_orders"] is False
    assert summary["order_attempted"] is False
    assert summary["order_status"] == "not_attempted"
    assert "execute_orders_disabled" in summary["reason_codes"]


def test_execute_orders_true_places_order_and_records_status(tmp_path):
    config = _build_config(tmp_path)
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = True

    fake = _FakeExchangeAdapter()
    result = run_live(config, exchange_adapter=fake)

    assert fake.calls == 1
    summary = result["summary"]
    assert summary["execute_orders"] is True
    assert summary["order_attempted"] is True
    assert summary["order_status"] == "accepted"
    assert "execute_orders_disabled" not in summary["reason_codes"]


def test_execute_orders_true_but_http_disabled_skips_order(tmp_path):
    config = _build_config(tmp_path)
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = False

    fake = _FakeExchangeAdapter()
    result = run_live(config, exchange_adapter=fake)

    assert fake.calls == 0
    summary = result["summary"]
    assert summary["execute_orders"] is True
    assert summary["live_http_enabled"] is False
    assert summary["live_http_active"] is False
    assert summary["order_attempted"] is False
    assert summary["order_status"] == "skipped_http_disabled"
    assert "live_http_disabled" in summary["reason_codes"]
