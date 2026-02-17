from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


_audit_log_max_bytes = 5 * 1024 * 1024
_audit_log_retention = 5


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def set_audit_log_policy(*, max_bytes: int, retention: int) -> None:
    global _audit_log_max_bytes, _audit_log_retention
    _audit_log_max_bytes = max(1, int(max_bytes))
    _audit_log_retention = max(1, int(retention))


_SECRET_KEYWORDS = {
    "api_key",
    "api_secret",
    "secret",
    "token",
    "password",
    "webhook_url",
}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if any(keyword in lowered for keyword in _SECRET_KEYWORDS):
                sanitized[key] = "***"
            else:
                sanitized[key] = _sanitize_value(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _rotate_audit_log_if_needed(log_path: Path) -> None:
    if not log_path.exists():
        return
    if log_path.stat().st_size <= _audit_log_max_bytes:
        return

    for index in range(_audit_log_retention, 0, -1):
        rotated_path = log_path.with_name(f"{log_path.name}.{index}")
        if rotated_path.exists():
            if index >= _audit_log_retention:
                rotated_path.unlink()
            else:
                next_path = log_path.with_name(f"{log_path.name}.{index + 1}")
                rotated_path.replace(next_path)

    first_rotated = log_path.with_name(f"{log_path.name}.1")
    log_path.replace(first_rotated)


def append_audit_event(
    *, logs_dir: str, event_type: str, payload: dict[str, Any]
) -> None:
    log_path = Path(logs_dir) / "audit_events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_audit_log_if_needed(log_path)

    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "payload": _sanitize_value(payload),
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
