from __future__ import annotations

from datetime import UTC, datetime

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import (
    NormalizedError,
    NormalizedKline,
    NormalizedOrderState,
    NormalizedPosition,
)


def test_gmo_read_models_success_with_http_stub(monkeypatch):
    now = datetime.now(UTC)

    def _mock_request_json(*, method, path, params=None, auth=False):
        if path == "/public/v1/klines":
            return {
                "data": [
                    {
                        "timestamp": now.isoformat(),
                        "open": "100",
                        "high": "110",
                        "low": "95",
                        "close": "105",
                        "volume": "1.5",
                    }
                ]
            }
        if path == "/private/v1/openPositions":
            return {
                "data": [
                    {
                        "symbol": "BTC_JPY",
                        "side": "buy",
                        "size": "0.01",
                        "price": "1000000",
                        "leverage": "2",
                        "lossGain": "100",
                    }
                ]
            }
        if path == "/private/v1/activeOrders":
            return {
                "data": [
                    {
                        "orderId": "oid-1",
                        "status": "active",
                        "symbol": "BTC_JPY",
                        "side": "buy",
                        "orderType": "limit",
                        "size": "0.01",
                        "price": "1000000",
                    }
                ]
            }
        return {"data": []}

    adapter = GMOAdapter(product_type="leverage", use_http=True)
    monkeypatch.setattr(adapter, "_request_json", _mock_request_json)

    klines = adapter.fetch_klines("BTC_JPY", "1m", now, now, 10)
    positions = adapter.fetch_positions("BTC_JPY")
    fetched = adapter.fetch_order("oid-1")

    assert klines and isinstance(klines[0], NormalizedKline)
    assert all(kline.timestamp.tzinfo is not None for kline in klines)
    assert positions and isinstance(positions[0], NormalizedPosition)
    assert all(position.product_type == "leverage" for position in positions)
    assert isinstance(fetched, NormalizedOrderState)
    assert fetched.product_type == "leverage"
    assert fetched.status == "active"


def test_gmo_read_models_network_failure_fallback(monkeypatch):
    adapter = GMOAdapter(product_type="spot", use_http=True)

    def _mock_error(*, method, path, params=None, auth=False):
        return NormalizedError(
            category="network",
            retryable=True,
            source_code="NETWORK_TIMEOUT",
            message="timeout",
        )

    monkeypatch.setattr(adapter, "_request_json", _mock_error)

    klines = adapter.fetch_klines(
        "BTC_JPY", "1m", datetime.now(UTC), datetime.now(UTC), 10
    )
    positions = adapter.fetch_positions("BTC_JPY")
    fetched = adapter.fetch_order("oid-1")

    assert klines == []
    assert positions == []
    assert fetched.status == "error"
    assert fetched.raw.get("error", {}).get("category") == "network"
