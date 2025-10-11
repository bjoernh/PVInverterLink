# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Deye Hard Backend is a FastAPI-based solar inverter management system that integrates with InfluxDB for time-series data storage. The application manages users and their solar inverters, providing authentication, data collection, and visualization capabilities.

## Technology Stack

- **Web Framework**: FastAPI with HTMX for dynamic frontend
- **Database**: PostgreSQL (primary), InfluxDB 2.x (time-series data)
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

# Run tests
uv run pytest

# Run specific test markers
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m smoke
```

### Docker Development
```bash
# Start all services (backend, postgres, influxdb)
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
- `solar_backend/db.py` - Database models (User, Inverter), SQLAlchemy session management
- `solar_backend/users.py` - User management, authentication backends, UserManager lifecycle hooks
- `solar_backend/config.py` - Pydantic settings, environment configuration loading
- `solar_backend/schemas.py` - Pydantic models for API request/response validation
- `solar_backend/inverter.py` - Inverter-specific business logic, InfluxDB bucket management

### API Routers

Located in `solar_backend/api/`:
- `signup.py` - User registration flow
- `login.py` - Authentication endpoints
- `start.py` - Main dashboard/homepage
- `inverter.py` - Inverter CRUD operations
- `healthcheck.py` - Service health monitoring

### Utilities

- `utils/influx.py` - InfluxDB management class for user/org/bucket creation and queries
- `utils/email.py` - Email sending for verification and password reset
- `utils/admin_auth.py` - Admin panel authentication backend

### Multi-Tenant InfluxDB Architecture

The application implements per-user InfluxDB isolation:

1. **User Registration Flow** (see `users.py:UserManager`):
   - User registers via fastapi-users
   - On email verification (`on_after_verify`), system creates:
     - Dedicated InfluxDB user
     - Private InfluxDB organization (named after user email)
     - User-specific authorization token
   - Credentials stored in `User` model (`influx_org_id`, `influx_token`)

2. **Inverter Registration Flow** (see `api/inverter.py`, `inverter.py`):
   - Authenticated user adds inverter with name and serial number
   - System creates dedicated InfluxDB bucket for that inverter
   - Bucket ID stored in `Inverter.influx_bucked_id`
   - Each inverter writes to its own bucket within user's org

3. **Data Access Pattern**:
   - External inverters call `/influx_token?serial=XXX` (requires superuser auth)
   - Returns user's InfluxDB token, bucket ID, org ID for writing data
   - Queries use user-scoped credentials for data isolation

### Database Models

**User** (`db.py`):
- Extends `SQLAlchemyBaseUserTable` from fastapi-users
- Stores InfluxDB org ID and token for multi-tenant data isolation
- Has one-to-many relationship with Inverter
- `tmp_pass` holds password temporarily until email verification

**Inverter** (`db.py`):
- Linked to User via `user_id` foreign key
- `serial_logger` is unique identifier for physical device
- `influx_bucked_id` links to dedicated InfluxDB bucket
- Optional metadata: `sw_version`, `rated_power`, `number_of_mppts`

### Authentication Architecture

Two parallel authentication backends exist (see `users.py`):

1. **Cookie-based** (`auth_backend_user`):
   - Used for HTML/HTMX frontend routes
   - Provides `current_active_user` dependency

2. **Bearer token** (`auth_backend_bearer`):
   - Used for API routes (e.g., `/influx_token`)
   - Provides `current_active_user_bearer`, `current_superuser_bearer` dependencies
   - Token URL: `auth/jwt/login`

Both use same JWT strategy with 2-day lifetime.

### Configuration & Environment

- Environment file path set via `ENV_FILE` environment variable
- Config loaded from `solar_backend/backend.env` by default
- Required variables: `DATABASE_URL`, `AUTH_SECRET`, `INFLUX_URL`, `INFLUX_OPERATOR_TOKEN`
- InfluxDB setup requires operator token (see README.md for initial setup)
- `WEB_DEV_TESTING` flag in `config.py` disables InfluxDB operations for local dev
- `COOKIE_SECURE` should be True in production, False for local development

### Testing

- Tests use SQLite in-memory database (`sqlite+aiosqlite://`)
- `conftest.py` provides fixtures for async test client and database setup
- `without_influx` fixture mocks InfluxDB operations via `WEB_DEV_TESTING`
- All tests use function-scoped database recreation for isolation
- HTMX templates must be initialized in test setup

## Initial InfluxDB Setup

InfluxDB requires a one-time operator token setup (detailed in README.md):

```bash
docker-compose up -d influxdb
docker exec -it <influxdb_container> sh

# Inside container
influx config create --config-name wtf --host-url http://localhost:8086 --org wtf --token <init_admin_token> --active
influx auth create --org wtf --operator

# Copy generated token to backend.env
echo 'INFLUX_OPERATOR_TOKEN="<generated_token>"' >> backend.env
```

This operator token allows the backend to create per-user organizations and tokens.

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

### Working with InfluxDB

- Always use user's `influx_token` and `influx_org_id` for queries (multi-tenant isolation)
- InfluxDB connection pattern: `InfluxManagement(user.influx_url).connect(org=user.email, token=user.influx_token)`
- Bucket operations should always link to user's organization
- Use `WEB_DEV_TESTING=True` to bypass InfluxDB during local development

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
