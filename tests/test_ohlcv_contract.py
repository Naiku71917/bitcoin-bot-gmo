from __future__ import annotations

from datetime import UTC, datetime

from bitcoin_bot.data.ohlcv import REQUIRED_OHLCV_COLUMNS, normalize_ohlcv


def test_ohlcv_contract_columns_utc_index_and_attrs():
    rows = [
        {
            "timestamp": datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            "open": 1,
            "high": 2,
            "low": 1,
            "close": 2,
            "volume": 10,
        }
    ]

    frame = normalize_ohlcv(
        rows,
        provider="gmo",
        symbol="BTC_JPY",
        timeframe="1m",
        missing_policy="drop",
    )

    assert list(frame.columns) == REQUIRED_OHLCV_COLUMNS
    assert str(frame.index.tz) == "UTC"
    assert frame.attrs["provider"] == "gmo"
    assert frame.attrs["symbol"] == "BTC_JPY"
    assert frame.attrs["timeframe"] == "1m"


def test_ohlcv_missing_policy_is_explicit_and_applied():
    rows = [
        {
            "timestamp": datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            "open": 1,
            "high": None,
            "low": 1,
            "close": 2,
            "volume": 10,
        },
        {
            "timestamp": datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            "open": 2,
            "high": 3,
            "low": 2,
            "close": 3,
            "volume": 11,
        },
    ]

    frame = normalize_ohlcv(
        rows,
        provider="gmo",
        symbol="BTC_JPY",
        timeframe="1m",
        missing_policy="drop",
    )

    assert len(frame) == 1
    assert frame.attrs["missing_policy"] == "drop"
