from __future__ import annotations

import json
from pathlib import Path

from bitcoin_bot.main import run


def test_run_complete_optimization_contract_and_trials_recorded(tmp_path):
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
runtime:
  mode: backtest
exchange:
  product_type: spot
optimizer:
  enabled: true
  opt_trials: 7
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

    artifact = json.loads(
        Path("var/artifacts/run_complete.json").read_text(encoding="utf-8")
    )

    optimization = artifact["optimization"]
    assert "score" in optimization
    assert "gates" in optimization
    assert "accept" in optimization["gates"]
    assert "reasons" in optimization["gates"]
    assert isinstance(optimization["gates"]["reasons"], list)
    assert "salvage" in optimization

    assert artifact["pipeline_summary"]["opt_trials_executed"] == 7


def test_run_complete_contract_top_level_keys_remain(tmp_path):
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
runtime:
  mode: backtest
exchange:
  product_type: spot
optimizer:
  enabled: false
  opt_trials: 3
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
    artifact = json.loads(
        Path("var/artifacts/run_complete.json").read_text(encoding="utf-8")
    )

    required_top_level = {
        "run_id",
        "started_at",
        "completed_at",
        "pipeline",
        "pipeline_summary",
        "optimization",
        "notifications",
    }
    assert required_top_level.issubset(artifact.keys())
