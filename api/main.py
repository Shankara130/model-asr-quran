"""Entrypoint: ``python -m api`` -> uvicorn dev server on 127.0.0.1:8000."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "api.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
