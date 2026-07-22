from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player, require_admin
from app.core.database import get_db
from app.models.player import Player
from app.schemas.event_log import EventLogResponse
from app.schemas.tournament import (
    TournamentCreate,
    TournamentResponse,
    TournamentSummary,
    TournamentUpdate,
)
from app.services.event_log import EventLogService
from app.services.tournament import TournamentService

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.post("/", response_model=TournamentResponse, status_code=status.HTTP_201_CREATED)
async def create_tournament(
    body: TournamentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(require_admin)],
):
    service = TournamentService(db)
    return await service.create(body, actor_id=current_player.id)


@router.get("/", response_model=list[TournamentSummary])
async def list_tournaments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    service = TournamentService(db)
    return await service.list_tournaments(
        status_filter=status, limit=limit, offset=offset
    )


@router.get("/{tournament_id}", response_model=TournamentResponse)
async def get_tournament(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    service = TournamentService(db)
    return await service.get(tournament_id)


@router.patch("/{tournament_id}", response_model=TournamentResponse)
async def update_tournament(
    tournament_id: uuid.UUID,
    body: TournamentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(require_admin)],
):
    service = TournamentService(db)
    return await service.update(tournament_id, body, actor_id=current_player.id)


@router.delete("/{tournament_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tournament(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(require_admin)],
):
    service = TournamentService(db)
    await service.delete(tournament_id, actor_id=current_player.id)


@router.get("/{tournament_id}/events", response_model=list[EventLogResponse])
async def get_tournament_events(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get event log for a specific tournament."""
    service = EventLogService(db)
    return await service.get_events(
        tournament_id=tournament_id, limit=limit, offset=offset
    )


# ─── Archive / Search ───


@router.get("/archive/search", response_model=dict)
async def search_tournaments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
    q: str | None = Query(None, description="Search query"),
    status: str | None = Query(None, description="Filter by status"),
    date_from: datetime | None = Query(None, description="Start date filter (ISO)"),
    date_to: datetime | None = Query(None, description="End date filter (ISO)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Search tournaments with full-text query and date filters."""
    service = TournamentService(db)
    results, total = await service.search_tournaments(
        query_str=q,
        status_filter=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "results": [TournamentResponse.model_validate(t) for t in results],
    }


@router.get("/archive/upcoming", response_model=list[TournamentSummary])
async def upcoming_tournaments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
    days: int = Query(7, ge=1, le=90),
):
    """Get upcoming tournaments within the next N days."""
    service = TournamentService(db)
    return await service.get_upcoming(days=days)


@router.get("/archive/completed", response_model=list[TournamentSummary])
async def recent_completed(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
    limit: int = Query(20, ge=1, le=100),
):
    """Get recently completed tournaments."""
    service = TournamentService(db)
    return await service.get_recent_completed(limit=limit)
