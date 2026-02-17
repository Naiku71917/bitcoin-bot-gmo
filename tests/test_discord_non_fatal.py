from __future__ import annotations

from bitcoin_bot.telemetry.discord import send_discord_webhook


def test_discord_failure_is_non_fatal(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    result = send_discord_webhook(enabled=True)
    assert result["status"] == "failed"
    assert result["reason"] == "missing_webhook_url"
