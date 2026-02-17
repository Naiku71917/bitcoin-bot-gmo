from __future__ import annotations

from datetime import UTC, datetime

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import (
    NormalizedAccountEvent,
    NormalizedError,
    NormalizedOrderEvent,
)


def test_stream_order_and_account_events_normal_path():
    now = datetime.now(UTC)

    def _order_source():
        yield {
            "order_id": "oid-1",
            "status": "active",
            "symbol": "BTC_JPY",
            "side": "buy",
            "qty": 0.01,
            "timestamp": now.isoformat(),
        }

    def _account_source():
        yield {
            "event_type": "balance_update",
            "asset": "JPY",
            "balance": 100000.0,
            "available": 90000.0,
            "timestamp": now.isoformat(),
        }

    adapter = GMOAdapter(
        product_type="spot",
        order_stream_source_factory=_order_source,
        account_stream_source_factory=_account_source,
    )

    order_events = list(adapter.stream_order_events())
    account_events = list(adapter.stream_account_events())

    assert len(order_events) == 1
    assert isinstance(order_events[0], NormalizedOrderEvent)
    assert order_events[0].status == "active"

    assert len(account_events) == 1
    assert isinstance(account_events[0], NormalizedAccountEvent)
    assert account_events[0].event_type == "balance_update"


def test_stream_order_events_handles_disconnect_and_recovers():
    now = datetime.now(UTC)
    state = {"calls": 0}

    def _order_source():
        state["calls"] += 1
        if state["calls"] == 1:
            yield {
                "order_id": "oid-1",
                "status": "active",
                "symbol": "BTC_JPY",
                "side": "buy",
                "qty": 0.01,
                "timestamp": now.isoformat(),
            }
            raise ConnectionError("ws disconnected")

        yield {
            "order_id": "oid-2",
            "status": "active",
            "symbol": "BTC_JPY",
            "side": "sell",
            "qty": 0.01,
            "timestamp": now.isoformat(),
        }

    adapter = GMOAdapter(
        product_type="leverage",
        order_stream_source_factory=_order_source,
    )

    events = list(adapter.stream_order_events())

    assert len(events) == 3
    assert isinstance(events[0], NormalizedOrderEvent)
    assert isinstance(events[1], NormalizedError)
    assert events[1].category == "network"
    assert events[1].retryable is True
    assert isinstance(events[2], NormalizedOrderEvent)
    assert events[2].status == "active"
