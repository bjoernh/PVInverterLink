# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Deye Hard Backend is a FastAPI-based solar inverter management system using TimescaleDB (PostgreSQL extension) for time-series data storage. The application manages users and their solar inverters, providing authentication, data collection, and visualization capabilities with multi-tenant data isolation.

## Technology Stack

- **Web Framework**: FastAPI with HTMX for dynamic frontend
- **Database**: PostgreSQL + TimescaleDB (time-series extension)
- **ORM**: SQLAlchemy 2.x with async support
- **Migrations**: Alembic
- **Authentication**: fastapi-users with JWT (Bearer + Cookie transport)
- **Admin Interface**: SQLAdmin
- **Template Engine**: Jinja2
- **Package Manager**: uv
- **Python Version**: 3.13+

## Development Commands

### Local Development
```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn solar_backend.app:app --reload

# Run tests (test environment auto-configured)
uv run pytest

# Run specific test markers
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m smoke

# Run with verbose output
uv run pytest -v

# Note: Test configuration is automatically loaded from tests/test.env
# No need to manually set ENV_FILE environment variable
```

### Docker Development
```bash
# Start all services (backend, timescale db)
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop all services
docker-compose down

# Rebuild backend after general changes (not backend code)
docker-compose up -d --build backend
```

### Database Migrations
```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

## Architecture

### Core Module Structure

- `solar_backend/app.py` - FastAPI application setup, middleware, router registration, admin interface
- `solar_backend/db.py` - Database models (User, Inverter, InverterMeasurement), SQLAlchemy session management, admin views
- `solar_backend/users.py` - User management, authentication backends, UserManager lifecycle hooks
- `solar_backend/config.py` - Pydantic settings, environment configuration loading
- `solar_backend/schemas.py` - Pydantic models for API request/response validation

### API Routers

Located in `solar_backend/api/`:
- `signup.py` - User registration flow
- `login.py` - Authentication endpoints
- `start.py` - Main dashboard/homepage
- `inverter.py` - Inverter CRUD operations
- `dashboard.py` - Dashboard data and time-series queries
- `measurements.py` - Measurement data ingestion endpoint
- `account.py` - Account management (password, email, deletion)
- `healthcheck.py` - Service health monitoring

### Utilities

- `utils/timeseries.py` - TimescaleDB utilities for time-series data operations
- `utils/email.py` - Email sending for verification and password reset
- `utils/admin_auth.py` - Admin panel authentication backend

### Multi-Tenant TimescaleDB Architecture

The application implements per-user data isolation using TimescaleDB:

1. **Time-Series Storage**:
   - All measurement data stored in `inverter_measurements` table
   - Multi-dimensional partitioning by time (7-day chunks) and user_id (4 space partitions)
   - Automatic compression after 7 days (disabled when RLS is enabled)
   - 2-year retention policy

2. **Data Isolation**:
   - Row-Level Security (RLS) enforces user isolation at database level
   - Application sets `app.current_user_id` session variable before queries
   - Queries automatically filtered by RLS policy
   - CASCADE deletion: deleting a user automatically deletes all inverters and measurements

3. **Data Ingestion**:
   - External inverters POST measurements to `/api/measurements`
   - Requires superuser Bearer token authentication
   - Data routed to correct user partition by inverter serial number
   - Measurements stored with (time, user_id, inverter_id) as composite primary key

### Database Models

**User** (`db.py`):
- Extends `SQLAlchemyBaseUserTable` from fastapi-users
- Has one-to-many relationship with Inverter
- `tmp_pass` field exists but is legacy (can be removed in future cleanup)

**Inverter** (`db.py`):
- Linked to User via `user_id` foreign key with CASCADE deletion
- `serial_logger` is unique identifier for physical device
- Optional metadata: `sw_version`, `rated_power`, `number_of_mppts`

**InverterMeasurement** (`db.py`):
- TimescaleDB hypertable for time-series data
- Composite primary key: (time, user_id, inverter_id)
- Foreign keys to User and Inverter with CASCADE deletion
- Fields: `time` (timestamptz), `user_id`, `inverter_id`, `total_output_power`

### Authentication Architecture

Two parallel authentication backends exist (see `users.py`):

1. **Cookie-based** (`auth_backend_user`):
   - Used for HTML/HTMX frontend routes
   - Provides `current_active_user` dependency

2. **Bearer token** (`auth_backend_bearer`):
   - Used for API routes (e.g., `/api/measurements`)
   - Provides `current_active_user_bearer`, `current_superuser_bearer` dependencies
   - Token URL: `auth/jwt/login`

Both use same JWT strategy with 2-day lifetime.

### Configuration & Environment

- Environment file path set via `ENV_FILE` environment variable
- Config loaded from `solar_backend/backend.env` by default
- Required variables: `DATABASE_URL`, `AUTH_SECRET`, `ENCRYPTION_KEY`, `BASE_URL`
- Optional: `FASTMAIL` config for email functionality
- `WEB_DEV_TESTING` flag in `config.py` is legacy (previously for InfluxDB, can be removed)
- `COOKIE_SECURE` should be True in production, False for local development

### Testing

- Tests use SQLite in-memory database (`sqlite+aiosqlite://`)
- `conftest.py` provides fixtures for async test client and database setup
- All tests use function-scoped database recreation for isolation
- HTMX templates must be initialized in test setup
- Test data created using helpers in `tests/helpers.py`

## Working with Time-Series Data

### TimescaleDB Setup

TimescaleDB is automatically enabled in the PostgreSQL container:

```bash
# Start database
docker-compose up -d db

# Verify TimescaleDB extension
docker-compose exec db psql -U deyehard -d deyehard -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
docker-compose exec db psql -U deyehard -d deyehard -c "\dx"
```

### Row-Level Security Pattern

Always set RLS context before querying time-series data:

```python
from solar_backend.utils.timeseries import set_rls_context, reset_rls_context

async with session:
    try:
        # Set RLS context
        await set_rls_context(session, user.id)

        # Perform queries - automatically filtered by user_id
        data = await get_power_timeseries(session, user.id, inverter.id, "24h")

    finally:
        # Always reset RLS context
        await reset_rls_context(session)
```

## Common Patterns

### Adding New API Endpoints

1. Create route in appropriate `api/*.py` file
2. Use `Depends(current_active_user)` or `Depends(current_active_user_bearer)` for auth
3. For HTMX routes, use `@htmx("template_name", "component_name")` decorator
4. Add Pydantic schemas to `schemas.py` for request/response validation

### Database Changes

1. Modify models in `db.py`
2. Generate migration: `uv run alembic revision --autogenerate -m "description"`
3. Review generated migration in `alembic/versions/`
4. Apply: `uv run alembic upgrade head`

### Working with Time-Series Queries

- Always include `user_id` in queries for partition pruning
- Set RLS context using `set_rls_context(session, user_id)` before queries
- Reset RLS context with `reset_rls_context(session)` after queries
- Use utilities in `utils/timeseries.py` for common operations:
  - `write_measurement()` - Insert measurement data
  - `get_latest_value()` - Get most recent measurement
  - `get_power_timeseries()` - Get time-bucketed data
  - `get_today_energy_production()` - Calculate daily kWh
  - `get_today_maximum_power()` - Get peak power for today
  - `get_last_hour_average()` - Get recent average power

### HTMX Error Handling

HTMX by default only processes 200-series HTTP responses. To display error messages for non-200 status codes, use the `response-targets` extension:

- **Extension loaded**: `base.jinja2:72` includes `response-targets.js`
- **Usage pattern**: Add `hx-target-XXX="#element-id"` attributes to forms/elements
- **Example**: `<form hx-post="/endpoint" hx-target-422="#error-div" hx-target-503="#error-div">
- **Backend**: Return `HTMLResponse` with error message and appropriate HTTP status codedocker

## Known Issues & TODOs

- `/inverter_metadata/{serial_logger}` endpoint has incomplete SELECT query (see `api/inverter.py:100-112`)
- Cycle import between `utils/influx.py` and user models (commented out at line 6)
- TODO in `inverter.py` to decide bucket data retention policy
- Structlog configured only for dev output (see `app.py:22`)
- don't rebuild the backend container, because in dev mode the app directory is mapped into the container and uvicorn is started with --reload option and detect file changes

### Dependency Compatibility Issues

**Pydantic 2.12+ and fastapi-mail 1.5.0 incompatibility** (as of October 2025):
- **Issue**: fastapi-mail 1.5.0 has a breaking bug with Pydantic 2.12+ that causes `AttributeError: 'ValidationInfo' object has no attribute 'multipart_subtype'` when sending emails
- **Root cause**: Schema validator in `fastapi_mail/schemas.py` line 100 uses incorrect API for Pydantic 2.12+ after-model validators
- **GitHub issue**: https://github.com/sabuhish/fastapi-mail/issues/236
- **Pending fix**: PR #237 (https://github.com/sabuhish/fastapi-mail/pull/237) not yet merged
- **Current workaround**: `pyproject.toml` line 20 constrains Pydantic to `>=2.0.0,<2.12` to maintain compatibility
- **Action required**: When fastapi-mail releases version 1.6.0+ with the fix, remove the Pydantic version constraint and upgrade both packages
- **Testing**: After upgrade, test email functionality (user registration, password reset) to verify compatibility
