from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player, require_admin
from app.core.database import get_db
from app.models.player import Player
from app.schemas.attendance import (
    AttendanceCreate,
    AttendanceResponse,
    AttendanceStats,
    AttendanceUpdate,
    CheckInRequest,
)
from app.services.attendance import AttendanceService

router = APIRouter(
    prefix="/tournaments/{tournament_id}/attendance",
    tags=["attendance"],
)


@router.post("/check-in", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
async def check_in_player(
    tournament_id: uuid.UUID,
    body: CheckInRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(require_admin)],
):
    """Check in a player for a tournament (admin only)."""
    service = AttendanceService(db)
    return await service.check_in(
        tournament_id, body.player_id, actor_id=current_player.id
    )


@router.post(
    "/bulk-check-in",
    response_model=list[AttendanceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_check_in(
    tournament_id: uuid.UUID,
    body: list[CheckInRequest],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(require_admin)],
):
    """Check in multiple players at once (admin only)."""
    service = AttendanceService(db)
    player_ids = [r.player_id for r in body]
    return await service.bulk_check_in(
        tournament_id, player_ids, actor_id=current_player.id
    )


@router.post("/no-show/{player_id}", response_model=AttendanceResponse)
async def mark_no_show(
    tournament_id: uuid.UUID,
    player_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(require_admin)],
):
    """Mark a player as no-show for a tournament (admin only)."""
    service = AttendanceService(db)
    return await service.mark_no_show(
        tournament_id, player_id, actor_id=current_player.id
    )


@router.patch("/{player_id}", response_model=AttendanceResponse)
async def update_attendance(
    tournament_id: uuid.UUID,
    player_id: uuid.UUID,
    body: AttendanceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(require_admin)],
):
    """Update an attendance record's status and notes (admin only)."""
    service = AttendanceService(db)
    return await service.update_attendance(
        tournament_id, player_id, body.status, notes=body.notes
    )


@router.get("/", response_model=list[AttendanceResponse])
async def list_attendance(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
    status: str | None = Query(None),
):
    """List attendance records for a tournament (authenticated)."""
    service = AttendanceService(db)
    return await service.get_attendance(tournament_id, status_filter=status)


@router.get("/stats", response_model=AttendanceStats)
async def get_attendance_stats(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    """Get attendance statistics for a tournament (authenticated)."""
    service = AttendanceService(db)
    return await service.get_attendance_stats(tournament_id)
