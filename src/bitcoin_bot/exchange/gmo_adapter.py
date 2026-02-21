from __future__ import annotations

import hashlib
import hmac
import json
import os
import base64
import secrets
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime
from time import sleep, time
from typing import Callable, Iterator, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
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
    ws_url: str = "wss://api.coin.z.com/ws"
    use_http: bool = False
    timeout_seconds: float = 5.0
    private_retry_max_attempts: int = 3
    private_retry_base_delay_seconds: float = 0.0
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
        if self.private_retry_max_attempts < 1:
            raise ValueError(
                f"private_retry_max_attempts must be >=1, got {self.private_retry_max_attempts}"
            )
        if self.private_retry_base_delay_seconds < 0.0:
            raise ValueError(
                "private_retry_base_delay_seconds must be >=0.0, "
                f"got {self.private_retry_base_delay_seconds}"
            )

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

    def _auth_headers(
        self,
        method: str,
        path_with_query: str,
        body_text: str = "",
    ) -> dict[str, str] | None:
        api_key = os.getenv("GMO_API_KEY")
        api_secret = os.getenv("GMO_API_SECRET")
        if not api_key or not api_secret:
            return None

        timestamp = str(int(time() * 1000))
        sign_text = f"{timestamp}{method}{path_with_query}{body_text}"
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
        body: dict[str, object] | None = None,
        auth: bool = False,
    ) -> dict | NormalizedError:
        query = urlencode(params or {})
        path_with_query = f"{path}?{query}" if query else path
        url = f"{self.api_base_url}{path_with_query}"

        body_text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        if body is not None:
            body_text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        else:
            body_text = ""

        headers = {"Content-Type": "application/json"}
        if auth:
            auth_headers = self._auth_headers(method, path_with_query, body_text)
            if auth_headers is None:
                return self.normalize_error(
                    source_code="AUTH_FAILED",
                    message="missing_gmo_api_credentials",
                )
            headers.update(auth_headers)

        request = Request(
            url=url,
            headers=headers,
            data=body_text.encode("utf-8") if body is not None else None,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return self._normalize_http_error(exc.code, str(exc))
        except (URLError, TimeoutError) as exc:
            return self.normalize_error(source_code="NETWORK_TIMEOUT", message=str(exc))

    def _request_json_private_with_retry(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        body: dict[str, object] | None = None,
    ) -> dict | NormalizedError:
        attempts = max(1, int(self.private_retry_max_attempts))
        base_delay = max(0.0, float(self.private_retry_base_delay_seconds))

        for attempt_index in range(attempts):
            result = self._request_json(
                method=method,
                path=path,
                params=params,
                auth=True,
                **({"body": body} if body is not None else {}),
            )
            if not isinstance(result, NormalizedError):
                return result

            if result.category not in {"rate_limit", "network"}:
                return result

            if attempt_index >= attempts - 1:
                return result

            if base_delay > 0.0:
                sleep(base_delay * (2**attempt_index))

        return self.normalize_error(
            source_code="EXCHANGE_ERROR",
            message="private_retry_exhausted",
        )

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

    def _ws_connect_socket(self) -> socket.socket:
        parsed = urlparse(self.ws_url)
        if parsed.scheme not in {"ws", "wss"}:
            raise ConnectionError("invalid_ws_scheme")

        host = parsed.hostname
        if host is None:
            raise ConnectionError("invalid_ws_host")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)

        sock = socket.create_connection((host, port), timeout=self.timeout_seconds)
        sock.settimeout(self.timeout_seconds)
        if parsed.scheme == "wss":
            context = ssl.create_default_context()
            wrapped = context.wrap_socket(sock, server_hostname=host)
            wrapped.settimeout(self.timeout_seconds)
            return wrapped
        return sock

    def _ws_handshake(self, ws_sock: socket.socket) -> None:
        parsed = urlparse(self.ws_url)
        host = parsed.hostname
        if host is None:
            raise ConnectionError("invalid_ws_host")
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        sec_key = secrets.token_bytes(16)
        sec_key_b64 = base64.b64encode(sec_key).decode("ascii")

        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {sec_key_b64}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        ws_sock.sendall(request.encode("utf-8"))
        response = ws_sock.recv(4096).decode("utf-8", errors="ignore")
        if " 101 " not in response:
            raise ConnectionError("ws_handshake_not_101")

    def _encode_ws_text_frame(self, text: str) -> bytes:
        payload = text.encode("utf-8")
        payload_len = len(payload)

        first = 0x81
        mask_bit = 0x80
        if payload_len < 126:
            header = bytes([first, mask_bit | payload_len])
        elif payload_len < (1 << 16):
            header = bytes([first, mask_bit | 126]) + payload_len.to_bytes(2, "big")
        else:
            header = bytes([first, mask_bit | 127]) + payload_len.to_bytes(8, "big")

        mask_key = secrets.token_bytes(4)
        masked = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
        return header + mask_key + masked

    def _recv_exact(self, ws_sock: socket.socket, length: int) -> bytes:
        data = bytearray()
        while len(data) < length:
            chunk = ws_sock.recv(length - len(data))
            if not chunk:
                raise ConnectionError("ws_connection_closed")
            data.extend(chunk)
        return bytes(data)

    def _recv_ws_text(self, ws_sock: socket.socket) -> str:
        first_two = self._recv_exact(ws_sock, 2)
        opcode = first_two[0] & 0x0F
        masked = (first_two[1] & 0x80) != 0
        length = first_two[1] & 0x7F

        if length == 126:
            length = int.from_bytes(self._recv_exact(ws_sock, 2), "big")
        elif length == 127:
            length = int.from_bytes(self._recv_exact(ws_sock, 8), "big")

        mask_key = self._recv_exact(ws_sock, 4) if masked else b""
        payload = self._recv_exact(ws_sock, length)
        if masked:
            payload = bytes(
                byte ^ mask_key[index % 4] for index, byte in enumerate(payload)
            )

        if opcode == 0x8:
            raise ConnectionError("ws_closed")
        if opcode == 0x9:
            pong = bytes([0x8A, 0x00])
            ws_sock.sendall(pong)
            return ""
        if opcode != 0x1:
            return ""

        return payload.decode("utf-8", errors="ignore")

    def _build_ws_subscribe_payload(
        self,
        *,
        channel: str,
        auth_required: bool,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"command": "subscribe", "channel": channel}
        if auth_required:
            api_key = os.getenv("GMO_API_KEY")
            api_secret = os.getenv("GMO_API_SECRET")
            if not api_key or not api_secret:
                raise PermissionError("missing_gmo_api_credentials")
            timestamp = str(int(time() * 1000))
            sign_text = f"{timestamp}GET/ws"
            signature = hmac.new(
                api_secret.encode("utf-8"),
                sign_text.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            payload.update(
                {
                    "apiKey": api_key,
                    "timestamp": timestamp,
                    "signature": signature,
                }
            )
        return payload

    def _open_ws_stream(
        self,
        *,
        channel: str,
        auth_required: bool,
    ) -> Iterator[dict]:
        ws_sock = self._ws_connect_socket()
        try:
            self._ws_handshake(ws_sock)
            subscribe_payload = self._build_ws_subscribe_payload(
                channel=channel,
                auth_required=auth_required,
            )
            ws_sock.sendall(
                self._encode_ws_text_frame(
                    json.dumps(
                        subscribe_payload, ensure_ascii=False, separators=(",", ":")
                    )
                )
            )

            while True:
                message = self._recv_ws_text(ws_sock)
                if not message:
                    continue
                parsed = json.loads(message)
                if isinstance(parsed, dict):
                    yield parsed
        finally:
            try:
                ws_sock.close()
            except OSError:
                pass

    def _iter_ws_stream(
        self,
        *,
        channel: str,
        auth_required: bool,
        parser: Callable[[dict], TStreamEvent],
    ) -> Iterator[TStreamEvent | NormalizedError]:
        if auth_required and (
            not os.getenv("GMO_API_KEY") or not os.getenv("GMO_API_SECRET")
        ):
            yield self.normalize_error(
                source_code="AUTH_FAILED",
                message="missing_gmo_api_credentials",
            )
            return

        reconnect_attempts = 0
        while True:
            try:
                for payload in self._open_ws_stream(
                    channel=channel,
                    auth_required=auth_required,
                ):
                    yield parser(payload)
                return
            except PermissionError as exc:
                yield self.normalize_error(
                    source_code="AUTH_FAILED",
                    message=str(exc),
                )
                return
            except (
                URLError,
                ConnectionError,
                TimeoutError,
                OSError,
                ssl.SSLError,
            ) as exc:
                yield self.normalize_error(
                    source_code="NETWORK_TIMEOUT",
                    message=str(exc),
                )
                reconnect_attempts += 1
                if reconnect_attempts > 1:
                    return
            except Exception as exc:  # pragma: no cover - defensive
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
            payload = self._request_json_private_with_retry(
                method="GET",
                path="/private/v1/account/assets",
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
            payload = self._request_json_private_with_retry(
                method="GET",
                path="/private/v1/openPositions",
                params={"symbol": symbol},
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
        if self.use_http:
            request_body: dict[str, object] = {
                "symbol": order_request.symbol,
                "side": order_request.side.upper(),
                "executionType": order_request.order_type.upper(),
                "size": str(order_request.qty),
            }
            if order_request.price is not None:
                request_body["price"] = str(order_request.price)
            if order_request.time_in_force is not None:
                request_body["timeInForce"] = order_request.time_in_force
            if self._is_leverage:
                request_body["reduceOnly"] = bool(reduce_only)

            payload = self._request_json_private_with_retry(
                method="POST",
                path="/private/v1/order",
                body=request_body,
            )

            if isinstance(payload, NormalizedError):
                return NormalizedOrderState(
                    order_id=order_request.client_order_id,
                    status="error",
                    symbol=order_request.symbol,
                    side=order_request.side,
                    order_type=order_request.order_type,
                    qty=order_request.qty,
                    price=order_request.price,
                    product_type=self.product_type,
                    reduce_only=reduce_only,
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

            response_data = payload.get("data", {}) if isinstance(payload, dict) else {}
            if isinstance(response_data, list):
                response_data = response_data[0] if response_data else {}
            if not isinstance(response_data, dict):
                response_data = {}

            resolved_order_id = str(
                response_data.get("orderId")
                or response_data.get("id")
                or order_request.client_order_id
            )
            resolved_status = str(response_data.get("status", "accepted"))

            return NormalizedOrderState(
                order_id=resolved_order_id,
                status=resolved_status,
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
                    "request": request_body,
                    "response": response_data,
                },
            )

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
        if self.use_http:
            payload = self._request_json_private_with_retry(
                method="POST",
                path="/private/v1/cancelOrder",
                body={"orderId": order_id},
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

            response_data = payload.get("data", {}) if isinstance(payload, dict) else {}
            if isinstance(response_data, list):
                response_data = response_data[0] if response_data else {}
            if not isinstance(response_data, dict):
                response_data = {}

            return NormalizedOrderState(
                order_id=str(response_data.get("orderId") or order_id),
                status=str(response_data.get("status", "cancelled")),
                symbol=response_data.get("symbol")
                if response_data.get("symbol") is not None
                else None,
                side=response_data.get("side")
                if response_data.get("side") is not None
                else None,
                order_type=response_data.get("orderType")
                if response_data.get("orderType") is not None
                else None,
                qty=self._to_float(
                    response_data.get("size") or response_data.get("qty")
                ),
                price=self._to_float(response_data.get("price")),
                product_type=self.product_type,
                reduce_only=(
                    bool(response_data.get("settleType")) if self._is_leverage else None
                ),
                raw={"exchange": "gmo", "payload": response_data},
            )

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
            payload = self._request_json_private_with_retry(
                method="GET",
                path="/private/v1/activeOrders",
                params={"orderId": order_id},
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
        if self.order_stream_source_factory is None and self.use_http:
            return self._iter_ws_stream(
                channel="orderEvents",
                auth_required=True,
                parser=self._parse_order_event,
            )
        return self._iter_with_reconnect(
            factory=self.order_stream_source_factory,
            parser=self._parse_order_event,
        )

    def stream_account_events(
        self,
    ) -> Iterator[NormalizedAccountEvent | NormalizedError]:
        if self.account_stream_source_factory is None and self.use_http:
            return self._iter_ws_stream(
                channel="executionEvents",
                auth_required=True,
                parser=self._parse_account_event,
            )
        return self._iter_with_reconnect(
            factory=self.account_stream_source_factory,
            parser=self._parse_account_event,
        )
