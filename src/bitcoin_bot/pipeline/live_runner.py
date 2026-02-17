from __future__ import annotations

from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig


def run_live(config: RuntimeConfig) -> dict:
    heartbeat = Path(config.paths.artifacts_dir) / "heartbeat.txt"
    heartbeat.write_text("ok", encoding="utf-8")
    return {
        "status": "success",
        "summary": {
            "mode": "live",
            "symbol": config.exchange.symbol,
            "product_type": config.exchange.product_type,
        },
    }
