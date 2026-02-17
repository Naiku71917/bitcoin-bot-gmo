from __future__ import annotations

import json
from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.main import run
from bitcoin_bot.pipeline.backtest_runner import run_backtest


def test_backtest_summary_contains_required_metrics():
    config = RuntimeConfig()
    result = run_backtest(config)

    summary = result["summary"]
    required_metrics = {
        "return",
        "max_drawdown",
        "win_rate",
        "profit_factor",
        "trade_count",
    }
    assert required_metrics.issubset(summary.keys())
    assert isinstance(result["optimization_score"], float)


def test_run_complete_optimization_score_is_present_for_backtest(tmp_path):
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
runtime:
  mode: backtest
exchange:
  product_type: spot
optimizer:
  enabled: true
  opt_trials: 9
notify:
  discord:
    enabled: false
paths:
  artifacts_dir: "./var/artifacts"
  logs_dir: "./var/logs"
  cache_dir: "./var/cache"
""",
        encoding="utf-8",
    )

    run(mode="backtest", config_path=str(config_path))

    payload = json.loads(
        Path("var/artifacts/run_complete.json").read_text(encoding="utf-8")
    )
    assert payload["optimization"]["score"] is not None
    assert isinstance(payload["optimization"]["score"], float)
