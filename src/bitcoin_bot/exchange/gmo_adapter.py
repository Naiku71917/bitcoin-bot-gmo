from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from bitcoin_bot.exchange.protocol import (
    NormalizedAccountEvent,
    ExchangeProtocol,
    NormalizedBalance,
    NormalizedKline,
    NormalizedOrder,
    NormalizedOrderEvent,
    NormalizedOrderState,
    NormalizedPosition,
    NormalizedTicker,
    ProductType,
)


@dataclass(slots=True)
class GMOAdapter(ExchangeProtocol):
    product_type: ProductType

    def __post_init__(self) -> None:
        if self.product_type not in {"spot", "leverage"}:
            raise ValueError(f"Unsupported product_type: {self.product_type}")

    @property
    def _is_leverage(self) -> bool:
        return self.product_type == "leverage"

    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[NormalizedKline]:
        return []

    def fetch_ticker(self, symbol: str) -> NormalizedTicker:
        return NormalizedTicker(
            symbol=symbol,
            bid=None,
            ask=None,
            last=None,
            timestamp=None,
            product_type=self.product_type,
        )

    def fetch_balances(self, account_type: str) -> list[NormalizedBalance]:
        return [
            NormalizedBalance(
                asset="JPY",
                total=0.0,
                available=0.0,
                account_type=account_type,
                product_type=self.product_type,
            )
        ]

    def fetch_positions(self, symbol: str) -> list[NormalizedPosition]:
        return []

    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState:
        reduce_only = order_request.reduce_only if self._is_leverage else None
        return NormalizedOrderState(
            order_id=order_request.client_order_id,
            status="accepted",
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            qty=order_request.qty,
            price=order_request.price,
            product_type=self.product_type,
            reduce_only=reduce_only,
            raw={"exchange": "gmo"},
        )

    def cancel_order(self, order_id: str) -> NormalizedOrderState:
        return NormalizedOrderState(
            order_id=order_id,
            status="cancelled",
            symbol=None,
            side=None,
            order_type=None,
            qty=None,
            price=None,
            product_type=self.product_type,
            reduce_only=None,
            raw={"exchange": "gmo"},
        )

    def fetch_order(self, order_id: str) -> NormalizedOrderState:
        return NormalizedOrderState(
            order_id=order_id,
            status="unknown",
            symbol=None,
            side=None,
            order_type=None,
            qty=None,
            price=None,
            product_type=self.product_type,
            reduce_only=None,
            raw={"exchange": "gmo"},
        )

    def stream_order_events(self) -> Iterator[NormalizedOrderEvent]:
        return iter(())

    def stream_account_events(self) -> Iterator[NormalizedAccountEvent]:
        return iter(())
