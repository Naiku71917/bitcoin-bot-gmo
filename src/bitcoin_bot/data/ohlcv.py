from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd

REQUIRED_OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
MissingPolicy = Literal["drop", "ffill"]


def normalize_ohlcv(
    rows: Sequence[dict[str, object]],
    *,
    provider: str,
    symbol: str,
    timeframe: str,
    missing_policy: MissingPolicy = "drop",
) -> pd.DataFrame:
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        frame = pd.DataFrame(columns=REQUIRED_OHLCV_COLUMNS)

    for column in REQUIRED_OHLCV_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA

    frame = frame[REQUIRED_OHLCV_COLUMNS].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    for numeric_column in REQUIRED_OHLCV_COLUMNS[1:]:
        frame[numeric_column] = pd.to_numeric(frame[numeric_column], errors="coerce")

    if missing_policy == "drop":
        frame = frame.dropna(subset=REQUIRED_OHLCV_COLUMNS)
    elif missing_policy == "ffill":
        frame = frame.ffill().dropna(subset=REQUIRED_OHLCV_COLUMNS)
    else:
        raise ValueError(f"Unsupported missing_policy: {missing_policy}")

    frame = frame.set_index("timestamp", drop=False)
    frame.attrs["provider"] = provider
    frame.attrs["symbol"] = symbol
    frame.attrs["timeframe"] = timeframe
    frame.attrs["missing_policy"] = missing_policy
    return frame


def validate_ohlcv_row(row: dict[str, object]) -> bool:
    frame = normalize_ohlcv(
        [row],
        provider="unknown",
        symbol="unknown",
        timeframe="unknown",
        missing_policy="drop",
    )
    if frame.empty:
        return False

    timestamp = frame.iloc[0]["timestamp"]
    return isinstance(timestamp, datetime)


def _synthetic_ohlcv(*, symbol: str, timeframe: str) -> pd.DataFrame:
    base_ts = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[dict[str, object]] = []
    for index in range(120):
        close = 100.0 + (index * 0.2) + ((index % 7) - 3) * 0.05
        open_price = close - 0.1
        high = close + 0.2
        low = close - 0.2
        rows.append(
            {
                "timestamp": base_ts + timedelta(minutes=index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 10 + (index % 5),
            }
        )

    return normalize_ohlcv(
        rows,
        provider="synthetic",
        symbol=symbol,
        timeframe=timeframe,
        missing_policy="drop",
    )


def load_ohlcv_for_backtest(
    *,
    csv_path: str,
    symbol: str,
    timeframe: str,
    provider: str = "csv",
    missing_policy: MissingPolicy = "drop",
    backtest_data_quality_mode: Literal["strict", "fallback"] = "fallback",
) -> tuple[pd.DataFrame, str, str | None]:
    if backtest_data_quality_mode not in {"strict", "fallback"}:
        raise ValueError(
            f"Unsupported backtest_data_quality_mode: {backtest_data_quality_mode}"
        )

    def _strict_or_fallback(reason: str) -> tuple[pd.DataFrame, str, str | None]:
        if backtest_data_quality_mode == "strict":
            raise ValueError(f"backtest_data_quality_error:{reason}")
        return (
            _synthetic_ohlcv(symbol=symbol, timeframe=timeframe),
            "synthetic_fallback",
            reason,
        )

    path = Path(csv_path)
    if not path.exists():
        return _strict_or_fallback("csv_not_found")

    try:
        csv_frame = pd.read_csv(path)
    except Exception:
        return _strict_or_fallback("csv_read_error")

    rows = csv_frame.to_dict("records")
    frame = normalize_ohlcv(
        rows,
        provider=provider,
        symbol=symbol,
        timeframe=timeframe,
        missing_policy=missing_policy,
    )

    if len(frame) < 2:
        return _strict_or_fallback("insufficient_rows")

    return frame, "csv", None
