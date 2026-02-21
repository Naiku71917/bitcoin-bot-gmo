from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Mode = Literal["backtest", "paper", "live"]
ProductType = Literal["spot", "leverage"]


@dataclass(slots=True)
class RuntimeSettings:
    mode: Mode = "live"
    profile: str = "default"
    interval_seconds: int = 300
    execute_orders: bool = False
    live_http_enabled: bool = False
    live_order_auto_cancel: bool = True


@dataclass(slots=True)
class ExchangeSettings:
    name: str = "gmo"
    product_type: ProductType = "spot"
    symbol: str = "BTC_JPY"
    api_base_url: str = "https://api.coin.z.com"
    ws_url: str = "wss://api.coin.z.com/ws"
    private_retry_max_attempts: int = 3
    private_retry_base_delay_seconds: float = 0.0


@dataclass(slots=True)
class DataSettings:
    timeframe: str = "1m"
    source_priority: list[str] = field(default_factory=lambda: ["api", "csv"])
    csv_path: str = "./data/sample_klines.csv"


@dataclass(slots=True)
class StrategySettings:
    min_confidence: float = 0.55
    ema_fast: int = 12
    ema_slow: int = 26
    rsi_period: int = 14
    atr_period: int = 14
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {"slope_norm": True, "gap_norm": True}
    )


@dataclass(slots=True)
class RiskSettings:
    max_drawdown: float = 0.2
    daily_loss_limit: float = 0.05
    max_position_size: float = 0.1
    max_leverage: float = 2.0
    position_risk_fraction: float = 0.01
    min_order_qty: float = 0.001
    qty_step: float = 0.001


@dataclass(slots=True)
class OptimizerSettings:
    enabled: bool = True
    opt_trials: int = 50


@dataclass(slots=True)
class DiscordSettings:
    enabled: bool = True
    webhook_env: str = "DISCORD_WEBHOOK_URL"


@dataclass(slots=True)
class NotifySettings:
    discord: DiscordSettings = field(default_factory=DiscordSettings)


@dataclass(slots=True)
class ObservabilitySettings:
    prometheus_enabled: bool = True
    prometheus_port: int = 9752
    health_port: int = 9754


@dataclass(slots=True)
class PathSettings:
    artifacts_dir: str = "./var/artifacts"
    logs_dir: str = "./var/logs"
    cache_dir: str = "./var/cache"


@dataclass(slots=True)
class RuntimeConfig:
    runtime: RuntimeSettings = field(default_factory=RuntimeSettings)
    exchange: ExchangeSettings = field(default_factory=ExchangeSettings)
    data: DataSettings = field(default_factory=DataSettings)
    strategy: StrategySettings = field(default_factory=StrategySettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    optimizer: OptimizerSettings = field(default_factory=OptimizerSettings)
    notify: NotifySettings = field(default_factory=NotifySettings)
    observability: ObservabilitySettings = field(default_factory=ObservabilitySettings)
    paths: PathSettings = field(default_factory=PathSettings)
