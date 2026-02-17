from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class NormalizedOrder:
    exchange: str
    product_type: str
    symbol: str
    side: str
    order_type: str
    time_in_force: str | None
    qty: float
    price: float | None
    reduce_only: bool | None
    client_order_id: str


@dataclass(slots=True)
class NormalizedFill:
    order_id: str
    fill_qty: float
    fill_price: float
    fee: float
    fee_currency: str
    timestamp: datetime


@dataclass(slots=True)
class NormalizedError:
    category: str
    retryable: bool
    source_code: str | None
    message: str


@runtime_checkable
class ExchangeProtocol(Protocol):
    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[dict[str, Any]]: ...

    def fetch_ticker(self, symbol: str) -> dict[str, Any]: ...

    def fetch_balances(self, account_type: str) -> dict[str, Any]: ...

    def fetch_positions(self, symbol: str) -> list[dict[str, Any]]: ...

    def place_order(self, order_request: NormalizedOrder) -> dict[str, Any]: ...

    def cancel_order(self, order_id: str) -> dict[str, Any]: ...

    def fetch_order(self, order_id: str) -> dict[str, Any]: ...

    def stream_order_events(self) -> Any: ...

    def stream_account_events(self) -> Any: ...
