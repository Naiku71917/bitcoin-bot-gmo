from __future__ import annotations

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import NormalizedError, NormalizedOrder


def _build_order(*, product_type: str, reduce_only: bool | None) -> NormalizedOrder:
    return NormalizedOrder(
        exchange="gmo",
        product_type=product_type,  # type: ignore[arg-type]
        symbol="BTC_JPY",
        side="buy",
        order_type="limit",
        time_in_force="GTC",
        qty=0.01,
        price=1000000.0,
        reduce_only=reduce_only,
        client_order_id="cid-http-order",
    )


def test_place_order_http_success_leverage_includes_reduce_only(monkeypatch):
    adapter = GMOAdapter(product_type="leverage", use_http=True)
    captured: dict[str, object] = {}

    def _mock_request_json(*, method, path, params=None, body=None, auth=False):
        captured.update(
            {
                "method": method,
                "path": path,
                "params": params,
                "body": body,
                "auth": auth,
            }
        )
        return {
            "data": {
                "orderId": "oid-http-1",
                "status": "active",
            }
        }

    monkeypatch.setattr(adapter, "_request_json", _mock_request_json)

    order = _build_order(product_type="leverage", reduce_only=True)
    result = adapter.place_order(order)

    assert captured["method"] == "POST"
    assert captured["path"] == "/private/v1/order"
    assert captured["auth"] is True
    assert isinstance(captured["body"], dict)
    assert captured["body"]["reduceOnly"] is True
    assert result.status == "active"
    assert result.order_id == "oid-http-1"
    assert result.reduce_only is True


def test_place_order_http_success_spot_forces_reduce_only_none(monkeypatch):
    adapter = GMOAdapter(product_type="spot", use_http=True)
    captured: dict[str, object] = {}

    def _mock_request_json(*, method, path, params=None, body=None, auth=False):
        captured.update(
            {
                "method": method,
                "path": path,
                "params": params,
                "body": body,
                "auth": auth,
            }
        )
        return {"data": {"orderId": "oid-http-spot", "status": "accepted"}}

    monkeypatch.setattr(adapter, "_request_json", _mock_request_json)

    order = _build_order(product_type="spot", reduce_only=True)
    result = adapter.place_order(order)

    assert captured["method"] == "POST"
    assert captured["path"] == "/private/v1/order"
    assert captured["auth"] is True
    assert "reduceOnly" not in captured["body"]
    assert result.reduce_only is None


def test_place_order_http_failure_keeps_normalized_error_in_raw(monkeypatch):
    adapter = GMOAdapter(product_type="leverage", use_http=True)

    def _mock_request_json(*, method, path, params=None, body=None, auth=False):
        return NormalizedError(
            category="network",
            retryable=True,
            source_code="NETWORK_TIMEOUT",
            message="timeout",
        )

    monkeypatch.setattr(adapter, "_request_json", _mock_request_json)

    order = _build_order(product_type="leverage", reduce_only=False)
    result = adapter.place_order(order)

    assert result.status == "error"
    assert result.product_type == "leverage"
    assert result.raw["error"]["category"] == "network"
    assert result.raw["error"]["source_code"] == "NETWORK_TIMEOUT"
    assert result.raw["error"]["retryable"] is True
