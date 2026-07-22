from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.player import Player
from app.schemas.event_log import EventLogListResponse, EventLogResponse
from app.services.event_log import EventLogService

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=EventLogListResponse)
async def list_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
    tournament_id: uuid.UUID | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    service = EventLogService(db)
    events = await service.get_events(
        tournament_id=tournament_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    total = await service.count_events(
        tournament_id=tournament_id, event_type=event_type
    )
    return EventLogListResponse(
        events=[EventLogResponse.model_validate(e) for e in events],
        total=total,
    )
