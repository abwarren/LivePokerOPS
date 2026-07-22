from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ─── Templates ───


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    category: str = Field(min_length=1, max_length=50)
    body_template: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    body_template: str | None = None
    variables: list[str] | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    category: str
    body_template: str
    variables: list[Any]
    is_builtin: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Broadcast ───


class BroadcastPreviewRequest(BaseModel):
    template_id: uuid.UUID
    variables: dict[str, Any]


class BroadcastSendRequest(BaseModel):
    template_id: uuid.UUID
    variables: dict[str, Any]
    subject: str = Field(default="", max_length=200)
    player_ids: list[uuid.UUID] | None = None  # None = all active players
    scheduled_for: datetime | None = None


class BroadcastManualRequest(BaseModel):
    """Send a one-off message without a template (override)."""

    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    player_ids: list[uuid.UUID] | None = None


class BroadcastResponse(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID | None = None
    subject: str
    rendered_body: str
    variables_used: dict[str, Any] | None = None
    status: str
    scheduled_for: datetime | None = None
    sent_at: datetime | None = None
    sent_by: uuid.UUID | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BroadcastRecipientResponse(BaseModel):
    id: uuid.UUID
    player_id: uuid.UUID
    player_name: str | None = None
    channel: str
    status: str
    delivered_at: datetime | None = None

    model_config = {"from_attributes": True}


class BroadcastDetailResponse(BroadcastResponse):
    recipients: list[BroadcastRecipientResponse] = []


class BroadcastHistoryParams(BaseModel):
    status: str | None = None
    category: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
