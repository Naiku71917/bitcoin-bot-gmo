from __future__ import annotations

import pytest

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter


@pytest.mark.parametrize(
    ("source_code", "expected_category", "expected_retryable"),
    [
        ("AUTH_FAILED", "auth", False),
        ("RATE_LIMIT", "rate_limit", True),
        ("INVALID_PARAM", "validation", False),
        ("NETWORK_TIMEOUT", "network", True),
        ("UNKNOWN_ERROR", "exchange", True),
    ],
)
def test_gmo_error_normalization_categories(
    source_code: str,
    expected_category: str,
    expected_retryable: bool,
):
    adapter = GMOAdapter(product_type="spot")
    normalized = adapter.normalize_error(source_code=source_code, message="failed")

    assert normalized.category == expected_category
    assert normalized.retryable == expected_retryable
    assert normalized.source_code == source_code
    assert normalized.message == "failed"
