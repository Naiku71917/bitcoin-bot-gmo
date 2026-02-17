from __future__ import annotations

from bitcoin_bot.config.models import RuntimeConfig


def run_paper(config: RuntimeConfig) -> dict:
    return {
        "status": "success",
        "summary": {
            "mode": "paper",
            "symbol": config.exchange.symbol,
            "product_type": config.exchange.product_type,
        },
    }
