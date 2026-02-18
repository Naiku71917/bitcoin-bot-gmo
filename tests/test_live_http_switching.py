from __future__ import annotations

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.pipeline.live_runner import run_live


class _DummyAdapter:
    def __init__(self, *, product_type: str, api_base_url: str, use_http: bool):
        self.product_type = product_type
        self.api_base_url = api_base_url
        self.use_http = use_http

    def stream_order_events(self):
        return iter(())

    def stream_account_events(self):
        return iter(())

    def place_order(self, order_request):
        from bitcoin_bot.exchange.protocol import NormalizedOrderState

        return NormalizedOrderState(
            order_id=order_request.client_order_id,
            status="accepted",
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            qty=order_request.qty,
            price=order_request.price,
            product_type=order_request.product_type,
            reduce_only=order_request.reduce_only,
            raw={"exchange": "dummy"},
        )


def _build_config(tmp_path) -> RuntimeConfig:
    config = RuntimeConfig()
    config.paths.artifacts_dir = str(tmp_path / "artifacts")
    config.paths.logs_dir = str(tmp_path / "logs")
    config.paths.cache_dir = str(tmp_path / "cache")
    return config


def test_live_http_enabled_true_activates_http(monkeypatch, tmp_path):
    config = _build_config(tmp_path)
    config.runtime.mode = "live"
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = True

    captured: dict[str, object] = {}

    def _adapter_factory(*, product_type, api_base_url, use_http):
        captured["use_http"] = use_http
        return _DummyAdapter(
            product_type=product_type,
            api_base_url=api_base_url,
            use_http=use_http,
        )

    monkeypatch.setattr("bitcoin_bot.pipeline.live_runner.GMOAdapter", _adapter_factory)

    run_live(config)

    assert captured["use_http"] is True


def test_live_http_disabled_keeps_http_off(monkeypatch, tmp_path):
    config = _build_config(tmp_path)
    config.runtime.mode = "live"
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = False

    captured: dict[str, object] = {}

    def _adapter_factory(*, product_type, api_base_url, use_http):
        captured["use_http"] = use_http
        return _DummyAdapter(
            product_type=product_type,
            api_base_url=api_base_url,
            use_http=use_http,
        )

    monkeypatch.setattr("bitcoin_bot.pipeline.live_runner.GMOAdapter", _adapter_factory)

    run_live(config)

    assert captured["use_http"] is False


def test_non_live_mode_keeps_http_off(monkeypatch, tmp_path):
    config = _build_config(tmp_path)
    config.runtime.mode = "paper"
    config.runtime.execute_orders = True
    config.runtime.live_http_enabled = True

    captured: dict[str, object] = {}

    def _adapter_factory(*, product_type, api_base_url, use_http):
        captured["use_http"] = use_http
        return _DummyAdapter(
            product_type=product_type,
            api_base_url=api_base_url,
            use_http=use_http,
        )

    monkeypatch.setattr("bitcoin_bot.pipeline.live_runner.GMOAdapter", _adapter_factory)

    run_live(config)

    assert captured["use_http"] is False
