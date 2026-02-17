from __future__ import annotations

import pytest

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.config.validator import validate_config


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
