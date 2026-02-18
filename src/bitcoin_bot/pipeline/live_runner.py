from __future__ import annotations

from pathlib import Path
from typing import cast
from typing import Protocol
from typing import Any

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import (
    NormalizedError,
    NormalizedOrder,
    NormalizedOrderState,
    ProductType,
)
from bitcoin_bot.optimizer.gates import evaluate_risk_guards
from bitcoin_bot.strategy.core import DecisionHooks, IndicatorInput, decide_action
from bitcoin_bot.telemetry.reason_codes import (
    REASON_CODE_EXECUTE_ORDERS_DISABLED,
    REASON_CODE_LIVE_HTTP_DISABLED,
    REASON_CODE_STREAM_DEGRADED,
    REASON_CODE_STREAM_RECONNECTING,
    normalize_reason_codes,
)
from bitcoin_bot.telemetry.reporters import emit_run_progress
from bitcoin_bot.utils.logging import append_audit_event


class OrderPlacerProtocol(Protocol):
    def place_order(self, order_request: NormalizedOrder) -> NormalizedOrderState: ...


def _probe_stream_monitor_status(adapter: Any) -> str:
    reconnecting_detected = False

    for method_name in ("stream_order_events", "stream_account_events"):
        stream_method = getattr(adapter, method_name, None)
        if not callable(stream_method):
            continue
        try:
            stream_iter = iter(stream_method())
            first_item = next(stream_iter, None)
        except Exception:
            return "degraded"

        if isinstance(first_item, NormalizedError):
            if first_item.retryable:
                reconnecting_detected = True
            else:
                return "degraded"

    return "reconnecting" if reconnecting_detected else "active"


def _default_risk_snapshot() -> dict[str, float]:
    return {
        "current_drawdown": 0.0,
        "current_daily_loss": 0.0,
        "current_position_size": 0.0,
        "current_trade_loss": 0.0,
        "current_leverage": 0.0,
        "current_wallet_drift": 0.0,
        "close": 100.0,
        "ema_fast": 101.0,
        "ema_slow": 100.0,
        "rsi": 50.0,
        "atr": 1.0,
    }


def run_live(
    config: RuntimeConfig,
    risk_snapshot: dict[str, float] | None = None,
    exchange_adapter: OrderPlacerProtocol | None = None,
) -> dict:
    execute_orders_enabled = config.runtime.execute_orders
    live_http_active = (
        config.runtime.mode == "live"
        and execute_orders_enabled
        and config.runtime.live_http_enabled
    )
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
    decision = decide_action(
        IndicatorInput(
            close=snapshot["close"],
            ema_fast=snapshot["ema_fast"],
            ema_slow=snapshot["ema_slow"],
            rsi=snapshot["rsi"],
            atr=max(snapshot["atr"], 1e-9),
        ),
        hooks=DecisionHooks(min_confidence=config.strategy.min_confidence),
    )
    adapter = exchange_adapter or GMOAdapter(
        product_type=cast(ProductType, config.exchange.product_type),
        api_base_url=config.exchange.api_base_url,
        use_http=live_http_active,
    )
    stream_monitor_status = _probe_stream_monitor_status(adapter)
    order_attempted = False
    order_status = "not_attempted"
    if not execute_orders_enabled:
        stop_reason_codes.append(REASON_CODE_EXECUTE_ORDERS_DISABLED)
    elif guard_result["status"] == "success" and decision.action in {"buy", "sell"}:
        if not live_http_active:
            stop_reason_codes.append(REASON_CODE_LIVE_HTTP_DISABLED)
            order_status = "skipped_http_disabled"
            append_audit_event(
                logs_dir=config.paths.logs_dir,
                event_type="order_attempt",
                payload={
                    "symbol": config.exchange.symbol,
                    "product_type": config.exchange.product_type,
                    "execute_orders": execute_orders_enabled,
                    "live_http_enabled": config.runtime.live_http_enabled,
                    "decision_action": decision.action,
                    "skipped": True,
                    "skip_reason": REASON_CODE_LIVE_HTTP_DISABLED,
                },
            )
        else:
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
                    side=decision.action,
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
                    "decision_action": decision.action,
                    "status": order_status,
                    "order_id": order_result.order_id,
                },
            )
    elif guard_result["status"] == "success":
        order_status = "skipped_by_strategy"
        append_audit_event(
            logs_dir=config.paths.logs_dir,
            event_type="order_attempt",
            payload={
                "symbol": config.exchange.symbol,
                "product_type": config.exchange.product_type,
                "execute_orders": execute_orders_enabled,
                "decision_action": decision.action,
                "skipped": True,
            },
        )
    else:
        order_status = "skipped_due_to_risk"
    if guard_result["status"] != "success":
        risk_reason_codes = normalize_reason_codes(guard_result["reason_codes"])
        append_audit_event(
            logs_dir=config.paths.logs_dir,
            event_type="risk_stop",
            payload={
                "status": guard_result["status"],
                "reason_codes": risk_reason_codes,
            },
        )

    reason_codes = normalize_reason_codes([*decision.reason_codes, *stop_reason_codes])
    stop_reason_codes = normalize_reason_codes(stop_reason_codes)
    if stream_monitor_status == "reconnecting":
        reason_codes.append(REASON_CODE_STREAM_RECONNECTING)
    elif stream_monitor_status == "degraded":
        reason_codes.append(REASON_CODE_STREAM_DEGRADED)

    reason_codes = normalize_reason_codes(reason_codes)

    resolved_monitor_status = (
        "degraded" if guard_result["status"] != "success" else stream_monitor_status
    )

    emit_run_progress(
        artifacts_dir=config.paths.artifacts_dir,
        mode="live",
        status=guard_result["status"],
        last_error=(
            stop_reason_codes[0]
            if stop_reason_codes
            else (reason_codes[0] if reason_codes else None)
        ),
        monitor_status=resolved_monitor_status,
    )

    return {
        "status": guard_result["status"],
        "summary": {
            "mode": "live",
            "symbol": config.exchange.symbol,
            "product_type": config.exchange.product_type,
            "execute_orders": execute_orders_enabled,
            "live_http_enabled": config.runtime.live_http_enabled,
            "live_http_active": live_http_active,
            "decision_action": decision.action,
            "confidence": decision.confidence,
            "order_attempted": order_attempted,
            "order_status": order_status,
            "reason_codes": reason_codes,
            "stop_reason_codes": stop_reason_codes,
            "risk_guards": guard_result,
            "monitor_summary": {
                "status": resolved_monitor_status,
                "reconnect_count": 0,
            },
        },
    }
