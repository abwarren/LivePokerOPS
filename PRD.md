# LivePokerOPS — Product Requirements Document

> **Version:** 1.0.0
> **Updated:** 2026-07-22

---

## 1. Product Vision

**LivePokerOPS** is an API-first Poker Club Operating System that automates the operational admin of running a live poker club — tournament announcements, RSVPs, player management, attendance, league points, and financial tracking.

The immediate goal is to replace the current manual workflow (WhatsApp announcements + Google Forms RSVPs) with an automated system that preserves the existing player experience while eliminating admin overhead for club organisers.

Long-term, LivePokerOPS should be deployable as a multi-club SaaS platform.

---

## 2. Current Club Scale

- ~300 active players
- ~1,000 players in database
- ~4 tournaments per week
- Tournament announcements via WhatsApp group
- RSVPs collected via Google Forms
- Manual player list updates in announcement messages

---

## 3. Target Users

| Role | Description |
|------|-------------|
| Club Admin (Gareth/Jade) | Creates tournaments, sends announcements, tracks RSVPs, posts results |
| Player | Receives announcements, RSVPs, checks in, views standings |

---

## 4. Functional Requirements

### 4.1 Player Management
- Store player profiles (name, nickname, email, phone)
- Search and filter players
- Player activity status (active/inactive)
- Admin role assignment

### 4.2 Tournament Management
- Create/edit/cancel tournaments
- Tournament types: Freeroll, Freezeout, Rebuy, Turbo, Satellites
- Status lifecycle: Draft → Announced → Confirmed → In Progress → Completed → Cancelled
- Date, time, venue, buy-in, structure
- Registration deadline
- Capacity limits

### 4.3 RSVP System
- Players RSVP for tournaments
- Waitlist when capacity reached
- Player confirmation deadline
- Late registration handling
- Prevent duplicate RSVPs
- Attendance tracking (showed vs no-show)

### 4.4 WhatsApp Broadcast Engine
- Announcement templates with variable substitution (player count, names, date/time)
- Tournament reminder messages
- Game-on / update messages
- Final table posts
- Results and recap messages
- Template preview before sending
- Delivery history per message
- Message scheduling (send at specific time)

### 4.5 Attendance & Check-in
- Check-in at venue (admin or self-service)
- No-show recording
- Attendance history per player
- Stats: attendance rate, reliability score

### 4.6 League & Points
- Points calculation based on finishing position
- Season management
- Leaderboard / standings table
- Historical league winners
- Points for attendance, final table, wins

### 4.7 Financial Tracking
- Buy-in collection tracking
- Rebuy tracking
- Prize pool calculation
- Sponsor contribution tracking
- Per-tournament financial summary

### 4.8 Tournament Archive
- Historical results with finishing positions
- Searchable by player, date, tournament type
- Analytics: average attendance, most popular formats
- Player head-to-head history

### 4.9 Analytics Dashboard
- Player growth (new vs returning)
- Attendance trends
- Revenue tracking
- Popular tournament formats
- Player retention metrics

---

## 5. Non-Functional Requirements

### 5.1 Architecture
- API-first design
- Clean Architecture / Vertical Slicing
- Twelve-Factor App
- Single-tenant v1 (multi-tenant ready)

### 5.2 Tech Stack
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL + Alembic
- **Frontend:** Next.js + React + Tailwind (scaffolded but deferred)
- **Infrastructure:** Docker + Docker Compose
- **Auth:** JWT with refresh tokens (httpOnly cookies)
- **Messaging:** WhatsApp abstraction layer (console logger v1 → full API)

### 5.3 Quality
- Every feature: unit + integration + API tests
- Pytest + Playwright (frontend)
- Ruff linting + formatting
- Small commits, descriptive messages

### 5.4 Security
- Passwords hashed with bcrypt
- JWT access tokens (30min expiry)
- Refresh tokens (7 day expiry)
- Role-based access (admin, player)
- Input validation on all endpoints

---

## 6. Development Approach

### Vertical Slicing
Every feature is built as a complete vertical slice through all layers:
Database → Models → Schemas → API → Tests → Docs

### Tracer Bullet
The first slice proves the full stack works end-to-end before any feature development begins.

### Build Order
1. **Project Bootstrap** — FastAPI + PostgreSQL + Auth + Docker + Tests
2. **WhatsApp Automation Engine** — tournament announcement + RSVP templates, player list generation
3. Player Management — CRUD + player profiles
4. Tournament Management — CRUD + lifecycle
5. RSVP System — capacity + waitlist + confirmation
6. WhatsApp Broadcast Engine — full scheduled messaging
7. Attendance & Check-in
8. League & Points
9. Financial Tracking
10. Analytics Dashboard

---

## 7. Current WhatsApp Workflow (To Be Automated)

Reference: Gareth Poker WhatsApp group messages (as of July 2026)

### Pre-Tournament Flow
1. Admin posts initial announcement (date/time/format)
2. Players confirm in-thread or via Google Form
3. Admin posts player list updates as names come in
4. When minimum threshold reached, admin announces "GAME ON"
5. Final player list posted before start

### During Tournament
6. Updates posted (table count, late registration window)
7. Side game announcements (ultra turbo, rebuy)
8. Final table chip counts posted
9. Results and winner announcement

### Manual Steps to Automate
- [ ] Player list aggregation (currently copy-pasted from Google Forms)
- [ ] Status updates (X players confirmed / Y needed)
- [ ] "GAME ON" threshold notification
- [ ] Final table chip count posts (requires manual entry)
- [ ] Results announcements

---

## 8. Glossary

| Term | Definition |
|------|------------|
| Freeroll | Free-entry tournament with sponsored prizes |
| Freezeout | No rebuys or add-ons |
| Rebuy | Tournament allowing additional buy-ins |
| Satellite | Tournament where prizes are seats to another event |
| Turbo | Fast blind structure |
| Late Registration | Period after tournament start where players can still enter |
| Add-on | Optional extra chips at a set point |
