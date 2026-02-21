from __future__ import annotations

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import NormalizedError


def test_stream_order_events_uses_ws_path_when_factory_absent(monkeypatch):
    adapter = GMOAdapter(product_type="spot", use_http=True)
    calls: list[tuple[str, bool]] = []

    def _mock_open_ws_stream(*, channel: str, auth_required: bool):
        calls.append((channel, auth_required))
        return iter(
            [
                {
                    "order_id": "oid-1",
                    "status": "active",
                    "symbol": "BTC_JPY",
                    "side": "buy",
                    "qty": 0.01,
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            ]
        )

    monkeypatch.setattr(adapter, "_open_ws_stream", _mock_open_ws_stream)
    monkeypatch.setenv("GMO_API_KEY", "key")
    monkeypatch.setenv("GMO_API_SECRET", "secret")

    event = next(iter(adapter.stream_order_events()))

    assert calls == [("orderEvents", True)]
    assert not isinstance(event, NormalizedError)
    assert event.order_id == "oid-1"
    assert event.status == "active"


def test_stream_events_fail_fast_on_missing_auth(monkeypatch):
    adapter = GMOAdapter(product_type="spot", use_http=True)

    monkeypatch.delenv("GMO_API_KEY", raising=False)
    monkeypatch.delenv("GMO_API_SECRET", raising=False)

    first = next(iter(adapter.stream_order_events()))

    assert isinstance(first, NormalizedError)
    assert first.category == "auth"
    assert first.retryable is False


def test_stream_events_retry_once_then_recover(monkeypatch):
    adapter = GMOAdapter(product_type="spot", use_http=True)
    monkeypatch.setenv("GMO_API_KEY", "key")
    monkeypatch.setenv("GMO_API_SECRET", "secret")

    calls = {"count": 0}

    def _mock_open_ws_stream(*, channel: str, auth_required: bool):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ConnectionError("temporary disconnect")
        return iter(
            [
                {
                    "order_id": "oid-2",
                    "status": "active",
                    "symbol": "BTC_JPY",
                    "side": "sell",
                    "qty": 0.02,
                    "timestamp": "2026-01-01T00:00:01+00:00",
                }
            ]
        )

    monkeypatch.setattr(adapter, "_open_ws_stream", _mock_open_ws_stream)

    stream = iter(adapter.stream_order_events())
    first = next(stream)
    second = next(stream)

    assert isinstance(first, NormalizedError)
    assert first.category == "network"
    assert not isinstance(second, NormalizedError)
    assert second.order_id == "oid-2"


def test_signed_subscribe_payload_for_auth_channel(monkeypatch):
    adapter = GMOAdapter(product_type="spot", use_http=True)
    monkeypatch.setenv("GMO_API_KEY", "key")
    monkeypatch.setenv("GMO_API_SECRET", "secret")

    payload = adapter._build_ws_subscribe_payload(
        channel="orderEvents",
        auth_required=True,
    )

    assert payload["command"] == "subscribe"
    assert payload["channel"] == "orderEvents"
    assert payload["apiKey"] == "key"
    assert isinstance(payload["timestamp"], str)
    assert isinstance(payload["signature"], str)
    assert len(payload["signature"]) == 64
