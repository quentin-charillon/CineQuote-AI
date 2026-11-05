# CineQuote AI 2.0

CineQuote AI is a full-stack movie-quote trivia game built as an AI-engineering portfolio project. Players identify films from dialogue, choose a genre and difficulty, track account statistics, and use guarded AI assistance without allowing a language model to invent quiz questions or decide scores.

The browser never receives a correct answer before submission. Quotes, choices, scoring, accounts, and statistics remain server controlled.

## Features

- Ten-question sessions with four distinct film choices.
- Easy, Medium, and Hard difficulties.
- All Genres, Horror, Comedy, Science Fiction, Thriller, Action, Animation, Romance / Musical Comedy, Fantasy, and Adventure modes.
- Strict genre filtering, randomized questions and choices, and distractor variety.
- Guest play or account-based statistics with secure HTTP-only sessions.
- GroqCloud as the optional primary AI provider, with OpenAI support and offline fallbacks.
- Guarded hints, post-answer explanations, personalized coaching, recommendations from missed films, and natural-language custom quiz planning.
- Provider-output validation, caching, timeouts, rate limits, and quota-safe fallbacks.
- SQLite locally, PostgreSQL in production, Alembic migrations, and an idempotent catalog bootstrap.

## Technology

| Area | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, CSS, Vitest |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database | SQLite locally, PostgreSQL in production |
| AI | Official Groq and OpenAI Python SDKs |
| Testing | pytest, FastAPI TestClient, Vitest, TypeScript |
| Hosting | Render, Vercel, same-origin `/api` proxy |

## Repository layout

```text
CineQuote-AI/
|-- back/
|   |-- alembic/              # Database migrations
|   |-- app/
|   |   |-- api/routes/       # FastAPI routes
|   |   |-- catalog/          # Catalog import/review utilities
|   |   |-- data/             # Movie and quote catalog JSON
|   |   |-- middleware/       # Browser and proxy security
|   |   |-- models/           # SQLAlchemy entities
|   |   |-- repositories/     # Catalog and quiz-session storage
|   |   |-- schemas/          # Pydantic contracts
|   |   `-- services/         # Quiz, auth, stats, and AI logic
|   |-- scripts/              # Imports, audits, and production start
|   |-- tests/                # Backend tests
|   `-- pyproject.toml
|-- front/
|   |-- api/                  # Same-origin Vercel proxy
|   |-- src/                  # React app and typed API client
|   |-- package.json
|   |-- package-lock.json
|   `-- vercel.json
|-- render.yaml               # Render monorepo configuration
|-- .env.example
`-- README.md
```

## Prerequisites

- Python 3.11 or newer. Production is pinned to Python 3.12.8.
- Node.js 20 or newer with npm.
- The examples below use Windows PowerShell from the repository root.

## Local installation

### Backend

```powershell
cd back
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
python scripts\bootstrap_database.py
uvicorn app.main:app --reload
```

The bootstrap applies Alembic migrations and idempotently imports `app/data/manual_catalog.json`. A fresh catalog contains 73 films and 421 quotes.

Useful URLs:

- `http://localhost:8000/health`
- `http://localhost:8000/health/ready`
- `http://localhost:8000/docs`

### Frontend

Open a second PowerShell terminal:

```powershell
cd front
npm ci
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`. Vite proxies same-origin `/api` requests to local FastAPI.

## Configuration and secrets

- `back/.env.example` documents backend settings.
- `front/.env.example` documents the optional frontend API override.
- `.env.example` is a short repository-level reference.

Never commit `.env` files. Never prefix a secret with `VITE_`, because Vite variables can enter the browser bundle. Keep `GROQ_API_KEY`, `OPENAI_API_KEY`, `DATABASE_URL`, `SESSION_SECRET`, and `PROXY_SHARED_SECRET` server-side. Missing AI credentials intentionally activate safe fallback behavior.

## Tests and checks

Backend:

```powershell
cd back
.\.venv\Scripts\python.exe -m pytest
```

Frontend:

```powershell
cd front
npm test
npm run typecheck
npm run build
```

Automated tests mock AI providers and make no paid/live provider calls. An optional test can target a disposable PostgreSQL database:

```powershell
cd back
$env:TEST_POSTGRES_DATABASE_URL = "postgresql://user:password@localhost:5432/cinequote_test"
.\.venv\Scripts\python.exe -m pytest tests/test_postgres_integration.py
Remove-Item Env:TEST_POSTGRES_DATABASE_URL
```

Never point this test at production.

## Catalog management

The authoritative catalog is `back/app/data/manual_catalog.json`. Imports normalize records and are idempotent. A film may have multiple distinct quotes and multiple genres.

After editing the catalog locally:

```powershell
cd back
.\.venv\Scripts\python.exe scripts\bootstrap_database.py
```

The catalog contains short dialogue excerpts entered and reviewed manually. Before a public or commercial launch, independently review wording, attribution, genre metadata, and quotation-licensing requirements for the intended jurisdiction.

## API overview

System:

- `GET /health`
- `GET /health/ready`

Accounts and statistics:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /stats/me`
- `POST /ai/coach`
- `POST /ai/recommendations`

Quiz:

- `GET /quiz/sessions/availability`
- `POST /quiz/sessions`
- `POST /quiz/sessions/custom`
- `GET /quiz/sessions/{id}/question`
- `POST /quiz/sessions/{id}/answers`
- `POST /quiz/sessions/{id}/hint`
- `POST /quiz/sessions/{id}/explanation`
- `GET /quiz/sessions/{id}/results`

## Security design

- Passwords use salted PBKDF2-HMAC-SHA256 hashes.
- Authentication tokens are random; production stores only keyed token hashes.
- Cookies are HTTP-only and become `Secure; SameSite=Strict` in production.
- Login is limited by IP and account identifier; registration is limited by IP.
- AI endpoints have per-IP, per-user, feature-specific, and global limits.
- Provider output is validated and replaced by conservative fallback text when unsafe.
- Unsafe browser requests require the configured origin and production proxy secret.
- Quiz sessions expire after inactivity and use bounded process memory.
- API keys, answers, full prompts, and passwords are not intentionally logged.

Rate limits, AI caches, and active quiz sessions are process-local. They reset on restart and suit the initial single-worker deployment. Shared storage such as Redis is required before horizontal scaling.

## Production database

Production requires PostgreSQL through `DATABASE_URL`. Render-style `postgresql://` URLs are normalized to Psycopg 3 automatically.

For a new empty database:

```powershell
cd back
$env:DATABASE_URL = "postgresql://user:password@host:5432/cinequote"
.\.venv\Scripts\python.exe scripts\bootstrap_database.py
Remove-Item Env:DATABASE_URL
```

This imports only the public catalog. It never reads the ignored local `cinequote.db`, so local users, authentication sessions, and statistics are not transferred.

## Deployment

Nothing is deployed automatically by this repository.

### Recommended order

1. Generate different random `SESSION_SECRET` and `PROXY_SHARED_SECRET` values.
2. Create an empty PostgreSQL database on Render.
3. Create the Render backend from `render.yaml` and configure its secrets.
4. Confirm `/health` and `/health/ready` return HTTP 200.
5. Create the Vercel project with `front` as its root directory.
6. Configure its two server-side variables.
7. Deploy and verify `/api/health/ready` through Vercel.
8. Create a new production test account and complete a quiz.

Generate secrets locally without saving them in a committed file:

```powershell
.\back\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48)); print(secrets.token_urlsafe(48))"
```

### Render backend

`render.yaml` configures:

- Root Directory: `back`
- Python: 3.12.8
- Build: `pip install --upgrade pip && pip install .`
- Start: `python -m scripts.start_production`
- Health check: `/health/ready`
- Region: Frankfurt
- Uvicorn workers: one

Required Render variables:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | Render PostgreSQL internal URL |
| `FRONTEND_URL` | Exact HTTPS Vercel production origin |
| `SESSION_SECRET` | Random value, at least 32 characters |
| `PROXY_SHARED_SECRET` | Different random value, at least 32 characters |
| `GROQ_API_KEY` | Optional server-side Groq key |
| `AI_PROVIDER` | `groq` or `fallback` |
| `AUTH_COOKIE_SECURE` | `true` |
| `AUTH_COOKIE_SAMESITE` | `strict` |
| `CSRF_ORIGIN_CHECK_ENABLED` | `true` |
| `TRUST_PROXY_HEADERS` | `true` |
| `REQUIRE_PROXY_SECRET` | `true` |

The entrypoint fails closed when critical configuration is missing, serializes migrations with a PostgreSQL advisory lock, imports the catalog, verifies counts, and then starts Uvicorn on Render's `$PORT`.

### Vercel frontend

| Setting | Value |
|---|---|
| Root Directory | `front` |
| Framework | Vite |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |

Server-side Vercel variables:

| Variable | Value |
|---|---|
| `RENDER_API_URL` | Public HTTPS Render service origin |
| `PROXY_SHARED_SECRET` | Same value as Render |

Leave `VITE_API_URL` unset in production. `front/api/[...path].ts` proxies `/api` requests and preserves status codes, cookies, response bodies, and important headers. `front/vercel.json` provides SPA refresh fallback after filesystem and API routes are checked.

## Hosting limitations and costs

- Render free web services sleep after inactivity, so the first request can be slow. Their filesystem is ephemeral; never use SQLite there.
- Render free PostgreSQL expires after 30 days and has no backups. Use a paid PostgreSQL plan for durable public data and confirm current pricing first.
- Every browser API call passes through a Vercel function. Monitor Vercel Hobby usage; Hobby is intended for personal, non-commercial projects.
- Monitor Render bandwidth/build usage and Groq quota. Keep AI limits and fallback mode enabled.
- Do not enable autoscaling or paid upgrades without a budget decision.
- A Render restart removes active quiz sessions and in-memory limits/caches, while PostgreSQL accounts and completed statistics remain.

## License and content notice

No software license has been selected yet. Add one before inviting reuse or contributions. Movie titles and short dialogue excerpts can have separate intellectual-property considerations; inclusion in this portfolio catalog is not a claim that the material is public domain.
