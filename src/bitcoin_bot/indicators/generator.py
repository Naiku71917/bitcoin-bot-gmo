from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _atr(frame: pd.DataFrame, period: int) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_close = (frame["low"] - frame["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def generate_indicators(
    frame: pd.DataFrame,
    *,
    ema_fast_window: int = 12,
    ema_slow_window: int = 26,
    rsi_window: int = 14,
    atr_window: int = 14,
    feature_flags: Mapping[str, bool] | None = None,
) -> pd.DataFrame:
    flags = dict(feature_flags or {})
    slope_enabled = bool(flags.get("slope_norm", True))
    gap_enabled = bool(flags.get("gap_norm", True))

    result = frame.copy()
    ema_fast_column = f"ema_{ema_fast_window}"
    ema_slow_column = f"ema_{ema_slow_window}"
    rsi_column = f"rsi_{rsi_window}"
    atr_column = f"atr_{atr_window}"

    indicator_cols = [ema_fast_column, ema_slow_column, rsi_column, atr_column]
    if slope_enabled:
        indicator_cols.append("slope_norm")
    if gap_enabled:
        indicator_cols.append("gap_norm")

    conflicts = [column for column in indicator_cols if column in result.columns]
    if conflicts:
        raise ValueError(f"Indicator columns already exist: {conflicts}")

    result[ema_fast_column] = (
        result["close"]
        .ewm(
            span=ema_fast_window,
            adjust=False,
            min_periods=ema_fast_window,
        )
        .mean()
    )
    result[ema_slow_column] = (
        result["close"]
        .ewm(
            span=ema_slow_window,
            adjust=False,
            min_periods=ema_slow_window,
        )
        .mean()
    )
    result[rsi_column] = _rsi(result["close"], rsi_window)
    result[atr_column] = _atr(result, atr_window)

    if slope_enabled:
        slope = result[ema_fast_column].diff()
        denom = result[atr_column].replace(0, pd.NA)
        result["slope_norm"] = (slope / denom).fillna(0.0)

    if gap_enabled:
        ema_gap = result[ema_fast_column] - result[ema_slow_column]
        denom = result["close"].replace(0, pd.NA)
        result["gap_norm"] = (ema_gap / denom).fillna(0.0)

    return result


def indicator_columns() -> list[str]:
    return ["ema_12", "ema_26", "rsi_14", "atr_14", "slope_norm", "gap_norm"]
