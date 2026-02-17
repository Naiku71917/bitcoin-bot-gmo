from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime
from time import time
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bitcoin_bot.exchange.protocol import (
    NormalizedAccountEvent,
    ExchangeProtocol,
    NormalizedBalance,
    NormalizedError,
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
    api_base_url: str = "https://api.coin.z.com"
    use_http: bool = False
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.product_type not in {"spot", "leverage"}:
            raise ValueError(f"Unsupported product_type: {self.product_type}")

    @property
    def _is_leverage(self) -> bool:
        return self.product_type == "leverage"

    def _normalize_http_error(self, status_code: int, message: str) -> NormalizedError:
        if status_code in {401, 403}:
            return self.normalize_error(source_code="AUTH_FAILED", message=message)
        if status_code == 429:
            return self.normalize_error(source_code="RATE_LIMIT", message=message)
        if 400 <= status_code < 500:
            return self.normalize_error(source_code="INVALID_PARAM", message=message)
        return self.normalize_error(source_code="EXCHANGE_ERROR", message=message)

    def _auth_headers(self, method: str, path_with_query: str) -> dict[str, str] | None:
        api_key = os.getenv("GMO_API_KEY")
        api_secret = os.getenv("GMO_API_SECRET")
        if not api_key or not api_secret:
            return None

        timestamp = str(int(time() * 1000))
        sign_text = f"{timestamp}{method}{path_with_query}"
        sign = hmac.new(
            api_secret.encode("utf-8"),
            sign_text.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "API-KEY": api_key,
            "API-TIMESTAMP": timestamp,
            "API-SIGN": sign,
        }

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        auth: bool = False,
    ) -> dict | NormalizedError:
        query = urlencode(params or {})
        path_with_query = f"{path}?{query}" if query else path
        url = f"{self.api_base_url}{path_with_query}"

        headers = {"Content-Type": "application/json"}
        if auth:
            auth_headers = self._auth_headers(method, path_with_query)
            if auth_headers is None:
                return self.normalize_error(
                    source_code="AUTH_FAILED",
                    message="missing_gmo_api_credentials",
                )
            headers.update(auth_headers)

        request = Request(url=url, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return self._normalize_http_error(exc.code, str(exc))
        except (URLError, TimeoutError) as exc:
            return self.normalize_error(source_code="NETWORK_TIMEOUT", message=str(exc))

    def normalize_error(
        self,
        *,
        source_code: str | None,
        message: str,
    ) -> NormalizedError:
        normalized_code = (source_code or "").upper()

        if normalized_code in {"AUTH_FAILED", "INVALID_API_KEY", "UNAUTHORIZED"}:
            return NormalizedError(
                category="auth",
                retryable=False,
                source_code=source_code,
                message=message,
            )

        if normalized_code in {"RATE_LIMIT", "TOO_MANY_REQUESTS", "THROTTLED"}:
            return NormalizedError(
                category="rate_limit",
                retryable=True,
                source_code=source_code,
                message=message,
            )

        if normalized_code in {
            "INVALID_PARAM",
            "BAD_REQUEST",
            "INSUFFICIENT_MARGIN",
        }:
            return NormalizedError(
                category="validation",
                retryable=False,
                source_code=source_code,
                message=message,
            )

        if normalized_code in {
            "NETWORK_TIMEOUT",
            "CONNECTION_ERROR",
            "DNS_ERROR",
        }:
            return NormalizedError(
                category="network",
                retryable=True,
                source_code=source_code,
                message=message,
            )

        return NormalizedError(
            category="exchange",
            retryable=True,
            source_code=source_code,
            message=message,
        )

    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[NormalizedKline]:
        return []

    def fetch_ticker(self, symbol: str) -> NormalizedTicker | NormalizedError:
        if self.use_http:
            payload = self._request_json(
                method="GET",
                path="/public/v1/ticker",
                params={"symbol": symbol},
            )
            if isinstance(payload, NormalizedError):
                return payload

            data = payload.get("data", [])
            ticker_raw = data[0] if isinstance(data, list) and data else {}
            return NormalizedTicker(
                symbol=symbol,
                bid=float(ticker_raw.get("bid", 0.0))
                if ticker_raw.get("bid")
                else None,
                ask=float(ticker_raw.get("ask", 0.0))
                if ticker_raw.get("ask")
                else None,
                last=float(ticker_raw.get("last", 0.0))
                if ticker_raw.get("last")
                else None,
                timestamp=None,
                product_type=self.product_type,
            )

        return NormalizedTicker(
            symbol=symbol,
            bid=None,
            ask=None,
            last=None,
            timestamp=None,
            product_type=self.product_type,
        )

    def fetch_balances(
        self, account_type: str
    ) -> list[NormalizedBalance] | NormalizedError:
        if self.use_http:
            payload = self._request_json(
                method="GET",
                path="/private/v1/account/assets",
                auth=True,
            )
            if isinstance(payload, NormalizedError):
                return payload

            balances_raw = payload.get("data", [])
            if not isinstance(balances_raw, list):
                balances_raw = []

            normalized: list[NormalizedBalance] = []
            for row in balances_raw:
                normalized.append(
                    NormalizedBalance(
                        asset=str(row.get("symbol", "")),
                        total=float(row.get("amount", 0.0)),
                        available=float(row.get("available", row.get("amount", 0.0))),
                        account_type=account_type,
                        product_type=self.product_type,
                    )
                )
            return normalized

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
