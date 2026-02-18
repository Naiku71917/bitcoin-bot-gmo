#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ARTIFACT_PATH="${LIVE_DRILL_ARTIFACT_PATH:-var/artifacts/live_connectivity_drill.json}"
PRODUCT_TYPE="${LIVE_DRILL_PRODUCT_TYPE:-spot}"
SYMBOL="${LIVE_DRILL_SYMBOL:-BTC_JPY}"

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

"$PYTHON_BIN" - <<'PY' "$ARTIFACT_PATH" "$PRODUCT_TYPE" "$SYMBOL"
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import ErrorAwareList, NormalizedError

artifact_path = Path(sys.argv[1])
product_type = sys.argv[2]
symbol = sys.argv[3]


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


def _check_stream_connection() -> tuple[bool, str | None, str | None]:
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


def _check_stream_reconnection() -> tuple[bool, str | None, str | None]:
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


checks: list[dict[str, object]] = []
adapter = GMOAdapter(product_type=product_type, use_http=True)

for name, func in (
    ("api_auth_balance", lambda: _check_balances(adapter)),
    ("ticker_read", lambda: _check_ticker(adapter)),
    ("balance_read", lambda: _check_balances(adapter)),
    ("position_read", lambda: _check_positions(adapter)),
    ("stream_connection", _check_stream_connection),
    ("stream_reconnection", _check_stream_reconnection),
):
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
report = {
    "generated_at": datetime.now(UTC).isoformat(),
    "product_type": product_type,
    "symbol": symbol,
    "passed": passed,
    "checks": checks,
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
