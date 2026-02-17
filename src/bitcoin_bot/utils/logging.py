from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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


def append_audit_event(
    *, logs_dir: str, event_type: str, payload: dict[str, Any]
) -> None:
    log_path = Path(logs_dir) / "audit_events.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "payload": _sanitize_value(payload),
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
