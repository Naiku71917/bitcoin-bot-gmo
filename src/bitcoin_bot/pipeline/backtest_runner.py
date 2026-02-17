from __future__ import annotations

from bitcoin_bot.config.models import RuntimeConfig


def run_backtest(config: RuntimeConfig) -> dict:
    return {
        "status": "success",
        "summary": {
            "mode": "backtest",
            "symbol": config.exchange.symbol,
            "product_type": config.exchange.product_type,
        },
    }
