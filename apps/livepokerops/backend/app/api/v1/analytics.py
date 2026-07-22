from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player, require_admin
from app.core.database import get_db
from app.models.player import Player
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
async def dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    """Top-level KPIs for the admin dashboard."""
    service = AnalyticsService(db)
    return await service.get_dashboard_summary()


@router.get("/tournaments")
async def tournament_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Monthly tournament stats for trend charts."""
    service = AnalyticsService(db)
    return await service.get_tournament_stats()


@router.get("/players/growth")
async def player_growth(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Player registration growth over time."""
    service = AnalyticsService(db)
    return await service.get_player_growth()


@router.get("/rsvps")
async def rsvp_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Aggregate RSVP statistics."""
    service = AnalyticsService(db)
    return await service.get_rsvp_stats()


@router.get("/broadcasts")
async def broadcast_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Aggregate broadcast statistics."""
    service = AnalyticsService(db)
    return await service.get_broadcast_stats()
