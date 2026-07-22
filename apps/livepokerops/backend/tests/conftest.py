import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.logging import setup_logging
from app.main import app
from app.models.broadcast import MessageTemplate

setup_logging()

# Use SQLite in-memory for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Enable WAL mode for concurrent test access
    async with test_engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.exec_driver_sql("PRAGMA busy_timeout=5000")
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, db_session: AsyncSession) -> str:
    """Register an admin player, promote in DB, return access token."""
    # Register via the API (goes through normal flow)
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Admin",
            "last_name": "Test",
            "email": "admin-test@test.com",
            "password": "StrongP@ss1",
        },
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    token = resp.json()["access_token"]

    # Promote to admin directly in the database
    from sqlalchemy import text

    await db_session.execute(
        text("UPDATE players SET is_admin = true WHERE email = 'admin-test@test.com'")
    )
    await db_session.commit()

    return token


@pytest_asyncio.fixture
async def player_token(client: AsyncClient) -> str:
    """Register a regular (non-admin) player and return access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Player",
            "last_name": "Test",
            "email": "player-test@test.com",
            "password": "StrongP@ss1",
        },
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def seed_templates(db_session: AsyncSession) -> list[MessageTemplate]:
    """Seed a few message templates for testing."""
    templates = [
        MessageTemplate(
            name="test_announcement",
            description="Test announcement",
            category="announcement",
            body_template="Game at {time} on {date}! {player_count} players: {player_list}",
            variables=["time", "date", "player_count", "player_list"],
            is_builtin=True,
        ),
        MessageTemplate(
            name="test_reminder",
            description="Test reminder",
            category="reminder",
            body_template="Reminder: {tournament} at {time}",
            variables=["tournament", "time"],
            is_builtin=False,
        ),
    ]
    for t in templates:
        db_session.add(t)
    await db_session.flush()
    await db_session.commit()
    return templates
