from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from bitcoin_bot.config.loader import load_runtime_config
from bitcoin_bot.config.validator import validate_config, validate_runtime_environment


def _load_run_live_module():
    module_name = "run_live_script_env_validation"
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_live.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed_to_load_run_live_module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_execute_orders_true_without_required_env_fails_startup(tmp_path, monkeypatch):
    run_live_script = _load_run_live_module()

    artifacts_dir = tmp_path / "artifacts"
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        f"""
runtime:
  mode: live
  execute_orders: true
notify:
  discord:
    enabled: false
paths:
  artifacts_dir: "{artifacts_dir}"
  logs_dir: "{tmp_path / "logs"}"
  cache_dir: "{tmp_path / "cache"}"
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.delenv("GMO_API_KEY", raising=False)
    monkeypatch.delenv("GMO_API_SECRET", raising=False)

    exit_code = run_live_script.main()
    assert exit_code == 1

    progress = json.loads(
        (artifacts_dir / "run_progress.json").read_text(encoding="utf-8")
    )
    assert progress["status"] == "failed"
    assert "missing_required_env" in str(progress["last_error"])
    assert progress["validation"]["fatal_errors"]


def test_discord_webhook_missing_is_non_fatal_warning(tmp_path):
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
runtime:
  mode: live
  execute_orders: false
notify:
  discord:
    enabled: true
""",
        encoding="utf-8",
    )

    loaded = load_runtime_config(str(config_path))
    validated = validate_config(loaded)
    env_validation = validate_runtime_environment(validated, environ={})

    assert env_validation["fatal_errors"] == []
    assert "discord_webhook_missing" in env_validation["warnings"]
    assert env_validation["discord"]["status"] == "failed"
    assert env_validation["discord"]["reason"] == "missing_webhook_url"


def test_execute_orders_true_with_required_env_passes_validation(tmp_path):
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
runtime:
  mode: live
  execute_orders: true
notify:
  discord:
    enabled: false
""",
        encoding="utf-8",
    )

    loaded = load_runtime_config(str(config_path))
    validated = validate_config(loaded)
    env_validation = validate_runtime_environment(
        validated,
        environ={
            "GMO_API_KEY": "dummy-key",
            "GMO_API_SECRET": "dummy-secret",
        },
    )

    assert env_validation["fatal_errors"] == []
