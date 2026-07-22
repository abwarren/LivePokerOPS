from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging import get_logger
from app.models.finance import BuyIn, PrizePool
from app.models.player import Player
from app.models.tournament import Tournament
from app.schemas.finance import BuyInCreate, BuyInResponse

logger = get_logger(__name__)

VALID_BUYIN_TYPES = frozenset({"buy_in", "re_buy", "add_on"})


class FinanceService:
    """Financial tracking for tournaments — buy-ins, rebuys, add-ons, prize pools."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_buy_in(
        self,
        tournament_id: uuid.UUID,
        player_id: uuid.UUID,
        amount: Decimal,
        type: str = "buy_in",
        notes: str | None = None,
    ) -> BuyIn:
        """Record a single buy-in/rebuy/addon and auto-update prize pool."""
        if type not in VALID_BUYIN_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid buy-in type: {type}. "
                f"Valid: {', '.join(sorted(VALID_BUYIN_TYPES))}",
            )
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be positive",
            )

        # Verify tournament exists
        await self._get_tournament(tournament_id)
        # Verify player exists
        await self._get_player(player_id)

        buy_in = BuyIn(
            tournament_id=tournament_id,
            player_id=player_id,
            amount=amount,
            type=type,
            notes=notes,
        )
        self.db.add(buy_in)
        await self.db.flush()

        await self._recalculate_prize_pool(tournament_id)

        # Re-fetch with player relationship for eager loading
        result = await self.db.execute(
            select(BuyIn)
            .options(joinedload(BuyIn.player))
            .where(BuyIn.id == buy_in.id)
        )
        return result.scalar_one()

    async def record_bulk_buy_ins(
        self,
        tournament_id: uuid.UUID,
        entries: list[BuyInCreate],
    ) -> list[BuyIn]:
        """Record multiple buy-ins at once and recalculate prize pool."""
        # Verify tournament exists
        await self._get_tournament(tournament_id)

        buy_ins: list[BuyIn] = []
        for entry in entries:
            if entry.type not in VALID_BUYIN_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid buy-in type: {entry.type}",
                )
            if entry.amount <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Amount must be positive; got {entry.amount}",
                )
            await self._get_player(entry.player_id)
            buy_in = BuyIn(
                tournament_id=tournament_id,
                player_id=entry.player_id,
                amount=entry.amount,
                type=entry.type,
                notes=entry.notes,
            )
            self.db.add(buy_in)
            buy_ins.append(buy_in)

        await self.db.flush()
        await self._recalculate_prize_pool(tournament_id)

        # Re-fetch all buy-ins with player relationships
        if buy_ins:
            ids = [b.id for b in buy_ins]
            result = await self.db.execute(
                select(BuyIn)
                .options(joinedload(BuyIn.player))
                .where(BuyIn.id.in_(ids))
            )
            return list(result.scalars().all())
        return buy_ins

    async def get_tournament_finances(
        self, tournament_id: uuid.UUID
    ) -> list[BuyIn]:
        """Get all buy-ins for a tournament with player names."""
        await self._get_tournament(tournament_id)
        result = await self.db.execute(
            select(BuyIn)
            .options(joinedload(BuyIn.player))
            .where(BuyIn.tournament_id == tournament_id)
            .order_by(BuyIn.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_prize_pool(
        self, tournament_id: uuid.UUID
    ) -> PrizePool:
        """Get or initialise prize pool summary for a tournament."""
        await self._get_tournament(tournament_id)
        result = await self.db.execute(
            select(PrizePool).where(PrizePool.tournament_id == tournament_id)
        )
        prize_pool = result.scalar_one_or_none()
        if prize_pool is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prize pool not found for this tournament",
            )
        return prize_pool

    async def _recalculate_prize_pool(
        self, tournament_id: uuid.UUID
    ) -> PrizePool:
        """Internal: recalculate prize pool from all buy-ins."""
        # Aggregate totals by type
        result = await self.db.execute(
            select(
                BuyIn.type,
                func.sum(BuyIn.amount).label("total"),
                func.count(BuyIn.id).label("count"),
            )
            .where(BuyIn.tournament_id == tournament_id)
            .group_by(BuyIn.type)
        )
        rows = result.all()

        totals: dict[str, Decimal] = {}
        total_entries = 0
        for row in rows:
            totals[row.type] = Decimal(str(row.total or 0))
            total_entries += row.count

        total_buy_in = totals.get("buy_in", Decimal("0.00"))
        total_rebuys = totals.get("re_buy", Decimal("0.00"))
        total_addons = totals.get("add_on", Decimal("0.00"))
        total_prize_pool = total_buy_in + total_rebuys + total_addons

        # Determine entries count: unique players who bought in at least once
        entries_result = await self.db.execute(
            select(func.count(func.distinct(BuyIn.player_id)))
            .where(
                BuyIn.tournament_id == tournament_id,
                BuyIn.type == "buy_in",
            )
        )
        entries_count = entries_result.scalar() or 0

        # Upsert prize pool
        result = await self.db.execute(
            select(PrizePool).where(PrizePool.tournament_id == tournament_id)
        )
        prize_pool = result.scalar_one_or_none()

        if prize_pool is None:
            prize_pool = PrizePool(
                tournament_id=tournament_id,
                total_buy_in=total_buy_in,
                total_rebuys=total_rebuys,
                total_addons=total_addons,
                total_prize_pool=total_prize_pool,
                entries_count=entries_count,
            )
            self.db.add(prize_pool)
        else:
            prize_pool.total_buy_in = total_buy_in
            prize_pool.total_rebuys = total_rebuys
            prize_pool.total_addons = total_addons
            prize_pool.total_prize_pool = total_prize_pool
            prize_pool.entries_count = entries_count
            prize_pool.updated_at = datetime.now(timezone.utc)

        await self.db.flush()
        return prize_pool

    async def get_player_finances(
        self, tournament_id: uuid.UUID, player_id: uuid.UUID
    ) -> tuple[list[BuyIn], Decimal]:
        """Get a player's transactions for a tournament."""
        await self._get_tournament(tournament_id)
        await self._get_player(player_id)

        result = await self.db.execute(
            select(BuyIn)
            .options(joinedload(BuyIn.player))
            .where(
                BuyIn.tournament_id == tournament_id,
                BuyIn.player_id == player_id,
            )
            .order_by(BuyIn.created_at.desc())
        )
        buy_ins = list(result.scalars().all())

        total = sum((b.amount for b in buy_ins), Decimal("0.00"))
        return buy_ins, total

    async def get_overall_summary(self) -> dict:
        """Get financial summary across all tournaments."""
        # Aggregate all buy-ins
        result = await self.db.execute(
            select(
                BuyIn.tournament_id,
                BuyIn.type,
                func.sum(BuyIn.amount).label("total"),
                func.count(BuyIn.id).label("count"),
            )
            .group_by(BuyIn.tournament_id, BuyIn.type)
        )
        rows = result.all()

        # Group by tournament
        tournament_data: dict[uuid.UUID, dict] = {}
        grand_totals: dict[str, Decimal] = {
            "buy_in": Decimal("0.00"),
            "re_buy": Decimal("0.00"),
            "add_on": Decimal("0.00"),
        }
        grand_entries = 0
        all_payer_ids: set[uuid.UUID] = set()

        for row in rows:
            tid = row.tournament_id
            if tid not in tournament_data:
                tournament_data[tid] = {
                    "totals": {"buy_in": Decimal("0.00"), "re_buy": Decimal("0.00"), "add_on": Decimal("0.00")},
                    "players": set(),
                }
            tournament_data[tid]["totals"][row.type] = Decimal(str(row.total or 0))
            grand_totals[row.type] += Decimal(str(row.total or 0))

        # Get per-tournament player counts and entry counts
        for tid in tournament_data:
            players_res = await self.db.execute(
                select(func.count(func.distinct(BuyIn.player_id)))
                .where(BuyIn.tournament_id == tid, BuyIn.type == "buy_in")
            )
            tournament_data[tid]["entry_count"] = players_res.scalar() or 0

            all_players_res = await self.db.execute(
                select(func.count(func.distinct(BuyIn.player_id)))
                .where(BuyIn.tournament_id == tid)
            )
            tournament_data[tid]["payer_count"] = all_players_res.scalar() or 0

        # Total unique payers across all tournaments
        payers_res = await self.db.execute(
            select(func.count(func.distinct(BuyIn.player_id)))
        )
        grand_payer_count = payers_res.scalar() or 0

        # Tournament count
        t_count_res = await self.db.execute(
            select(func.count(func.distinct(BuyIn.tournament_id)))
        )
        tournament_count = t_count_res.scalar() or 0

        # Get tournament names
        t_names: dict[uuid.UUID, str] = {}
        if tournament_data:
            t_result = await self.db.execute(
                select(Tournament.id, Tournament.name).where(
                    Tournament.id.in_(list(tournament_data.keys()))
                )
            )
            for t_row in t_result.all():
                t_names[t_row.id] = t_row.name

        total_buy_in = grand_totals["buy_in"]
        total_rebuys = grand_totals["re_buy"]
        total_addons = grand_totals["add_on"]
        total_prize_pool = total_buy_in + total_rebuys + total_addons

        tournaments_list = []
        for tid, data in tournament_data.items():
            t_total = (
                data["totals"]["buy_in"]
                + data["totals"]["re_buy"]
                + data["totals"]["add_on"]
            )
            tournaments_list.append({
                "tournament_id": tid,
                "tournament_name": t_names.get(tid, "Unknown"),
                "total_buy_ins": data["totals"]["buy_in"],
                "total_rebuys": data["totals"]["re_buy"],
                "total_addons": data["totals"]["add_on"],
                "total_prize_pool": t_total,
                "entries_count": data.get("entry_count", 0),
                "payer_count": data.get("payer_count", 0),
            })

        return {
            "total_buy_ins": total_buy_in,
            "total_rebuys": total_rebuys,
            "total_addons": total_addons,
            "total_prize_pool": total_prize_pool,
            "entries_count": sum(
                d.get("entry_count", 0) for d in tournament_data.values()
            ),
            "payer_count": grand_payer_count,
            "tournament_count": tournament_count,
            "tournaments": tournaments_list,
        }

    async def _get_tournament(self, tournament_id: uuid.UUID) -> Tournament:
        result = await self.db.execute(
            select(Tournament).where(Tournament.id == tournament_id)
        )
        t = result.scalar_one_or_none()
        if t is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tournament not found",
            )
        return t

    async def _get_player(self, player_id: uuid.UUID) -> Player:
        result = await self.db.execute(
            select(Player).where(Player.id == player_id)
        )
        p = result.scalar_one_or_none()
        if p is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Player not found",
            )
        return p
