from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.exchange.protocol import NormalizedOrder, NormalizedOrderState
from bitcoin_bot.pipeline.live_runner import run_live
from bitcoin_bot.utils.logging import set_audit_log_policy


@dataclass(slots=True)
class _LifecycleAdapter:
    transitions: tuple[str, ...]
    fetch_retryable: bool | None = None
    cancel_retryable: bool | None = None
    calls: int = 0
    fetch_calls: int = 0
    cancel_calls: int = 0

    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState:
        self.calls += 1
        return NormalizedOrderState(
            order_id="oid-1",
            status=self.transitions[0],
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            qty=order_request.qty,
            price=order_request.price,
            product_type=order_request.product_type,
            reduce_only=order_request.reduce_only,
            raw={"exchange": "fake"},
        )

    def fetch_order(self, order_id: str) -> NormalizedOrderState:
        self.fetch_calls += 1
        status = self.transitions[1] if len(self.transitions) > 1 else "active"
        if status == "error":
            return NormalizedOrderState(
                order_id=order_id,
                status="error",
                symbol="BTC_JPY",
                side="buy",
                order_type="market",
                qty=0.01,
                price=None,
                product_type="spot",
                reduce_only=None,
                raw={
                    "exchange": "fake",
                    "error": {
                        "source_code": "NETWORK_TIMEOUT",
                        "retryable": bool(self.fetch_retryable),
                    },
                },
            )
        return NormalizedOrderState(
            order_id=order_id,
            status=status,
            symbol="BTC_JPY",
            side="buy",
            order_type="market",
            qty=0.01,
            price=None,
            product_type="spot",
            reduce_only=None,
            raw={"exchange": "fake"},
        )

    def cancel_order(self, order_id: str) -> NormalizedOrderState:
        self.cancel_calls += 1
        status = self.transitions[2] if len(self.transitions) > 2 else "cancelled"
        if status == "error":
            return NormalizedOrderState(
                order_id=order_id,
                status="error",
                symbol="BTC_JPY",
                side="buy",
                order_type="market",
                qty=0.01,
                price=None,
                product_type="spot",
                reduce_only=None,
                raw={
                    "exchange": "fake",
                    "error": {
                        "source_code": "EXCHANGE_ERROR",
                        "retryable": bool(self.cancel_retryable),
                    },
                },
            )
        return NormalizedOrderState(
            order_id=order_id,
            status=status,
            symbol="BTC_JPY",
            side="buy",
            order_type="market",
            qty=0.01,
            price=None,
            product_type="spot",
            reduce_only=None,
            raw={"exchange": "fake"},
        )


def _build_config(tmp_path) -> RuntimeConfig:
    set_audit_log_policy(max_bytes=5 * 1024 * 1024, retention=5)
    config = RuntimeConfig()
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = True
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    return config


def _read_events(logs_dir: Path) -> list[dict]:
    events: list[dict] = []
    for path in sorted(logs_dir.glob("audit_events.jsonl*")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            events.append(json.loads(line))
    return events


def test_lifecycle_transition_accepted_active_cancelled(tmp_path):
    config = _build_config(tmp_path)
    adapter = _LifecycleAdapter(("accepted", "active", "cancelled"))

    result = run_live(config, exchange_adapter=adapter)
    summary = result["summary"]

    assert summary["order_status"] == "cancelled"
    assert summary["order_lifecycle"]["transitions"] == [
        "accepted",
        "active",
        "cancelled",
    ]
    assert summary["live_order_auto_cancel"] is True
    assert adapter.fetch_calls == 1
    assert adapter.cancel_calls == 1

    events = _read_events(Path(config.paths.logs_dir))
    event_types = [event["event_type"] for event in events]
    assert "order_fetch_result" in event_types
    assert "order_cancel_result" in event_types


def test_lifecycle_auto_cancel_disabled_stops_at_active_and_logs(tmp_path):
    config = _build_config(tmp_path)
    config.runtime.live_order_auto_cancel = False
    adapter = _LifecycleAdapter(("accepted", "active", "cancelled"))

    result = run_live(config, exchange_adapter=adapter)
    summary = result["summary"]

    assert summary["order_status"] == "active"
    assert summary["order_lifecycle"]["transitions"] == ["accepted", "active"]
    assert summary["live_order_auto_cancel"] is False
    assert adapter.fetch_calls == 1
    assert adapter.cancel_calls == 0

    events = _read_events(Path(config.paths.logs_dir))
    cancel_events = [
        event for event in events if event["event_type"] == "order_cancel_result"
    ]
    assert cancel_events
    assert cancel_events[-1]["payload"]["status"] == "skipped_auto_cancel_disabled"


def test_lifecycle_transition_accepted_rejected_sets_reason_code(tmp_path):
    config = _build_config(tmp_path)
    adapter = _LifecycleAdapter(("accepted", "rejected"))

    result = run_live(config, exchange_adapter=adapter)
    summary = result["summary"]

    assert summary["order_status"] == "rejected"
    assert "order_rejected" in summary["reason_codes"]


def test_lifecycle_fetch_error_keeps_retryable_and_reason_code(tmp_path):
    config = _build_config(tmp_path)
    adapter = _LifecycleAdapter(("accepted", "error"), fetch_retryable=True)

    result = run_live(config, exchange_adapter=adapter)
    summary = result["summary"]

    assert summary["order_status"] == "error"
    assert "order_fetch_failed" in summary["reason_codes"]
    assert summary["order_lifecycle"]["retryable"] is True
