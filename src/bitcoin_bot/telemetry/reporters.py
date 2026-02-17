from __future__ import annotations

import json
import uuid
from datetime import datetime

from bitcoin_bot.optimizer.orchestrator import build_optimization_snapshot
from bitcoin_bot.telemetry.discord import send_discord_webhook
from bitcoin_bot.utils.io import atomic_dump_json


def emit_run_complete(
    *,
    mode: str,
    started_at: datetime,
    completed_at: datetime,
    pipeline_result: dict,
    artifacts_dir: str,
    discord_enabled: bool,
) -> dict:
    discord_result_raw = send_discord_webhook(enabled=discord_enabled)
    discord_result = {
        "status": discord_result_raw.get("status", "failed"),
        "reason": discord_result_raw.get("reason"),
    }
    optimization = build_optimization_snapshot(enabled=True, opt_trials=50)

    run_complete = {
        "run_id": str(uuid.uuid4()),
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "pipeline": {
            "mode": mode,
            "status": pipeline_result.get("status", "unknown"),
            "summary": pipeline_result.get("summary", {}),
        },
        "pipeline_summary": pipeline_result.get("summary", {}),
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
