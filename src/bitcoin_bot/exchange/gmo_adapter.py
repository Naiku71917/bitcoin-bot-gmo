from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bitcoin_bot.exchange.protocol import ExchangeProtocol, NormalizedOrder


@dataclass(slots=True)
class GMOAdapter(ExchangeProtocol):
    product_type: str

    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        return []

    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol}

    def fetch_balances(self, account_type: str) -> dict[str, Any]:
        return {"account_type": account_type, "balances": []}

    def fetch_positions(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def place_order(self, order_request: NormalizedOrder) -> dict[str, Any]:
        return {"status": "accepted", "client_order_id": order_request.client_order_id}

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return {"status": "cancelled", "order_id": order_id}

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        return {"order_id": order_id, "status": "unknown"}

    def stream_order_events(self) -> Any:
        return iter(())

    def stream_account_events(self) -> Any:
        return iter(())
