from __future__ import annotations

import pandas as pd
import pytest

from bitcoin_bot.indicators.generator import generate_indicators


def _base_ohlcv_frame(rows: int = 60) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="min", tz="UTC")
    close = pd.Series(range(100, 100 + rows), dtype="float64")
    frame = pd.DataFrame(
        {
            "timestamp": index,
            "open": close.values,
            "high": (close + 1).values,
            "low": (close - 1).values,
            "close": close.values,
            "volume": [10.0] * rows,
        }
    )
    frame.index = index
    return frame


def test_indicator_columns_and_naming_contract():
    frame = _base_ohlcv_frame()
    result = generate_indicators(
        frame,
        ema_fast_window=10,
        ema_slow_window=20,
        rsi_window=7,
        atr_window=5,
        feature_flags={"slope_norm": True, "gap_norm": True},
    )

    assert "ema_10" in result.columns
    assert "ema_20" in result.columns
    assert "rsi_7" in result.columns
    assert "atr_5" in result.columns
    assert "slope_norm" in result.columns
    assert "gap_norm" in result.columns


def test_flags_off_do_not_create_optional_columns():
    frame = _base_ohlcv_frame()
    result = generate_indicators(
        frame,
        feature_flags={"slope_norm": False, "gap_norm": False},
    )

    assert "ema_12" in result.columns
    assert "ema_26" in result.columns
    assert "rsi_14" in result.columns
    assert "atr_14" in result.columns
    assert "slope_norm" not in result.columns
    assert "gap_norm" not in result.columns


def test_existing_columns_are_not_overwritten():
    frame = _base_ohlcv_frame()
    frame["ema_12"] = 0.0

    with pytest.raises(ValueError):
        generate_indicators(frame)
