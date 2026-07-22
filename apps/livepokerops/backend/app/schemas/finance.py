from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BuyInCreate(BaseModel):
    player_id: uuid.UUID
    amount: Decimal = Field(decimal_places=2, gt=0)
    type: str = Field(
        default="buy_in",
        pattern=r"^(buy_in|re_buy|add_on)$",
    )
    notes: str | None = Field(default=None, max_length=500)


class BulkBuyInCreate(BaseModel):
    entries: list[BuyInCreate] = Field(min_length=1, max_length=200)


class BuyInResponse(BaseModel):
    id: uuid.UUID
    tournament_id: uuid.UUID
    player_id: uuid.UUID
    player_name: str | None = None
    amount: Decimal
    type: str
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PrizePoolResponse(BaseModel):
    tournament_id: uuid.UUID
    tournament_name: str | None = None
    total_buy_in: Decimal = Decimal("0.00")
    total_rebuys: Decimal = Decimal("0.00")
    total_addons: Decimal = Decimal("0.00")
    total_prize_pool: Decimal = Decimal("0.00")
    entries_count: int = 0
    average_buy_in: Decimal = Decimal("0.00")

    model_config = {"from_attributes": True}


class PlayerFinanceResponse(BaseModel):
    buy_ins: list[BuyInResponse]
    total_spent: Decimal = Decimal("0.00")
    tournament_id: uuid.UUID
    player_id: uuid.UUID
    player_name: str | None = None

    model_config = {"from_attributes": True}


class TournamentFinanceSummary(BaseModel):
    tournament_id: uuid.UUID
    tournament_name: str
    total_buy_ins: Decimal = Decimal("0.00")
    total_rebuys: Decimal = Decimal("0.00")
    total_addons: Decimal = Decimal("0.00")
    total_prize_pool: Decimal = Decimal("0.00")
    entries_count: int = 0
    payer_count: int = 0

    model_config = {"from_attributes": True}


class FinancialSummary(BaseModel):
    total_buy_ins: Decimal = Decimal("0.00")
    total_rebuys: Decimal = Decimal("0.00")
    total_addons: Decimal = Decimal("0.00")
    total_prize_pool: Decimal = Decimal("0.00")
    entries_count: int = 0
    payer_count: int = 0
    tournament_count: int = 0
    tournaments: list[TournamentFinanceSummary] = []

    model_config = {"from_attributes": True}
