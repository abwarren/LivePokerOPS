# ConceptPokerMTTpro — Vertical Slice Integration Plan

> **For Hermes:** Execute slice-by-slice, in order. Each slice touches ALL layers before the next begins. Do not skip to the next slice until the current slice passes every acceptance criterion.

**Goal:** Integrate full tournament operations (seating, balancing, realtime, overlays, feature table, dealer voice, NFC, CMS) into LivePokerOPS — one repo, one stack, one deploy target.

**Current foundation:** FastAPI + PostgreSQL + SQLAlchemy + Docker Compose with players, auth, broadcast engine working.

---

## Slice Map (Vertical, in dependency order)

| Slice | Feature | Proves | Depends On |
|-------|---------|--------|------------|
| 1 | `event_logs` table + tournament CRUD | Event system + tournament lifecycle works | Nothing (uses existing DB infra) |
| 2 | Tables + seat assignments | Physical table model + duplicate seat protection | Slice 1 |
| 3 | Player movement + bust + clock | Tournament lifecycle actions + blind levels | Slice 2 |
| 4 | Table balancing engine | Balancing logic + suggestion/approve/reject | Slice 3 |
| 5 | Projections / read models | Event → current state separation | Slice 4 |
| 6 | WebSocket realtime layer | Live state push to clients | Slice 5 |
| 7 | OBS overlay system | External read-only browser-source output | Slice 6 |
| 8 | Feature table capture | Hole cards + board with public/private split | Slice 6 |
| 9 | Dealer voice system | STT → parser → event pipeline | Slice 6 |
| 10 | NFC scan system | Physical identity → event flow | Slice 6 |
| 11 | CMS | Player profiles, balances, permissions | Slice 1 (parallel-safe after slice 1) |

---

## Slice 1 — Event Log + Tournament CRUD

**What it proves:** The event system works. Tournaments can be created with a status lifecycle. Every action generates an immutable event_log row.

### New Files

```
backend/app/models/event_log.py
backend/app/models/tournament.py
backend/app/schemas/event_log.py
backend/app/schemas/tournament.py
backend/app/services/event_log.py
backend/app/services/tournament.py
backend/app/api/v1/event_logs.py
backend/app/api/v1/tournaments.py
```

### DB Tables (Alembic migration 0003)

**event_logs**
```sql
CREATE TABLE event_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,       -- TOURNAMENT_CREATED, PLAYER_BUSTED, etc.
    source VARCHAR(50) NOT NULL DEFAULT 'api',  -- api, voice, nfc, system
    tournament_id UUID REFERENCES tournaments(id),
    actor_id UUID REFERENCES players(id),
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_event_logs_tournament ON event_logs(tournament_id, created_at DESC);
CREATE INDEX ix_event_logs_type ON event_logs(event_type);
```

**tournaments**
```sql
CREATE TABLE tournaments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planned',
    -- planned, announced, in_progress, paused, completed, cancelled
    buy_in DECIMAL(12,2) DEFAULT 0,
    starting_stack BIGINT DEFAULT 0,
    min_players INT DEFAULT 0,
    max_players INT DEFAULT 0,
    late_reg_levels INT DEFAULT 4,
    start_time TIMESTAMPTZ,
    registration_deadline TIMESTAMPTZ,
    created_by UUID REFERENCES players(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_tournaments_status ON tournaments(status);
```

### Models

```python
# backend/app/models/event_log.py
class EventLog(Base):
    __tablename__ = "event_logs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="api")
    tournament_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tournaments.id"), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("players.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

# backend/app/models/tournament.py
class Tournament(Base):
    __tablename__ = "tournaments"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    buy_in: Mapped[Decimal | None] = mapped_column(Numeric(12,2), nullable=True)
    starting_stack: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    min_players: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_players: Mapped[int | None] = mapped_column(Integer, nullable=True)
    late_reg_levels: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("players.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

### Service Layer

```python
# backend/app/services/event_log.py
class EventLogService:
    def __init__(self, db: AsyncSession): ...

    async def log_event(
        event_type: str,
        source: str = "api",
        tournament_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        payload: dict | None = None,
    ) -> EventLog: ...

    async def get_events(
        tournament_id: uuid.UUID | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventLog]: ...
```

### API Endpoints

```python
# backend/app/api/v1/tournaments.py
POST   /api/v1/tournaments                    # Create tournament
GET    /api/v1/tournaments                     # List tournaments (filterable by status)
GET    /api/v1/tournaments/{id}                # Get tournament detail
PATCH  /api/v1/tournaments/{id}                # Update tournament (status change, etc.)
DELETE /api/v1/tournaments/{id}                # Soft-delete / cancel tournament

# backend/app/api/v1/event_logs.py
GET    /api/v1/tournaments/{id}/events         # Get events for a tournament (paginated)
GET    /api/v1/events                          # Get all events (admin)
```

### Acceptance Criteria

```
[ ] POST /api/v1/tournaments { name, buy_in, starting_stack } → 201 + tournament + event_log row
[ ] GET  /api/v1/tournaments → list includes new tournament
[ ] PATCH /api/v1/tournaments/{id} { status: "in_progress" } → event_log has TOURNAMENT_STATUS_CHANGED
[ ] GET  /api/v1/tournaments/{id}/events → returns event_log rows
[ ] Edge case: create tournament with missing name → 422
[ ] Edge case: get events for nonexistent tournament → 404
[ ] event_logs table has TOURNAMENT_CREATED after POST
```

---

## Slice 2 — Tables + Seat Assignments

**What it proves:** Tables belong to tournaments. Seats have duplicate protection. Event logging fires on every seat change.

### New Files

```
backend/app/models/tournament_table.py
backend/app/models/seat_assignment.py
backend/app/schemas/table.py
backend/app/schemas/seat.py
backend/app/services/table.py
backend/app/services/seat.py
backend/app/api/v1/tables.py
backend/app/api/v1/seats.py
```

### DB Tables (Alembic migration 0004)

**tournament_tables**
```sql
CREATE TABLE tournament_tables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    table_number INT NOT NULL,
    max_seats INT NOT NULL DEFAULT 9,
    is_feature_table BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, broken, completed
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tournament_id, table_number)
);
```

**seat_assignments**
```sql
CREATE TABLE seat_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    table_id UUID NOT NULL REFERENCES tournament_tables(id) ON DELETE CASCADE,
    seat_number INT NOT NULL,
    player_name VARCHAR(200) NOT NULL,
    player_id UUID REFERENCES players(id),
    stack_size BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    -- active, busted, moved_out, empty
    moved_from_id UUID REFERENCES seat_assignments(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_active_seat UNIQUE (table_id, seat_number, status)
    -- Note: unique on (table_id, seat_number) WHERE status='active' via partial index
);
CREATE UNIQUE INDEX ix_seat_active ON seat_assignments(table_id, seat_number) WHERE status = 'active';
```

### Duplicate Seat Protection

```python
# backend/app/services/seat.py
class SeatService:
    async def validate_seat_available(
        self, table_id: uuid.UUID, seat_number: int
    ) -> bool:
        """Raise HTTPException 409 if seat is occupied by an active assignment."""
        result = await self.db.execute(
            select(SeatAssignment).where(
                SeatAssignment.table_id == table_id,
                SeatAssignment.seat_number == seat_number,
                SeatAssignment.status == "active",
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(409, detail="Seat already occupied")
        return True

    async def validate_table_exists(
        self, tournament_id: uuid.UUID, table_id: uuid.UUID
    ) -> TournamentTable:
        """Raise 404 if table doesn't belong to this tournament."""
        ...

    async def assign_seat(...) -> SeatAssignment:
        """Validate tournament → validate table → validate seat available → create → log event."""
        ...
```

### API Endpoints

```python
POST   /api/v1/tournaments/{id}/tables                # Create table
GET    /api/v1/tournaments/{id}/tables                 # List tables with seat counts
GET    /api/v1/tournaments/{id}/tables/{table_id}       # Table detail with seats
DELETE /api/v1/tournaments/{id}/tables/{table_id}       # Break table (if no active seats)

POST   /api/v1/tournaments/{id}/tables/{table_id}/seats  # Assign seat
GET    /api/v1/tournaments/{id}/tables/{table_id}/seats   # List seats at table
PATCH  /api/v1/seats/{seat_id}                             # Update stack / player_name
DELETE /api/v1/seats/{seat_id}                             # Open seat (mark inactive)
```

### Acceptance Criteria

```
[ ] POST /api/v1/tournaments/{id}/tables { table_number: 1, max_seats: 9 } → 201 + event
[ ] POST same table_number again → 409 (duplicate table in tournament)
[ ] POST seat { seat_number: 1, player_name: "Alice", stack_size: 50000 } → 201 + SEAT_ASSIGNED event
[ ] POST same seat again → 409 (already occupied)
[ ] POST seat at nonexistent table → 404
[ ] GET seats → returns [ { seat_number, player_name, stack_size, status } ]
[ ] PATCH /api/v1/seats/{id} { stack_size: 55000 } → updated
[ ] DELETE /api/v1/seats/{id} → seat status = "empty", SEAT_OPEN event
[ ] event_logs has SEAT_ASSIGNED after assign, SEAT_OPEN after delete
```

---

## Slice 3 — Player Movement, Bust, Clock, Blind Levels

**What it proves:** Tournament lifecycle actions work — moving players between tables, busting players, clock start/pause/level changes.

### New Files

```
backend/app/models/blind_level.py
backend/app/models/tournament_clock.py
backend/app/schemas/movement.py
backend/app/schemas/clock.py
backend/app/services/movement.py
backend/app/services/clock.py
backend/app/api/v1/movement.py
backend/app/api/v1/clock.py
```

### DB Tables (Alembic migration 0005)

**blind_levels**
```sql
CREATE TABLE blind_levels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    level_number INT NOT NULL,
    small_blind BIGINT NOT NULL,
    big_blind BIGINT NOT NULL,
    ante BIGINT DEFAULT 0,
    duration_minutes INT NOT NULL DEFAULT 20,
    is_break BOOLEAN NOT NULL DEFAULT false,
    UNIQUE(tournament_id, level_number)
);
```

**tournament_clock**
```sql
CREATE TABLE tournament_clock (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE UNIQUE,
    current_level INT NOT NULL DEFAULT 1,
    seconds_remaining INT NOT NULL DEFAULT 1200,
    is_running BOOLEAN NOT NULL DEFAULT false,
    started_at TIMESTAMPTZ,
    paused_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**tournament_players**
```sql
CREATE TABLE tournament_players (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    player_id UUID REFERENCES players(id),
    player_name VARCHAR(200) NOT NULL,
    initial_stack BIGINT NOT NULL DEFAULT 0,
    current_stack BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'registered',
    -- registered, seated, busted, moved, withdrawn, disqualified
    registration_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    busted_at TIMESTAMPTZ,
    finishing_position INT,
    UNIQUE(tournament_id, player_name)
);
```

### Service Methods

```python
# backend/app/services/movement.py
class MovementService:
    async def move_player(seat_id, to_table_id, to_seat_number, reason) -> SeatAssignment
        # 1. Find current active seat
        # 2. Validate destination table exists in tournament
        # 3. Validate destination seat empty
        # 4. Mark old seat status = "moved_out", moved_from_id pointing at old
        # 5. Create new seat_assignment with same player, new location
        # 6. Log PLAYER_MOVED event
        # 7. Update player's current_stack on new seat
        # 8. Return new seat

    async def bust_player(seat_id) -> None
        # 1. Find active seat
        # 2. Mark seat status = "busted", stack = 0
        # 3. Update tournament_player status = "busted", busted_at = now
        # 4. Log PLAYER_BUSTED event
        # 5. Log SEAT_OPEN event
        # 6. Trigger balancing check

    async def update_stack(seat_id, new_stack) -> SeatAssignment
        # 1. Find active seat
        # 2. Update stack_size
        # 3. Update tournament_player.current_stack
        # 4. Log STACK_UPDATED event

# backend/app/services/clock.py
class ClockService:
    async def start_clock(tournament_id) -> dict
    async def pause_clock(tournament_id) -> dict
    async def advance_level(tournament_id) -> dict
    async def get_clock_state(tournament_id) -> dict
```

### API Endpoints

```python
# Movement
POST   /api/v1/tournaments/{id}/move-player    # Move player between tables
POST   /api/v1/tournaments/{id}/bust-player    # Bust player
POST   /api/v1/tournaments/{id}/stacks          # Update stack
POST   /api/v1/tournaments/{id}/register        # Register player in tournament
GET    /api/v1/tournaments/{id}/players         # List tournament players

# Clock
POST   /api/v1/tournaments/{id}/clock/start    # Start clock
POST   /api/v1/tournaments/{id}/clock/pause    # Pause clock
POST   /api/v1/tournaments/{id}/clock/advance  # Advance to next level
GET    /api/v1/tournaments/{id}/clock          # Get clock state

# Blind levels
POST   /api/v1/tournaments/{id}/blind-levels   # Set blind structure (bulk)
GET    /api/v1/tournaments/{id}/blind-levels   # Get blind structure
```

### Acceptance Criteria

```
[ ] POST /api/v1/tournaments/{id}/register { player_name, stack } → PLAYER_REGISTERED event
[ ] POST move-player { seat_assignment_id, to_table_id, to_seat_number } → old seat inactive, new seat created, PLAYER_MOVED event
[ ] POST bust-player { seat_assignment_id } → seat busted, SEAT_OPEN + PLAYER_BUSTED events
[ ] POST clock/start → CLOCK_STARTED event
[ ] POST clock/pause → CLOCK_PAUSED event
[ ] POST clock/advance → LEVEL_CHANGED event
[ ] Move player to occupied seat → 409
[ ] Bust already-busted player → 400
```

---

## Slice 4 — Table Balancing Engine

**What it proves:** Balancing logic generates suggestions, operator approves/rejects, move executes.

### New Files

```
backend/app/models/balancing.py
backend/app/schemas/balancing.py
backend/app/services/balancing/rules.py
backend/app/services/balancing/service.py
backend/app/api/v1/balancing.py
backend/tests/test_balancing.py
```

### DB Tables (Alembic migration 0006)

**balancing_suggestions**
```sql
CREATE TABLE balancing_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    from_table_id UUID NOT NULL REFERENCES tournament_tables(id),
    from_seat_id UUID NOT NULL REFERENCES seat_assignments(id),
    to_table_id UUID NOT NULL REFERENCES tournament_tables(id),
    to_seat_number INT NOT NULL,
    player_name VARCHAR(200) NOT NULL,
    reason VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, approved, rejected, expired
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES players(id)
);
```

### Balancing Rules (backend/app/services/balancing/rules.py)

```python
class BalancingRules:
    @staticmethod
    def needs_balancing(table_counts: dict[int, int], target_diff: int = 2) -> bool
        """Returns True if max table count - min table count > target_diff."""

    @staticmethod
    def find_source_and_target(table_counts: dict[int, int]) -> tuple[int, int]
        """Returns (source_table_number, target_table_number)."""

    @staticmethod
    def should_move_player(seat: SeatAssignment, recent_moves: list) -> bool
        """Avoid moving players who were just moved (within last N levels)."""
```

### Service (backend/app/services/balancing/service.py)

```python
class BalancingService:
    async def check_and_suggest(tournament_id) -> list[BalancingSuggestion]
        """Check all tables. If unbalanced, generate suggestions."""

    async def approve(suggestion_id, actor_id) -> SeatAssignment
        """Validate suggestion still valid → execute move_player → mark approved."""

    async def reject(suggestion_id, actor_id) -> None
        """Mark suggestion rejected, log BALANCE_SUGGESTION_REJECTED."""
```

### API Endpoints

```python
GET    /api/v1/tournaments/{id}/balancing/suggestions    # Get pending suggestions
POST   /api/v1/balancing/{suggestion_id}/approve         # Approve and execute
POST   /api/v1/balancing/{suggestion_id}/reject          # Reject suggestion
POST   /api/v1/tournaments/{id}/balancing/check          # Force recheck now
```

### Acceptance Criteria

```
[ ] Create 2 tables: T1 has 5 seats, T2 has 2 seats → check returns suggestion
[ ] Approve suggestion → player moved, suggestion status = approved
[ ] Reject suggestion → suggestion status = rejected, no seat change
[ ] Approve expired suggestion (seat already filled) → 409
[ ] event_logs has TABLE_MOVE_SUGGESTED, TABLE_BALANCE_COMPLETED
```

---

## Slice 5 — Projections / Read Models

**What it proves:** Current state is built from events, not raw DB queries. Event history and current state are separate concerns.

### New Files

```
backend/app/projections/__init__.py
backend/app/projections/tournament_state.py
backend/app/projections/seating_state.py
backend/app/projections/overlay_state.py
backend/app/projections/feature_table_state.py
backend/app/api/v1/projections.py
```

### Projection Design

```python
# backend/app/projections/tournament_state.py
class TournamentProjection:
    """Read model: current tournament state built from event_logs + DB."""

    async def get_summary(tournament_id) -> dict:
        """{
            id, name, status,
            total_players: int,
            remaining_players: int,
            average_stack: int,
            total_chips: int,
            current_level: int,
            clock: { is_running, seconds_remaining },
            table_count: int,
        }"""

    async def get_table_breakdown(tournament_id) -> list[dict]:
        """Per-table: table_number, seat_count, occupied_seats, total_chips."""

# backend/app/projections/seating_state.py
class SeatingProjection:
    async def get_seating_chart(tournament_id) -> list[dict]:
        """All tables with all seats, status per seat."""

    async def get_table(tournament_id, table_id) -> dict:
        """Single table with seat assignments."""

# backend/app/projections/overlay_state.py
class OverlayProjection:
    async def get_clock_overlay(tournament_id) -> dict:
        """Clock, level, blinds, next level info."""

    async def get_player_stack_overlay(table_id) -> list[dict]:
        """Player name + stack for OBS overlay."""

# backend/app/projections/feature_table_state.py
class FeatureTableProjection:
    async def get_public_state(table_id) -> dict:
        """Board cards, pot, player stacks (no hole cards)."""

    async def get_private_state(table_id) -> dict:
        """Includes hole cards — requires auth check."""
```

### API Endpoints

```python
GET    /api/v1/projections/tournaments/{id}/summary
GET    /api/v1/projections/tournaments/{id}/seating
GET    /api/v1/projections/tournaments/{id}/clock
GET    /api/v1/projections/tables/{id}/stacks
GET    /api/v1/projections/tables/{id}/feature/public
GET    /api/v1/projections/tables/{id}/feature/private     # Auth required
```

### Acceptance Criteria

```
[ ] After seating 5 players, projection summary shows total_players=5
[ ] After busting 2 players, projection shows remaining_players=3
[ ] After moving player, seating projection reflects new table
[ ] Clock projection reflects start/pause/level changes
[ ] Projection stays correct after 10 mutations
```

---

## Slice 6 — WebSocket Realtime Layer

**What it proves:** Events broadcast to all connected clients in real time. No polling needed.

### New Files

```
backend/app/realtime/__init__.py
backend/app/realtime/manager.py
backend/app/realtime/router.py
backend/app/realtime/broadcaster.py
```

### Connection Manager

```python
# backend/app/realtime/manager.py
class ConnectionManager:
    _connections: dict[uuid.UUID, WebSocket]  # client_id → ws
    _subscriptions: dict[str, set[uuid.UUID]]  # tournament_id → {client_ids}
    _client_types: dict[uuid.UUID, str]  # client_id → operator|overlay|projector|admin

    async def connect(ws, client_type: str) -> uuid.UUID
    async def disconnect(client_id: uuid.UUID)
    async def subscribe(client_id: uuid.UUID, tournament_id: str)
    async def unsubscribe(client_id: uuid.UUID, tournament_id: str)

# backend/app/realtime/broadcaster.py
class Broadcaster:
    async def broadcast_event(event_type: str, payload: dict, tournament_id: str | None = None)
        """Send to all subscribed clients. Respect client type permissions."""
        # overlay clients → only public events (no hole cards)
        # operator clients → all events
        # projector clients → public + seating events
```

### WebSocket Endpoint

```
WS   /api/v1/ws?client_type={operator|overlay|projector|admin}
     → On connect: register, send full current state
     → On message: subscribe/unsubscribe to tournament
     → On broadcast: receive typed events
```

### Event Types Broadcast

| Event Type | Consumers |
|------------|-----------|
| SEAT_ASSIGNED | operator, projector |
| PLAYER_MOVED | operator, projector |
| PLAYER_BUSTED | operator, projector |
| STACK_UPDATED | operator, overlay, projector |
| CLOCK_STARTED | operator, overlay, projector |
| LEVEL_CHANGED | operator, overlay, projector |
| TABLE_BALANCE_REQUIRED | operator |
| HOLE_CARDS (private) | operator only |
| BOARD_UPDATE | overlay (public), operator |
| POT_UPDATE | overlay, operator |

### Acceptance Criteria

```
[ ] Connect WS as operator → receives full tournament state on connect
[ ] Connect WS as overlay → does NOT receive hole cards
[ ] Assign a seat → WS receives SEAT_ASSIGNED
[ ] Bust a player → WS receives PLAYER_BUSTED
[ ] Start clock → WS receives CLOCK_STARTED
[ ] Disconnect client → reconnection resends full state
```

---

## Slice 7 — OBS Overlay System

**What it proves:** Browser-source HTML served by FastAPI, reads projections, auto-updates via WebSocket.

### New Files

```
backend/app/overlays/__init__.py
backend/app/overlays/router.py
backend/app/overlays/templates/
├── clock.html
├── stacks.html
├── break_screen.html
├── balancing_alert.html
├── feature_table.html
backend/app/overlays/static/
├── overlay.js          # WebSocket client + DOM update helpers
├── overlay.css         # Dark theme, 1920x1080 sizing
```

### Architecture

```
OBS Browser Source ──→ FastAPI /overlays/clock?tournament_id=X
                              │
                              ├── Returns HTML page with embedded WS client
                              │
                              └── OBS page connects WS → receives events → DOM updates

Overlay rules (enforced by code):
  - Overlays NEVER write to DB or API
  - Overlays connect with client_type="overlay"
  - Private data (hole cards) is filtered by broadcaster
  - All state comes from projections, never raw SQL
```

### Overlay Endpoints

```
GET    /overlays/clock?tournament_id={id}          # Level, blinds, time remaining
GET    /overlays/stacks?table_id={id}              # Player stacks for a table
GET    /overlays/feature-table?table_id={id}       # Board, pot, stacks, actions
GET    /overlays/break-screen?tournament_id={id}   # Next level info, countdown
GET    /overlays/balancing-alert?tournament_id={id} # Auto-show when balancing needed
```

### Overlay JS Client (overlay.js)

```javascript
// Connect to WS with client_type=overlay
// Subscribe to tournament_id
// On event: update DOM via data- attributes
// On disconnect: auto-reconnect with exponential backoff
// Styling: 1920x1080, transparent background, large poker font
```

### Acceptance Criteria

```
[ ] GET /overlays/clock returns valid HTML with clock state
[ ] GET /overlays/stacks returns valid HTML with seated players + stacks
[ ] Stack update via API → overlay HTML auto-updates via WS
[ ] Clock start via API → overlay clock starts counting
[ ] Open overlays in browser (not just OBS) — same pages work
[ ] overlay.js connects WS with client_type=overlay, no auth token needed
```

---

## Slice 8 — Feature Table Capture

**What it proves:** Hole cards, board cards, pot size, actions captured with public/private split.

### New Files

```
backend/app/models/feature_table.py
backend/app/schemas/feature_table.py
backend/app/services/feature_table.py
backend/app/api/v1/feature_table.py
```

### DB Tables (Alembic migration 0007)

**feature_table_hands**
```sql
CREATE TABLE feature_table_hands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_id UUID NOT NULL REFERENCES tournament_tables(id),
    hand_number INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    dealer_position INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
```

**feature_table_hole_cards**
```sql
CREATE TABLE feature_table_hole_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hand_id UUID NOT NULL REFERENCES feature_table_hands(id) ON DELETE CASCADE,
    seat_assignment_id UUID NOT NULL REFERENCES seat_assignments(id),
    card1 VARCHAR(3) NOT NULL,
    card2 VARCHAR(3) NOT NULL,
    reader_id VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_hole_cards_hand ON feature_table_hole_cards(hand_id);
```

**feature_table_public_state**
```sql
CREATE TABLE feature_table_public_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_id UUID NOT NULL REFERENCES tournament_tables(id) UNIQUE,
    hand_id UUID REFERENCES feature_table_hands(id),
    board_cards JSONB NOT NULL DEFAULT '[]',
    pot_size BIGINT NOT NULL DEFAULT 0,
    current_action_seat INT,
    last_action VARCHAR(100),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### API Endpoints

```python
POST   /api/v1/feature-table/hands                          # Start new hand
POST   /api/v1/feature-table/hole-cards                      # Capture hole cards (private)
POST   /api/v1/feature-table/board                           # Update board cards
POST   /api/v1/feature-table/pot                             # Update pot size
POST   /api/v1/feature-table/action                          # Record action (bet/call/fold)
POST   /api/v1/feature-table/complete-hand                   # End current hand
GET    /api/v1/projections/tables/{id}/feature/public        # Public state for overlays
GET    /api/v1/projections/tables/{id}/feature/private       # Includes hole cards (auth'd)
```

### Private/Public Split

```python
# backend/app/services/feature_table.py
class FeatureTableService:
    async def capture_hole_cards(hand_id, seat_number, card1, card2, reader_id) -> None
        """Store in feature_table_hole_cards (private table).
        Broadcast HOLE_CARDS only to operator+admin WS clients.
        Do NOT update feature_table_public_state."""

    async def update_board(hand_id, cards: list[str]) -> dict
        """Update feature_table_public_state.board_cards.
        Broadcast BOARD_UPDATE to all WS clients (public)."""

    async def set_pot(hand_id, size: int) -> dict
        """Update feature_table_public_state.pot_size.
        Broadcast POT_UPDATE to all WS clients."""
```

### Acceptance Criteria

```
[ ] POST feature-table/hands → 201, new hand active
[ ] POST hole-cards { hand_id, seat_number, card1: "Ah", card2: "Kd" } → 200, private event logged
[ ] POST board { hand_id, cards: ["As", "7c", "2d"] } → public state shows board, WS broadcast
[ ] POST pot { hand_id, size: 42000 } → public state shows pot
[ ] POST action { hand_id, seat, action: "raise", amount: 15000 } → recorded
[ ] Complete hand → is_active=false, public state board clears
[ ] Overlay WS client does NOT receive hole_cards event
[ ] Operator WS client DOES receive hole_cards event
```

---

## Slice 9 — Dealer Voice System

**What it proves:** Speech → text → structured command → validation → event log pipeline.

### New Files

```
backend/voice_gateway/
├── __init__.py
├── audio_capture.py        # File/stream input for now
├── stt_provider.py         # STT abstraction (console mock v1, real API later)
├── parser.py               # Strict command parser
├── validator.py            # Validate against current game state
├── router.py               # FastAPI endpoints
└── submit_event.py         # Submit parsed command to event system
```

### Command Grammar

```
STACK    seat <N> <amount>        → update stack for seat N
POT     <amount>                  → set feature table pot
SEAT    OPEN seat <N>             → open seat N
SEAT    CLOSE seat <N>            → close seat N
PLAYER  BUSTED seat <N>           → bust player at seat N
LEVEL   <N>                       → advance to level N
CLOCK   START                     → start tournament clock
CLOCK   PAUSE                     → pause tournament clock
BLINDS  <SB>/<BB> [ante <ANTE>]   → set current blind level
TABLE   <N> SEAT <M>              → assign new player to table N seat M
```

### Flow

```
Dealer speech → microphone/audio file
    │
    ▼
audio_capture.py → raw audio bytes
    │
    ▼
stt_provider.py → text string
    │
    ▼
parser.py → structured command
    │
    ▼
validator.py → check against current table/tournament state
    │
    ├── invalid → return error to operator
    │
    ▼ valid
submit_event.py → calls existing API endpoint or service
    │
    ▼
event_logs + projection update + WS broadcast
```

### API Endpoints

```python
POST   /voice-gateway/transcribe             # Upload audio → submit event
POST   /voice-gateway/command                 # Submit text command directly (for testing)
GET    /voice-gateway/pending-approvals       # Commands needing operator approval
POST   /voice-gateway/approve/{approval_id}   # Approve queued command
POST   /voice-gateway/reject/{approval_id}    # Reject queued command
```

### Acceptance Criteria

```
[ ] POST /voice-gateway/command { text: "STACK seat 4 185000" } → STACK_UPDATED event
[ ] POST /voice-gateway/command { text: "POT 42000" } → POT_UPDATE event
[ ] POST /voice-gateway/command { text: "PLAYER BUSTED seat 3" } → PLAYER_BUSTED event
[ ] POST /voice-gateway/command { text: "CLOCK START" } → CLOCK_STARTED event
[ ] Invalid command "BLINDS XYZ" → 400 with parse error
[ ] Command referencing nonexistent seat → 400 validation error
[ ] Stack-sensitive commands (STACK, POT) go to approval queue by default
```

---

## Slice 10 — NFC Scan System

**What it proves:** NFC scan → player identity → event flow → UI update.

### New Files

```
backend/app/models/nfc_card.py
backend/app/schemas/nfc.py
backend/app/services/nfc.py
backend/app/api/v1/nfc.py
backend/tests/test_nfc.py
```

### DB Tables (Alembic migration 0008)

```sql
CREATE TABLE nfc_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_uid VARCHAR(100) UNIQUE NOT NULL,
    player_id UUID REFERENCES players(id),
    player_name VARCHAR(200),
    is_active BOOLEAN NOT NULL DEFAULT true,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_scanned_at TIMESTAMPTZ
);
```

### Flow

```
NFC reader scans card
    │
    ▼
POST /api/v1/nfc/scan { reader_id, card_uid, table_id, seat_number }
    │
    ▼
nfc_service.py:
  - Validate reader is registered
  - Look up player by card_uid
  - If check-in: mark player checked in for tournament
  - If seat confirmation: verify player at correct seat
  - If movement: add to pending confirmation
    │
    ▼
PLAYER_SCAN event logged
    │
    ▼
WS broadcast → operator UI updates
```

### API Endpoints

```python
POST   /api/v1/nfc/cards                        # Register NFC card to player
GET    /api/v1/nfc/cards                         # List registered cards
POST   /api/v1/nfc/scan                          # Process NFC scan
DELETE /api/v1/nfc/cards/{id}                    # Deactivate card
```

### Acceptance Criteria

```
[ ] POST /api/v1/nfc/cards { card_uid: "ABC123", player_id } → registered
[ ] POST /api/v1/nfc/scan { card_uid: "ABC123", table_id, seat_number } → PLAYER_SCAN event
[ ] Scan with unknown card_uid → 404
[ ] Scan at wrong seat → warning logged, operator can override
[ ] event_logs has PLAYER_SCAN after successful scan
```

---

## Slice 11 — CMS

**What it proves:** Player profiles, tournament history, player balances, permissions. Built last — reads from same DB.

### New Files

```
backend/app/models/cms.py
backend/app/schemas/cms.py
backend/app/services/cms.py
backend/app/api/v1/cms.py
```

### DB Tables (Alembic migration 0009)

```sql
-- Extends players with CMS-specific fields
ALTER TABLE players ADD COLUMN membership_tier VARCHAR(20) DEFAULT 'standard';
ALTER TABLE players ADD COLUMN total_buyins DECIMAL(12,2) DEFAULT 0;
ALTER TABLE players ADD COLUMN total_rebuys DECIMAL(12,2) DEFAULT 0;
ALTER TABLE players ADD COLUMN total_winnings DECIMAL(12,2) DEFAULT 0;
ALTER TABLE players ADD COLUMN games_played INT DEFAULT 0;
ALTER TABLE players ADD COLUMN last_game_date TIMESTAMPTZ;

CREATE TABLE cms_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type VARCHAR(50) NOT NULL,  -- news, banner, rule, announcement
    title VARCHAR(200),
    body TEXT,
    is_published BOOLEAN DEFAULT false,
    created_by UUID REFERENCES players(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE player_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    note TEXT,
    created_by UUID REFERENCES players(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### API Endpoints

```python
# Player profiles (extend existing players endpoint)
GET    /api/v1/players/{id}/stats              # Tournament history, winnings, games played
GET    /api/v1/players/{id}/history            # Tournament results for this player

# CMS content
GET    /api/v1/cms/content                     # List published content
POST   /api/v1/cms/content                     # Create content item (admin)
PATCH  /api/v1/cms/content/{id}                # Update content
DELETE /api/v1/cms/content/{id}                # Delete content

# Permissions
POST   /api/v1/players/{id}/role               # Change player role (admin only)
```

### Acceptance Criteria

```
[ ] GET /api/v1/players/{id}/stats returns { games_played, total_winnings, ... }
[ ] POST /api/v1/cms/content { type: "news", title, body } → created
[ ] CMS content has publish/unpublish toggle
[ ] Tournament results auto-update player stats
```

---

## File Manifest (Complete Project)

### New Files Created

```
backend/app/models/
├── event_log.py
├── tournament.py
├── tournament_table.py
├── seat_assignment.py
├── blind_level.py
├── tournament_clock.py
├── balancing.py
├── feature_table.py
├── nfc_card.py
├── cms.py

backend/app/schemas/
├── event_log.py
├── tournament.py
├── table.py
├── seat.py
├── movement.py
├── clock.py
├── balancing.py
├── feature_table.py
├── nfc.py
├── cms.py

backend/app/services/
├── event_log.py
├── tournament.py
├── table.py
├── seat.py
├── movement.py
├── clock.py
├── balancing/
│   ├── __init__.py
│   ├── rules.py
│   └── service.py
├── feature_table.py
├── nfc.py
├── cms.py

backend/app/projections/
├── __init__.py
├── tournament_state.py
├── seating_state.py
├── overlay_state.py
├── feature_table_state.py

backend/app/realtime/
├── __init__.py
├── manager.py
├── router.py
├── broadcaster.py

backend/app/api/v1/
├── event_logs.py
├── tournaments.py
├── tables.py
├── seats.py
├── movement.py
├── clock.py
├── balancing.py
├── projections.py
├── feature_table.py
├── nfc.py
├── cms.py

backend/app/overlays/
├── __init__.py
├── router.py
├── templates/
│   ├── clock.html
│   ├── stacks.html
│   ├── break_screen.html
│   ├── balancing_alert.html
│   └── feature_table.html
└── static/
    ├── overlay.js
    └── overlay.css

backend/voice_gateway/
├── __init__.py
├── audio_capture.py
├── stt_provider.py
├── parser.py
├── validator.py
├── router.py
└── submit_event.py

backend/alembic/versions/
├── 0003_concept_mtt_tournaments.py
├── 0004_concept_mtt_tables.py
├── 0005_concept_mtt_movement.py
├── 0006_concept_mtt_balancing.py
├── 0007_concept_mtt_feature_table.py
├── 0008_concept_mtt_nfc.py
└── 0009_concept_mtt_cms.py

backend/tests/
├── test_event_log.py
├── test_tournament.py
├── test_tables.py
├── test_seats.py
├── test_movement.py
├── test_clock.py
├── test_balancing.py
├── test_feature_table.py
├── test_nfc.py
├── test_cms.py
├── test_websocket.py
├── test_voice_gateway.py
├── test_overlays.py
├── test_projections.py
```

### Modified Files

```
backend/app/__init__.py        # No change needed
backend/app/main.py            # Register all new routers + mount overlays
backend/app/models/__init__.py # Import all new models
backend/app/schemas/__init__.py # Import all new schemas
ARCHITECTURE.md                # Add all new tables, slices, file tree
```

### NO CHANGE To

```
backend/app/core/config.py     # Settings untouched
backend/app/core/database.py   # Base class unchanged
backend/app/core/security.py   # Auth untouched (reused for new endpoints)
backend/app/core/logging.py    # Unchanged
backend/app/services/broadcast.py  # Broadcast engine unchanged
backend/app/services/template_engine.py  # Unchanged
backend/app/services/message_provider.py # Unchanged
backend/app/models/player.py   # Unchanged
backend/app/models/broadcast.py # Unchanged
frontend/                      # Not touched (Tauri app replaces it for tournament ops)
```

---

## Verification Strategy

### Per-Slice: Automated Tests

Every slice produces:
1. **Unit tests** for service layer methods (pytest, async)
2. **Integration tests** hitting API endpoints (httpx AsyncClient)
3. **Event log assertion** — verify correct events created

### Run tests after every slice

```bash
docker compose exec backend pytest -v -k "test_tournament or test_seats"
```

### Manual Verification (every 3 slices)

```bash
# Full integration flow
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/api/v1/tournaments -H 'Content-Type: application/json' -d '{"name":"Test MTT"}'
# ... chain through all endpoints
```

---

## Risks & Decisions

| Risk | Mitigation |
|------|-----------|
| SQLite test DB doesn't support JSONB | Use `sqlalchemy.JSON` instead of `postgresql.JSONB` in models. PostgreSQL JSONB for prod. |
| WebSocket tests hang | Use `pytest-asyncio` with `event_loop` fixture. Set WS timeout. |
| OBS overlay HTML complexity | Start with one overlay (clock) in Slice 7. Extend after proven. |
| Dealer voice STT dependency | Console mock v1. Wire to real STT as deployment step. |
| NFC reader hardware not available | Mock NFC reader in tests. Scan API works with POST directly. |
| Tauri app build time | Defer Tauri building. Use FastAPI static SPA + WS HTML pages for operator dashboard in v1. |
| Migration conflicts with existing alembic | Each slice gets its own migration revision. Use `down_revision` chain. |
