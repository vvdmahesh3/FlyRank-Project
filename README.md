# Embeddable Widget & Lead-Capture Platform

> A production-style, multi-tenant backend platform that lets customers create embeddable lead-capture widgets and deploy them on external websites using a single `<script>` tag.

**Author:** Peruri Veera Venkata Durga Mahesh
**Lane:** Backend Engineering Track
**Repository:** [srinivascl167/Embeddable-Widget-Lead-Capture-Platform](https://github.com/srinivascl167/Embeddable-Widget-Lead-Capture-Platform)
**Date:** September 2026
**License:** MIT

---

## Table of Contents

- [Abstract](#abstract)
- [Problem Framing](#problem-framing)
- [Data Safety & Tenant Isolation](#data-safety--tenant-isolation)
- [Baseline & Improvements](#baseline--improvements)
- [Architecture](#architecture)
- [Security & Reliability](#security--reliability)
- [Geo-Enrichment Fallback](#geo-enrichment-fallback)
- [Widget Delivery & Caching](#widget-delivery--caching)
- [Idempotency](#idempotency)
- [Background Processing](#background-processing)
- [API Surface](#api-surface)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Demo Credentials](#demo-credentials)
- [Testing](#testing)
- [Evaluator Acceptance Probes](#evaluator-acceptance-probes)
- [Design Decisions & Trade-offs](#design-decisions--trade-offs)
- [Five-Minute Demo Outline](#five-minute-demo-outline)
- [Key Engineering Outcomes](#key-engineering-outcomes)
- [Project Summaries](#project-summaries)
- [Acknowledgments](#acknowledgments)
- [License](#license)

---

## Abstract

This project implements a production-style, multi-tenant backend platform that allows customers to create embeddable lead-capture widgets and deploy them on external websites using a single `<script>` tag.

The system handles the complete lead-capture lifecycle, including:

- Authenticated widget management
- Secure cross-origin submissions
- Request validation
- Rate limiting
- Spam protection
- IP-based geo enrichment
- Idempotent submissions
- Asynchronous notification processing
- Retry handling
- Tenant-scoped analytics

The backend is built with **Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Docker, and Pytest**. The architecture focuses on clean separation of concerns, secure tenant isolation, reliable background processing, real database persistence, reproducible local deployment, and evaluator-friendly acceptance probes.

The project was developed as part of the **FlyRank Backend Engineering Track Capstone**.

---

## Problem Framing

The project addresses the problem of collecting leads from external websites without requiring every customer to build and maintain their own backend form-processing infrastructure.

A customer should be able to create a widget, receive a generated embed snippet, place that snippet on their website, and start receiving leads through a secure backend.

| Aspect | Description |
|---|---|
| **Unit of analysis** | A tenant-owned widget and the lead submissions generated through that widget |
| **Input** | Public form submissions originating from customer websites |
| **Output** | Persisted lead records with validation, optional geo information, and asynchronous notification processing |
| **Human action** | Tenant owners create and manage widgets, embed them on their websites, and review captured submissions through dashboard APIs |
| **Primary engineering challenge** | Handle public traffic securely while keeping tenant data isolated and ensuring that unreliable side effects do not cause lead loss |
| **Why this architecture** | The workflow combines authentication, CORS, validation, rate limiting, persistence, geo enrichment, asynchronous processing, retries, and idempotency — separated into dedicated application layers |

---

## Data Safety & Tenant Isolation

The platform uses PostgreSQL as the primary persistence layer and enforces tenant isolation at the backend level.

### Authentication

Authenticated owner endpoints use JWT bearer authentication.

- Passwords are stored as hashes.
- Invalid or expired JWTs are rejected.
- Protected widget and dashboard operations require authentication.
- Tenant ownership is determined on the backend.

### Tenant Isolation

Tenant-specific resources are never filtered only at the frontend. Widgets and submissions are queried using the authenticated tenant context, ensuring that one tenant cannot access another tenant's data.

```text
Tenant / User
      │
      ├── Widgets
      │      │
      │      └── Submissions
      │
      └── Dashboard Data
```

### Request Safety

The public submission endpoint applies multiple protection layers:

- Pydantic request validation
- Required field validation
- Field length restrictions
- Unknown-field rejection
- Maximum request body size of **16 KiB**
- Per-IP/per-widget rate limiting
- Honeypot spam detection
- CORS origin restrictions
- Idempotency protection

### Secret Management

Sensitive configuration is loaded through environment variables:

```text
DATABASE_URL
JWT_SECRET_KEY
CORS_ALLOWED_ORIGINS
GEO_PROVIDER_A_URL
GEO_PROVIDER_B_URL
```

The `.env` file is excluded from Git and `.env.example` contains safe configuration placeholders.

> The application does not use an AI API at runtime.

---

## Baseline & Improvements

### Baseline

A simple lead-capture implementation could expose a public endpoint that accepts form data, stores it directly, and sends a notification inside the same HTTP request.

While functional, that approach creates several problems:

- Duplicate submissions during retries
- Notification failures affecting lead capture
- No protection against abusive public traffic
- Potential cross-tenant data access
- No controlled CORS policy
- No fallback when an external geo service fails
- Tight coupling between persistence and external side effects

### Improvements

This project improves that baseline through a layered backend architecture:

- JWT-based authentication
- Tenant-isolated widget and submission access
- Secure CORS configuration
- Boundary-level request validation
- Payload-size protection
- IP/widget rate limiting
- Honeypot spam protection
- Deterministic geo-provider fallback
- PostgreSQL persistence
- Idempotency keys
- Durable background jobs
- Retry with exponential backoff
- Versioned widget delivery
- Cached public widget configuration
- Tenant-scoped dashboard analytics

---

## Architecture

The application follows a layered FastAPI architecture.

```text
                         ┌──────────────────────┐
                         │     Owner Browser    │
                         │    JWT Authenticated │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      FastAPI API     │
                         │                      │
                         │ Auth                 │
                         │ Widget Management    │
                         │ Public Submission    │
                         │ Dashboard            │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
               PostgreSQL      Public Widget     Dashboard
                    │               │
                    │               │
                    │          Customer Website
                    │          Second Origin
                    │
                    ▼
             Background Jobs
                    │
                    ▼
             Worker Process
                    │
                    ▼
             Notification
```

### Customer Website Flow

```text
Customer Website
       │
       │ <script src="/widget.v1.js?id=...">
       ▼
Versioned Widget
       │
       ├── GET public configuration
       │
       └── POST lead submission
                    │
                    ▼
              Validation
                    │
                    ▼
             Rate Limiting
                    │
                    ▼
             Honeypot Check
                    │
                    ▼
           Geo Enrichment
                    │
                    ▼
          Persist Submission
                    │
                    ▼
          Queue Background Job
                    │
                    ▼
               Worker
                    │
             ┌──────┴──────┐
             ▼             ▼
          Success        Failure
                            │
                       Retry + Backoff
```

### Layer Responsibilities

| Layer | Responsibility |
|---|---|
| **API** | HTTP routing, authentication, CORS and request handling |
| **Schemas** | Request/response contracts and validation |
| **Services** | Business logic, submission workflow and external integrations |
| **Repositories** | Tenant-scoped database operations |
| **Models** | PostgreSQL domain entities |
| **Migrations** | Version-controlled database schema |
| **Workers** | Background processing and retries |
| **Widget** | Embeddable customer-facing form |
| **Dashboard** | Tenant-scoped analytics and submissions |

---

## Security & Reliability

### Authentication

Protected endpoints require JWT bearer authentication.

```text
Unauthenticated request
        │
        ▼
     401 Error
```

Authenticated users can access only resources belonging to their tenant.

### Tenant Isolation

Tenant ownership is enforced in backend queries.

```text
Tenant A
   │
   ├── Widget A
   └── Submissions A

Tenant B
   │
   ├── Widget B
   └── Submissions B

Tenant A ──X──> Tenant B data
Tenant B ──X──> Tenant A data
```

### Public Endpoint Protection

| Layer | Mechanism |
|---|---|
| **CORS** | Configured customer-origin allowlist |
| **Validation** | Pydantic schemas |
| **Payload limit** | 16 KiB maximum |
| **Rate limiting** | IP + widget based |
| **Spam protection** | Honeypot field |
| **Idempotency** | `Idempotency-Key` |
| **Geo enrichment** | Provider A → Provider B → no geo |

### Reliable Side Effects

Lead persistence is intentionally independent of notification delivery.

```text
HTTP Request
     │
     ▼
Validate
     │
     ▼
Protect
     │
     ▼
Geo Enrichment
     │
     ▼
Store Lead
     │
     └──────────────► Queue Job
                           │
                           ▼
                        Worker
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
               Success           Failure
                                      │
                               Retry + Backoff
                                      │
                               Max Attempts
                                      │
                                      ▼
                                   Failed
```

If notification processing fails, the lead remains stored. This prevents external side-effect failures from causing lead loss.

---

## Geo-Enrichment Fallback

The platform supports a deterministic geo-enrichment fallback chain.

```text
                Provider A
                    │
             ┌──────┴──────┐
             │             │
          Success        Failure
             │             │
             ▼             ▼
        Store Geo      Provider B
                           │
                    ┌──────┴──────┐
                    │             │
                 Success        Failure
                    │             │
                    ▼             ▼
               Store Geo      Store Lead
                              Without Geo
```

The application supports three provider modes:

- `mock_up` — provider succeeds
- `mock_down` — provider intentionally fails
- `real` — configured external provider

This makes the fallback behavior reproducible during development and evaluation without depending completely on external network availability.

### Fallback Guarantees

If Provider A fails:

```text
Provider A → Provider B
```

If both providers fail:

```text
Provider A → Provider B → Store Lead Without Geo
```

The lead-capture operation continues even when geo enrichment is unavailable.

---

## Widget Delivery & Caching

The platform provides a versioned JavaScript widget that can be embedded into an external website with a single script tag.

```html
<script src="http://localhost:8000/widget.v1.js?id=YOUR_WIDGET_ID"></script>
```

### Widget Delivery Features

- Versioned JavaScript assets
- Long-lived cache headers
- Immutable asset caching
- Cached public widget configuration
- Widget version increments when configuration changes
- Backward-compatible versioning strategy

The versioned architecture allows a future implementation to be introduced as `widget.v2.js` without immediately breaking existing `widget.v1.js` integrations.

---

## Idempotency

Public clients can provide an `Idempotency-Key` header.

```http
Idempotency-Key: demo-lead-001
```

For the same widget and idempotency key, repeated requests do not create duplicate leads.

```text
First Request
     │
     ▼
Create Submission
     │
     ▼
Store Idempotency Key

Second Request
     │
     ▼
Same Widget + Same Key
     │
     ▼
Return Existing Submission
```

The database also contains a uniqueness constraint on `(widget_id, idempotency_key)`, providing an additional safeguard against concurrent duplicate submissions.

---

## Background Processing

Notification processing is implemented using a PostgreSQL-backed durable job queue. Instead of requiring the HTTP request to complete the notification operation:

```text
API
 │
 ├── Store Lead
 │
 └── Create Job
          │
          ▼
       Worker
          │
          ▼
      Process Job
```

### Worker Lifecycle

```text
Pending
   │
   ▼
Running
   │
   ├── Success ─────► Completed
   │
   └── Failure
          │
          ▼
      Retry + Backoff
          │
          ├── Attempts Remaining
          │        │
          │        ▼
          │      Pending
          │
          └── Max Attempts
                   │
                   ▼
                 Failed
```

The worker supports:

- Durable jobs
- Separate worker process
- Row-lock based claiming
- Retry tracking
- Exponential backoff
- Maximum attempt limits
- Failed-job state

---

## API Surface

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a tenant owner |
| `POST` | `/api/v1/auth/login` | Authenticate and receive JWT |
| `GET` | `/api/v1/auth/me` | Return authenticated owner |
| `GET` | `/api/v1/widgets` | List tenant widgets |
| `POST` | `/api/v1/widgets` | Create a widget |
| `GET` | `/api/v1/widgets/{widget_id}` | Retrieve a widget |
| `PATCH` | `/api/v1/widgets/{widget_id}` | Update a widget |
| `DELETE` | `/api/v1/widgets/{widget_id}` | Delete a widget |
| `GET` | `/widget.v1.js?id={widget_id}` | Serve widget JavaScript |
| `GET` | `/api/v1/public/widgets/{widget_id}/config` | Retrieve public widget configuration |
| `POST` | `/api/v1/public/submissions` | Capture a public lead |
| `OPTIONS` | `/api/v1/public/submissions` | CORS preflight |
| `GET` | `/api/v1/dashboard/submissions` | Retrieve tenant submissions |
| `GET` | `/api/v1/dashboard/stats` | Retrieve dashboard statistics |
| `GET` | `/health` | Service health check |

Interactive API documentation is available through FastAPI Swagger UI:

```text
http://localhost:8000/docs
```

---

## Technology Stack

| Component | Technology |
|---|---|
| **Language** | Python 3.11+ |
| **Framework** | FastAPI |
| **Database** | PostgreSQL |
| **ORM** | SQLAlchemy |
| **Migrations** | Alembic |
| **Validation** | Pydantic |
| **Authentication** | JWT |
| **Rate Limiting** | IP/Widget based limiter |
| **Widget** | JavaScript |
| **Background Jobs** | PostgreSQL-backed worker |
| **Containerization** | Docker Compose |
| **Testing** | Pytest |
| **Dashboard** | HTML / CSS / JavaScript |
| **License** | MIT |

---

## Project Structure

```text
flyrank-capstone-widget-platform/
│
├── app/
│   ├── api/                 # FastAPI route modules
│   ├── core/                # Configuration, security and logging
│   ├── db/                  # Database configuration
│   ├── models/               # SQLAlchemy models
│   ├── repositories/        # Tenant-scoped database operations
│   ├── schemas/              # Pydantic schemas
│   ├── services/              # Business logic
│   ├── utils/                  # Shared utilities
│   └── workers/               # Background worker
│
├── alembic/
│   └── versions/            # Database migrations
│
├── customer-site/           # Second-origin demo website
├── dashboard/               # Owner dashboard
├── widget/                  # Public widget bundle
├── scripts/                 # Seed and verification scripts
├── tests/                   # Automated tests
│
├── README.md
├── EVIDENCE.md
├── BUILDLOG.md
├── capstone.yaml
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── .env.example
├── .gitignore
└── LICENSE
```

---

## Getting Started

The project is designed to run locally through Docker Compose.

### Prerequisites

- Python 3.11+
- Docker Desktop
- Git

### Docker Setup

```bash
git clone https://github.com/srinivascl167/Embeddable-Widget-Lead-Capture-Platform.git

cd Embeddable-Widget-Lead-Capture-Platform

cp .env.example .env

docker compose up --build
```

Seed demo data:

```bash
docker compose exec api python scripts/seed.py
```

Start the customer website:

```bash
cd customer-site
python -m http.server 5500
```

Access points:

```text
API documentation:   http://localhost:8000/docs
Customer website:    http://localhost:5500
```

### Local Development (without Docker for the API)

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it and install dependencies:

```bash
pip install -r requirements.txt
```

Start PostgreSQL:

```bash
docker compose up -d db
```

Apply migrations:

```bash
alembic upgrade head
```

Seed data:

```bash
python scripts/seed.py
```

Start the API:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Start the worker:

```bash
python -m app.workers
```

---

## Demo Credentials

The seed script provides a local evaluation account:

```text
Email:    demo@flyrank.local
Password: Demo@12345
```

> These credentials are intended only for local development and evaluation. They should not be reused in production.

---

## Testing

Run the automated test suite:

```bash
pytest -q
```

The current repository documentation records:

```text
7 passed, 7 warnings
```

The test suite covers the core backend workflow, including:

- Authentication
- Widget CRUD
- Tenant isolation
- Public submission validation
- Idempotency
- Honeypot protection
- Rate limiting
- CORS preflight
- Dashboard tenant scoping

The automated tests use an isolated test database, while local evaluation and deployment use PostgreSQL through Docker.

---

## Evaluator Acceptance Probes

The implementation is designed around reproducible acceptance scenarios.

| Probe | Expected Behavior |
|---|---|
| Valid second-origin submission | `201 Created` and lead persisted |
| Malformed submission | `4xx` validation response |
| Oversized payload | `413 Content Too Large` |
| Rate limit exceeded | `429 Too Many Requests` |
| Honeypot submission | `400 Bad Request` |
| Geo Provider A failure | Fallback to Provider B |
| Both geo providers fail | Lead stored without geo |
| Notification failure | Lead remains stored |
| Background job failure | Retry with backoff |
| Idempotent retry | Existing submission returned |
| Cross-tenant access | Unauthorized/not-found behavior |
| CORS preflight | Successful preflight response |

Detailed evaluator procedures are maintained in `EVIDENCE.md`. The evidence file intentionally does not contain fabricated PASS results — actual evaluator evidence should be generated from real local test runs.

---

## Design Decisions & Trade-offs

### In-Memory Rate Limiting

The current limiter is intentionally lightweight for local capstone evaluation. It is suitable for a single API instance but is not a distributed rate limiter for multiple API replicas. A production deployment could move rate-limit state to Redis or another shared store.

### PostgreSQL-Backed Background Queue

Instead of introducing Redis/RQ or another queue infrastructure, background jobs are stored in PostgreSQL. This keeps the stack compact while still providing:

- Durable jobs
- Separate worker processing
- Retry tracking
- Row-lock based claiming
- Exponential backoff
- Failed-job state

### Lightweight Dashboard

The dashboard is intentionally simple because the primary focus of this capstone is backend engineering, reliability, security, and API behavior rather than frontend design.

### Second-Origin Customer Site

The customer website intentionally runs separately from the API:

```text
API:       http://localhost:8000
Customer:  http://localhost:5500
```

This allows CORS and cross-origin submission behavior to be demonstrated realistically.

---

## Five-Minute Demo Outline

- **The Question:** How can customers embed a reusable lead-capture form on their websites without building their own backend?
- **The Method:** Build a FastAPI + PostgreSQL multi-tenant backend with JWT authentication, widget management, public submissions, CORS, rate limiting, geo fallback, idempotency, and background workers.
- **One Flow:** Create a widget → copy the generated `<script>` tag → open the second-origin customer website → submit a lead → inspect the dashboard.
- **One Security Point:** Attempt to access another tenant's widget or submissions and demonstrate backend tenant isolation.
- **One Reliability Point:** Force a notification failure and show that the lead remains stored while the background worker retries independently.
- **One Scalability Point:** Explain how distributed rate limiting and external notification infrastructure could replace the lightweight local implementations for production deployment.

---

## Key Engineering Outcomes

### Backend Development

- REST API design
- FastAPI application architecture
- JWT authentication
- Pydantic validation
- SQLAlchemy ORM
- PostgreSQL persistence

### Security

- Tenant isolation
- CORS configuration
- Request validation
- Payload-size protection
- Rate limiting
- Honeypot spam protection
- Secure environment configuration

### Reliability

- Idempotent submissions
- Durable background jobs
- Retry handling
- Exponential backoff
- Graceful geo-provider failure
- Side-effect isolation

### Deployment

- Dockerized API
- PostgreSQL container
- Reproducible local environment
- Database migrations
- Automated tests

---

## Project Summaries

### LinkedIn

Built and completed my **FlyRank Backend Engineering Capstone** 🚀

I developed a production-style **Embeddable Widget & Lead-Capture Platform** using FastAPI and PostgreSQL.

The system supports multi-tenant authentication, secure cross-origin lead submissions, widget management, rate limiting, honeypot protection, IP-based geo enrichment with fallback providers, idempotent requests, and durable background jobs with retries.

I also containerized the application with Docker Compose and implemented automated testing, database migrations, tenant isolation, and evaluator-focused acceptance flows.

This project gave me hands-on experience building backend systems around security, reliability, persistence, asynchronous processing, and API design.

**Tech Stack:** Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Docker, Pytest

`#BackendDevelopment #Python #FastAPI #PostgreSQL #Docker #SoftwareEngineering #FlyRank #BackendEngineering`

### Employer-Facing Summary

I built an end-to-end multi-tenant backend platform that allows customers to create embeddable lead-capture widgets and deploy them on external websites using a single script tag.

The system uses FastAPI and PostgreSQL with JWT authentication, tenant-isolated queries, CORS, Pydantic validation, rate limiting, honeypot protection, IP-based geo-enrichment fallback, idempotency, and a PostgreSQL-backed background worker with retry handling.

The project demonstrates practical backend engineering across API design, authentication, database persistence, security, asynchronous processing, reliability, Docker-based deployment, and automated testing.

---

## Acknowledgments

This project was developed as part of the **FlyRank Backend Engineering Track Capstone**.

The project uses open-source technologies including Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Pydantic, Docker, JavaScript, and Pytest.

Development decisions and AI-assisted development activities are documented in `BUILDLOG.md`.

---

## License

This project is licensed under the **MIT License**. See [`LICENSE`](LICENSE) for details.
