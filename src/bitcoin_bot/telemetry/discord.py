from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


def send_discord_webhook(enabled: bool) -> dict:
    if not enabled:
        return {"status": "disabled", "reason": None}

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return {"status": "failed", "reason": "missing_webhook_url"}

    payload = json.dumps({"content": "bitcoin-bot run completed"}).encode("utf-8")
    request = Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=5):
            return {"status": "sent", "reason": None}
    except URLError as exc:
        return {"status": "failed", "reason": str(exc)}
    except Exception as exc:  # pragma: no cover
        return {"status": "failed", "reason": str(exc)}
