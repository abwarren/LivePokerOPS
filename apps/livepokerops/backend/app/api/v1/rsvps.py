from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player, require_admin
from app.core.database import get_db
from app.models.player import Player
from app.schemas.rsvp import RsvpCreate, RsvpResponse, RsvpUpdate, TournamentRsvpStats
from app.services.rsvp import RsvpService

router = APIRouter(prefix="/tournaments/{tournament_id}/rsvps", tags=["rsvps"])


@router.post("/", response_model=RsvpResponse, status_code=status.HTTP_201_CREATED)
async def create_rsvp(
    tournament_id: uuid.UUID,
    body: RsvpCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
):
    """RSVP to a tournament. Auto-waitlists if full."""
    service = RsvpService(db)
    rsvp = await service.create_rsvp(
        tournament_id=tournament_id,
        player_id=current_player.id,
        notes=body.notes,
    )
    # Fetch player name for response
    rows = await service.list_rsvps(tournament_id)
    for row in rows:
        if row["player_id"] == current_player.id:
            return RsvpResponse(**row)
    return RsvpResponse.model_validate(rsvp)


@router.get("/", response_model=list[RsvpResponse])
async def list_rsvps(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
    status: str | None = Query(None),
):
    """List RSVPs for a tournament, optionally filtered by status."""
    service = RsvpService(db)
    rows = await service.list_rsvps(tournament_id, status_filter=status)
    return [RsvpResponse(**row) for row in rows]


@router.patch("/{player_id}", response_model=RsvpResponse)
async def update_rsvp(
    tournament_id: uuid.UUID,
    player_id: uuid.UUID,
    body: RsvpUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
):
    """Update RSVP status. Player can update their own; admin can update any."""
    if current_player.id != player_id and not current_player.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update another player's RSVP",
        )
    service = RsvpService(db)
    await service.update_rsvp(tournament_id, player_id, body.status)
    rows = await service.list_rsvps(tournament_id)
    for row in rows:
        if row["player_id"] == player_id:
            return RsvpResponse(**row)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="RSVP not found after update",
    )


@router.delete("/{player_id}", status_code=status.HTTP_200_OK, response_model=RsvpResponse)
async def cancel_rsvp(
    tournament_id: uuid.UUID,
    player_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
):
    """Cancel an RSVP. Player can cancel their own; admin can cancel any."""
    if current_player.id != player_id and not current_player.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot cancel another player's RSVP",
        )
    service = RsvpService(db)
    rsvp = await service.cancel_rsvp(tournament_id, player_id)
    rows = await service.list_rsvps(tournament_id)
    for row in rows:
        if row["player_id"] == player_id:
            return RsvpResponse(**row)
    return RsvpResponse.model_validate(rsvp)


@router.get("/stats", response_model=TournamentRsvpStats)
async def get_rsvp_stats(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
):
    """Get RSVP statistics for a tournament."""
    service = RsvpService(db)
    return await service.get_rsvp_stats(tournament_id)


@router.get("/my", response_model=list[dict])
async def get_my_rsvps(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_player: Annotated[Player, Depends(get_current_player)],
):
    """Get the current player's RSVPs across all tournaments."""
    service = RsvpService(db)
    return await service.get_player_rsvps(current_player.id)


@router.post("/promote", response_model=dict)
async def promote_waitlist(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Admin: promote all eligible waitlisters to confirmed."""
    service = RsvpService(db)
    promoted = await service.promote_from_waitlist(tournament_id)
    return {"promoted": len(promoted)}
