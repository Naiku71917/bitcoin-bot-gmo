from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import (
    ExchangeProtocol,
    NormalizedAccountEvent,
    NormalizedBalance,
    NormalizedError,
    NormalizedOrder,
    NormalizedOrderEvent,
    NormalizedOrderState,
    NormalizedTicker,
)


def test_gmo_adapter_satisfies_exchange_protocol():
    adapter = GMOAdapter(product_type="spot")
    assert isinstance(adapter, ExchangeProtocol)


@pytest.mark.parametrize(
    ("product_type", "expected_reduce_only"),
    [("spot", None), ("leverage", True)],
)
def test_gmo_adapter_spot_leverage_switching(
    product_type: str, expected_reduce_only: bool | None
):
    adapter = GMOAdapter(product_type=product_type)  # type: ignore[arg-type]

    balances = adapter.fetch_balances(account_type="main")
    assert not isinstance(balances, NormalizedError)
    assert balances
    assert isinstance(balances[0], NormalizedBalance)
    assert all(balance.product_type == product_type for balance in balances)

    order_request = NormalizedOrder(
        exchange="gmo",
        product_type=product_type,  # type: ignore[arg-type]
        symbol="BTC_JPY",
        side="buy",
        order_type="limit",
        time_in_force="GTC",
        qty=0.01,
        price=1000000.0,
        reduce_only=True,
        client_order_id="cid-1",
    )
    placed = adapter.place_order(order_request)
    assert isinstance(placed, NormalizedOrderState)
    assert placed.product_type == product_type
    assert placed.reduce_only == expected_reduce_only


def test_gmo_adapter_mandatory_methods_return_normalized_models():
    adapter = GMOAdapter(product_type="leverage")

    klines = adapter.fetch_klines(
        symbol="BTC_JPY",
        timeframe="1m",
        start=datetime.now(UTC),
        end=datetime.now(UTC),
        limit=10,
    )
    ticker = adapter.fetch_ticker(symbol="BTC_JPY")
    positions = adapter.fetch_positions(symbol="BTC_JPY")
    cancelled = adapter.cancel_order(order_id="oid-1")
    fetched = adapter.fetch_order(order_id="oid-1")
    order_events = list(adapter.stream_order_events())
    account_events = list(adapter.stream_account_events())

    assert isinstance(klines, list)
    assert isinstance(ticker, NormalizedTicker)
    assert ticker.product_type == "leverage"
    assert isinstance(positions, list)
    assert isinstance(cancelled, NormalizedOrderState)
    assert isinstance(fetched, NormalizedOrderState)
    assert all(isinstance(event, NormalizedOrderEvent) for event in order_events)
    assert all(isinstance(event, NormalizedAccountEvent) for event in account_events)
