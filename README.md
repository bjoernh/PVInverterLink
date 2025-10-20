# Deye Hard Backend

> FastAPI-based solar inverter management system with multi-tenant TimescaleDB storage

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)
![TimescaleDB](https://img.shields.io/badge/TimescaleDB-PostgreSQL-orange.svg)
![Rust](https://img.shields.io/badge/Rust-Collector-red.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)

## Overview

Deye Hard Backend is a multi-tenant solar inverter monitoring and data collection system that provides real-time and historical power generation data. The system supports multiple inverter types through different integration methods while maintaining strict data isolation between users.

### Key Features

- **Multi-Tenant Architecture**: TimescaleDB with Row-Level Security (RLS) for automatic user data isolation
- **Deye Inverter Support**: High-performance Rust collector using Solarman V5 protocol
- **OpenDTU Integration**: HTTP API for Hoymiles microinverters via OpenDTU firmware
- **Real-Time Monitoring**: Interactive web dashboard with live power data
- **Time-Series Storage**: Automatic data compression and 2-year retention policy
- **Comprehensive API**: RESTful API with interactive documentation
- **Modern Web UI**: HTMX-powered interface with responsive design
- **Secure Authentication**: JWT-based authentication with rate limiting and CSRF protection

## Supported Inverter Types

### Deye Inverters (Primary Support)

Deye inverters communicate via Solarman data loggers using a proprietary TCP protocol. The system includes a high-performance Rust collector that:

- Listens on TCP port 10000 for Solarman logger connections
- Decodes Solarman V5 protocol packets
- Validates checksums and message integrity
- Forwards telemetry data into the timescaledb

**Documentation**: See [`collector/README.md`](./collector/README.md) for detailed collector setup and protocol information.

### OpenDTU Devices

OpenDTU is open-source firmware for ESP32 microcontrollers that communicates with Hoymiles microinverters. Integration is achieved through HTTP push:

- ESP32 with OpenDTU firmware pushes data via HTTP POST
- Endpoint: `POST /api/opendtu/measurements`
- Authentication via `X-API-Key` header
- Supports multiple inverters per DTU
- Comprehensive measurement data including DC channels

**Firmware**: Use the forked OpenDTU repository with HTTP push feature: https://github.com/bjoernh/OpenDTU

**Configuration**: Configure the HTTP push target in OpenDTU's web interface to point to your backend API endpoint. See the forked repository for detailed configuration instructions.

## Technology Stack

### Backend
- **FastAPI 0.115+**: Modern async web framework
- **Python 3.13+**: Runtime environment
- **Uvicorn**: ASGI server
- **Pydantic**: Data validation and settings

### Database
- **PostgreSQL + TimescaleDB**: Time-series database extension
- **SQLAlchemy 2.x**: Async ORM with declarative models
- **Alembic**: Database migration management
- **Row-Level Security (RLS)**: Multi-tenant data isolation

### Collector (Deye Support)
- **Rust**: High-performance systems language
- **Tokio**: Async runtime
- **Solarman V5 Protocol**: Custom TCP protocol decoder
- **TCP Server**: Port 10000 listener

### Frontend
- **HTMX**: Dynamic HTML interactions without JavaScript
- **Jinja2**: Server-side templating
- **DaisyUI + Tailwind CSS**: Modern UI components and styling
- **Plotly**: Interactive charts and visualizations

### Authentication & Security
- **fastapi-users**: User management framework
- **JWT**: Token-based authentication (2-day lifetime)
- **CSRF Protection**: fastapi-csrf-protect middleware
- **Rate Limiting**: slowapi for endpoint throttling
- **Fernet Encryption**: Symmetric encryption for sensitive data

### Development Tools
- **uv**: Fast Python package manager
- **Docker & Docker Compose**: Containerized development
- **pytest**: Async test framework

## Quick Start

### Prerequisites

```bash
# Docker and Docker Compose
# Install from: https://docs.docker.com/get-docker/

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Rust (for collector development, optional)
# Install from: https://rustup.rs/
```

### Docker Development (Recommended)

```bash
# Clone repository with submodules
git clone --recursive <repository-url>
cd solar-backend

# Start all services (backend + TimescaleDB)
docker-compose up -d

# Run database migrations
docker-compose exec backend uv run alembic upgrade head

# Access the application
# - Web UI: http://localhost:8000
# - API Documentation: http://localhost:8000/docs
# - Admin Interface: http://localhost:8000/admin
```

### Local Development

```bash
# Install dependencies
uv sync

# Configure environment
cp backend.env.example backend.env
# Edit backend.env with your settings

# Set environment variable
export ENV_FILE=backend.env

# Start TimescaleDB (if not using Docker for everything)
docker-compose up -d db

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn solar_backend.app:app --reload
```

## Deye Collector Setup

### Building the Collector

```bash
cd collector

# Development build
cargo build

# Release build (optimized)
cargo build --release

# Run tests
cargo test
```

### Configuration

Create `collector/.env`:

```bash
PORT=10000
BACKEND_URL=http://localhost:8000
API_KEY=your-api-key-here
RUST_LOG=info
```

### Running the Collector

```bash
# Using cargo
cargo run --release

# Or using Docker
docker-compose -f collector/docker-compose.yml up -d
```

### How It Works

1. **Deye Inverter** sends telemetry via Solarman data logger
2. **Solarman Logger** forwards data to Collector TCP port 10000
3. **Rust Collector** decodes Solarman V5 protocol packets
4. **Rust Collector** stores measurements in TimescaleDB

For detailed collector documentation, protocol specifications, and troubleshooting, see [`collector/README.md`](./collector/README.md).

## OpenDTU Setup

### Requirements

- ESP32 microcontroller with OpenDTU-compatible hardware
- Modified OpenDTU firmware with HTTP push feature

### Firmware Installation

#### A) Pre Build generic_esp32 firmware
Download `firmware.http-push.bin` from [https://github.com/bjoernh/OpenDTU](https://github.com/bjoernh/OpenDTU)

Flash the file in OpenDTU's web interface (Settings -> Firmware Upgrade)

#### B) Build from Source
1. Download firmware from forked repository: https://github.com/bjoernh/OpenDTU
2. Follow the repository's flashing instructions for your ESP32 hardware
3. Configure WiFi settings via OpenDTU's initial setup wizard

### Configuration

Configure HTTP push in OpenDTU's web interface (Settings > HTTP Push Settings):

![screenshot of dtu config](./img/opendtu-config.jpg)

```
Target URL: http://your-backend-host:8000/api/opendtu/measurements
Publish Interval: 60
Authentication Header Name: X-API-Key 
Authentication Token: your-api-key-here
```

The OpenDTU device will automatically push measurement data at regular intervals.
## Configuration

### Required Environment Variables

Create a `backend.env` file with the following settings:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | TimescaleDB connection string | `postgresql+asyncpg://user:pass@localhost:5432/deyehard` |
| `AUTH_SECRET` | JWT signing secret (32+ bytes) | `your-secret-key-min-32-characters-long` |
| `ENCRYPTION_KEY` | Fernet encryption key (base64) | `6DLfBB4KnMuChUJZsMHWz2kJTtNRNTTtoTCCbH7CYyw=` |
| `BASE_URL` | Public URL for email links | `http://localhost:8000` |
| `API_KEY` | API key for collectors/OpenDTU | `your-secure-api-key-here` |
| `COOKIE_SECURE` | Secure flag for cookies | `False` (dev), `True` (production) |

### Email Configuration (Optional)

For user registration and password reset emails:

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
FASTMAIL__SUPPRESS_SEND=false
```

### Development Settings

```bash
COOKIE_SECURE=False      # Allow HTTP cookies in development
DEBUG=False              # Enable SQLAlchemy query logging if True
```

See `backend.env.example` for a complete configuration template.

## Database Setup

### TimescaleDB Extension

The TimescaleDB extension is automatically enabled when using the Docker setup. For manual PostgreSQL installations:

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

### Running Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Create a new migration after model changes
uv run alembic revision --autogenerate -m "description of changes"

# Rollback one migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

### Database Architecture

- **Hypertable**: `inverter_measurements` with 7-day time-based chunks
- **Multi-dimensional Partitioning**: By time and user_id (4 space partitions)
- **Row-Level Security (RLS)**: Automatic user data isolation at database level
- **Automatic Compression**: Data compressed after 7 days
- **Retention Policy**: 2-year data retention

The RLS policy ensures users can only access their own data, even if application-level authorization fails. The database automatically filters queries based on the `app.current_user_id` session variable.

## API Documentation

### OpenDTU Measurements Endpoint

Send measurement data from OpenDTU devices:

**Endpoint:** `POST /api/opendtu/measurements`

**Authentication:** API Key in `X-API-Key` header

**Request Example:**

```bash
curl -X POST "http://localhost:8000/api/opendtu/measurements" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-10-19T17:54:43+02:00",
    "dtu_serial": "145680140006",
    "inverters": [{
      "serial": "116166771004",
      "name": "Inverter 1",
      "reachable": true,
      "producing": true,
      "last_update": 1760889277,
      "measurements": {
        "power_ac": 16.1,
        "voltage_ac": 229.8,
        "current_ac": 0.07,
        "frequency": 49.99,
        "power_factor": 0.617,
        "power_dc": 17
      },
      "dc_channels": [{
        "channel": 1,
        "name": "Panel 1",
        "power": 3.4,
        "voltage": 30.4,
        "current": 0.11,
        "yield_day": 337,
        "yield_total": 444.671,
        "irradiation": 1.545455
      }]
    }]
  }'
```

**Response (201 Created):**

```json
{
  "dtu_serial": "199980140256",
  "timestamp": "2025-10-19T17:54:43+02:00",
  "total_inverters": 1,
  "success_count": 1,
  "error_count": 0,
  "results": [{
    "serial": "116183771004",
    "status": "ok",
    "inverter_id": 1,
    "power_ac": 16
  }]
}
```

**Status Codes:**
- `201 Created`: All inverters processed successfully
- `207 Multi-Status`: Some inverters succeeded, some failed
- `404 Not Found`: All inverters not found in database
- `401 Unauthorized`: Invalid or missing API key

### Interactive API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

The interactive documentation provides full API specifications, request/response schemas, and a testing interface.

## Testing

```bash
# Run all tests
uv run pytest

# Run tests by marker
uv run pytest -m unit          # Unit tests only
uv run pytest -m integration   # Integration tests
uv run pytest -m smoke         # Smoke tests

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_measurements_api_key.py

# Run with coverage report
uv run pytest --cov=solar_backend
```

**Note**: Test configuration is automatically loaded from `tests/test.env`. No manual environment setup required.

### Test Coverage

- ✅ Authentication & authorization
- ✅ User registration & email verification
- ✅ Inverter CRUD operations
- ✅ OpenDTU measurements API
- ✅ Time-series data queries
- ✅ Multi-tenant data isolation
- ✅ Rate limiting
- ✅ Concurrent request handling

## Project Structure

```
solar-backend/
├── collector/                    # Rust collector (git submodule)
│   ├── src/                     # Solarman V5 protocol implementation
│   │   ├── protocol/            # Packet decoder, control codes
│   │   ├── server/              # TCP server
│   │   └── ...
│   ├── Cargo.toml               # Rust dependencies
│   ├── README.md                # Collector documentation
│   └── DEPLOYMENT.md            # Deployment guide
│
├── solar_backend/               # Python backend
│   ├── api/                     # API endpoint modules
│   │   ├── measurements.py      # OpenDTU endpoint
│   │   ├── inverter.py          # Inverter management
│   │   ├── dashboard.py         # Dashboard data
│   │   ├── signup.py            # User registration
│   │   ├── login.py             # Authentication
│   │   ├── account.py           # Account management
│   │   └── start.py             # Homepage
│   │
│   ├── utils/                   # Utility modules
│   │   ├── timeseries.py        # TimescaleDB operations
│   │   ├── email.py             # Email sending
│   │   ├── crypto.py            # Encryption utilities
│   │   └── admin_auth.py        # Admin authentication
│   │
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── email/               # Email templates
│   │   └── ...
│   │
│   ├── app.py                   # FastAPI application setup
│   ├── db.py                    # SQLAlchemy models
│   ├── config.py                # Pydantic settings
│   ├── users.py                 # User management
│   └── schemas.py               # Pydantic validation models
│
├── tests/                       # Pytest test suite
│   ├── integration/             # Integration tests
│   ├── unit/                    # Unit tests
│   ├── conftest.py              # Test fixtures
│   └── ...
│
├── alembic/                     # Database migrations
│   └── versions/                # Migration scripts
│
├── docker-compose.yml           # Docker services configuration
├── pyproject.toml               # Python dependencies (uv)
├── Dockerfile                   # Backend container
├── CLAUDE.md                    # Development guide for Claude Code
├── SPEC.md                      # System specification
└── README.md                    # This file
```

## Development Workflow

### Adding New Features

1. **Modify Database Models**: Update models in `solar_backend/db.py`
2. **Generate Migration**: `uv run alembic revision --autogenerate -m "description"`
3. **Review Migration**: Check generated file in `alembic/versions/`
4. **Apply Migration**: `uv run alembic upgrade head`
5. **Add API Endpoints**: Create/update files in `solar_backend/api/`
6. **Write Tests**: Add tests in `tests/`
7. **Run Tests**: `uv run pytest`

### Important Development Notes

- **Don't rebuild the backend Docker container in dev mode**: The code directory is volume-mounted with uvicorn's `--reload` flag, so changes are detected automatically
- **Use RLS Context**: Always call `set_rls_context(session, user_id)` before time-series queries in production code
- **Reset RLS**: Always call `reset_rls_context(session)` after queries to clean up session state
- **HTMX Templates**: Must be initialized in test setup with correct path

### Code Style

- Follow PEP 8 for Python code
- Use type hints for function signatures
- Write docstrings for public functions and classes
- Keep functions focused and single-purpose
- Use async/await for I/O operations

## Architecture

### Multi-Tenant Data Isolation

```
User A                           User B
├─ Inverter 1                    ├─ Inverter 3
│  └─ Measurements               │  └─ Measurements
└─ Inverter 2                    └─ Inverter 4
   └─ Measurements                  └─ Measurements

TimescaleDB Hypertable (inverter_measurements)
├─ Partitioned by time (7-day chunks)
├─ Partitioned by user_id (4 space partitions)
└─ RLS Policy: user_id = app.current_user_id
```

Data isolation is enforced at the database level through Row-Level Security. Even if application logic fails, users cannot access other users' data.

### Data Flow - Deye Inverters

```
Deye Inverter
    ↓
Solarman Data Logger (TCP client)
    ↓
Rust Collector (TCP server on port 10000)
    ├─ Decode Solarman V5 protocol
    ├─ Validate checksums
    └─ Extract telemetry data
    ↓
TimescaleDB (Multi-tenant storage)
    ├─ Partition by user_id
    ├─ Compress after 7 days
    └─ Retain for 2 years
```

### Data Flow - OpenDTU Devices

```
Hoymiles Microinverter
    ↓
OpenDTU (ESP32 microcontroller)
    ├─ Collect inverter telemetry
    ├─ Format as JSON payload
    └─ HTTP POST to backend
    ↓
Backend API (/api/opendtu/measurements)
    ├─ Validate API key (X-API-Key header)
    ├─ Parse multi-inverter payload
    ├─ Match inverters by serial number
    └─ Set RLS context per user
    ↓
TimescaleDB (Multi-tenant storage)
    └─ Same storage as Deye inverters
```

## Deployment

### Production Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:strong-password@prod-host:5432/deyehard

# Security
AUTH_SECRET=generate-strong-random-secret-min-32-characters
ENCRYPTION_KEY=generate-fernet-key-base64-encoded
API_KEY=generate-strong-random-api-key-for-collectors

# Application
COOKIE_SECURE=True
BASE_URL=https://yourdomain.com

# Email (if using)
FASTMAIL__MAIL_SERVER=smtp.yourdomain.com
FASTMAIL__MAIL_FROM=noreply@yourdomain.com
# ... other email settings
```

### Docker Deployment

```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d

# Run database migrations
docker-compose exec backend uv run alembic upgrade head

# View logs
docker-compose logs -f backend

# Check health
curl http://localhost:8000/healthcheck
```

### Security Checklist

- Set `COOKIE_SECURE=True` in production
- Use strong random values for `AUTH_SECRET`, `ENCRYPTION_KEY`, and `API_KEY`
- Enable HTTPS/TLS for all endpoints (use reverse proxy like nginx or Traefik)
- Configure firewall to allow only necessary ports (80, 443, 10000 for collector)
- Use strong database passwords (avoid default credentials)
- Regularly update dependencies: `uv sync --upgrade`
- Monitor application logs for security events
- Implement backup strategy for TimescaleDB
- Restrict admin interface access (IP whitelist or VPN)
- Rotate API keys periodically

### Monitoring

The system uses structured logging with `structlog`. Key events logged:

- User registration and verification
- Login attempts (successful and failed)
- Measurement data ingestion
- Database errors
- API authentication failures
- RLS context operations

Configure log aggregation in production (e.g., ELK stack, Grafana Loki, or CloudWatch).

## Related Documentation

- **[CLAUDE.md](./CLAUDE.md)**: Comprehensive development guide for working with Claude Code
- **[collector/README.md](./collector/README.md)**: Rust collector documentation and protocol details
- **[collector/DEPLOYMENT.md](./collector/DEPLOYMENT.md)**: Collector deployment and configuration guide
- **[OpenDTU Fork](https://github.com/bjoernh/OpenDTU)**: Modified OpenDTU firmware with HTTP push
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)**: FastAPI framework reference
- **[TimescaleDB Documentation](https://docs.timescale.com/)**: TimescaleDB time-series features

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Write or update tests for your changes
5. Ensure all tests pass: `uv run pytest`
6. Commit your changes: `git commit -m "feat: add your feature"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Submit a pull request

### Commit Message Convention

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions or modifications
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

## License

TBD

## Authors

**Björn Hauffe**
WTF Kooperative eG

## Acknowledgments

- OpenDTU project for the excellent ESP32 firmware
- TimescaleDB team for the powerful time-series extension
- FastAPI community for the amazing web framework
