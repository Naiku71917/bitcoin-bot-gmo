from __future__ import annotations

from pathlib import Path
from typing import cast
from typing import Protocol

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import (
    NormalizedOrder,
    NormalizedOrderState,
    ProductType,
)
from bitcoin_bot.optimizer.gates import evaluate_risk_guards
from bitcoin_bot.telemetry.reporters import emit_run_progress
from bitcoin_bot.utils.logging import append_audit_event


class OrderPlacerProtocol(Protocol):
    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState: ...


def _default_risk_snapshot() -> dict[str, float]:
    return {
        "current_drawdown": 0.0,
        "current_daily_loss": 0.0,
        "current_position_size": 0.0,
        "current_trade_loss": 0.0,
        "current_leverage": 0.0,
        "current_wallet_drift": 0.0,
    }


def run_live(
    config: RuntimeConfig,
    risk_snapshot: dict[str, float] | None = None,
    exchange_adapter: OrderPlacerProtocol | None = None,
) -> dict:
    execute_orders_enabled = config.runtime.execute_orders
    emit_run_progress(
        artifacts_dir=config.paths.artifacts_dir,
        mode="live",
        status="running",
        last_error=None,
        monitor_status="active",
    )
    heartbeat = Path(config.paths.artifacts_dir) / "heartbeat.txt"
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.write_text("ok", encoding="utf-8")

    snapshot = _default_risk_snapshot()
    if risk_snapshot:
        snapshot.update(risk_snapshot)
    guard_result = evaluate_risk_guards(
        max_drawdown=config.risk.max_drawdown,
        daily_loss_limit=config.risk.daily_loss_limit,
        max_position_size=config.risk.max_position_size,
        max_trade_loss=max(config.risk.daily_loss_limit * 0.5, 0.0),
        max_leverage=config.risk.max_leverage,
        max_wallet_drift=0.02,
        current_drawdown=snapshot["current_drawdown"],
        current_daily_loss=snapshot["current_daily_loss"],
        current_position_size=snapshot["current_position_size"],
        current_trade_loss=snapshot["current_trade_loss"],
        current_leverage=snapshot["current_leverage"],
        current_wallet_drift=snapshot["current_wallet_drift"],
    )
    stop_reason_codes = list(guard_result["reason_codes"])
    order_attempted = False
    order_status = "not_attempted"
    if not execute_orders_enabled:
        stop_reason_codes.append("execute_orders_disabled")
    elif guard_result["status"] == "success":
        adapter = exchange_adapter or GMOAdapter(
            product_type=cast(ProductType, config.exchange.product_type),
            api_base_url=config.exchange.api_base_url,
            use_http=False,
        )
        order_attempted = True
        append_audit_event(
            logs_dir=config.paths.logs_dir,
            event_type="order_attempt",
            payload={
                "symbol": config.exchange.symbol,
                "product_type": config.exchange.product_type,
                "execute_orders": execute_orders_enabled,
            },
        )
        order_result = adapter.place_order(
            NormalizedOrder(
                exchange=config.exchange.name,
                product_type=cast(ProductType, config.exchange.product_type),
                symbol=config.exchange.symbol,
                side="buy",
                order_type="market",
                time_in_force="GTC",
                qty=0.01,
                price=None,
                reduce_only=False
                if config.exchange.product_type == "leverage"
                else None,
                client_order_id="live-min-order",
            )
        )
        order_status = order_result.status
        append_audit_event(
            logs_dir=config.paths.logs_dir,
            event_type="order_result",
            payload={
                "symbol": config.exchange.symbol,
                "product_type": config.exchange.product_type,
                "status": order_status,
                "order_id": order_result.order_id,
            },
        )
    else:
        order_status = "skipped_due_to_risk"
    if guard_result["status"] != "success":
        append_audit_event(
            logs_dir=config.paths.logs_dir,
            event_type="risk_stop",
            payload={
                "status": guard_result["status"],
                "reason_codes": guard_result["reason_codes"],
            },
        )

    reason_codes = list(stop_reason_codes)
    emit_run_progress(
        artifacts_dir=config.paths.artifacts_dir,
        mode="live",
        status=guard_result["status"],
        last_error=reason_codes[0] if reason_codes else None,
        monitor_status="active" if guard_result["status"] == "success" else "degraded",
    )

    return {
        "status": guard_result["status"],
        "summary": {
            "mode": "live",
            "symbol": config.exchange.symbol,
            "product_type": config.exchange.product_type,
            "execute_orders": execute_orders_enabled,
            "order_attempted": order_attempted,
            "order_status": order_status,
            "reason_codes": reason_codes,
            "stop_reason_codes": stop_reason_codes,
            "risk_guards": guard_result,
            "monitor_summary": {
                "status": "active"
                if guard_result["status"] == "success"
                else "degraded",
                "reconnect_count": 0,
            },
        },
    }
