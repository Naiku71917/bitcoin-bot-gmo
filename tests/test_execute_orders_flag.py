from __future__ import annotations

from bitcoin_bot.config.loader import load_runtime_config
from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.config.validator import validate_config
from bitcoin_bot.pipeline.live_runner import run_live


def test_execute_orders_false_adds_reason_and_disables_execution(tmp_path):
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    config.runtime.execute_orders = False

    result = run_live(config)
    summary = result["summary"]

    assert summary["execute_orders"] is False
    assert "execute_orders_disabled" in summary["stop_reason_codes"]


def test_execute_orders_true_keeps_existing_flow(tmp_path):
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    config.runtime.execute_orders = True

    result = run_live(config)
    summary = result["summary"]

    assert summary["execute_orders"] is True
    assert "execute_orders_disabled" not in summary["stop_reason_codes"]


def test_loader_and_validator_accept_execute_orders_bool(tmp_path):
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
runtime:
  mode: live
  execute_orders: true
exchange:
  product_type: spot
paths:
  artifacts_dir: "./var/artifacts"
  logs_dir: "./var/logs"
  cache_dir: "./var/cache"
""",
        encoding="utf-8",
    )

    loaded = load_runtime_config(str(config_path))
    validated = validate_config(loaded)
    assert validated.runtime.execute_orders is True
