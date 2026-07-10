from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class JSONLStorage:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def append(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self._lock:
            with path.open(
                "a",
                encoding="utf-8",
            ) as file:
                file.write(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                    )
                    + "\n"
                )