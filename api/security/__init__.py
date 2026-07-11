from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CurrentUser:
    """The authenticated principal, attached to ``request.state.principal``."""

    user_id: str
    email: str
    name: str
    learning_level: str
