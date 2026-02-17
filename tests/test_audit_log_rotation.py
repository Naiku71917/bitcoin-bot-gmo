from __future__ import annotations

import json
from pathlib import Path

from bitcoin_bot.utils.logging import append_audit_event, set_audit_log_policy


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_audit_log_rotates_by_size_and_keeps_generations(tmp_path):
    logs_dir = tmp_path / "logs"

    set_audit_log_policy(max_bytes=200, retention=2)

    for index in range(30):
        append_audit_event(
            logs_dir=str(logs_dir),
            event_type="order_attempt",
            payload={"index": index, "message": "x" * 80},
        )

    active = logs_dir / "audit_events.jsonl"
    gen1 = logs_dir / "audit_events.jsonl.1"
    gen2 = logs_dir / "audit_events.jsonl.2"
    gen3 = logs_dir / "audit_events.jsonl.3"

    assert active.exists()
    assert gen1.exists()
    assert gen2.exists()
    assert not gen3.exists()


def test_audit_log_rotation_keeps_secret_masking(tmp_path):
    logs_dir = tmp_path / "logs"

    set_audit_log_policy(max_bytes=120, retention=1)

    for index in range(8):
        append_audit_event(
            logs_dir=str(logs_dir),
            event_type="startup_validation",
            payload={
                "index": index,
                "api_secret": "very-secret",
                "token": "abc",
                "nested": {"webhook_url": "https://example.com/hook"},
                "message": "x" * 40,
            },
        )

    all_events = _read_jsonl(logs_dir / "audit_events.jsonl") + _read_jsonl(
        logs_dir / "audit_events.jsonl.1"
    )
    assert all_events
    for event in all_events:
        payload = event["payload"]
        assert payload["api_secret"] == "***"
        assert payload["token"] == "***"
        assert payload["nested"]["webhook_url"] == "***"
