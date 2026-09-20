# FlyRank — Embeddable Widget & Lead-Capture Platform

A production-ready backend system that allows customers to create embeddable
widgets via a single `<script>` tag, handle public submissions securely,
enrich data with geo/IP info, and provide an owner dashboard for analytics.

Built as the **FlyRank Backend Track Capstone Project**.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Browser (Visitor)                       │
│  ┌─────────────┐    ┌──────────────┐                          │
│  │  <script>   │───▶│  Widget JS   │ (cached, versioned)      │
│  │  embed tag  │    │  (rendered)  │                          │
│  └─────────────┘    └──────┬───────┘                          │
│                            │ POST /api/v1/public/submit        │
│                            ▼                                   │
├──────────────────────────────────────────────────────────────┤
│                     FastAPI Application                        │
│                                                               │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐    │
│  │  Auth API   │  │ Widget CRUD │  │ Public Submission    │    │
│  │  /auth/*    │  │ /widgets/*  │  │ /public/submit/{id}  │    │
│  └─────┬──────┘  └─────┬──────┘  └──────────┬───────────┘    │
│        │               │                     │                │
│        ▼               ▼                     ▼                │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              Service Layer                            │     │
│  │  • Geo Enrichment (ip-api → ipinfo → none)           │     │
│  │  • Spam Protection (honeypot + rate limit)           │     │
│  │  • Email (Mailpit) / Webhook (fire-and-forget)       │     │
│  │  • Snippet Generation & Cached JS Delivery           │     │
│  └──────────────────────┬──────────────────────────────┘     │
│                         ▼                                     │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              PostgreSQL (multi-tenant)               │     │
│  │  tenants · users · widgets · submissions             │     │
│  │  Row-level isolation via tenant_id on every table     │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### Multi-Tenant Isolation

Every tenant-scoped table carries a `tenant_id` foreign key. All queries
filter by `tenant_id` derived from the authenticated user's session —
Tenant A can never read, write, or query Tenant B's data.

### Security Layers

| Layer            | Mechanism                                              |
|-----------------|-------------------------------------------------------|
| CORS            | Widget-specific origin allowlist; dashboard API separate |
| Rate Limiting   | Per-IP + per-widget limits via SlowAPI (429 on burst)  |
| Input Validation| Pydantic strict mode; max payload size; field allowlist |
| Spam Protection | Honeypot field + timing check + rate limit             |
| Geo Enrichment  | Fallback chain: ip-api → ipinfo → store without geo   |
| Side Effects    | Email/webhook failures never block submission success |

---

## Tech Stack ($0 Cost)

| Component       | Technology                          |
|----------------|-------------------------------------|
| Language        | Python 3.11+                        |
| Framework       | FastAPI                             |
| Database        | PostgreSQL 16 (Docker)              |
| ORM             | SQLAlchemy 2.0                      |
| Validation      | Pydantic v2                         |
| Rate Limiting   | SlowAPI                             |
| Email Testing   | Mailpit (Docker)                     |
| Geo Enrichment  | ip-api.com (free) + ipinfo.io (free)|
| Containerization| Docker Compose                      |

---

## Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local dev without Docker)

### Quick Start

```bash
# 1. Clone & enter
cd flyrank-backend

# 2. Copy env
cp .env.example .env

# 3. Start everything (Postgres + Mailpit + API)
docker compose up --build

# 4. API docs at:
open http://localhost:8000/docs

# 5. Mailpit UI at:
open http://localhost:8025
```

### Local Dev (without Docker for the API)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start just the database + mailpit
docker compose up db mailpit -d

# Run migrations
python -m app.db.init_db

# Start the API
uvicorn app.main:app --reload --port 8000
```

---

## API Overview

### Authentication
| Method | Path                  | Description              |
|--------|-----------------------|--------------------------|
| POST   | /api/v1/auth/register | Create a new tenant+user |
| POST   | /api/v1/auth/login    | Get JWT access token     |
| GET    | /api/v1/auth/me       | Current user info        |

### Widget Management (authenticated, tenant-isolated)
| Method | Path                       | Description                  |
|--------|----------------------------|------------------------------|
| POST   | /api/v1/widgets            | Create widget                |
| GET    | /api/v1/widgets            | List own widgets             |
| GET    | /api/v1/widgets/{id}       | Get single widget            |
| PUT    | /api/v1/widgets/{id}       | Update widget                |
| DELETE | /api/v1/widgets/{id}       | Delete widget                |
| GET    | /api/v1/widgets/{id}/snippet | Get embed `<script>` tag   |

### Public Submission (no auth, CORS-open, rate-limited)
| Method | Path                                | Description                    |
|--------|-------------------------------------|--------------------------------|
| GET    | /api/v1/public/widget/{id}/config   | Fetch widget config (cached)   |
| GET    | /api/v1/public/widget/{id}/script   | Fetch widget JS (cached)       |
| POST   | /api/v1/public/submit/{id}          | Submit form data               |
| OPTIONS| /api/v1/public/submit/{id}          | CORS preflight                 |

### Owner Dashboard (authenticated, tenant-isolated)
| Method | Path                              | Description                    |
|--------|-----------------------------------|--------------------------------|
| GET    | /api/v1/dashboard/stats           | Aggregate stats               |
| GET    | /api/v1/dashboard/widgets/{id}/submissions | Per-widget submissions |
| GET    | /api/v1/dashboard/submissions     | Paginated submission list      |

---

## Project Structure

```
flyrank-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory, middleware, routers
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic Settings (env loading)
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   ├── security.py          # JWT, password hashing
│   │   ├── deps.py              # Dependency injection (current user, db)
│   │   └── rate_limit.py        # SlowAPI limiter setup
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py              # Declarative base + mixins
│   │   ├── tenant.py            # Tenant + User
│   │   ├── widget.py            # Widget
│   │   └── submission.py        # Submission
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── widget.py
│   │   ├── submission.py
│   │   └── dashboard.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── widgets.py
│   │   ├── public.py            # Public submission + delivery
│   │   └── dashboard.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── geo.py                # Geo enrichment fallback chain
│   │   ├── email_svc.py          # Email (Mailpit SMTP)
│   │   ├── webhook.py            # Webhook fire-and-forget
│   │   ├── spam.py               # Honeypot + timing checks
│   │   └── snippet.py            # <script> tag generation
│   └── db/
│       ├── __init__.py
│       └── init_db.py            # Table creation + seed
├── static/
│   └── widget.js                 # Versioned widget bundle
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_widgets.py
│   └── test_public.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── capstone.yaml
├── EVIDENCE.md
├── BUILDLOG.md
└── README.md
```

---

## License

MIT — Capstone project, educational use.
