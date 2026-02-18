from __future__ import annotations

from datetime import UTC, datetime

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import ErrorAwareList, NormalizedError


def test_fetch_klines_failure_returns_error_aware_empty_list(monkeypatch):
    adapter = GMOAdapter(product_type="spot", use_http=True)

    def _mock_error(*, method, path, params=None, auth=False):
        return NormalizedError(
            category="network",
            retryable=True,
            source_code="NETWORK_TIMEOUT",
            message="timeout",
        )

    monkeypatch.setattr(adapter, "_request_json", _mock_error)

    result = adapter.fetch_klines(
        "BTC_JPY", "1m", datetime.now(UTC), datetime.now(UTC), 10
    )

    assert isinstance(result, ErrorAwareList)
    assert result == []
    assert result.error is not None
    assert result.error.category == "network"
    assert result.error.source_code == "NETWORK_TIMEOUT"


def test_fetch_positions_failure_returns_error_aware_empty_list(monkeypatch):
    adapter = GMOAdapter(product_type="leverage", use_http=True)

    def _mock_error(*, method, path, params=None, auth=False):
        return NormalizedError(
            category="auth",
            retryable=False,
            source_code="AUTH_FAILED",
            message="invalid credentials",
        )

    monkeypatch.setattr(adapter, "_request_json", _mock_error)

    result = adapter.fetch_positions("BTC_JPY")

    assert isinstance(result, ErrorAwareList)
    assert result == []
    assert result.error is not None
    assert result.error.category == "auth"
    assert result.error.source_code == "AUTH_FAILED"


def test_fetch_order_failure_keeps_error_status_and_product_type(monkeypatch):
    adapter = GMOAdapter(product_type="spot", use_http=True)

    def _mock_error(*, method, path, params=None, auth=False):
        return NormalizedError(
            category="exchange",
            retryable=True,
            source_code="EXCHANGE_ERROR",
            message="temporary unavailable",
        )

    monkeypatch.setattr(adapter, "_request_json", _mock_error)

    result = adapter.fetch_order("oid-1")

    assert result.status == "error"
    assert result.product_type == "spot"
    assert result.raw["error"]["category"] == "exchange"
    assert result.raw["error"]["source_code"] == "EXCHANGE_ERROR"
