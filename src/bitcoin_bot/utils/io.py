from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex


def atomic_dump_json(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def build_live_client_order_id(symbol: str) -> str:
    symbol_token = "".join(
        character for character in symbol.upper() if character.isalnum()
    )
    if not symbol_token:
        symbol_token = "SYMBOL"
    symbol_token = symbol_token[:16]
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    random_suffix = token_hex(4)
    return f"live-{symbol_token}-{timestamp}-{random_suffix}"
