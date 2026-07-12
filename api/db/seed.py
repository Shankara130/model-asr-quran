from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.ids import new_user_id
from api.db.models import User, UserPreference
from api.settings import settings

log = logging.getLogger("api.seed")


async def seed_dev_user(session: AsyncSession) -> str:
    """Insert the dev user + default preferences if none exist. Idempotent."""
    result = await session.execute(select(User).limit(1))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing.id

    user = User(
        id=new_user_id(),
        name=settings.dev_user_name,
        email=settings.dev_user_email,
        learning_level=settings.dev_user_level,
        avatar_url=None,
    )
    session.add(user)
    await session.flush()  # populate user.id

    session.add(
        UserPreference(
            user_id=user.id,
            practice_level=settings.dev_user_level,
            practice_mode="phrases",
            audio_feedback_enabled=True,
            daily_report_frequency="weekly_sunday",
            reminder_enabled=False,
            reminder_time=None,
        )
    )
    await session.commit()
    log.info("seeded dev user %s (%s)", user.id, user.email)
    return user.id
