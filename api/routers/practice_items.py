from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.errors import ApiError
from api.core.pagination import decode_cursor, encode_cursor
from api.db import get_db
from api.db.models import PracticeItem
from api.schemas.practice_items import (
    PracticeItemDetail,
    PracticeItemDetailResponse,
    PracticeItemListResponse,
    PracticeItemOut,
    Segment,
)
from api.services.seed_data import _segments

router = APIRouter(prefix="/practice-items", tags=["practice-items"])


def item_to_out(item: PracticeItem) -> PracticeItemOut:
    return PracticeItemOut(
        id=item.id,
        surah_name=item.surah_name,
        surah_number=item.surah_number,
        ayah_label=item.ayah_label,
        ayah_number_start=item.ayah_number_start,
        ayah_number_end=item.ayah_number_end,
        arabic_name=item.arabic_name,
        arabic_text=item.arabic_text,
        translation=item.translation,
        latin_hint=item.latin_hint,
        focus=item.focus or None,
        level=item.level,
        estimated_minutes=item.estimated_minutes,
        reference_audio_url=item.reference_audio_url,
        is_daily=bool(item.is_daily),
        tags=list(item.tags or []),
    )


def item_segments(item: PracticeItem) -> list[Segment]:
    return [Segment(**seg) for seg in _segments(item.arabic_text)]


def item_to_detail(item: PracticeItem) -> PracticeItemDetail:
    base = item_to_out(item)
    return PracticeItemDetail(
        **base.model_dump(by_alias=False),
        segments=item_segments(item),
    )


@router.get("", response_model=PracticeItemListResponse, summary="List practice items")
async def list_items(
    q: str | None = Query(default=None, description="Substring match on surah name or item id."),
    level: str | None = Query(
        default=None, description="Filter by level: beginner | intermediate | advanced."
    ),
    tag: str | None = Query(
        default=None, description="Filter by tag, e.g. daily, juz30, juz1, letters."
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Page size."),
    cursor: str | None = Query(
        default=None, description="Opaque cursor from a previous nextCursor."
    ),
    db: AsyncSession = Depends(get_db),
) -> PracticeItemListResponse:
    """Curated verses (Juz 30 + Al-Fatihah) and hijaiyah letter drills."""
    offset = int(decode_cursor(cursor).get("o", 0))

    stmt = select(PracticeItem).order_by(
        PracticeItem.surah_number, PracticeItem.ayah_number_start, PracticeItem.id
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.where((PracticeItem.surah_name.ilike(like)) | (PracticeItem.id.ilike(like)))
    if level:
        stmt = stmt.where(PracticeItem.level == level)
    if tag:
        stmt = stmt.where(cast(PracticeItem.tags, String).like(f'%"{tag}"%'))

    page = list((await db.execute(stmt.offset(offset).limit(limit + 1))).scalars().all())
    has_more = len(page) > limit
    page = page[:limit]
    next_cursor = encode_cursor({"o": offset + limit}) if has_more else None

    return PracticeItemListResponse(items=[item_to_out(i) for i in page], next_cursor=next_cursor)


@router.get(
    "/{practice_item_id}", response_model=PracticeItemDetailResponse, summary="Get a practice item"
)
async def get_item(
    practice_item_id: str,
    db: AsyncSession = Depends(get_db),
) -> PracticeItemDetailResponse:
    """A single item including word-level `segments` (arabic-text char offsets)."""
    item = await db.get(PracticeItem, practice_item_id)
    if item is None:
        raise ApiError("practice_not_found")
    return PracticeItemDetailResponse(item=item_to_detail(item))
