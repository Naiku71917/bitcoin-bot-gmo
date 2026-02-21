from __future__ import annotations

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import NormalizedError, NormalizedOrder


def _order() -> NormalizedOrder:
    return NormalizedOrder(
        exchange="gmo",
        product_type="spot",
        symbol="BTC_JPY",
        side="buy",
        order_type="limit",
        time_in_force="GTC",
        qty=0.01,
        price=1000000.0,
        reduce_only=None,
        client_order_id="cid-retry-test",
    )


def test_private_retry_retries_network_until_success(monkeypatch):
    adapter = GMOAdapter(
        product_type="spot",
        use_http=True,
        private_retry_max_attempts=3,
        private_retry_base_delay_seconds=0.0,
    )
    calls = {"count": 0}

    def _mock_request_json(*, method, path, params=None, body=None, auth=False):
        calls["count"] += 1
        if calls["count"] < 3:
            return NormalizedError(
                category="network",
                retryable=True,
                source_code="NETWORK_TIMEOUT",
                message="temporary timeout",
            )
        return {"data": {"orderId": "oid-network-recovered", "status": "accepted"}}

    monkeypatch.setattr(adapter, "_request_json", _mock_request_json)

    result = adapter.place_order(_order())

    assert calls["count"] == 3
    assert result.status == "accepted"
    assert result.order_id == "oid-network-recovered"


def test_private_retry_fail_fast_on_auth(monkeypatch):
    adapter = GMOAdapter(
        product_type="spot",
        use_http=True,
        private_retry_max_attempts=5,
        private_retry_base_delay_seconds=0.0,
    )
    calls = {"count": 0}

    def _mock_request_json(*, method, path, params=None, body=None, auth=False):
        calls["count"] += 1
        return NormalizedError(
            category="auth",
            retryable=False,
            source_code="AUTH_FAILED",
            message="invalid key",
        )

    monkeypatch.setattr(adapter, "_request_json", _mock_request_json)

    result = adapter.place_order(_order())

    assert calls["count"] == 1
    assert result.status == "error"
    assert result.raw["error"]["category"] == "auth"


def test_private_retry_fail_fast_on_validation(monkeypatch):
    adapter = GMOAdapter(
        product_type="spot",
        use_http=True,
        private_retry_max_attempts=4,
        private_retry_base_delay_seconds=0.0,
    )
    calls = {"count": 0}

    def _mock_request_json(*, method, path, params=None, body=None, auth=False):
        calls["count"] += 1
        return NormalizedError(
            category="validation",
            retryable=False,
            source_code="INVALID_PARAM",
            message="bad request",
        )

    monkeypatch.setattr(adapter, "_request_json", _mock_request_json)

    result = adapter.fetch_positions("BTC_JPY")

    assert calls["count"] == 1
    assert result.error is not None
    assert result.error.category == "validation"


def test_private_retry_retries_rate_limit_until_max(monkeypatch):
    adapter = GMOAdapter(
        product_type="spot",
        use_http=True,
        private_retry_max_attempts=3,
        private_retry_base_delay_seconds=0.0,
    )
    calls = {"count": 0}

    def _mock_request_json(*, method, path, params=None, body=None, auth=False):
        calls["count"] += 1
        return NormalizedError(
            category="rate_limit",
            retryable=True,
            source_code="RATE_LIMIT",
            message="too many requests",
        )

    monkeypatch.setattr(adapter, "_request_json", _mock_request_json)

    result = adapter.place_order(_order())

    assert calls["count"] == 3
    assert result.status == "error"
    assert result.raw["error"]["category"] == "rate_limit"
