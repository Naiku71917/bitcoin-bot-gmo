from __future__ import annotations

from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig

ALLOWED_MODES = {"backtest", "paper", "live"}
ALLOWED_PRODUCT_TYPES = {"spot", "leverage"}


def validate_config(config: RuntimeConfig) -> RuntimeConfig:
    if config.runtime.mode not in ALLOWED_MODES:
        raise ValueError(f"Invalid runtime.mode: {config.runtime.mode}")

    if not isinstance(config.runtime.execute_orders, bool):
        raise ValueError(
            f"Invalid runtime.execute_orders: {config.runtime.execute_orders}"
        )

    if config.exchange.product_type not in ALLOWED_PRODUCT_TYPES:
        raise ValueError(
            f"Invalid exchange.product_type: {config.exchange.product_type}"
        )

    config.optimizer.opt_trials = max(1, min(500, config.optimizer.opt_trials))

    Path(config.paths.artifacts_dir).mkdir(parents=True, exist_ok=True)
    Path(config.paths.logs_dir).mkdir(parents=True, exist_ok=True)
    Path(config.paths.cache_dir).mkdir(parents=True, exist_ok=True)
    return config
