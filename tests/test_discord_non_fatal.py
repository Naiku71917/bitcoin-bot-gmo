from __future__ import annotations

from urllib.error import URLError

from bitcoin_bot.telemetry.discord import send_discord_webhook


def test_discord_failure_is_non_fatal(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    result = send_discord_webhook(enabled=True)
    assert result["status"] == "failed"
    assert result["reason"] == "missing_webhook_url"


def test_discord_http_failure_is_non_fatal(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/webhook")

    def _raise_url_error(*args, **kwargs):
        raise URLError("network down")

    monkeypatch.setattr("bitcoin_bot.telemetry.discord.urlopen", _raise_url_error)

    result = send_discord_webhook(enabled=True)
    assert result["status"] == "failed"
    assert "network down" in str(result["reason"])
