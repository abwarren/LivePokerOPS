from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import Auth, Player
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    PlayerMeResponse,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Register a new player account."""
    # Check email uniqueness
    result = await db.execute(select(Player).where(Player.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Check nickname uniqueness if provided
    if body.nickname:
        result = await db.execute(select(Player).where(Player.nickname == body.nickname))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nickname already taken",
            )

    player = Player(
        first_name=body.first_name,
        last_name=body.last_name,
        nickname=body.nickname,
        email=body.email,
        phone=body.phone,
    )
    db.add(player)
    await db.flush()

    auth = Auth(
        player_id=player.id,
        password_hash=hash_password(body.password),
    )
    db.add(auth)
    await db.flush()

    access_token = create_access_token(player.id)
    refresh_token = create_refresh_token(player.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate and receive tokens."""
    result = await db.execute(select(Player).where(Player.email == body.email))
    player = result.scalar_one_or_none()

    if player is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    result = await db.execute(select(Auth).where(Auth.player_id == player.id))
    auth = result.scalar_one_or_none()

    if auth is None or not verify_password(body.password, auth.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not player.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    auth.last_login_at = datetime.now(timezone.utc)
    db.add(auth)

    access_token = create_access_token(player.id)
    refresh_token = create_refresh_token(player.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: TokenRefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Get a new access token using a refresh token."""
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    player_id = payload.get("sub")
    if player_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    result = await db.execute(
        select(Player).where(Player.id == uuid.UUID(player_id))
    )
    player = result.scalar_one_or_none()

    if player is None or not player.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    access_token = create_access_token(player.id)
    refresh_token = create_refresh_token(player.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,
    )


@router.get("/me", response_model=PlayerMeResponse)
async def get_me(
    player: Player = Depends(get_current_player),
) -> PlayerMeResponse:
    """Get the current authenticated player's profile."""
    return PlayerMeResponse.model_validate(player)
