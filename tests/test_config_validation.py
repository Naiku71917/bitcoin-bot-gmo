from __future__ import annotations

from pathlib import Path

import pytest

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.config.validator import validate_config


def test_opt_trials_clamped_lower_bound():
    config = RuntimeConfig()
    config.optimizer.opt_trials = 0
    validated = validate_config(config)
    assert validated.optimizer.opt_trials == 1


def test_opt_trials_clamped_upper_bound():
    config = RuntimeConfig()
    config.optimizer.opt_trials = 999
    validated = validate_config(config)
    assert validated.optimizer.opt_trials == 500


def test_invalid_mode_raises():
    config = RuntimeConfig()
    config.runtime.mode = "invalid"  # type: ignore[assignment]
    with pytest.raises(ValueError):
        validate_config(config)


def test_invalid_product_type_raises():
    config = RuntimeConfig()
    config.exchange.product_type = "invalid"  # type: ignore[assignment]
    with pytest.raises(ValueError):
        validate_config(config)


def test_paths_are_creatable(tmp_path: Path):
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")

    validate_config(config)

    assert (tmp_path / "artifacts").is_dir()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "cache").is_dir()
