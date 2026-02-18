from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    Generic,
    Iterable,
    Iterator,
    Literal,
    Protocol,
    TypeVar,
    runtime_checkable,
)


ProductType = Literal["spot", "leverage"]
TReadModel = TypeVar("TReadModel")


@dataclass(slots=True)
class NormalizedOrder:
    exchange: str
    product_type: ProductType
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
    category: Literal["auth", "rate_limit", "validation", "network", "exchange"]
    retryable: bool
    source_code: str | None
    message: str


@dataclass(slots=True)
class ReadFailureInfo:
    category: Literal["auth", "rate_limit", "validation", "network", "exchange"]
    retryable: bool
    source_code: str | None
    message: str


class ErrorAwareList(Generic[TReadModel], list[TReadModel]):
    def __init__(
        self,
        items: Iterable[TReadModel] | None = None,
        *,
        error: ReadFailureInfo | None = None,
    ) -> None:
        super().__init__(items or [])
        self.error = error


@dataclass(slots=True)
class NormalizedKline:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class NormalizedBalance:
    asset: str
    total: float
    available: float
    account_type: str
    product_type: ProductType


@dataclass(slots=True)
class NormalizedPosition:
    symbol: str
    side: str
    qty: float
    entry_price: float | None
    leverage: float | None
    unrealized_pnl: float | None
    product_type: ProductType


@dataclass(slots=True)
class NormalizedOrderState:
    order_id: str
    status: str
    symbol: str | None
    side: str | None
    order_type: str | None
    qty: float | None
    price: float | None
    product_type: ProductType
    reduce_only: bool | None
    raw: dict[str, Any]


@dataclass(slots=True)
class NormalizedTicker:
    symbol: str
    bid: float | None
    ask: float | None
    last: float | None
    timestamp: datetime | None
    product_type: ProductType


@dataclass(slots=True)
class NormalizedOrderEvent:
    order_id: str
    status: str
    symbol: str | None
    side: str | None
    qty: float | None
    product_type: ProductType
    timestamp: datetime | None


@dataclass(slots=True)
class NormalizedAccountEvent:
    event_type: str
    asset: str | None
    balance: float | None
    available: float | None
    product_type: ProductType
    timestamp: datetime | None


@runtime_checkable
class ExchangeProtocol(Protocol):
    def normalize_error(
        self,
        *,
        source_code: str | None,
        message: str,
    ) -> NormalizedError: ...

    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> ErrorAwareList[NormalizedKline]: ...

    def fetch_ticker(self, symbol: str) -> NormalizedTicker | NormalizedError: ...

    def fetch_balances(
        self, account_type: str
    ) -> list[NormalizedBalance] | NormalizedError: ...

    def fetch_positions(self, symbol: str) -> ErrorAwareList[NormalizedPosition]: ...

    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState: ...

    def cancel_order(self, order_id: str) -> NormalizedOrderState: ...

    def fetch_order(self, order_id: str) -> NormalizedOrderState: ...

    def stream_order_events(
        self,
    ) -> Iterator[NormalizedOrderEvent | NormalizedError]: ...

    def stream_account_events(
        self,
    ) -> Iterator[NormalizedAccountEvent | NormalizedError]: ...
