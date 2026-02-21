#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ARTIFACT_PATH="${LIVE_DRILL_ARTIFACT_PATH:-var/artifacts/live_connectivity_drill.json}"
PRODUCT_TYPE="${LIVE_DRILL_PRODUCT_TYPE:-spot}"
SYMBOL="${LIVE_DRILL_SYMBOL:-BTC_JPY}"
REAL_CONNECT="${LIVE_DRILL_REAL_CONNECT:-0}"
REQUIRE_AUTH="${LIVE_DRILL_REQUIRE_AUTH:-0}"
API_BASE_URL="${LIVE_DRILL_API_BASE_URL:-https://api.coin.z.com}"
WS_URL="${LIVE_DRILL_WS_URL:-wss://api.coin.z.com/ws}"

resolve_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "$PYTHON_BIN"
    return 0
  fi

  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  return 1
}

PYTHON_BIN="$(resolve_python_bin || true)"
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "[live-drill] FAIL: python_not_found"
  echo "[live-drill] cause=exchange detail=python interpreter not available"
  exit 1
fi

mkdir -p "$(dirname "$ARTIFACT_PATH")"

if [[ "$REAL_CONNECT" != "0" && "$REAL_CONNECT" != "1" ]]; then
    echo "[live-drill] FAIL: invalid_live_drill_real_connect"
    echo "[live-drill] cause=exchange detail=LIVE_DRILL_REAL_CONNECT must be 0 or 1"
    exit 1
fi

if [[ "$REQUIRE_AUTH" != "0" && "$REQUIRE_AUTH" != "1" ]]; then
    echo "[live-drill] FAIL: invalid_live_drill_require_auth"
    echo "[live-drill] cause=exchange detail=LIVE_DRILL_REQUIRE_AUTH must be 0 or 1"
    exit 1
fi

"$PYTHON_BIN" - <<'PY' "$ARTIFACT_PATH" "$PRODUCT_TYPE" "$SYMBOL" "$REAL_CONNECT" "$API_BASE_URL" "$WS_URL" "$REQUIRE_AUTH"
from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import ssl
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import URLError

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import ErrorAwareList, NormalizedError

artifact_path = Path(sys.argv[1])
product_type = sys.argv[2]
symbol = sys.argv[3]
real_connect = sys.argv[4] == "1"
api_base_url = sys.argv[5]
ws_url = sys.argv[6]
require_auth = sys.argv[7] == "1"


def _classify_error(error: NormalizedError) -> str:
    return error.category


def _check_ticker(adapter: GMOAdapter) -> tuple[bool, str | None, str | None]:
    result = adapter.fetch_ticker(symbol)
    if isinstance(result, NormalizedError):
        return False, _classify_error(result), result.message
    return True, None, None


def _check_balances(adapter: GMOAdapter) -> tuple[bool, str | None, str | None]:
    result = adapter.fetch_balances("main")
    if isinstance(result, NormalizedError):
        return False, _classify_error(result), result.message
    return True, None, None


def _check_positions(adapter: GMOAdapter) -> tuple[bool, str | None, str | None]:
    result = adapter.fetch_positions(symbol)
    if isinstance(result, ErrorAwareList) and result.error is not None:
        return False, result.error.category, result.error.message
    return True, None, None


def _check_stream_connection_non_destructive() -> tuple[bool, str | None, str | None]:
    adapter = GMOAdapter(
        product_type="spot",
        use_http=False,
        order_stream_source_factory=lambda: iter(
            [
                {
                    "order_id": "drill-order-1",
                    "status": "active",
                    "symbol": symbol,
                    "side": "buy",
                    "qty": 0.001,
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            ]
        ),
        account_stream_source_factory=lambda: iter(
            [
                {
                    "event_type": "balance_update",
                    "asset": "JPY",
                    "balance": 1000,
                    "available": 1000,
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            ]
        ),
    )

    first_order_event = next(iter(adapter.stream_order_events()), None)
    first_account_event = next(iter(adapter.stream_account_events()), None)
    if isinstance(first_order_event, NormalizedError):
        return False, _classify_error(first_order_event), first_order_event.message
    if isinstance(first_account_event, NormalizedError):
        return False, _classify_error(first_account_event), first_account_event.message
    if first_order_event is None or first_account_event is None:
        return False, "exchange", "stream_source_empty"
    return True, None, None


def _check_stream_reconnection_non_destructive() -> tuple[bool, str | None, str | None]:
    state = {"attempt": 0}

    def factory():
        state["attempt"] += 1
        if state["attempt"] == 1:
            def failing_gen():
                raise URLError("temporary disconnect")
                yield {}

            return failing_gen()

        return iter(
            [
                {
                    "order_id": "drill-order-2",
                    "status": "active",
                    "symbol": symbol,
                    "side": "buy",
                    "qty": 0.001,
                    "timestamp": "2026-01-01T00:00:01+00:00",
                }
            ]
        )

    adapter = GMOAdapter(
        product_type="spot",
        use_http=False,
        order_stream_source_factory=factory,
    )

    events = list(adapter.stream_order_events())
    if not events:
        return False, "exchange", "stream_no_events"

    first = events[0]
    if not isinstance(first, NormalizedError):
        return False, "exchange", "expected_reconnect_error_event"
    if first.category != "network":
        return False, first.category, first.message

    recovered = [event for event in events[1:] if not isinstance(event, NormalizedError)]
    if not recovered:
        return False, "network", "reconnect_not_recovered"

    return True, None, None


def _check_required_auth_env() -> tuple[bool, str | None, str | None]:
    api_key = os.getenv("GMO_API_KEY")
    api_secret = os.getenv("GMO_API_SECRET")
    if api_key and api_secret:
        return True, None, None
    return False, "auth", "missing_gmo_api_credentials"


def _classify_exception(exc: Exception) -> str:
    text = str(exc).lower()
    if "timed out" in text or "timeout" in text:
        return "network"
    if "429" in text or "rate" in text:
        return "rate_limit"
    return "exchange"


def _ws_handshake_once(target_url: str) -> tuple[bool, str | None, str | None]:
    parsed = urlparse(target_url)
    if parsed.scheme not in {"ws", "wss"}:
        return False, "exchange", "unsupported_ws_scheme"

    host = parsed.hostname
    if host is None:
        return False, "exchange", "invalid_ws_host"

    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    try:
        sock = socket.create_connection((host, port), timeout=5)
        if parsed.scheme == "wss":
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=host)

        sec_key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {sec_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("utf-8"))
        response = sock.recv(4096).decode("utf-8", errors="ignore")
        sock.close()
    except Exception as exc:
        return False, _classify_exception(exc), str(exc)

    if " 101 " not in response:
        return False, "exchange", "ws_handshake_not_101"

    return True, None, None


def _check_stream_connection_real() -> tuple[bool, str | None, str | None]:
    return _ws_handshake_once(ws_url)


def _check_stream_reconnection_real() -> tuple[bool, str | None, str | None]:
    first_ok, first_category, first_detail = _ws_handshake_once(ws_url)
    if not first_ok:
        return False, first_category, f"first_connect_failed:{first_detail}"

    second_ok, second_category, second_detail = _ws_handshake_once(ws_url)
    if not second_ok:
        return False, second_category, f"reconnect_failed:{second_detail}"

    return True, None, None


def _check_non_real_guard() -> tuple[bool, str | None, str | None]:
    return True, None, "real_connect_guarded"


checks: list[dict[str, object]] = []
auth_ready = bool(os.getenv("GMO_API_KEY") and os.getenv("GMO_API_SECRET"))
if real_connect:
    adapter = GMOAdapter(
        product_type=product_type,
        api_base_url=api_base_url,
        use_http=True,
    )
    check_plan = (
        ("api_auth", _check_required_auth_env),
        ("ticker_read", lambda: _check_ticker(adapter)),
        ("balance_read", lambda: _check_balances(adapter)),
        ("position_read", lambda: _check_positions(adapter)),
        ("stream_connection", _check_stream_connection_real),
        ("stream_reconnection", _check_stream_reconnection_real),
    )
else:
    adapter = GMOAdapter(product_type=product_type, use_http=False)
    check_plan = (
        ("real_connect_guard", _check_non_real_guard),
        ("ticker_read", lambda: _check_ticker(adapter)),
        ("balance_read", lambda: _check_balances(adapter)),
        ("position_read", lambda: _check_positions(adapter)),
        ("stream_connection", _check_stream_connection_non_destructive),
        ("stream_reconnection", _check_stream_reconnection_non_destructive),
    )

if require_auth and not auth_ready:
    checks.append(
        {
            "name": "auth_prereq",
            "ok": False,
            "category": "auth",
            "detail": "missing_gmo_api_credentials",
        }
    )
    check_plan = ()

for name, func in check_plan:
    ok, category, detail = func()
    checks.append(
        {
            "name": name,
            "ok": ok,
            "category": category,
            "detail": detail,
        }
    )

passed = all(bool(item["ok"]) for item in checks)
failed_category_counts: dict[str, int] = {}
for item in checks:
    if bool(item["ok"]):
        continue
    category = str(item["category"] or "exchange")
    failed_category_counts[category] = failed_category_counts.get(category, 0) + 1

report = {
    "generated_at": datetime.now(UTC).isoformat(),
    "mode": "real_connect" if real_connect else "non_destructive",
    "require_auth": require_auth,
    "auth_ready": auth_ready,
    "product_type": product_type,
    "symbol": symbol,
    "passed": passed,
    "checks": checks,
    "failed_category_counts": failed_category_counts,
}
artifact_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

for item in checks:
    status = "PASS" if item["ok"] else "FAIL"
    if item["ok"]:
        print(f"[live-drill] {status}: {item['name']}")
    else:
        category = item["category"] or "exchange"
        detail = item["detail"] or "unknown"
        print(f"[live-drill] {status}: {item['name']} cause={category} detail={detail}")

if passed:
    print(f"[live-drill] SUCCESS: all_connectivity_checks_passed artifact={artifact_path}")
    sys.exit(0)

failed_categories = sorted(
    {
        (item["category"] or "exchange")
        for item in checks
        if not bool(item["ok"])
    }
)
print(
    "[live-drill] FAIL: connectivity_checks_failed "
    + "categories="
    + ",".join(failed_categories)
)
sys.exit(1)
PY
