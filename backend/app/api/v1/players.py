import csv
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models import Player

router = APIRouter(prefix="/players", tags=["players"])


class PlayerImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = []


class PlayerSummary(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    nickname: str | None = None
    email: str
    phone: str | None = None
    is_active: bool
    is_admin: bool

    model_config = {"from_attributes": True}


@router.post("/import-csv", response_model=PlayerImportResult)
async def import_players_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
    file: UploadFile = File(...),
):
    """Import players from a CSV file. Expected columns: first_name, last_name, phone, email (optional), nickname (optional)."""  # noqa: E501
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files accepted")

    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    # Normalize column headers
    rows = []
    for row in reader:
        normalized = {}
        for k, v in row.items():
            key = k.strip().lower().replace(" ", "_").replace("-", "_")
            normalized[key] = v.strip() if v else ""
        rows.append(normalized)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    # Validate required columns
    required = {"first_name", "last_name", "phone"}
    headers = set(rows[0].keys())
    missing = required - headers
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(sorted(missing))}. Found: {', '.join(sorted(headers))}",  # noqa: E501
        )

    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(rows, start=2):  # line 2 = first data row
        phone = row.get("phone", "").strip()
        if not phone:
            skipped += 1
            errors.append(f"Row {i}: missing phone number")
            continue

        # Check duplicate by phone
        result = await db.execute(select(Player).where(Player.phone == phone))
        if result.scalar_one_or_none():
            skipped += 1
            continue

        # Generate email if not provided
        email = row.get("email", "").strip()
        if not email:
            first = row.get("first_name", "").strip().lower().replace(" ", ".")
            last = row.get("last_name", "").strip().lower().replace(" ", ".")
            email = f"{first}.{last}.{uuid.uuid4().hex[:4]}@import.livepokerops"

        player = Player(
            first_name=row.get("first_name", "").strip()[:100],
            last_name=row.get("last_name", "").strip()[:100],
            nickname=row.get("nickname", "").strip()[:100] or None,
            email=email[:255],
            phone=phone[:50],
        )
        db.add(player)
        imported += 1

    await db.flush()

    return PlayerImportResult(imported=imported, skipped=skipped, errors=errors[:20])


@router.get("/", response_model=list[PlayerSummary])
async def list_players(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
    search: str | None = None,
    limit: int = 100,
):
    """List all players, optionally search by name, email, or phone."""
    query = select(Player).order_by(Player.first_name, Player.last_name).limit(limit)
    if search:
        like = f"%{search}%"
        query = query.where(
            Player.first_name.ilike(like)
            | Player.last_name.ilike(like)
            | Player.email.ilike(like)
            | Player.phone.ilike(like)
        )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/count")
async def player_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Player = Depends(require_admin),
):
    """Get total player count."""
    from sqlalchemy import func

    result = await db.execute(select(func.count(Player.id)))
    return {"total": result.scalar() or 0}
