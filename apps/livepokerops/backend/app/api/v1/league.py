from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player, require_admin
from app.core.database import get_db
from app.models.player import Player
from app.schemas.league import (
    LeaderboardResponse,
    PlayerPointsInput,
    PlayerPointsResponse,
    SeasonCreate,
    SeasonResponse,
    SeasonSummary,
    SeasonTournamentCreate,
    SeasonTournamentResponse,
    SeasonUpdate,
)
from app.services.league import LeagueService

router = APIRouter(prefix="/league", tags=["league"])


# ─── Seasons ───


@router.post("/seasons", response_model=SeasonResponse, status_code=status.HTTP_201_CREATED)
async def create_season(
    body: SeasonCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Create a new competitive season."""
    service = LeagueService(db)
    return await service.create_season(body)


@router.get("/seasons", response_model=list[SeasonSummary])
async def list_seasons(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    """List all seasons."""
    service = LeagueService(db)
    return await service.list_seasons()


@router.get("/seasons/{season_id}", response_model=SeasonResponse)
async def get_season(
    season_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    """Get a season with stats."""
    service = LeagueService(db)
    season = await service.get_season(season_id)
    stats = await service.get_season_stats(season_id)
    # Merge stats into response
    data = SeasonResponse.model_validate(season)
    data.tournament_count = stats["tournament_count"]
    data.player_count = stats["player_count"]
    return data


@router.patch("/seasons/{season_id}", response_model=SeasonResponse)
async def update_season(
    season_id: uuid.UUID,
    body: SeasonUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Update a season."""
    service = LeagueService(db)
    return await service.update_season(season_id, body)


@router.delete("/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_season(
    season_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Delete a season."""
    service = LeagueService(db)
    await service.delete_season(season_id)


# ─── Season-Tournament Assignment ───


@router.post(
    "/seasons/{season_id}/tournaments",
    response_model=SeasonTournamentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_tournament(
    season_id: uuid.UUID,
    body: SeasonTournamentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Assign a tournament to a season."""
    service = LeagueService(db)
    st = await service.assign_tournament(season_id, body)
    return SeasonTournamentResponse(
        id=st.id,
        season_id=st.season_id,
        tournament_id=st.tournament_id,
        points_schedule=st.points_schedule,
        attendance_points=st.attendance_points,
        final_table_bonus=st.final_table_bonus,
    )


@router.get(
    "/seasons/{season_id}/tournaments",
    response_model=list[SeasonTournamentResponse],
)
async def list_season_tournaments(
    season_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    """List tournaments assigned to a season."""
    service = LeagueService(db)
    return await service.list_season_tournaments(season_id)


@router.delete(
    "/seasons/{season_id}/tournaments/{tournament_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unassign_tournament(
    season_id: uuid.UUID,
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Remove a tournament from a season."""
    service = LeagueService(db)
    await service.unassign_tournament(season_id, tournament_id)


# ─── Points & Results ───


@router.post(
    "/seasons/{season_id}/tournaments/{tournament_id}/results",
    status_code=status.HTTP_201_CREATED,
)
async def record_tournament_results(
    season_id: uuid.UUID,
    tournament_id: uuid.UUID,
    body: list[PlayerPointsInput],
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[Player, Depends(require_admin)],
):
    """Record finishing positions and calculate league points for a tournament."""
    service = LeagueService(db)
    await service.record_tournament_results(
        season_id, tournament_id, body, actor_id=admin.id
    )
    return {"status": "ok", "players": len(body)}


@router.get("/seasons/{season_id}/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    season_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
    limit: int = Query(50, ge=1, le=200),
):
    """Get the leaderboard for a season."""
    service = LeagueService(db)
    return await service.get_leaderboard(season_id, limit=limit)


@router.get(
    "/seasons/{season_id}/players/{player_id}/points",
    response_model=list[PlayerPointsResponse],
)
async def get_player_points(
    season_id: uuid.UUID,
    player_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    """Get all points for a player in a season."""
    service = LeagueService(db)
    records = await service.get_player_season_points(season_id, player_id)
    return [
        PlayerPointsResponse.model_validate(r) for r in records
    ]


# ─── Points Schedule (default) ───


@router.get("/points-schedule/default")
async def get_default_schedule():
    """Get the default points schedule."""
    from app.schemas.league import DEFAULT_POINTS_SCHEDULE
    return {"schedule": DEFAULT_POINTS_SCHEDULE}
