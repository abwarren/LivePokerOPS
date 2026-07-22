
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player, require_admin
from app.core.database import get_db
from app.models import Player, Broadcast, BroadcastRecipient
from app.schemas.broadcast import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    BroadcastPreviewRequest,
    BroadcastSendRequest,
    BroadcastManualRequest,
    BroadcastResponse,
    BroadcastDetailResponse,
    BroadcastRecipientResponse,
)
from app.services.broadcast import BroadcastService

router = APIRouter(prefix="/broadcast", tags=["broadcast"])

# ─── Template Endpoints ───


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
    category: str | None = Query(None, description="Filter by category"),
):
    """List all message templates, optionally filtered by category."""
    service = BroadcastService(db)
    return await service.list_templates(category=category)


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
):
    """Get a specific template."""
    service = BroadcastService(db)
    tmpl = await service.get_template(template_id)
    if tmpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return tmpl


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
):
    """Create a new message template."""
    service = BroadcastService(db)
    # Check name uniqueness
    existing = await service.list_templates()
    if any(t.name == body.name for t in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template '{body.name}' already exists",
        )

    return await service.create_template(
        name=body.name,
        description=body.description,
        category=body.category,
        body_template=body.body_template,
        variables=body.variables,
    )


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
):
    """Update a message template."""
    service = BroadcastService(db)
    tmpl = await service.update_template(
        template_id,
        name=body.name,
        description=body.description,
        category=body.category,
        body_template=body.body_template,
        variables=body.variables,
    )
    if tmpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return tmpl


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
):
    """Delete a custom template (built-in templates cannot be deleted)."""
    service = BroadcastService(db)
    deleted = await service.delete_template(template_id)
    if not deleted:
        tmpl = await service.get_template(template_id)
        if tmpl is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Built-in templates cannot be deleted",
        )


# ─── Preview & Send ───


@router.post("/preview")
async def preview_message(
    body: BroadcastPreviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
):
    """Preview a rendered template message without sending."""
    service = BroadcastService(db)
    rendered = await service.preview(body.template_id, body.variables)
    if rendered is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return {"rendered_body": rendered}


@router.post("/send", response_model=BroadcastResponse, status_code=status.HTTP_201_CREATED)
async def send_broadcast(
    body: BroadcastSendRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Player = Depends(require_admin),
):
    """Send a broadcast from a template immediately or schedule it."""
    service = BroadcastService(db)
    broadcast = await service.send(
        template_id=body.template_id,
        variables=body.variables,
        subject=body.subject,
        player_ids=body.player_ids,
        sent_by=admin.id,
        scheduled_for=body.scheduled_for,
    )
    if broadcast is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return broadcast


@router.post("/send-manual", response_model=BroadcastResponse, status_code=status.HTTP_201_CREATED)
async def send_manual_broadcast(
    body: BroadcastManualRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Player = Depends(require_admin),
):
    """Send a one-off message without a template (override)."""
    service = BroadcastService(db)
    broadcast = await service.send_manual(
        subject=body.subject,
        body=body.body,
        player_ids=body.player_ids,
        sent_by=admin.id,
    )
    return broadcast


# ─── History & Recipients ───


@router.get("/history", response_model=list[BroadcastResponse])
async def list_broadcasts(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
    status: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List broadcast history with optional filters."""
    service = BroadcastService(db)
    return await service.list_broadcasts(
        status=status, category=category, limit=limit, offset=offset
    )


@router.get("/history/{broadcast_id}", response_model=BroadcastDetailResponse)
async def get_broadcast_detail(
    broadcast_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
):
    """Get a specific broadcast with recipient delivery details."""
    service = BroadcastService(db)
    broadcast = await service.get_broadcast(broadcast_id)
    if broadcast is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broadcast not found")

    # Load recipients
    from sqlalchemy import select as sel
    result = await db.execute(
        sel(BroadcastRecipient).where(BroadcastRecipient.broadcast_id == broadcast_id)
    )
    recipients = list(result.scalars().all())

    # Load player names for recipients
    recipient_responses = []
    for r in recipients:
        player_result = await db.execute(sel(Player).where(Player.id == r.player_id))
        player = player_result.scalar_one_or_none()
        recipient_responses.append(BroadcastRecipientResponse(
            id=r.id,
            player_id=r.player_id,
            player_name=f"{player.first_name} {player.last_name}" if player else "Unknown",
            channel=r.channel,
            status=r.status,
            delivered_at=r.delivered_at,
        ))

    return BroadcastDetailResponse(
        id=broadcast.id,
        template_id=broadcast.template_id,
        subject=broadcast.subject,
        rendered_body=broadcast.rendered_body,
        variables_used=broadcast.variables_used,
        status=broadcast.status,
        scheduled_for=broadcast.scheduled_for,
        sent_at=broadcast.sent_at,
        sent_by=broadcast.sent_by,
        error_message=broadcast.error_message,
        created_at=broadcast.created_at,
        recipients=recipient_responses,
    )


@router.get("/stats")
async def broadcast_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
):
    """Get aggregate broadcast statistics."""
    service = BroadcastService(db)
    return await service.get_broadcast_stats()


# ─── Template Categories (for dropdown) ───

@router.get("/categories")
async def list_categories():
    """List available template categories."""
    return {
        "categories": [
            {"id": "announcement", "name": "Tournament Announcement"},
            {"id": "game_on", "name": "Game On / Kickoff"},
            {"id": "final_table", "name": "Final Table Post"},
            {"id": "results", "name": "Results & Recap"},
            {"id": "reminder", "name": "Reminder"},
        ]
    }
