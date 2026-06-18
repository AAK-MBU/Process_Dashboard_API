# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

REST API for monitoring and managing business processes. Processes have ordered **steps**; each execution of a process is a **run**, and each run has **step runs** (one per step). The API persists to Microsoft SQL Server and exposes filtering, search, soft-delete/retention, API-key auth, and audit logging.

## Commands

Dependencies are managed with **uv** (not pip). Python 3.11+.

```bash
uv sync                          # install all deps (incl. dev) from uv.lock
uv sync --extra dev              # ensure ruff/mypy are present

# Run the API locally (requires a reachable SQL Server + .env)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Lint / format / type-check
uv run ruff check app            # lint (line-length 100, see [tool.ruff] in pyproject.toml)
uv run ruff format app           # format
uv run mypy app                  # type-check (pydantic + sqlalchemy plugins enabled)

# Docker (local, exposes :8000)
docker compose -f docker-compose.local.yml up --build
# Docker (prod; joins external `edge` network, no published port)
docker compose up -d

# Version bump (updates pyproject.toml, app/version.py, .env.example, Dockerfile)
uv run python scripts/update_version.py [patch|minor|major|X.Y.Z]
```

There is **no test suite** in this repo. The README references some scripts (`scripts/migrate_db.py`, `scripts/add_api_key_roles.py`) that do not exist; the actual scripts are `update_version.py`, `docker_setup_api_keys.py`, and shell/PowerShell API-key setup helpers. Tables are auto-created at startup via `SQLModel.metadata.create_all` (no Alembic migrations).

## Architecture

Layered FastAPI app. Request flow: **endpoint → service → model**, with cross-cutting auth, auditing, and SQLAlchemy event automation.

- **`app/main.py`** — app factory. Registers CORS, the audit ASGI middleware, `fastapi-pagination`, and exception handlers mapping custom exceptions (`app/core/exceptions.py`) to HTTP responses. The lifespan hook calls `create_db_and_tables()` then `register_events()`. **The entire `/api/v1` router is gated by `verify_api_key`** (applied as a router-level dependency), so every v1 endpoint requires a valid `X-API-Key`.

- **`app/api/v1/`** — `api.py` aggregates routers under prefixes (`/processes`, `/runs`, `/steps`, `/step-runs`, `/dashboard`, `/auth`, `/api-keys`, `/admin`, `/audit-logs`, `/test`). Endpoints are thin and delegate to services.

- **`app/api/dependencies.py`** — DI wiring. Provides `get_*_service` factories and the `RequireApiKey` / `RequireAdminKey` annotated dependencies. Admin-only endpoints depend on `require_admin_key` (checks `api_key.role == "admin"`).

- **`app/services/`** — all business logic lives here. Each service takes a `Session` in its constructor. This is where queries, soft-delete filtering, status logic, and retention calculations belong.

- **`app/models/`** — SQLModel table models plus their Pydantic create/read/update schemas, colocated per entity (`process.py`, `process_run.py`, `process_step.py`, `process_step_run.py`). `enums.py` defines `StepRunStatus` and `ProcessRunStatus`. `base.py` has the `TimestampsMixin`.

- **`app/db/database.py`** — single `engine` (pool_size 10, max_overflow 20, `pool_pre_ping`). Connection URL comes from `DATABASE_URL` or is assembled from individual `DATABASE_*` settings. `SessionDep` / `get_session` provide per-request sessions.

### SQLAlchemy event automation (`app/models/events.py`)

Critical, non-obvious behavior — much of the data consistency is implicit, not in the endpoints:

- `before_insert` on `ProcessStepRun` auto-populates `step_index` from the related `ProcessStep`.
- `before_commit` on the `Session` recalculates each affected parent `ProcessRun`'s status from its step runs, and manages `started_at`/`finished_at` timestamps on status transitions.
- **Deadlock constraint:** the `before_commit` handler must operate **only on objects already in the session identity map** — it deliberately avoids issuing new queries (uses `session.get`, which checks the identity map first). A previous deadlock was caused by querying inside this handler. Preserve this when editing run-status logic. The status priority order (failed > cancelled > running > completed > pending; optional steps don't block completion) lives in `ProcessRun.update_status_from_steps`.

### Soft delete & retention

Entities support soft delete and are **excluded from all list/query endpoints by default**; fetching a soft-deleted item by ID returns 404. Runs get a `scheduled_deletion_at` computed from the parent process's `retention_months` at creation (see `run_service.create_run_with_steps`). Admin cleanup endpoints neutralize PII (irreversible) on runs past their retention. Retention/neutralization logic is in `app/services/retention_service.py` and `app/models/retention.py`.

### Rerun adapter pattern

Failed step runs can be re-executed against an external orchestrator. `app/adapters/` defines `BaseRerunAdapter` and the `RerunAdapterRegistry` (singleton, selected by `RERUN_ADAPTER_TYPE`). The only implementation is `AutomationServerAdapter` (configured via `AUTOMATION_SERVER_URL` / `AUTOMATION_SERVER_TOKEN`). Add new backends by implementing `BaseRerunAdapter` and registering them in `registry.py`.

### Auditing

`app/middleware/audit_middleware_asgi.py` is the active middleware (registered in `main.py`); it records every request (user, method, path, status, duration) to the `audit_log` table, queryable via `/api/v1/audit-logs`. `audit_middleware.py` is an older variant.

## Configuration

Settings load from `.env` via pydantic-settings (`app/core/config.py`, `case_sensitive=True`). Copy `.env.example` to `.env`. `CORS_ORIGINS` must be a JSON array string. The single source of truth for the version is `pyproject.toml` / `app/version.py` — bump with `scripts/update_version.py`, don't edit by hand. SQL Server access requires ODBC Driver 18 (installed in the Docker runtime image).
