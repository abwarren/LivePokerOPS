from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import analytics as analytics_router
from app.api.v1 import attendance as attendance_router
from app.api.v1 import auth as auth_router
from app.api.v1 import broadcast as broadcast_router
from app.api.v1 import event_logs as event_logs_router
from app.api.v1 import finances as finances_router
from app.api.v1 import league as league_router
from app.api.v1 import players as players_router
from app.api.v1 import rsvps as rsvps_router
from app.api.v1 import tournaments as tournaments_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.health import router as health_router

settings = get_settings()
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(players_router.router, prefix="/api/v1")
app.include_router(broadcast_router.router, prefix="/api/v1")
app.include_router(tournaments_router.router, prefix="/api/v1")
app.include_router(event_logs_router.router, prefix="/api/v1")
app.include_router(attendance_router.router, prefix="/api/v1")
app.include_router(finances_router.router, prefix="/api/v1")
app.include_router(league_router.router, prefix="/api/v1")
app.include_router(rsvps_router.router, prefix="/api/v1")
app.include_router(analytics_router.router, prefix="/api/v1")
