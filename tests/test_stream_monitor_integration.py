from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.exchange.protocol import (
    NormalizedAccountEvent,
    NormalizedError,
    NormalizedOrder,
    NormalizedOrderEvent,
    NormalizedOrderState,
)
from bitcoin_bot.pipeline.live_runner import run_live


def _load_run_live_module():
    module_name = "run_live_script_stream_monitor"
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_live.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed_to_load_run_live_module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


run_live_script = _load_run_live_module()


@dataclass(slots=True)
class _FakeAdapter:
    order_event: NormalizedOrderEvent | NormalizedError | None = None
    account_event: NormalizedAccountEvent | NormalizedError | None = None

    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState:
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

    def stream_order_events(self):
        if self.order_event is not None:
            yield self.order_event

    def stream_account_events(self):
        if self.account_event is not None:
            yield self.account_event


def _base_config(tmp_path) -> RuntimeConfig:
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    return config


def test_stream_healthy_keeps_monitor_active(tmp_path):
    config = _base_config(tmp_path)
    adapter = _FakeAdapter(
        order_event=NormalizedOrderEvent(
            order_id="oid-1",
            status="active",
            symbol="BTC_JPY",
            side="buy",
            qty=0.01,
            product_type="spot",
            timestamp=datetime.now(UTC),
        )
    )

    result = run_live(config, exchange_adapter=adapter)
    assert result["summary"]["monitor_summary"]["status"] == "active"


def test_stream_disconnect_marks_reconnecting(tmp_path):
    config = _base_config(tmp_path)
    adapter = _FakeAdapter(
        order_event=NormalizedError(
            category="network",
            retryable=True,
            source_code="NETWORK_TIMEOUT",
            message="stream disconnected",
        )
    )

    result = run_live(config, exchange_adapter=adapter)
    assert result["summary"]["monitor_summary"]["status"] == "reconnecting"


def test_stream_non_retryable_marks_degraded(tmp_path):
    config = _base_config(tmp_path)
    adapter = _FakeAdapter(
        order_event=NormalizedError(
            category="auth",
            retryable=False,
            source_code="AUTH_FAILED",
            message="auth invalid",
        )
    )

    result = run_live(config, exchange_adapter=adapter)
    assert result["summary"]["monitor_summary"]["status"] == "degraded"


def test_run_daemon_loop_reflects_pipeline_monitor_status():
    stop_event = Event()
    runtime_state = run_live_script.RuntimeMetricsState(stop_event=stop_event)

    def _run_once(*, mode: str, config_path: str):
        stop_event.set()
        return {
            "pipeline_summary": {
                "monitor_summary": {
                    "status": "reconnecting",
                }
            }
        }

    run_live_script._run_daemon_loop(
        stop_event=stop_event,
        config_path="configs/runtime.live.spot.yaml",
        artifacts_dir="./var/artifacts",
        interval_seconds=0,
        max_reconnect_retries=0,
        reconnect_wait_seconds=0,
        runtime_state=runtime_state,
        run_func=_run_once,
    )

    assert runtime_state.monitor_status == "reconnecting"
