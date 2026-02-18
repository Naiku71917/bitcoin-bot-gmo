from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime
from time import time
from typing import Callable, Iterator, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bitcoin_bot.exchange.protocol import (
    ErrorAwareList,
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
    ReadFailureInfo,
)


TStreamEvent = TypeVar("TStreamEvent")


@dataclass(slots=True)
class GMOAdapter(ExchangeProtocol):
    product_type: ProductType
    api_base_url: str = "https://api.coin.z.com"
    use_http: bool = False
    timeout_seconds: float = 5.0
    order_stream_source_factory: Callable[[], Iterator[dict]] | None = None
    account_stream_source_factory: Callable[[], Iterator[dict]] | None = None

    def _to_float(self, value: object) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

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

    def _to_datetime(self, value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _iter_with_reconnect(
        self,
        *,
        factory: Callable[[], Iterator[dict]] | None,
        parser: Callable[[dict], TStreamEvent],
    ) -> Iterator[TStreamEvent | NormalizedError]:
        if factory is None:
            return

        reconnect_attempts = 0
        while True:
            source = factory()
            try:
                for payload in source:
                    yield parser(payload)
                return
            except (URLError, ConnectionError, TimeoutError) as exc:
                yield self.normalize_error(
                    source_code="NETWORK_TIMEOUT",
                    message=str(exc),
                )
                reconnect_attempts += 1
                if reconnect_attempts > 1:
                    return
            except Exception as exc:  # pragma: no cover - defensive fallback
                yield self.normalize_error(
                    source_code="EXCHANGE_ERROR",
                    message=str(exc),
                )
                return

    def _failure_info_from_error(self, error: NormalizedError) -> ReadFailureInfo:
        return ReadFailureInfo(
            category=error.category,
            retryable=error.retryable,
            source_code=error.source_code,
            message=error.message,
        )

    def _parse_order_event(self, payload: dict) -> NormalizedOrderEvent:
        return NormalizedOrderEvent(
            order_id=str(payload.get("order_id", "")),
            status=str(payload.get("status", "active")),
            symbol=payload.get("symbol") if payload.get("symbol") is not None else None,
            side=payload.get("side") if payload.get("side") is not None else None,
            qty=self._to_float(payload.get("qty")),
            product_type=self.product_type,
            timestamp=self._to_datetime(payload.get("timestamp")),
        )

    def _parse_account_event(self, payload: dict) -> NormalizedAccountEvent:
        return NormalizedAccountEvent(
            event_type=str(payload.get("event_type", "balance_update")),
            asset=payload.get("asset") if payload.get("asset") is not None else None,
            balance=self._to_float(payload.get("balance")),
            available=self._to_float(payload.get("available")),
            product_type=self.product_type,
            timestamp=self._to_datetime(payload.get("timestamp")),
        )

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
    ) -> ErrorAwareList[NormalizedKline]:
        if self.use_http:
            payload = self._request_json(
                method="GET",
                path="/public/v1/klines",
                params={
                    "symbol": symbol,
                    "interval": timeframe,
                    "limit": str(limit),
                },
            )
            if isinstance(payload, NormalizedError):
                return ErrorAwareList(error=self._failure_info_from_error(payload))

            klines_raw = payload.get("data", [])
            if not isinstance(klines_raw, list):
                return ErrorAwareList(
                    error=ReadFailureInfo(
                        category="validation",
                        retryable=False,
                        source_code="INVALID_RESPONSE",
                        message="klines_data_is_not_list",
                    )
                )

            normalized: list[NormalizedKline] = []
            for row in klines_raw:
                timestamp = self._to_datetime(
                    row.get("timestamp") or row.get("openTime") or row.get("time")
                )
                open_price = self._to_float(row.get("open"))
                high_price = self._to_float(row.get("high"))
                low_price = self._to_float(row.get("low"))
                close_price = self._to_float(row.get("close"))
                volume = self._to_float(row.get("volume"))
                if (
                    timestamp is None
                    or open_price is None
                    or high_price is None
                    or low_price is None
                    or close_price is None
                    or volume is None
                ):
                    continue
                normalized.append(
                    NormalizedKline(
                        timestamp=timestamp,
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=volume,
                    )
                )
            return ErrorAwareList(normalized)
        return ErrorAwareList()

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

    def fetch_positions(self, symbol: str) -> ErrorAwareList[NormalizedPosition]:
        if self.use_http:
            payload = self._request_json(
                method="GET",
                path="/private/v1/openPositions",
                params={"symbol": symbol},
                auth=True,
            )
            if isinstance(payload, NormalizedError):
                return ErrorAwareList(error=self._failure_info_from_error(payload))

            positions_raw = payload.get("data", [])
            if not isinstance(positions_raw, list):
                return ErrorAwareList(
                    error=ReadFailureInfo(
                        category="validation",
                        retryable=False,
                        source_code="INVALID_RESPONSE",
                        message="positions_data_is_not_list",
                    )
                )

            normalized: list[NormalizedPosition] = []
            for row in positions_raw:
                qty = self._to_float(row.get("size") or row.get("qty"))
                if qty is None:
                    continue
                normalized.append(
                    NormalizedPosition(
                        symbol=str(row.get("symbol", symbol)),
                        side=str(row.get("side", "buy")),
                        qty=qty,
                        entry_price=self._to_float(
                            row.get("price") or row.get("entryPrice")
                        ),
                        leverage=self._to_float(row.get("leverage")),
                        unrealized_pnl=self._to_float(
                            row.get("lossGain") or row.get("unrealized_pnl")
                        ),
                        product_type=self.product_type,
                    )
                )
            return ErrorAwareList(normalized)
        return ErrorAwareList()

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
            raw={
                "exchange": "gmo",
                "product_type": self.product_type,
                "client_order_id": order_request.client_order_id,
            },
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
        if self.use_http:
            payload = self._request_json(
                method="GET",
                path="/private/v1/activeOrders",
                params={"orderId": order_id},
                auth=True,
            )
            if isinstance(payload, NormalizedError):
                return NormalizedOrderState(
                    order_id=order_id,
                    status="error",
                    symbol=None,
                    side=None,
                    order_type=None,
                    qty=None,
                    price=None,
                    product_type=self.product_type,
                    reduce_only=None,
                    raw={
                        "exchange": "gmo",
                        "error": {
                            "category": payload.category,
                            "retryable": payload.retryable,
                            "source_code": payload.source_code,
                            "message": payload.message,
                        },
                    },
                )

            orders_raw = payload.get("data", [])
            row = orders_raw[0] if isinstance(orders_raw, list) and orders_raw else {}
            return NormalizedOrderState(
                order_id=str(row.get("orderId", order_id)),
                status=str(row.get("status", "unknown")),
                symbol=row.get("symbol") if row.get("symbol") is not None else None,
                side=row.get("side") if row.get("side") is not None else None,
                order_type=row.get("orderType")
                if row.get("orderType") is not None
                else None,
                qty=self._to_float(row.get("size") or row.get("qty")),
                price=self._to_float(row.get("price")),
                product_type=self.product_type,
                reduce_only=(
                    bool(row.get("settleType")) if self._is_leverage else None
                ),
                raw={"exchange": "gmo", "payload": row},
            )
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

    def stream_order_events(self) -> Iterator[NormalizedOrderEvent | NormalizedError]:
        return self._iter_with_reconnect(
            factory=self.order_stream_source_factory,
            parser=self._parse_order_event,
        )

    def stream_account_events(
        self,
    ) -> Iterator[NormalizedAccountEvent | NormalizedError]:
        return self._iter_with_reconnect(
            factory=self.account_stream_source_factory,
            parser=self._parse_account_event,
        )
