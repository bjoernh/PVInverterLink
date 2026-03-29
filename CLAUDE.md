# CLAUDE.md

FastAPI solar inverter management system with TimescaleDB, multi-tenant RLS, HTMX frontend.

## Stack
FastAPI · TimescaleDB/PostgreSQL · SQLAlchemy 2.x async · Alembic · fastapi-users JWT · Jinja2/HTMX · uv · Python 3.13+

## Critical Rules

**Git**: Always use `git --no-pager` to avoid interactive pager.

**ENV_FILE**: Required for all scripts/migrations (except pytest which auto-loads `tests/test.env`):
```bash
ENV_FILE=solar_backend/backend.local.env uv run alembic upgrade head
```

**Docker dev**: Never rebuild the backend container — app dir is volume-mounted, uvicorn uses `--reload`.

**Tailwind**: After adding new classes to templates, run `npm run tailwind:build` or styles won't appear.

**Migrations**: Alembic autogenerate misses TimescaleDB features (hypertables, RLS policies) — always review and manually add them.

**RLS**: Always use `rls_context` manager when querying time-series data:
```python
async with rls_context(session, user.id):
    data = await get_power_timeseries(...)
```

## Dev Commands
```bash
uv sync                                          # install deps
uv run uvicorn solar_backend.app:app --reload   # dev server
uv run pytest                                    # tests (no ENV_FILE needed)
npm run tailwind:build                           # rebuild CSS
docker-compose up -d                             # start services
ENV_FILE=... uv run alembic upgrade head         # apply migrations
ENV_FILE=... uv run alembic revision --autogenerate -m "desc"
```

## Architecture

**Core**: `app.py` · `db.py` (models) · `users.py` (auth) · `config.py` · `schemas.py`

**API** (`solar_backend/api/`): `signup` · `login` · `start` · `inverter` · `dashboard` · `measurements` · `account` · `healthcheck`

**Services** (`solar_backend/services/`): `inverter_service.py` · `exceptions.py`

**Utils**: `utils/timeseries.py` (rls_context, write/read helpers) · `utils/query_builder.py` (TimeSeriesQueryBuilder) · `utils/email.py` · `utils/admin_auth.py`

## Database Models
- **User**: extends SQLAlchemyBaseUserTable, one-to-many Inverter
- **Inverter**: `serial_logger` = unique device ID, CASCADE delete
- **InverterMeasurement**: hypertable, PK (time, user_id, inverter_id)
- **DCChannelMeasurement**: hypertable, PK (time, user_id, inverter_id, channel); fields: power/voltage/current/yield_day_wh/yield_total_kwh/irradiation; controlled by `STORE_DC_CHANNEL_DATA` config

## Auth
- Cookie (`auth_backend_user`) → HTMX routes → `current_active_user`
- Bearer (`auth_backend_bearer`) → API routes → `current_active_user_bearer` / `current_superuser_bearer`
- Both JWT, 2-day lifetime

## Config
Required: `DATABASE_URL`, `AUTH_SECRET`, `ENCRYPTION_KEY`, `BASE_URL`
Optional: `FASTMAIL` (email), `COOKIE_SECURE` (True in prod), `STORE_DC_CHANNEL_DATA` (default True)

## TimescaleDB
- 7-day time chunks, 4 user_id space partitions, 2-year retention
- RLS via `app.current_user_id` session variable
- CASCADE delete: user → inverters → measurements

## Adding New Endpoints
1. Business logic in `services/`
2. Route in `api/*.py` calling the service
3. Auth: `Depends(current_active_user)` or `Depends(current_active_user_bearer)`
4. HTMX: `@htmx("template_name", "component_name")`
5. Schemas in `schemas.py`

## HTMX Error Handling
Use `response-targets` extension (loaded in `base.jinja2:72`):
```html
<form hx-post="/endpoint" hx-target-422="#error-div" hx-target-503="#error-div">
```

## Docker Registry
Images at `ghcr.io/bjoernh/pvinverterlink`. Tags: `prod`/`vX.Y.Z` for production, `test`/`staging` for lower envs. Never use `latest` in production. See [docs/DOCKER-REGISTRY.md](docs/DOCKER-REGISTRY.md).

## Password Reset
```bash
ENV_FILE=.env uv run python reset_password.py user@example.com ['NewPassword123!']
```

## Known Issues
- `api/inverter.py:100-112` incomplete SELECT query in `/inverter_metadata/{serial_logger}`
- `utils/influx.py:6` cycle import (commented out)
- Structlog dev-only config in `app.py:22`
- **Pydantic pinned to `<2.12`** due to fastapi-mail 1.5.0 incompatibility (fix pending in fastapi-mail PR #237). When fastapi-mail 1.6.0+ releases, remove the constraint and test email flows.
