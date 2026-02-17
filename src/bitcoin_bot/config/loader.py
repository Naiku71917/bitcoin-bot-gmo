from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bitcoin_bot.config.models import (
    DataSettings,
    DiscordSettings,
    ExchangeSettings,
    NotifySettings,
    ObservabilitySettings,
    OptimizerSettings,
    PathSettings,
    RiskSettings,
    RuntimeConfig,
    RuntimeSettings,
    StrategySettings,
)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    section = data.get(name, {})
    return section if isinstance(section, dict) else {}


def load_runtime_config(config_path: str) -> RuntimeConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("Config root must be a mapping")

    runtime = RuntimeSettings(**_section(payload, "runtime"))
    exchange = ExchangeSettings(**_section(payload, "exchange"))
    data = DataSettings(**_section(payload, "data"))
    strategy = StrategySettings(**_section(payload, "strategy"))
    risk = RiskSettings(**_section(payload, "risk"))
    optimizer = OptimizerSettings(**_section(payload, "optimizer"))

    notify_raw = _section(payload, "notify")
    discord = DiscordSettings(**_section(notify_raw, "discord"))
    notify = NotifySettings(discord=discord)

    observability = ObservabilitySettings(**_section(payload, "observability"))
    paths = PathSettings(**_section(payload, "paths"))

    return RuntimeConfig(
        runtime=runtime,
        exchange=exchange,
        data=data,
        strategy=strategy,
        risk=risk,
        optimizer=optimizer,
        notify=notify,
        observability=observability,
        paths=paths,
    )
