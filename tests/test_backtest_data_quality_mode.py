from __future__ import annotations

from pathlib import Path

import pytest

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.pipeline.backtest_runner import run_backtest


def _write_csv(path: Path, closes: list[float]) -> None:
    lines = ["timestamp,open,high,low,close,volume"]
    for idx, close in enumerate(closes):
        lines.append(
            f"2026-01-01 00:{idx:02d}:00+00:00,{close - 0.5},{close + 0.5},{close - 1.0},{close},10"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _base_config(csv_path: Path) -> RuntimeConfig:
    config = RuntimeConfig()
    config.runtime.mode = "backtest"
    config.data.csv_path = str(csv_path)
    return config


def test_backtest_data_quality_fallback_keeps_current_behavior(tmp_path):
    missing = tmp_path / "missing.csv"
    config = _base_config(missing)
    config.data.backtest_data_quality_mode = "fallback"

    summary = run_backtest(config)["summary"]

    assert summary["data_source"] == "synthetic_fallback"
    assert summary["data_fallback_reason"] == "csv_not_found"


def test_backtest_data_quality_strict_fails_fast_on_invalid_data(tmp_path):
    invalid_csv = tmp_path / "invalid.csv"
    invalid_csv.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01 00:00:00+00:00,100,101,99,100,10\n",
        encoding="utf-8",
    )

    config = _base_config(invalid_csv)
    config.data.backtest_data_quality_mode = "strict"

    with pytest.raises(
        ValueError, match="backtest_data_quality_error:insufficient_rows"
    ):
        run_backtest(config)


def test_backtest_data_quality_strict_allows_valid_csv(tmp_path):
    valid_csv = tmp_path / "valid.csv"
    _write_csv(valid_csv, [100, 101, 102])

    config = _base_config(valid_csv)
    config.data.backtest_data_quality_mode = "strict"

    summary = run_backtest(config)["summary"]

    assert summary["data_source"] == "csv"
    assert summary["data_fallback_reason"] is None
