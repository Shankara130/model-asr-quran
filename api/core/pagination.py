from __future__ import annotations

import base64
import json


def encode_cursor(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def decode_cursor(token: str | None) -> dict:
    if not token:
        return {}
    try:
        return json.loads(base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8"))
    except Exception:
        return {}
