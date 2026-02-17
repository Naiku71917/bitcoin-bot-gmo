from __future__ import annotations

from datetime import datetime

REQUIRED_OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def validate_ohlcv_row(row: dict[str, object]) -> bool:
    has_columns = all(column in row for column in REQUIRED_OHLCV_COLUMNS)
    if not has_columns:
        return False

    timestamp = row.get("timestamp")
    return isinstance(timestamp, datetime)
