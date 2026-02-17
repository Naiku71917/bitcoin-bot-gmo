from __future__ import annotations

from datetime import UTC, datetime

from bitcoin_bot.data.ohlcv import validate_ohlcv_row


def test_ohlcv_row_contract():
    row = {
        "timestamp": datetime.now(UTC),
        "open": 1,
        "high": 2,
        "low": 1,
        "close": 2,
        "volume": 10,
    }
    assert validate_ohlcv_row(row)
