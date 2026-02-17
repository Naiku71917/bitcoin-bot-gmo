from __future__ import annotations

from bitcoin_bot.exchange.gmo_adapter import GMOAdapter
from bitcoin_bot.exchange.protocol import ExchangeProtocol


def test_gmo_adapter_satisfies_exchange_protocol():
    adapter = GMOAdapter(product_type="spot")
    assert isinstance(adapter, ExchangeProtocol)
