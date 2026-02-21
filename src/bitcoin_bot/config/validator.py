from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from bitcoin_bot.config.models import RuntimeConfig

ALLOWED_MODES = {"backtest", "paper", "live"}
ALLOWED_PRODUCT_TYPES = {"spot", "leverage"}
ALLOWED_BACKTEST_DATA_QUALITY_MODES = {"strict", "fallback"}


def validate_config(config: RuntimeConfig) -> RuntimeConfig:
    if config.runtime.mode not in ALLOWED_MODES:
        raise ValueError(f"Invalid runtime.mode: {config.runtime.mode}")

    if not isinstance(config.runtime.execute_orders, bool):
        raise ValueError(
            f"Invalid runtime.execute_orders: {config.runtime.execute_orders}"
        )

    if not isinstance(config.runtime.live_http_enabled, bool):
        raise ValueError(
            f"Invalid runtime.live_http_enabled: {config.runtime.live_http_enabled}"
        )

    if not isinstance(config.runtime.live_order_auto_cancel, bool):
        raise ValueError(
            "Invalid runtime.live_order_auto_cancel: "
            f"{config.runtime.live_order_auto_cancel}"
        )

    if config.exchange.product_type not in ALLOWED_PRODUCT_TYPES:
        raise ValueError(
            f"Invalid exchange.product_type: {config.exchange.product_type}"
        )

    if config.exchange.private_retry_max_attempts < 1:
        raise ValueError(
            "Invalid exchange.private_retry_max_attempts: "
            f"{config.exchange.private_retry_max_attempts}"
        )

    if config.exchange.private_retry_base_delay_seconds < 0.0:
        raise ValueError(
            "Invalid exchange.private_retry_base_delay_seconds: "
            f"{config.exchange.private_retry_base_delay_seconds}"
        )

    if (
        config.data.backtest_data_quality_mode
        not in ALLOWED_BACKTEST_DATA_QUALITY_MODES
    ):
        raise ValueError(
            "Invalid data.backtest_data_quality_mode: "
            f"{config.data.backtest_data_quality_mode}"
        )

    if not (0.0 < config.risk.position_risk_fraction <= 1.0):
        raise ValueError(
            f"Invalid risk.position_risk_fraction: {config.risk.position_risk_fraction}"
        )

    if config.risk.min_order_qty <= 0.0:
        raise ValueError(f"Invalid risk.min_order_qty: {config.risk.min_order_qty}")

    if config.risk.qty_step <= 0.0:
        raise ValueError(f"Invalid risk.qty_step: {config.risk.qty_step}")

    config.optimizer.opt_trials = max(1, min(500, config.optimizer.opt_trials))

    Path(config.paths.artifacts_dir).mkdir(parents=True, exist_ok=True)
    Path(config.paths.logs_dir).mkdir(parents=True, exist_ok=True)
    Path(config.paths.cache_dir).mkdir(parents=True, exist_ok=True)
    return config


def validate_runtime_environment(
    config: RuntimeConfig,
    environ: Mapping[str, str] | None = None,
) -> dict:
    env = environ if environ is not None else os.environ
    fatal_errors: list[str] = []
    warnings: list[str] = []

    if (
        config.runtime.mode == "live"
        and config.runtime.execute_orders
        and config.runtime.live_http_enabled
    ):
        required_envs = ["GMO_API_KEY", "GMO_API_SECRET"]
        missing = [name for name in required_envs if not env.get(name)]
        if missing:
            fatal_errors.append("missing_required_env:" + ",".join(sorted(missing)))

    discord_status = "disabled"
    discord_reason: str | None = None
    if config.notify.discord.enabled:
        webhook_env = config.notify.discord.webhook_env
        if env.get(webhook_env):
            discord_status = "ready"
        else:
            discord_status = "failed"
            discord_reason = "missing_webhook_url"
            warnings.append("discord_webhook_missing")

    return {
        "fatal_errors": fatal_errors,
        "warnings": warnings,
        "discord": {
            "status": discord_status,
            "reason": discord_reason,
        },
    }
