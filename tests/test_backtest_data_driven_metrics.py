from __future__ import annotations

from pathlib import Path

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.pipeline.backtest_runner import run_backtest


def _write_csv(path: Path, closes: list[float]) -> None:
    lines = ["timestamp,open,high,low,close,volume"]
    for idx, close in enumerate(closes):
        open_price = close - 0.5
        high = close + 0.5
        low = close - 1.0
        lines.append(
            f"2026-01-01 00:{idx:02d}:00+00:00,{open_price},{high},{low},{close},10"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _base_config(csv_path: Path) -> RuntimeConfig:
    config = RuntimeConfig()
    config.runtime.mode = "backtest"
    config.data.csv_path = str(csv_path)
    return config


def test_backtest_metrics_change_with_ohlcv_input(tmp_path):
    rising_csv = tmp_path / "rising.csv"
    falling_csv = tmp_path / "falling.csv"

    _write_csv(rising_csv, [100, 101, 102, 103, 104])
    _write_csv(falling_csv, [100, 99, 98, 97, 96])

    rising = run_backtest(_base_config(rising_csv))["summary"]
    falling = run_backtest(_base_config(falling_csv))["summary"]

    assert rising["data_source"] == "csv"
    assert falling["data_source"] == "csv"
    assert rising["return"] > falling["return"]
    assert rising["trade_count"] == falling["trade_count"] == 4.0


def test_backtest_uses_explicit_fallback_on_invalid_data(tmp_path):
    invalid_csv = tmp_path / "invalid.csv"
    invalid_csv.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01 00:00:00+00:00,100,101,99,100,10\n",
        encoding="utf-8",
    )

    summary = run_backtest(_base_config(invalid_csv))["summary"]

    assert summary["data_source"] == "synthetic_fallback"
    assert summary["data_fallback_reason"] == "insufficient_rows"
    assert summary["data_points"] > 1
