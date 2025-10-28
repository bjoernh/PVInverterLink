# Deye Hard Backend - System Specification

Version: 1.0
Last Updated: October 2025
Status: Production

## Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture](#architecture)
4. [Database Models](#database-models)
5. [Feature Specifications](#feature-specifications)
6. [API Endpoints](#api-endpoints)
7. [Security Features](#security-features)
8. [Infrastructure](#infrastructure)
9. [Configuration](#configuration)

## System Overview

Deye Hard Backend is a FastAPI-based solar inverter management system that provides multi-tenant data collection, storage, and visualization for solar power installations. The system integrates with InfluxDB for time-series data storage and PostgreSQL for relational data, implementing a secure multi-tenant architecture where each user has isolated InfluxDB resources.

### Key Capabilities

- User registration and authentication with email verification
- Multi-inverter management per user
- Real-time power monitoring and historical data storage
- Multi-tenant data isolation using InfluxDB organizations
- Admin interface for system management
- RESTful API for external inverter integration

## Technology Stack

### Backend Framework
- **FastAPI 0.115+**: Modern async web framework
- **Python 3.13+**: Runtime environment
- **Uvicorn**: ASGI server

### Databases
- **PostgreSQL**: Primary relational database for users and inverter metadata
- **InfluxDB 2.x**: Time-series database for inverter telemetry data

### ORM & Migrations
- **SQLAlchemy 2.x**: Async ORM with declarative mapping
- **Alembic**: Database migration tool

### Authentication
- **fastapi-users**: User management and authentication framework
- **JWT**: Token-based authentication (2-day lifetime)
- **PyJWT**: JWT encoding/decoding

### Frontend
- **HTMX**: Dynamic HTML interactions
- **Jinja2**: Template engine
- **DaisyUI/Tailwind CSS**: UI components and styling

### Security
- **fastapi-csrf-protect**: CSRF protection middleware
- **slowapi**: Rate limiting
- **cryptography (Fernet)**: Symmetric encryption for temporary passwords

### Admin & Monitoring
- **SQLAdmin**: Admin interface
- **structlog**: Structured logging

### Email
- **fastapi-mail**: Email sending library
- **Jinja2**: Email template rendering

### Package Management
- **uv**: Fast Python package manager

## Architecture

### Application Structure

```
solar_backend/
├── app.py                 # FastAPI application setup and configuration
├── config.py              # Pydantic settings and environment configuration
├── db.py                  # Database models and session management
├── users.py               # User management and authentication
├── schemas.py             # Pydantic request/response models
├── inverter.py            # Inverter business logic
├── limiter.py             # Rate limiting configuration
├── api/                   # API route modules
│   ├── signup.py          # User registration endpoints
│   ├── login.py           # Authentication endpoints
│   ├── start.py           # Dashboard/homepage
│   ├── inverter.py        # Inverter CRUD operations
│   ├── account.py         # Account management endpoints
│   └── healthcheck.py     # Health monitoring
├── utils/                 # Utility modules
│   ├── influx.py          # InfluxDB management class
│   ├── email.py           # Email sending utilities
│   ├── admin_auth.py      # Admin authentication backend
│   └── crypto.py          # Encryption utilities
└── templates/             # Jinja2 templates
    └── email/             # Email templates
```

### Multi-Tenant Architecture

The system implements strict per-user data isolation using InfluxDB's multi-tenancy features:

1. **User Level**: Each user gets a dedicated InfluxDB organization (named after their email)
2. **Inverter Level**: Each inverter gets a dedicated bucket within the user's organization
3. **Access Control**: User-specific authorization tokens limit access to their organization only

#### Data Flow

```
User Registration → Email Verification → InfluxDB Org Creation
                                       ↓
                          User-specific token generated
                                       ↓
Inverter Registration → InfluxDB Bucket Creation → Data Collection
```

### Authentication Architecture

Two parallel authentication systems:

1. **Cookie-based Auth** (auth_backend_user)
   - Used for web UI routes
   - Session-based authentication
   - Automatic HTMX integration
   - Provides: `current_active_user`, `current_superuser` dependencies

2. **Bearer Token Auth** (auth_backend_bearer)
   - Used for API routes
   - JWT token in Authorization header
   - Token URL: `/auth/jwt/login`
   - Provides: `current_active_user_bearer`, `current_superuser_bearer` dependencies

Both use the same JWT strategy with 2-day token lifetime.

## Database Models

### User Model

**Location**: `db.py:34-46`

```python
class User(SQLAlchemyBaseUserTable[int], Base):
    id: int (primary key)
    email: str (unique, required)
    hashed_password: str (required)
    is_active: bool (default: True)
    is_superuser: bool (default: False)
    is_verified: bool (default: False)
    first_name: str (max 32 chars)
    last_name: str (max 32 chars)
    influx_url: str (max 64 chars, default from settings)
    influx_org_id: str | None
    influx_token: str | None
    tmp_pass: str | None  # Encrypted password for InfluxDB setup

    # Relationships
    inverters: List[Inverter] (one-to-many)
```

**Key Features**:
- Extends `SQLAlchemyBaseUserTable` from fastapi-users
- Stores InfluxDB credentials for multi-tenant isolation
- `tmp_pass` is encrypted and cleared after email verification
- Relationship to inverters provides cascade deletion capability

### Inverter Model

**Location**: `db.py:16-32`

```python
class Inverter(Base):
    id: int (primary key)
    user_id: int (foreign key → User.id)
    name: str (required)
    serial_logger: str (unique, required)  # Physical device identifier
    influx_bucked_id: str | None          # Links to InfluxDB bucket
    sw_version: str | None
    rated_power: int | None               # Watts
    number_of_mppts: int | None           # Maximum Power Point Trackers

    # Relationships
    users: User (many-to-one)
```

**Key Features**:
- `serial_logger` must be unique across all users
- Each inverter links to a dedicated InfluxDB bucket
- Metadata fields for device specifications

## Feature Specifications

### 1. User Registration & Verification

**Location**: `api/signup.py`

#### Registration Flow

**Endpoint**: `POST /signup`
**Rate Limit**: 3 requests/hour per IP
**Requirements**: CSRF token

**Process**:
1. User submits: first_name, last_name, email, password
2. Password validation (see Security section)
3. Password is hashed for PostgreSQL storage
4. Password is encrypted (Fernet) and stored in `tmp_pass`
5. User record created with `is_verified=False`
6. Verification email sent automatically
7. Returns success page

**Error Handling**:
- Email already registered → 422 error
- Invalid email address → SMTP refused, user deleted, 503 error
- Password validation failed → 422 error with reason

#### Email Verification Flow

**Endpoint**: `GET /verify?token=<jwt_token>`

**Process**:
1. JWT token decoded and validated
2. User marked as `is_verified=True`
3. `tmp_pass` decrypted
4. InfluxDB user, organization, and token created
5. `influx_org_id` and `influx_token` saved to user record
6. `tmp_pass` cleared (encrypt-then-delete pattern)
7. User automatically logged in via cookie
8. Redirect to dashboard

**Error Handling**:
- Token already used → Redirect to login
- Token invalid/expired → Error page
- InfluxDB setup fails → User still verified, admin notified via logs

**Security Note**: The encrypt-then-delete pattern ensures plaintext passwords are never persistently stored on disk.

### 2. Authentication

**Location**: `api/login.py`

#### Login

**Endpoint**: `POST /login`
**Rate Limit**: 5 requests/minute per IP
**Requirements**: CSRF token

**Process**:
1. User submits username (email) and password
2. Credentials authenticated via fastapi-users
3. Check user is active
4. JWT token generated and set as cookie
5. HTMX redirect to dashboard

**Error Response**: HTML alert component with error message

#### Logout

**Endpoint**: `GET /logout`

**Process**:
1. JWT token invalidated
2. Cookie cleared
3. Redirect to login page

#### Password Reset

**Request Reset**: `POST /request_reset_passwort`
**Rate Limit**: 5 requests/hour per IP
**Input**: Email address via HX-Prompt header

**Process**:
1. User email retrieved from database
2. Reset token generated (JWT)
3. Password reset email sent
4. Returns success message

**Reset Password**: `POST /reset_password`
**Requirements**: CSRF token

**Process**:
1. Token validated
2. New passwords verified to match
3. Password validation applied
4. Password updated
5. Returns success with login link

**Error Handling**:
- Invalid/expired token → 422 error
- Passwords don't match → 422 error
- Password validation failed → 422 error with reason

### 3. Inverter Management

**Location**: `api/inverter.py`, `inverter.py`

#### Add Inverter

**Endpoint**: `POST /inverter`
**Authentication**: Required (Cookie-based)
**Authorization**: Verified users only
**Requirements**: CSRF token

**Request Body**:
```json
{
  "name": "string",
  "serial": "string"
}
```

**Process**:
1. Verify user is authenticated and verified
2. Check InfluxDB credentials exist
3. Create Inverter record in PostgreSQL
4. Validate serial number uniqueness (database constraint)
5. Create dedicated InfluxDB bucket
6. Store bucket ID in inverter record
7. Return success page

**Error Handling**:
- User not verified → 403 Forbidden
- Missing InfluxDB credentials → 500 Internal Server Error
- Serial number exists → 422 Unprocessable Entity
- InfluxDB bucket creation fails → Rollback inverter creation, 503 Service Unavailable

**Rollback Strategy**: If InfluxDB bucket creation fails, the inverter record is deleted from PostgreSQL to maintain consistency.

#### Delete Inverter

**Endpoint**: `DELETE /inverter/{inverter_id}`
**Authentication**: Required (Cookie-based)

**Process**:
1. Retrieve inverter from database
2. Delete inverter from PostgreSQL
3. Delete InfluxDB bucket
4. Commit transaction

**Error Handling**:
- InfluxDB bucket deletion fails → Log error, continue with PostgreSQL deletion

**Note**: PostgreSQL deletion proceeds even if InfluxDB cleanup fails. Orphaned buckets can be cleaned up manually.

#### Get Inverter Token (External API)

**Endpoint**: `GET /influx_token?serial=<serial_number>`
**Authentication**: Required (Bearer token)
**Authorization**: Superuser only

**Response**:
```json
{
  "serial": "string",
  "token": "string",
  "bucket_id": "string",
  "bucket_name": "string",
  "org_id": "string",
  "is_metadata_complete": boolean
}
```

**Use Case**: External inverter devices call this endpoint to retrieve InfluxDB credentials for data submission.

**Error Handling**:
- Serial not found → 404 Not Found
- User not superuser → 403 Forbidden

#### View Inverters (Dashboard)

**Endpoint**: `GET /`
**Authentication**: Required (Cookie-based)
**Location**: `api/start.py`

**Response**: HTML page with:
- List of user's inverters
- Current power output (latest value from InfluxDB)
- Last update timestamp (humanized, German locale)
- "No current values" message if no data in last 24 hours

**Data Enrichment**:
- Queries InfluxDB for latest power values
- Uses 5-minute moving average over 10-minute period
- Queries last 24 hours of data
- Timestamps displayed in relative format (e.g., "vor 5 Minuten")

### 4. Account Management

**Location**: `api/account.py`

#### View Account

**Endpoint**: `GET /account`
**Authentication**: Required (Cookie-based)

**Response**: HTML page with account details and management forms

#### Change Email

**Endpoint**: `POST /account/change-email`
**Rate Limit**: 5 requests/hour per IP
**Requirements**: CSRF token

**Process**:
1. Verify new email is not already in use
2. Update user email in database
3. Set `is_verified=False`
4. Send verification email to new address
5. Return success message

**Error Handling**:
- Email already in use → 422 Unprocessable Entity
- User not authenticated → 401 Unauthorized

**Security Note**: User must re-verify their new email address before they can add inverters.

#### Change Password

**Endpoint**: `POST /account/change-password`
**Rate Limit**: 5 requests/hour per IP
**Requirements**: CSRF token

**Process**:
1. Verify current password
2. Validate new passwords match
3. Validate new password strength
4. Update password in PostgreSQL (hashed)
5. Update password in InfluxDB
6. Return success message

**Error Handling**:
- Current password wrong → 422 Unprocessable Entity
- Passwords don't match → 422 Unprocessable Entity
- Password validation failed → 422 error with reason
- InfluxDB update failed → 207 Multi-Status (partial success)

**Dual Password Management**: Passwords are updated in both FastAPI (hashed) and InfluxDB (for user's InfluxDB account).

#### Delete Account

**Endpoint**: `POST /account/delete`
**Rate Limit**: 3 requests/hour per IP
**Requirements**: CSRF token

**Process**:
1. Verify password
2. Retrieve all user's inverters
3. Delete all InfluxDB buckets
4. Delete user's InfluxDB organization
5. Delete all inverter records
6. Delete user record
7. Clear authentication cookie
8. Redirect to login with success message

**Error Handling**:
- Password wrong → 422 Unprocessable Entity
- User not authenticated → 401 Unauthorized
- InfluxDB cleanup errors logged but don't stop deletion

**Cleanup Strategy**: Complete cleanup of all user data from both PostgreSQL and InfluxDB.

### 5. Admin Interface

**Location**: `app.py:66`, `utils/admin_auth.py`

**Access URL**: `/admin`

#### Authentication

**Custom Backend**: `AdminAuth` class
**Session Lifetime**: 8 hours
**Token Type**: JWT with `is_superuser=True` claim

**Login Process**:
1. Admin submits credentials via SQLAdmin login form
2. Credentials validated via fastapi-users
3. User must have `is_superuser=True`
4. JWT token created with 8-hour expiration
5. Token stored in session

#### Admin Views

**User Admin** (`users.py:144-151`):
- Columns: ID, Email, Last Name
- Searchable: Email, Last Name
- Sortable: ID, Email
- Hidden: hashed_password

**Inverter Admin** (`inverter.py:41-54`):
- Columns: ID, Name
- Searchable: Name
- Sortable: ID, Name
- Auto-creates InfluxDB bucket on creation

#### Security

- JWT token validation on each request
- Expired tokens redirected to login
- Non-superusers blocked from access
- Session-based token storage

### 6. InfluxDB Integration

**Location**: `utils/influx.py`

#### InfluxManagement Class

**Context Manager**: Async with automatic client cleanup

**Connection Methods**:
1. Operator token (for user/org creation)
2. User token (for bucket operations)
3. Username/password (legacy)

#### Operations

**Create User and Organization**
**Method**: `create_influx_user_and_org(username, password)`

**Process**:
1. Create InfluxDB user with username (email)
2. Set user password
3. Create organization (named after email)
4. Add user as organization owner
5. Create authorization token with bucket read/write permissions
6. Return (user, org, token)

**Permissions**: Read and write access to all buckets in user's organization

**Create Bucket**
**Method**: `create_bucket(bucket_name, org_id, retention_seconds=63072000)`

**Process**:
1. Connect with user's token
2. Create bucket in user's organization with retention policy
3. Return bucket object with ID

**Retention Policy**: 2 years (63,072,000 seconds / 730 days) by default, configurable via `retention_seconds` parameter

**Update Bucket Retention**
**Method**: `update_bucket_retention(bucket_id, retention_seconds=63072000)`

**Process**:
1. Find bucket by ID
2. Update retention rules
3. Save updated bucket configuration

**Delete Bucket**
**Method**: `delete_bucket(bucket_id)`

**Query Latest Values**
**Method**: `get_latest_values(user, bucket_name)`

**Query**:
```flux
from(bucket:"<bucket_name>")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "grid")
  |> filter(fn: (r) => r["_field"] == "total_output_power")
  |> timedMovingAverage(every: 5m, period: 10m)
  |> last()
```

**Returns**: (timestamp, power_value)
**Raises**: `NoValuesException` if no data found

**Update User Password**
**Method**: `update_user_password(username, new_password)`

**Delete Organization**
**Method**: `delete_organization(org_id)`

### 7. Email System

**Location**: `utils/email.py`

#### Configuration

- **Template Engine**: Jinja2
- **Template Directory**: `solar_backend/templates/email/`
- **Library**: fastapi-mail
- **Format**: HTML with bilingual content (German/English)

#### Email Verification

**Function**: `send_verify_mail(email, token)`
**Template**: `verify_email.html`
**Subject**: "E-Mail-Adresse bestätigen / Verify Email Address - Deye Hard"

**Template Variables**:
- `verify_url`: Full URL with JWT token

**Link Format**: `{BASE_URL}/verify?token={jwt_token}`

#### Password Reset

**Function**: `send_reset_passwort_mail(email, token)`
**Template**: `reset_password.html`
**Subject**: "Passwort zurücksetzen / Reset Password - Deye Hard"

**Template Variables**:
- `reset_url`: Full URL with JWT token

**Link Format**: `{BASE_URL}/reset_passwort?token={jwt_token}`

#### Error Handling

Both functions return `True` on success, `False` on failure. Errors are logged with full exception information.

## API Endpoints

### Public Endpoints

| Method | Path | Description | Rate Limit |
|--------|------|-------------|------------|
| GET | `/signup` | Registration form | None |
| POST | `/signup` | Submit registration | 3/hour |
| GET | `/verify` | Email verification | None |
| GET | `/login` | Login form | None |
| POST | `/login` | Submit login | 5/minute |
| GET | `/logout` | Logout | None |
| POST | `/request_reset_passwort` | Request password reset | 5/hour |
| GET | `/reset_passwort` | Password reset form | None |
| POST | `/reset_password` | Submit new password | None |
| GET | `/healthcheck` | Health check | None |

### Authenticated Endpoints (Cookie-based)

| Method | Path | Description | Authorization |
|--------|------|-------------|---------------|
| GET | `/` | Dashboard | Any user |
| GET | `/add_inverter` | Add inverter form | Verified users |
| POST | `/inverter` | Create inverter | Verified users |
| DELETE | `/inverter/{id}` | Delete inverter | Owner |
| GET | `/account` | Account management | Any user |
| POST | `/account/change-email` | Change email | Any user |
| POST | `/account/change-password` | Change password | Any user |
| POST | `/account/delete` | Delete account | Any user |

### API Endpoints (Bearer token)

| Method | Path | Description | Authorization |
|--------|------|-------------|---------------|
| POST | `/auth/jwt/login` | Get JWT token | None |
| GET | `/influx_token` | Get inverter InfluxDB credentials | Superuser |
| GET | `/authenticated-route` | Test authentication | Any user |

### Admin Endpoints

| Path | Description | Authorization |
|------|-------------|---------------|
| `/admin` | Admin interface | Superuser |
| `/admin/user` | User management | Superuser |
| `/admin/inverter` | Inverter management | Superuser |

## Security Features

### 1. Password Security

**Validation Rules** (`users.py:33-52`):
- Minimum 8 characters
- At least 1 digit
- At least 1 uppercase letter
- Cannot be common password (password, 123456, 12345678, qwerty)

**Storage**:
- PostgreSQL: bcrypt hashed via fastapi-users
- InfluxDB: Native InfluxDB password storage
- Temporary: Fernet encrypted in `tmp_pass` field

**Encrypt-then-Delete Pattern**:
1. Password encrypted with Fernet during registration
2. Stored in `tmp_pass` field
3. Decrypted only during email verification
4. Immediately cleared after InfluxDB setup
5. Never persistently stored in plaintext

### 2. CSRF Protection

**Library**: fastapi-csrf-protect
**Token Header**: `HX-CSRF-Token`
**Secret**: `settings.AUTH_SECRET`

**Protected Endpoints**:
- All POST endpoints
- All DELETE endpoints
- All PUT/PATCH endpoints

**Exception Handler**: Returns 403 JSON response on CSRF validation failure

**Disabled In**: Testing mode (`WEB_DEV_TESTING=True`)

### 3. Rate Limiting

**Library**: slowapi
**Strategy**: IP-based (`get_remote_address`)

**Limits**:
| Endpoint | Limit | Reason |
|----------|-------|--------|
| POST /signup | 3/hour | Prevent spam registrations |
| POST /login | 5/minute | Prevent brute force attacks |
| POST /request_reset_passwort | 5/hour | Prevent email bombing |
| POST /account/change-email | 5/hour | Prevent abuse |
| POST /account/change-password | 5/hour | Prevent automated attacks |
| POST /account/delete | 3/hour | Prevent accidental deletions |

**Error Response**: 429 Too Many Requests with retry-after header

### 4. Authentication Security

**JWT Configuration**:
- Algorithm: HS256
- Secret: `settings.AUTH_SECRET` (min 32 bytes recommended)
- Lifetime: 2 days (172,800 seconds)
- Claims: user_id, email, is_superuser, is_active, is_verified

**Cookie Security**:
- Secure flag: Configurable via `COOKIE_SECURE` setting
- HttpOnly: Enabled
- SameSite: Strict
- Production recommendation: `COOKIE_SECURE=True`

**Bearer Token**:
- Header: `Authorization: Bearer <token>`
- Token URL: `/auth/jwt/login`

### 5. Authorization Checks

**User Verification Gate** (`api/inverter.py:33-51`, `70-94`):
- Inverter creation blocked for unverified users
- Returns 403 Forbidden
- Clear error message displayed

**Superuser Checks**:
- `/influx_token` endpoint requires superuser
- Admin interface requires superuser
- Validated in both JWT and database

**Ownership Validation**:
- Inverter operations check `user_id` matches authenticated user
- Organization-level isolation in InfluxDB

### 6. Input Validation

**Pydantic Models**:
- Email format validation
- Required field enforcement
- Type checking
- String length limits

**Database Constraints**:
- Unique email addresses
- Unique inverter serial numbers
- Foreign key constraints
- NOT NULL constraints

### 7. Logging & Monitoring

**Structured Logging**: structlog with JSON output

**Security Events Logged**:
- User registration
- Email verification
- Login attempts
- Password resets
- Password changes
- Account deletions
- InfluxDB setup failures
- Invalid tokens
- CSRF violations

**Log Fields**:
- user_id
- user_email
- event type
- timestamp
- error details (sanitized)

## Infrastructure

### Database Management

**PostgreSQL Setup**:
- Async SQLAlchemy engine
- Connection pooling
- Transaction management
- Migration tracking via Alembic

**InfluxDB Setup**:
- Operator token required for user/org management
- Per-user isolation via organizations
- Per-inverter buckets
- Token-based authentication

### Session Management

**DatabaseSessionManager** (`db.py:48-101`):
- Singleton pattern
- Context managers for connections and sessions
- Automatic rollback on exceptions
- Cleanup on application shutdown

### Migrations

**Alembic Configuration**:
- Auto-generation from models
- Version tracking
- Up/down migration support
- Environment-specific configurations

**Commands**:
```bash
# Create migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback
uv run alembic downgrade -1
```

### Docker Support

**Services**:
- backend: FastAPI application
- postgres: PostgreSQL database
- influxdb: InfluxDB 2.x

**Development Mode**:
- Source code volume-mounted
- Uvicorn auto-reload enabled
- No container rebuild needed for code changes

**Note**: Do NOT rebuild backend container in dev mode as it's designed for hot reload.

### Testing

**Test Framework**: pytest with async support
**Database**: SQLite in-memory (`sqlite+aiosqlite://`)
**Fixtures**: Function-scoped database recreation

**Test Markers**:
- `unit`: Unit tests
- `integration`: Integration tests
- `smoke`: Smoke tests

**InfluxDB Mocking**: `WEB_DEV_TESTING` flag bypasses InfluxDB operations

**Configuration**: Auto-loaded from `tests/test.env`

### Health Monitoring

**Endpoint**: `GET /healthcheck`
**Response**:
```json
{
  "FastAPI": "OK"
}
```

**Use Case**: Docker health checks, load balancer monitoring

**TODO**: Expand to include PostgreSQL and InfluxDB connectivity checks

## Configuration

### Environment Variables

**Required Variables**:

| Variable | Type | Description |
|----------|------|-------------|
| DATABASE_URL | PostgreSQL URL | Format: `postgresql+asyncpg://user:pass@host:port/db` |
| AUTH_SECRET | String (32+ bytes) | JWT signing secret |
| ENCRYPTION_KEY | Base64 String | Fernet encryption key for tmp_pass |
| INFLUX_URL | HTTP URL | InfluxDB instance URL |
| INFLUX_OPERATOR_TOKEN | String | InfluxDB operator token for user/org creation |
| BASE_URL | HTTP URL | Public URL for email links |
| FASTMAIL__MAIL_USERNAME | String | SMTP username |
| FASTMAIL__MAIL_PASSWORD | String | SMTP password |
| FASTMAIL__MAIL_FROM | Email | From address |
| FASTMAIL__MAIL_SERVER | String | SMTP server hostname |
| FASTMAIL__MAIL_PORT | Integer | SMTP server port |
| FASTMAIL__MAIL_FROM_NAME | String | Display name for emails |
| FASTMAIL__MAIL_STARTTLS | Boolean | Enable STARTTLS |
| FASTMAIL__MAIL_SSL_TLS | Boolean | Enable SSL/TLS |

**Optional Variables**:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| INFLUX_OPERATOR_ORG | String | "wtf" | InfluxDB operator organization |
| COOKIE_SECURE | Boolean | True | Secure flag for cookies |
| WEB_DEV_TESTING | Boolean | False | Disable InfluxDB operations for local dev |
| DEBUG | Boolean | False | SQLAlchemy echo mode |

### Configuration Loading

**File Path**: Specified via `ENV_FILE` environment variable
**Default**: `solar_backend/.env` (relative to config.py)
**Format**: Key=value pairs

**Example**:
```bash
export ENV_FILE=backend.env
uv run uvicorn solar_backend.app:app --reload
```

### Development Settings

**Local Development**:
```bash
WEB_DEV_TESTING=True    # Bypass InfluxDB
COOKIE_SECURE=False      # Allow HTTP cookies
DEBUG=True               # SQLAlchemy query logging
```

**Production Settings**:
```bash
WEB_DEV_TESTING=False
COOKIE_SECURE=True
DEBUG=False
```

### Email Configuration

**Nested Configuration**: Use double underscores for nested Pydantic models

**Example**:
```bash
FASTMAIL__MAIL_USERNAME=user@example.com
FASTMAIL__MAIL_PASSWORD=secret
FASTMAIL__MAIL_FROM=noreply@example.com
FASTMAIL__MAIL_SERVER=smtp.example.com
FASTMAIL__MAIL_PORT=587
FASTMAIL__MAIL_FROM_NAME="Deye Hard"
FASTMAIL__MAIL_STARTTLS=true
FASTMAIL__MAIL_SSL_TLS=false
FASTMAIL__USE_CREDENTIALS=true
FASTMAIL__VALIDATE_CERTS=true
FASTMAIL__SUPPRESS_SEND=false  # Set to true to prevent actual email sending
```

### InfluxDB Initial Setup

**One-time Setup** (detailed in README.md):

1. Start InfluxDB container
2. Access InfluxDB UI (http://localhost:8086)
3. Create initial user and organization
4. Generate operator token:
```bash
docker exec -it <container> sh
influx config create --config-name wtf --host-url http://localhost:8086 \
  --org wtf --token <admin_token> --active
influx auth create --org wtf --operator
```
5. Copy operator token to `INFLUX_OPERATOR_TOKEN`

**Operator Token Permissions**: Full admin access to create users, organizations, buckets

## Known Issues & Limitations

### Active Issues

1. ~~**Incomplete Metadata Endpoint**~~ ✅ **RESOLVED** (January 2025)
   - `POST /inverter_metadata/{serial_logger}` fully implemented
   - Complete SELECT query, error handling, logging
   - 8 passing tests covering all scenarios
   - See: `api/inverter.py:224-288`, tests: `tests/test_inverter_metadata.py`

2. ~~**InfluxDB Bucket Retention**~~ ✅ **RESOLVED** (January 2025)
   - 2-year retention policy implemented (63,072,000 seconds)
   - Applied automatically to all new buckets
   - `update_bucket_retention()` method available for existing buckets
   - See: `utils/influx.py:66-108`, tests: `tests/test_influx_retention.py`

3. **Cycle Import** (`utils/influx.py:6`)
   - Commented import of User model due to circular dependency
   - TODO: Refactor to resolve cycle

4. **Health Check Coverage** (`api/healthcheck.py`)
   - Only checks FastAPI is running
   - TODO: Add PostgreSQL and InfluxDB connectivity checks

5. **Logging Configuration** (`app.py:29`)
   - Only dev console renderer configured
   - TODO: Add production JSON renderer and log rotation

### Dependency Compatibility

**Pydantic 2.12+ and fastapi-mail 1.5.0 Incompatibility**:
- **Issue**: fastapi-mail 1.5.0 incompatible with Pydantic 2.12+
- **Error**: `AttributeError: 'ValidationInfo' object has no attribute 'multipart_subtype'`
- **Root Cause**: Schema validator uses incorrect API for Pydantic 2.12+
- **GitHub Issue**: https://github.com/sabuhish/fastapi-mail/issues/236
- **Workaround**: Pydantic constrained to `>=2.0.0,<2.12` in `pyproject.toml:20`
- **Action Required**: Remove constraint when fastapi-mail 1.6.0+ is released

### Test Environment Considerations

- InfluxDB operations bypassed when `WEB_DEV_TESTING=True`
- SQLite in-memory database doesn't support all PostgreSQL features
- HTMX templates must be initialized in test setup
- CSRF protection disabled in test mode

## Appendix

### Glossary

- **Inverter**: Solar power inverter device that converts DC to AC power
- **Serial Logger**: Unique identifier for physical inverter device
- **Bucket**: InfluxDB time-series data container
- **Organization**: InfluxDB tenant isolation unit
- **MPPT**: Maximum Power Point Tracker, optimizes solar panel output
- **Operator Token**: InfluxDB admin token with full management permissions
- **Encrypt-then-Delete**: Security pattern where sensitive data is encrypted for temporary storage then permanently deleted

### Related Documentation

- [CLAUDE.md](./CLAUDE.md) - Development guide for Claude Code
- [README.md](./README.md) - Setup and installation instructions
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [InfluxDB 2.x Documentation](https://docs.influxdata.com/influxdb/v2/)
- [fastapi-users Documentation](https://fastapi-users.github.io/fastapi-users/)

### Version History

- **1.0** (October 2025): Initial specification document
  - Complete feature documentation
  - API endpoint specifications
  - Security feature documentation
  - Configuration guide

---

**Document Maintenance**: This specification should be updated whenever significant features are added, modified, or deprecated. Update the version number and date at the top of the document.
