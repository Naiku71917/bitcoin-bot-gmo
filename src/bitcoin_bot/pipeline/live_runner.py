from __future__ import annotations

from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.optimizer.gates import evaluate_risk_guards
from bitcoin_bot.telemetry.reporters import emit_run_progress


def _default_risk_snapshot() -> dict[str, float]:
    return {
        "current_drawdown": 0.0,
        "current_daily_loss": 0.0,
        "current_position_size": 0.0,
    }


def run_live(
    config: RuntimeConfig, risk_snapshot: dict[str, float] | None = None
) -> dict:
    emit_run_progress(
        artifacts_dir=config.paths.artifacts_dir,
        mode="live",
        status="running",
        last_error=None,
    )
    heartbeat = Path(config.paths.artifacts_dir) / "heartbeat.txt"
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.write_text("ok", encoding="utf-8")

    snapshot = risk_snapshot or _default_risk_snapshot()
    guard_result = evaluate_risk_guards(
        max_drawdown=config.risk.max_drawdown,
        daily_loss_limit=config.risk.daily_loss_limit,
        max_position_size=config.risk.max_position_size,
        current_drawdown=snapshot["current_drawdown"],
        current_daily_loss=snapshot["current_daily_loss"],
        current_position_size=snapshot["current_position_size"],
    )
    emit_run_progress(
        artifacts_dir=config.paths.artifacts_dir,
        mode="live",
        status=guard_result["status"],
        last_error=guard_result["reason_codes"][0]
        if guard_result["reason_codes"]
        else None,
    )

    return {
        "status": guard_result["status"],
        "summary": {
            "mode": "live",
            "symbol": config.exchange.symbol,
            "product_type": config.exchange.product_type,
            "stop_reason_codes": guard_result["reason_codes"],
            "risk_guards": guard_result,
        },
    }
