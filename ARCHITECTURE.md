# LivePokerOPS — Architecture Document

> **Last update:** 2026-07-22 — Integrated ConceptPokerMTTpro (11 vertical slices)

---

## End Goal

A single deployable Docker Compose stack running a multi-module Poker Club OS:
Player Management → Tournaments → RSVP → WhatsApp Broadcast → Attendance → League/Points → Financials → Archive → Analytics.

1 VPS, 1 PostgreSQL, 1 FastAPI, 1 Next.js frontend. The system the club runs on, not alongside.

---

## Architecture Decision Log

| # | Decision | Rationale | Alternatives Considered |
|---|----------|-----------|------------------------|
| D1 | Single-tenant v1, club_id columns on high-cardinality tables | YAGNI — no second club exists yet. Adding FK later on 1K rows is trivial | Multi-tenant from day 1 (rejected: over-engineering for zero clubs) |
| D2 | JWT + refresh tokens (httpOnly cookies) | Best practice, secure, logout works, phone-login-friendly | Simple Bearer tokens (rejected: no logout, less secure) |
| D3 | Roles: `admin` + `player` v1 | Covers actual club operations. Dealer/TD can be added later | More granular (rejected: YAGNI) |
| D4 | Full Next.js frontend scaffolded now | Slice 4 (RSVP) and Slice 5 (WhatsApp) need real UI. Rewriting from Jinja2 is waste | Jinja2/vanilla JS (rejected: tech-debt within 3 slices) |
| D5 | WhatsApp abstraction layer (SMS fallback) | Don't block on Meta approval; ship with console logging, wire real API later | Block on Cloud API (rejected: unknown approval timeline) |
| D6 | Clean start — no data migration | No existing structured data to migrate | Google Sheets import (rejected: one-off, not architecturally interesting) |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Docker Compose (single host, single network)                │
│                                                              │
│  ┌──────────────┐    :8000    ┌──────────────────┐          │
│  │  Next.js App  │ ────────── │  FastAPI Server   │          │
│  │  (frontend/)  │ ◄───────── │  (backend/)       │          │
│  │  :3000        │    REST    │  :8000             │          │
│  └──────────────┘            └────────┬───────────┘          │
│                                        │                     │
│                                        │ SQLAlchemy          │
│                                        ▼                     │
│                              ┌──────────────────┐           │
│                              │  PostgreSQL 16   │           │
│                              │  :5432            │           │
│                              └──────────────────┘           │
│                                                              │
│  ┌────────────────────────────────────────────────┐          │
│  │  WhatsApp Abstraction Layer                     │          │
│  │  (console logger → Twilio → Meta Cloud API)    │          │
│  └────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema (Initial — grows per slice)

```
players
├── id (UUID, PK)
├── club_id (UUID, nullable — future multi-tenant)
├── first_name (text, not null)
├── last_name (text, not null)
├── nickname (text, unique)
├── email (text, unique, not null)
├── phone (text, unique)
├── avatar_url (text)
├── is_active (boolean, default true)
├── is_admin (boolean, default false)
├── notes (text)
├── created_at (timestamptz)
└── updated_at (timestamptz)

auth
├── id (UUID, PK)
├── player_id (UUID, FK → players.id, unique)
├── password_hash (text, not null)
├── refresh_token_hash (text, nullable)
├── refresh_token_expires_at (timestamptz, nullable)
├── last_login_at (timestamptz)
├── created_at (timestamptz)
└── updated_at (timestamptz)
```

---

## Vertical Slice Map

| Slice | What | Proves | Depends On | Est. |
|-------|------|--------|------------|------|
| 1 | Project Bootstrap | Full stack works: API ↔ DB ↔ Auth ↔ Health | Nothing | ~1h |
| 2 | Player Management | CRUD + search + validation | Slice 1 | ~1.5h |
| 3 | Tournament Management | Status lifecycle + scheduling | Slice 1 | ~1.5h |
| 4 | RSVP System | Capacity + waitlist + attendance | Slice 2 + 3 | ~2h |
| 5 | WhatsApp Broadcast Engine | Message delivery abstraction | Slice 2 | ~2h |
| 6 | Attendance & Check-in | Check-in + no-show tracking | Slice 2 + 4 | ~1.5h |
| 7 | League & Points | Points calc + standings + seasons | Slice 2 + 3 + 4 | ~2h |
| 8 | Financial Tracking | Buy-ins + rebuys + prize pools | Slice 2 + 3 | ~2h |
| 9 | Tournament Archive | History + search + analytics | Slice 3 + 4 + 8 | ~1.5h |
| 10 | Analytics Dashboard | KPIs + trends + growth metrics | Slice 2-9 | ~2h |

---

## Repository Structure

```
LivePokerOPS/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── players.py
│   │   │   │   ├── tournaments.py
│   │   │   │   ├── rsvps.py
│   │   │   │   ├── broadcast.py
│   │   │   │   ├── attendance.py
│   │   │   │   ├── league.py
│   │   │   │   ├── finances.py
│   │   │   │   └── analytics.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── database.py
│   │   │   └── logging.py
│   │   ├── models/
│   │   │   ├── player.py
│   │   │   ├── tournament.py
│   │   │   ├── rsvp.py
│   │   │   ├── attendance.py
│   │   │   ├── league.py
│   │   │   └── broadcast.py
│   │   ├── schemas/
│   │   │   ├── player.py
│   │   │   ├── tournament.py
│   │   │   ├── rsvp.py
│   │   │   ├── auth.py
│   │   │   └── ... (per slice)
│   │   ├── services/
│   │   │   ├── player.py
│   │   │   ├── tournament.py
│   │   │   ├── rsvp.py
│   │   │   ├── broadcast.py
│   │   │   ├── attendance.py
│   │   │   ├── league.py
│   │   │   └── finance.py
│   │   ├── main.py
│   │   └── health.py
│   ├── alembic/
│   │   ├── env.py
│   │   ├── versions/
│   │   └── alembic.ini
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   ├── test_auth.py
│   │   ├── test_players.py
│   │   └── ... (per slice)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── login/
│   │   │   ├── players/
│   │   │   ├── tournaments/
│   │   │   └── ... (per slice)
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   └── ... (per slice)
│   │   ├── lib/
│   │   │   └── api.ts
│   │   └── types/
│   ├── Dockerfile
│   ├── next.config.js
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── docker-compose.yml
├── docker-compose.override.yml
├── .env.example
├── .gitignore
├── Makefile
└── ARCHITECTURE.md
```
