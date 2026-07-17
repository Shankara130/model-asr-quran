from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Time

from api.db.models import User, UserPreference, WeeklyReport, utc_now


def test_temporal_columns_use_native_sqlalchemy_types():
    assert isinstance(User.__table__.c.created_at.type, DateTime)
    assert User.__table__.c.created_at.type.timezone is True
    assert isinstance(User.__table__.c.updated_at.type, DateTime)
    assert isinstance(UserPreference.__table__.c.reminder_time.type, Time)
    assert isinstance(WeeklyReport.__table__.c.week_start.type, Date)
    assert isinstance(WeeklyReport.__table__.c.week_end.type, Date)


def test_temporal_defaults_return_native_values():
    now = utc_now()

    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert isinstance(date.today(), date)
    assert isinstance(time(6, 30), time)
