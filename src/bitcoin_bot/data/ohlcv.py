from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
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
