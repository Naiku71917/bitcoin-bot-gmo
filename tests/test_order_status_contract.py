from __future__ import annotations

from dataclasses import dataclass

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import NormalizedOrder, NormalizedOrderState
from bitcoin_bot.pipeline.live_runner import run_live
from bitcoin_bot.telemetry.reason_codes import REASON_CODES


def test_fetch_order_without_http_returns_explicit_error_state():
    adapter = GMOAdapter(product_type="spot", use_http=False)

    state = adapter.fetch_order("oid-1")

    assert state.status == "error"
    assert state.raw["error"]["source_code"] == "INVALID_RESPONSE"
    assert state.raw["error"]["message"] == "fetch_order_requires_http_mode"
    assert isinstance(state.raw["error"]["retryable"], bool)


def test_fetch_order_http_unknown_status_returns_explicit_error(monkeypatch):
    adapter = GMOAdapter(product_type="spot", use_http=True)

    def _mock_request(*, method, path, params=None, body=None, auth=False):
        return {"data": [{"orderId": "oid-2"}]}

    monkeypatch.setattr(adapter, "_request_json", _mock_request)

    state = adapter.fetch_order("oid-2")

    assert state.status == "error"
    assert state.raw["error"]["source_code"] == "INVALID_RESPONSE"
    assert state.raw["error"]["message"] == "fetch_order_status_unknown"
    assert state.raw["error"]["retryable"] is False


@dataclass(slots=True)
class _FetchUnknownAdapter:
    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState:
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

    def fetch_order(self, order_id: str) -> NormalizedOrderState:
        return NormalizedOrderState(
            order_id=order_id,
            status="error",
            symbol="BTC_JPY",
            side="buy",
            order_type="market",
            qty=0.01,
            price=None,
            product_type="spot",
            reduce_only=None,
            raw={
                "exchange": "fake",
                "error": {
                    "source_code": "INVALID_RESPONSE",
                    "message": "fetch_order_status_unknown",
                    "retryable": False,
                },
            },
        )

    def cancel_order(self, order_id: str) -> NormalizedOrderState:
        return NormalizedOrderState(
            order_id=order_id,
            status="cancelled",
            symbol="BTC_JPY",
            side="buy",
            order_type="market",
            qty=0.01,
            price=None,
            product_type="spot",
            reduce_only=None,
            raw={"exchange": "fake"},
        )

    def fetch_balances(self, account_type: str):
        return []


def test_summary_reason_codes_stay_within_dictionary_values(tmp_path):
    config = RuntimeConfig()
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = True
    config.strategy.min_confidence = 0.0
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")

    result = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 102.0,
            "ema_slow": 100.0,
            "rsi": 50.0,
            "atr": 1.0,
        },
        exchange_adapter=_FetchUnknownAdapter(),
    )

    reason_codes = result["summary"]["reason_codes"]
    assert "order_fetch_failed" in reason_codes
    assert set(reason_codes).issubset(REASON_CODES)
