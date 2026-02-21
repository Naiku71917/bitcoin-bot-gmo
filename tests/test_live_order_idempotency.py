from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.exchange.protocol import NormalizedOrder, NormalizedOrderState
from bitcoin_bot.pipeline.live_runner import _register_order_attempt, run_live
from bitcoin_bot.utils.io import build_live_client_order_id


@dataclass(slots=True)
class _FakeExchangeAdapter:
    calls: int = 0

    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState:
        self.calls += 1
        return NormalizedOrderState(
            order_id=order_request.client_order_id,
            status="accepted",
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            qty=order_request.qty,
            price=order_request.price,
            product_type=order_request.product_type,
            reduce_only=order_request.reduce_only,
            raw={"exchange": "fake"},
        )


def _build_config(tmp_path) -> RuntimeConfig:
    config = RuntimeConfig()
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = True
    config.strategy.min_confidence = 0.0
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    return config


def _read_audit_events(logs_dir: Path) -> list[dict]:
    events: list[dict] = []
    for path in sorted(logs_dir.glob("audit_events.jsonl*")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            events.append(json.loads(line))
    return events


def test_build_live_client_order_id_contains_symbol_timestamp_and_random():
    oid = build_live_client_order_id("BTC_JPY")

    assert oid.startswith("live-BTCJPY-")
    parts = oid.split("-")
    assert len(parts) == 4
    assert parts[2].isdigit()
    assert len(parts[3]) == 8


def test_register_order_attempt_prevents_duplicate_in_same_loop():
    sent_ids: set[str] = set()

    assert _register_order_attempt("oid-1", sent_ids) is True
    assert _register_order_attempt("oid-1", sent_ids) is False


def test_run_live_stores_client_order_id_in_summary_and_audit(tmp_path):
    config = _build_config(tmp_path)
    adapter = _FakeExchangeAdapter()

    result = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 102.0,
            "ema_slow": 100.0,
            "rsi": 50.0,
            "atr": 1.0,
        },
        exchange_adapter=adapter,
    )

    summary = result["summary"]
    client_order_id = summary["order_client_order_id"]

    assert adapter.calls == 1
    assert isinstance(client_order_id, str)
    assert client_order_id.startswith("live-BTCJPY-")

    events = _read_audit_events(Path(config.paths.logs_dir))
    order_attempt_events = [
        event for event in events if event["event_type"] == "order_attempt"
    ]
    order_result_events = [
        event for event in events if event["event_type"] == "order_result"
    ]
    assert order_attempt_events
    assert order_result_events
    assert order_attempt_events[-1]["payload"]["client_order_id"] == client_order_id
    assert order_result_events[-1]["payload"]["client_order_id"] == client_order_id
