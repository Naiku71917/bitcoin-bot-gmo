from __future__ import annotations

from datetime import UTC, datetime

from bitcoin_bot.telemetry.reporters import (
    RUN_COMPLETE_SCHEMA_VERSION,
    emit_run_complete,
)


def test_run_complete_schema_version_is_fixed(tmp_path):
    payload = emit_run_complete(
        mode="backtest",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        pipeline_result={
            "status": "success",
            "summary": {
                "mode": "backtest",
                "symbol": "BTC_JPY",
                "product_type": "spot",
            },
        },
        artifacts_dir=str(tmp_path / "artifacts"),
        discord_enabled=False,
        optimizer_enabled=True,
        opt_trials_executed=5,
    )

    assert payload["schema_version"] == RUN_COMPLETE_SCHEMA_VERSION
    assert payload["schema_version"] == "1.0.0"
