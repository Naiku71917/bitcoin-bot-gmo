from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from bitcoin_bot.optimizer.orchestrator import build_optimization_snapshot
from bitcoin_bot.telemetry.discord import send_discord_webhook
from bitcoin_bot.utils.io import atomic_dump_json


def monitor_status_to_value(status: str) -> int:
    mapping = {
        "active": 1,
        "reconnecting": 2,
        "degraded": 0,
    }
    return mapping.get(status, 0)


def emit_run_progress(
    *,
    artifacts_dir: str,
    mode: str,
    status: str,
    last_error: str | None,
    monitor_status: str | None = None,
    reconnect_count: int = 0,
    validation: dict | None = None,
) -> dict:
    allowed_monitor_statuses = {"active", "reconnecting", "degraded"}
    resolved_monitor_status = monitor_status
    if resolved_monitor_status is None:
        if status in {"running", "success"}:
            resolved_monitor_status = "active"
        elif status in {"degraded", "abort", "failed"}:
            resolved_monitor_status = "degraded"
        else:
            resolved_monitor_status = "reconnecting"
    if resolved_monitor_status not in allowed_monitor_statuses:
        resolved_monitor_status = "degraded"

    progress: dict[str, object] = {
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "last_error": last_error,
        "monitor_status": resolved_monitor_status,
        "reconnect_count": reconnect_count,
    }
    if validation is not None:
        progress["validation"] = validation
    output_path = f"{artifacts_dir}/run_progress.json"
    atomic_dump_json(output_path, progress)
    return progress


def emit_run_complete(
    *,
    mode: str,
    started_at: datetime,
    completed_at: datetime,
    pipeline_result: dict,
    artifacts_dir: str,
    discord_enabled: bool,
    optimizer_enabled: bool,
    opt_trials_executed: int,
) -> dict:
    discord_result_raw = send_discord_webhook(enabled=discord_enabled)
    discord_result = {
        "status": discord_result_raw.get("status", "failed"),
        "reason": discord_result_raw.get("reason"),
    }
    optimization_score = pipeline_result.get("optimization_score")
    optimization_salvage = pipeline_result.get("optimization_salvage")
    optimization = build_optimization_snapshot(
        enabled=optimizer_enabled,
        opt_trials=opt_trials_executed,
        score=optimization_score,
        salvage=optimization_salvage,
    )
    pipeline_summary = dict(pipeline_result.get("summary", {}))
    pipeline_summary["opt_trials_executed"] = opt_trials_executed

    run_complete = {
        "run_id": str(uuid.uuid4()),
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "pipeline": {
            "mode": mode,
            "status": pipeline_result.get("status", "unknown"),
            "summary": pipeline_result.get("summary", {}),
        },
        "pipeline_summary": pipeline_summary,
        "optimization": optimization,
        "notifications": {
            "discord": discord_result,
        },
    }

    output_path = f"{artifacts_dir}/run_complete.json"
    atomic_dump_json(output_path, run_complete)

    print("BEGIN_RUN_COMPLETE_JSON")
    print(json.dumps(run_complete, ensure_ascii=False))
    print("END_RUN_COMPLETE_JSON")

    return run_complete
