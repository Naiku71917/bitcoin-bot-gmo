from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.exchange.protocol import (
    NormalizedBalance,
    NormalizedOrder,
    NormalizedOrderState,
)
from bitcoin_bot.pipeline.live_runner import run_live


@dataclass(slots=True)
class _SizingAdapter:
    available_jpy: float
    last_qty: float | None = None

    def fetch_balances(self, account_type: str):
        return [
            NormalizedBalance(
                asset="JPY",
                total=self.available_jpy,
                available=self.available_jpy,
                account_type=account_type,
                product_type="spot",
            )
        ]

    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState:
        self.last_qty = order_request.qty
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

    def fetch_order(self, order_id: str) -> NormalizedOrderState:
        return NormalizedOrderState(
            order_id=order_id,
            status="accepted",
            symbol="BTC_JPY",
            side="buy",
            order_type="market",
            qty=self.last_qty,
            price=None,
            product_type="spot",
            reduce_only=None,
            raw={"exchange": "fake"},
        )

    def cancel_order(self, order_id: str) -> NormalizedOrderState:
        return NormalizedOrderState(
            order_id=order_id,
            status="cancelled",
            symbol="BTC_JPY",
            side="buy",
            order_type="market",
            qty=self.last_qty,
            price=None,
            product_type="spot",
            reduce_only=None,
            raw={"exchange": "fake"},
        )


def _config(tmp_path) -> RuntimeConfig:
    config = RuntimeConfig()
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = True
    config.strategy.min_confidence = 0.0
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    return config


def _read_events(logs_dir: Path) -> list[dict]:
    path = logs_dir / "audit_events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_qty_changes_with_atr_and_balance(tmp_path):
    config = _config(tmp_path)

    low_vol = _SizingAdapter(available_jpy=100_000)
    high_vol = _SizingAdapter(available_jpy=50_000)

    low_result = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 102.0,
            "ema_slow": 100.0,
            "rsi": 50.0,
            "atr": 1.0,
        },
        exchange_adapter=low_vol,
    )
    high_result = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 102.0,
            "ema_slow": 100.0,
            "rsi": 50.0,
            "atr": 5.0,
        },
        exchange_adapter=high_vol,
    )

    low_qty = low_result["summary"]["order_sizing"]["final_qty"]
    high_qty = high_result["summary"]["order_sizing"]["final_qty"]

    assert low_qty > high_qty
    assert low_qty > 0.0
    assert high_qty > 0.0


def test_qty_respects_min_order_and_step_and_logs_basis(tmp_path):
    config = _config(tmp_path)
    config.risk.min_order_qty = 0.02
    config.risk.qty_step = 0.01
    config.risk.position_risk_fraction = 0.001

    adapter = _SizingAdapter(available_jpy=10)
    result = run_live(
        config,
        risk_snapshot={
            "close": 100.0,
            "ema_fast": 102.5,
            "ema_slow": 100.0,
            "rsi": 50.0,
            "atr": 10.0,
        },
        exchange_adapter=adapter,
    )

    summary = result["summary"]
    assert summary["order_status"] == "skipped_qty_too_small"
    assert summary["order_sizing"]["final_qty"] == 0.0
    assert "order_size_too_small" in summary["reason_codes"]

    events = _read_events(Path(config.paths.logs_dir))
    order_attempts = [e for e in events if e["event_type"] == "order_attempt"]
    assert order_attempts
    assert "order_sizing" in order_attempts[-1]["payload"]
