from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TournamentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    buy_in: Decimal | None = Field(default=None, decimal_places=2, gt=0)
    starting_stack: int | None = Field(default=None, gt=0)
    min_players: int | None = Field(default=None, ge=0)
    max_players: int | None = Field(default=None, ge=0)
    late_reg_levels: int = Field(default=4, ge=0, le=50)
    start_time: datetime | None = None
    registration_deadline: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class TournamentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(
        default=None,
        pattern=r"^(planned|announced|in_progress|paused|completed|cancelled)$",
    )
    buy_in: Decimal | None = Field(default=None, decimal_places=2, gt=0)
    starting_stack: int | None = Field(default=None, gt=0)
    min_players: int | None = Field(default=None, ge=0)
    max_players: int | None = Field(default=None, ge=0)
    late_reg_levels: int | None = Field(default=None, ge=0, le=50)
    start_time: datetime | None = None
    registration_deadline: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class TournamentResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    buy_in: Decimal | None = None
    starting_stack: int | None = None
    min_players: int | None = None
    max_players: int | None = None
    late_reg_levels: int = 4
    start_time: datetime | None = None
    registration_deadline: datetime | None = None
    notes: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TournamentSummary(BaseModel):
    """Lightweight list item — no notes or timestamps."""
    id: uuid.UUID
    name: str
    status: str
    buy_in: Decimal | None = None
    starting_stack: int | None = None
    min_players: int | None = None
    max_players: int | None = None
    late_reg_levels: int = 4
    start_time: datetime | None = None
    player_count: int = 0

    model_config = {"from_attributes": True}
