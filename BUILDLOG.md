# BUILDLOG — FlyRank Capstone

An honest log of AI assistance used during this project.

---

## Phase 1: Design & Initial Setup

### Session 1 — 2026-09-20

**Task:** Project structure, data model design, API contract sketch, initial files.

**AI assistance used:**
- Claude (Anthropic) assisted with:
  - Defining the folder structure for a scalable FastAPI application
  - Drafting SQLAlchemy models with multi-tenant isolation (tenant_id on every table)
  - Drafting Pydantic schemas with strict validation
  - Writing requirements.txt, docker-compose.yml, .env.example, README.md
  - Writing capstone.yaml and EVIDENCE.md templates
  - Explaining security decisions (CORS, rate limiting, honeypot, geo fallback chain)

**What I did myself:**
- Reviewed and understood every file before accepting it
- Verified the $0 stack constraint (all free-tier tools, no paid APIs)
- Adjusted the README architecture diagram to match the actual implementation

**Decisions made:**
- Used `public_id` (16-char URL-safe token) separate from the UUID primary key
  so the internal ID is never exposed on the public internet
- Honeypot field named `website_url` — common bot pattern, hidden via CSS
- Geo enrichment runs synchronously but with 3s timeouts; if both providers
  fail, submission is stored without geo (graceful degradation)
- Email + webhook run in daemon threads (fire-and-forget) so they never block
  the submission response
- Rate limiting via SlowAPI with per-IP+widget keying for the public endpoint

**Files created:**
- `requirements.txt`
- `docker-compose.yml`
- `Dockerfile`
- `.env.example`
- `.gitignore`
- `README.md`
- `capstone.yaml`
- `EVIDENCE.md`
- `BUILDLOG.md`
- `app/__init__.py`
- `app/main.py`
- `app/core/config.py`
- `app/core/database.py`
- `app/core/security.py`
- `app/core/deps.py`
- `app/core/rate_limit.py`
- `app/models/base.py`
- `app/models/tenant.py`
- `app/models/widget.py`
- `app/models/submission.py`
- `app/schemas/auth.py`
- `app/schemas/widget.py`
- `app/schemas/submission.py`
- `app/schemas/dashboard.py`
- `app/routers/auth.py`
- `app/routers/widgets.py`
- `app/routers/public.py`
- `app/routers/dashboard.py`
- `app/services/geo.py`
- `app/services/email_svc.py`
- `app/services/webhook.py`
- `app/services/spam.py`
- `app/services/snippet.py`
- `app/db/init_db.py`

---

### Phase 2: Testing & Evidence Collection

_(To be filled as tests are run and evidence is collected)_

---

### Phase 3: Polish & Documentation

_(To be filled)_
