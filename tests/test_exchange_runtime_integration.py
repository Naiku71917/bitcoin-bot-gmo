from __future__ import annotations

import json
from typing import Literal
from urllib.error import URLError

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import (
    NormalizedBalance,
    NormalizedError,
    NormalizedTicker,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_gmo_read_only_http_success(monkeypatch):
    requests_seen: list[object] = []

    def _mock_urlopen(request, timeout=5.0):
        requests_seen.append(request)
        if request.full_url.endswith("/public/v1/ticker?symbol=BTC_JPY"):
            return _FakeHTTPResponse(
                {
                    "data": [
                        {
                            "symbol": "BTC_JPY",
                            "bid": "100.1",
                            "ask": "100.2",
                            "last": "100.15",
                        }
                    ]
                }
            )
        return _FakeHTTPResponse(
            {
                "data": [
                    {
                        "symbol": "JPY",
                        "amount": "120000.5",
                        "available": "100000.0",
                    }
                ]
            }
        )

    monkeypatch.setenv("GMO_API_KEY", "dummy-key")
    monkeypatch.setenv("GMO_API_SECRET", "dummy-secret")
    monkeypatch.setattr("bitcoin_bot.exchange.gmo_adapter.urlopen", _mock_urlopen)

    adapter = GMOAdapter(product_type="leverage", use_http=True)
    ticker = adapter.fetch_ticker("BTC_JPY")
    balances = adapter.fetch_balances("main")

    assert isinstance(ticker, NormalizedTicker)
    assert ticker.product_type == "leverage"
    assert isinstance(balances, list)
    assert balances
    assert isinstance(balances[0], NormalizedBalance)
    assert all(balance.product_type == "leverage" for balance in balances)

    private_request = requests_seen[1]
    normalized_headers = {k.lower(): v for k, v in private_request.headers.items()}
    assert normalized_headers.get("api-key")
    assert normalized_headers.get("api-timestamp")
    assert normalized_headers.get("api-sign")


def test_gmo_read_only_http_failure_normalizes_error(monkeypatch):
    def _raise_network_error(request, timeout=5.0):
        raise URLError("network unreachable")

    monkeypatch.setattr(
        "bitcoin_bot.exchange.gmo_adapter.urlopen", _raise_network_error
    )

    adapter = GMOAdapter(product_type="spot", use_http=True)
    ticker = adapter.fetch_ticker("BTC_JPY")

    assert isinstance(ticker, NormalizedError)
    assert ticker.category == "network"
    assert ticker.retryable is True


def test_fetch_balances_requires_auth_and_returns_normalized_error(monkeypatch):
    monkeypatch.delenv("GMO_API_KEY", raising=False)
    monkeypatch.delenv("GMO_API_SECRET", raising=False)

    adapter = GMOAdapter(product_type="spot", use_http=True)
    balances = adapter.fetch_balances("main")

    assert isinstance(balances, NormalizedError)
    assert balances.category == "auth"
    assert balances.retryable is False
