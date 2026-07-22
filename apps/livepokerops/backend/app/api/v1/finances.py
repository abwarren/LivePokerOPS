from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player, require_admin
from app.core.database import get_db
from app.models.finance import BuyIn
from app.models.player import Player
from app.schemas.finance import (
    BulkBuyInCreate,
    BuyInCreate,
    BuyInResponse,
    FinancialSummary,
    PlayerFinanceResponse,
    PrizePoolResponse,
)
from app.services.finance import FinanceService
from app.services.tournament import TournamentService

router = APIRouter(
    prefix="/tournaments/{tournament_id}/finances",
    tags=["finances"],
)


@router.post(
    "/buy-ins",
    response_model=BuyInResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_buy_in(
    tournament_id: uuid.UUID,
    body: BuyInCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Record a single buy-in, rebuy, or add-on (admin only)."""
    service = FinanceService(db)
    buy_in = await service.record_buy_in(
        tournament_id=tournament_id,
        player_id=body.player_id,
        amount=body.amount,
        type=body.type,
        notes=body.notes,
    )
    return _enrich_buy_in(buy_in)


@router.post(
    "/bulk-buy-ins",
    response_model=list[BuyInResponse],
    status_code=status.HTTP_201_CREATED,
)
async def record_bulk_buy_ins(
    tournament_id: uuid.UUID,
    body: BulkBuyInCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Record multiple buy-ins at once (admin only)."""
    service = FinanceService(db)
    buy_ins = await service.record_bulk_buy_ins(
        tournament_id=tournament_id,
        entries=body.entries,
    )
    return [_enrich_buy_in(b) for b in buy_ins]


@router.get("/buy-ins", response_model=list[BuyInResponse])
async def list_buy_ins(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    """List all buy-ins for a tournament."""
    service = FinanceService(db)
    buy_ins = await service.get_tournament_finances(tournament_id)
    return [_enrich_buy_in(b) for b in buy_ins]


@router.get("/prize-pool", response_model=PrizePoolResponse)
async def get_prize_pool(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    """Get prize pool summary for a tournament."""
    service = FinanceService(db)
    prize_pool = await service.get_prize_pool(tournament_id)
    # Get tournament name
    ts = TournamentService(db)
    tournament = await ts.get(tournament_id)
    return PrizePoolResponse(
        tournament_id=prize_pool.tournament_id,
        tournament_name=tournament.name,
        total_buy_in=prize_pool.total_buy_in,
        total_rebuys=prize_pool.total_rebuys,
        total_addons=prize_pool.total_addons,
        total_prize_pool=prize_pool.total_prize_pool,
        entries_count=prize_pool.entries_count,
        average_buy_in=(
            prize_pool.total_prize_pool / prize_pool.entries_count
            if prize_pool.entries_count > 0
            else Decimal("0.00")
        ),
    )


@router.get(
    "/players/{player_id}",
    response_model=PlayerFinanceResponse,
)
async def get_player_finances(
    tournament_id: uuid.UUID,
    player_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(get_current_player)],
):
    """Get a player's financial transactions for a tournament."""
    service = FinanceService(db)
    buy_ins, total = await service.get_player_finances(
        tournament_id, player_id
    )
    player_name = None
    if buy_ins:
        player_name = (
            f"{buy_ins[0].player.first_name} {buy_ins[0].player.last_name}"
        )
    return PlayerFinanceResponse(
        buy_ins=[_enrich_buy_in(b) for b in buy_ins],
        total_spent=total,
        tournament_id=tournament_id,
        player_id=player_id,
        player_name=player_name,
    )


@router.get("/overview", response_model=FinancialSummary)
async def get_overall_financial_summary(
    tournament_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Player, Depends(require_admin)],
):
    """Get overall financial summary across all tournaments (admin only).

    The tournament_id path param is ignored; this returns cross-tournament totals.
    """
    service = FinanceService(db)
    summary = await service.get_overall_summary()
    return FinancialSummary(**summary)


def _enrich_buy_in(buy_in: BuyIn) -> dict:

    player_name = None
    if buy_in.player:
        player_name = f"{buy_in.player.first_name} {buy_in.player.last_name}"
    return {
        "id": buy_in.id,
        "tournament_id": buy_in.tournament_id,
        "player_id": buy_in.player_id,
        "player_name": player_name,
        "amount": buy_in.amount,
        "type": buy_in.type,
        "notes": buy_in.notes,
        "created_at": buy_in.created_at,
    }
