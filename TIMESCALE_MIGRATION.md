# TimescaleDB Migration Plan

## Overview

This document provides a step-by-step plan to migrate from InfluxDB to PostgreSQL + TimescaleDB for time-series data storage. The migration implements multi-tenant partitioning with Row-Level Security for data isolation.

**Timeline**: 1-2 days
**Risk Level**: Medium (no production data to migrate)
**Rollback**: Git branch allows easy rollback

---

## Pre-Migration Checklist

- [ ] All tests passing on master branch
- [ ] Current docker-compose setup working
- [ ] No production data (confirmed: fresh start is acceptable)
- [ ] Team reviewed this plan

---

## Phase 0: Preparation (15 minutes)

### Step 0.1: Create Feature Branch

```bash
# Create and switch to feature branch
git checkout -b feature/timescaledb-migration

# Verify branch
git branch
```

### Step 0.2: Backup Current State

```bash
# Backup database schema (if needed)
docker-compose exec db pg_dump -U deyehard --schema-only deyehard > backup_schema_pre_migration.sql

# Commit current state
git add -A
git commit -m "chore: Snapshot before TimescaleDB migration"
```

### Step 0.3: Document Current Architecture

Take note of:
- Current InfluxDB URL and credentials
- Number of users in system
- External systems that write to InfluxDB (inverters/collectors)

---

## Phase 1: Database Infrastructure (30 minutes)

### Step 1.1: Update Docker Compose

**File**: `docker-compose.yml`

**Changes**:
```yaml
services:
  db:
    image: timescale/timescaledb:latest-pg16  # Changed from postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: deyehard
      POSTGRES_PASSWORD: dev-testing-ok
      POSTGRES_DB: deyehard
    ports:
      - 5432:5432
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U deyehard"]
      interval: 2s

  # Remove or comment out influxdb service (keep for rollback during testing)
  # influxdb:
  #   image: "influxdb:2.7-alpine"
  #   ...

volumes:
  pgdata:
  # influxdb:  # Comment out for now
```

**Commit**:
```bash
git add docker-compose.yml
git commit -m "feat: Switch to TimescaleDB image in docker-compose"
```

### Step 1.2: Restart Database with TimescaleDB

```bash
# Stop all services
docker-compose down

# Remove old PostgreSQL volume (fresh start)
docker volume rm solar-backend_pgdata

# Start database
docker-compose up -d db

# Wait for health check
docker-compose ps

# Verify TimescaleDB is installed
docker-compose exec db psql -U deyehard -d deyehard -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
docker-compose exec db psql -U deyehard -d deyehard -c "\dx"
# Should show timescaledb extension
```

**Expected Output**:
```
                                      List of installed extensions
    Name     | Version |   Schema   |                        Description
-------------+---------+------------+-----------------------------------------------------------
 plpgsql     | 1.0     | pg_catalog | PL/pgSQL procedural language
 timescaledb | 2.x.x   | public     | Enables scalable inserts and complex queries for time-series data
```

### Step 1.3: Initialize Application Database

```bash
# Run existing migrations to create User and Inverter tables
uv run alembic upgrade head
```

---

## Phase 2: Database Schema Changes (1 hour)

### Step 2.1: Create Alembic Migration

```bash
# Generate migration
uv run alembic revision -m "feat: Add time-series table and remove InfluxDB fields"
```

**File**: `alembic/versions/XXXXX_feat_add_time_series_table.py`

**Content**:
```python
"""feat: Add time-series table and remove InfluxDB fields

Revision ID: XXXXX
Revises: YYYYY
Create Date: 2025-10-17

Changes:
1. Remove InfluxDB-specific fields from User and Inverter models
2. Create inverter_measurements table for time-series data
3. Configure TimescaleDB hypertable with multi-dimensional partitioning
4. Enable Row-Level Security for multi-tenant isolation
5. Set up compression and retention policies
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'XXXXX'
down_revision = 'YYYYY'  # Update with actual previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Remove InfluxDB fields from User table
    op.drop_column('user', 'influx_url')
    op.drop_column('user', 'influx_org_id')
    op.drop_column('user', 'influx_token')
    # Note: Keep tmp_pass if used for other purposes, otherwise remove
    # op.drop_column('user', 'tmp_pass')

    # Step 2: Remove InfluxDB fields from Inverter table
    op.drop_column('inverter', 'influx_bucked_id')

    # Step 3: Create time-series measurements table
    op.create_table(
        'inverter_measurements',
        sa.Column('time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('inverter_id', sa.Integer(), nullable=False),
        sa.Column('total_output_power', sa.Integer(), nullable=False),
        # Optional: Add more measurement fields as needed
        # sa.Column('grid_voltage', sa.Numeric(6, 2), nullable=True),
        # sa.Column('grid_frequency', sa.Numeric(5, 2), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inverter_id'], ['inverter.id'], ondelete='CASCADE'),
    )

    # Step 4: Convert to TimescaleDB hypertable with multi-dimensional partitioning
    op.execute("""
        SELECT create_hypertable(
            'inverter_measurements',
            'time',
            partitioning_column => 'user_id',
            number_partitions => 4,
            chunk_time_interval => INTERVAL '7 days'
        );
    """)

    # Step 5: Create indexes for performance
    op.create_index(
        'idx_user_time',
        'inverter_measurements',
        ['user_id', sa.text('time DESC')],
        unique=False
    )
    op.create_index(
        'idx_inverter_time',
        'inverter_measurements',
        ['inverter_id', sa.text('time DESC')],
        unique=False
    )

    # Step 6: Enable Row-Level Security
    op.execute("""
        ALTER TABLE inverter_measurements ENABLE ROW LEVEL SECURITY;
    """)

    # Step 7: Create RLS policy for tenant isolation
    op.execute("""
        CREATE POLICY user_isolation_policy ON inverter_measurements
            FOR ALL
            USING (user_id = current_setting('app.current_user_id', true)::int);
    """)

    # Step 8: Configure compression (after 7 days)
    op.execute("""
        ALTER TABLE inverter_measurements SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'user_id, inverter_id',
            timescaledb.compress_orderby = 'time DESC'
        );
    """)

    op.execute("""
        SELECT add_compression_policy('inverter_measurements', INTERVAL '7 days');
    """)

    # Step 9: Set retention policy (2 years)
    op.execute("""
        SELECT add_retention_policy('inverter_measurements', INTERVAL '730 days');
    """)


def downgrade() -> None:
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS user_isolation_policy ON inverter_measurements;")

    # Drop indexes
    op.drop_index('idx_inverter_time', table_name='inverter_measurements')
    op.drop_index('idx_user_time', table_name='inverter_measurements')

    # Drop table (also removes hypertable)
    op.drop_table('inverter_measurements')

    # Restore InfluxDB fields to Inverter
    op.add_column('inverter', sa.Column('influx_bucked_id', sa.String(), nullable=True))

    # Restore InfluxDB fields to User
    op.add_column('user', sa.Column('influx_token', sa.String(), nullable=True))
    op.add_column('user', sa.Column('influx_org_id', sa.Column(), nullable=True))
    op.add_column('user', sa.Column('influx_url', sa.String(64), nullable=True))
```

### Step 2.2: Run Migration

```bash
# Apply migration
uv run alembic upgrade head

# Verify table structure
docker-compose exec db psql -U deyehard -d deyehard -c "\d inverter_measurements"
docker-compose exec db psql -U deyehard -d deyehard -c "SELECT * FROM timescaledb_information.hypertables;"
docker-compose exec db psql -U deyehard -d deyehard -c "SELECT * FROM timescaledb_information.jobs;"
```

**Expected Output**:
- Table `inverter_measurements` exists
- Hypertable configured with 4 space partitions
- Compression and retention policies active

**Commit**:
```bash
git add alembic/versions/
git commit -m "feat: Add TimescaleDB time-series table and remove InfluxDB fields"
```

---

## Phase 3: Update Database Models (30 minutes)

### Step 3.1: Update User Model

**File**: `solar_backend/db.py`

**Remove from User class**:
```python
# DELETE these lines:
influx_url: Mapped[str] = mapped_column(String(64), default=settings.INFLUX_URL)
influx_org_id: Mapped[Optional[str]]
influx_token: Mapped[Optional[str]]
```

**Keep**:
- `tmp_pass` (can be removed later if not needed for other purposes)

### Step 3.2: Update Inverter Model

**File**: `solar_backend/db.py`

**Remove from Inverter class**:
```python
# DELETE this line:
influx_bucked_id: Mapped[Optional[str]]
```

### Step 3.3: Add Measurement Model

**File**: `solar_backend/db.py`

**Add new model**:
```python
from datetime import datetime

class InverterMeasurement(Base):
    __tablename__ = "inverter_measurements"

    time: Mapped[datetime] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    inverter_id: Mapped[int] = mapped_column(ForeignKey("inverter.id"), primary_key=True)
    total_output_power: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships (optional, for ORM convenience)
    user = relationship("User", lazy="noload")
    inverter = relationship("Inverter", lazy="noload")

    def __repr__(self):
        return f"<Measurement(time={self.time}, inverter={self.inverter_id}, power={self.total_output_power})>"
```

**Commit**:
```bash
git add solar_backend/db.py
git commit -m "feat: Update models - remove InfluxDB fields, add InverterMeasurement"
```

---

## Phase 4: Create Time-Series Utility Layer (2 hours)

### Step 4.1: Create TimescaleDB Utils

**File**: `solar_backend/utils/timeseries.py` (NEW FILE)

**Content**:
```python
"""
Time-series data utilities for TimescaleDB.

Replaces solar_backend/utils/influx.py with PostgreSQL/TimescaleDB queries.
"""
import structlog
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class TimeSeriesException(Exception):
    """Base exception for time-series operations."""
    pass


class NoDataException(TimeSeriesException):
    """Raised when query returns no data."""
    pass


async def write_measurement(
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
    timestamp: datetime,
    total_output_power: int
) -> None:
    """
    Write a single measurement point to TimescaleDB.

    Args:
        session: Database session
        user_id: User ID (for partitioning and RLS)
        inverter_id: Inverter ID
        timestamp: Measurement timestamp (with timezone)
        total_output_power: Power in Watts

    Raises:
        TimeSeriesException: If write fails
    """
    try:
        stmt = text("""
            INSERT INTO inverter_measurements (time, user_id, inverter_id, total_output_power)
            VALUES (:time, :user_id, :inverter_id, :power)
            ON CONFLICT DO NOTHING
        """)

        await session.execute(stmt, {
            "time": timestamp,
            "user_id": user_id,
            "inverter_id": inverter_id,
            "power": total_output_power
        })
        await session.commit()

        logger.debug(
            "Measurement written",
            user_id=user_id,
            inverter_id=inverter_id,
            power=total_output_power
        )
    except Exception as e:
        await session.rollback()
        logger.error(
            "Failed to write measurement",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id
        )
        raise TimeSeriesException(f"Failed to write measurement: {str(e)}") from e


async def get_latest_value(
    session: AsyncSession,
    user_id: int,
    inverter_id: int
) -> tuple[datetime, int]:
    """
    Get the latest power measurement for an inverter.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        Tuple of (timestamp, power_value)

    Raises:
        NoDataException: If no data found
    """
    try:
        query = text("""
            SELECT time, total_output_power
            FROM inverter_measurements
            WHERE user_id = :user_id
              AND inverter_id = :inverter_id
              AND time > NOW() - INTERVAL '24 hours'
            ORDER BY time DESC
            LIMIT 1
        """)

        result = await session.execute(query, {
            "user_id": user_id,
            "inverter_id": inverter_id
        })

        row = result.first()
        if not row:
            raise NoDataException(f"No data found for inverter {inverter_id}")

        return (row.time, int(row.total_output_power))

    except NoDataException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get latest value",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id
        )
        raise TimeSeriesException(f"Failed to query latest value: {str(e)}") from e


async def get_power_timeseries(
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
    time_range: str = "24h"
) -> list[dict]:
    """
    Get time-series power data with automatic time bucketing.

    Args:
        session: Database session with RLS context set
        user_id: User ID (for partition pruning)
        inverter_id: Inverter ID
        time_range: Time range (1h, 6h, 24h, 7d, 30d)

    Returns:
        List of dicts with 'time' (ISO string) and 'power' (int)

    Raises:
        NoDataException: If no data found
        TimeSeriesException: On query error
    """
    # Map time range to bucket size
    bucket_sizes = {
        "1h": "1 minute",
        "6h": "5 minutes",
        "24h": "10 minutes",
        "7d": "1 hour",
        "30d": "4 hours"
    }

    bucket = bucket_sizes.get(time_range, "5 minutes")

    try:
        query = text("""
            SELECT
                time_bucket(:bucket, time) AS bucket_time,
                AVG(total_output_power)::int AS power
            FROM inverter_measurements
            WHERE user_id = :user_id
              AND inverter_id = :inverter_id
              AND time > NOW() - INTERVAL :range
            GROUP BY bucket_time
            ORDER BY bucket_time ASC
        """)

        result = await session.execute(query, {
            "bucket": bucket,
            "user_id": user_id,
            "inverter_id": inverter_id,
            "range": time_range
        })

        data_points = [
            {
                "time": row.bucket_time.isoformat(),
                "power": row.power if row.power is not None else 0
            }
            for row in result
        ]

        if not data_points:
            logger.warning(
                "No time-series data found",
                user_id=user_id,
                inverter_id=inverter_id,
                time_range=time_range
            )
            raise NoDataException(f"No data for time range {time_range}")

        logger.info(
            "Retrieved time-series data",
            user_id=user_id,
            inverter_id=inverter_id,
            time_range=time_range,
            data_points=len(data_points)
        )

        return data_points

    except NoDataException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get time-series data",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
            time_range=time_range
        )
        raise TimeSeriesException(f"Failed to query time-series: {str(e)}") from e


async def get_today_energy_production(
    session: AsyncSession,
    user_id: int,
    inverter_id: int
) -> float:
    """
    Calculate today's energy production in kWh using trapezoidal integration.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        Energy produced today in kWh
    """
    try:
        query = text("""
            WITH power_data AS (
                SELECT
                    time,
                    total_output_power,
                    EXTRACT(EPOCH FROM time - LAG(time) OVER (ORDER BY time)) AS time_diff_seconds
                FROM inverter_measurements
                WHERE user_id = :user_id
                  AND inverter_id = :inverter_id
                  AND time >= DATE_TRUNC('day', NOW())
                ORDER BY time
            )
            SELECT
                COALESCE(
                    SUM((total_output_power * time_diff_seconds) / 3600000.0),
                    0
                ) AS energy_kwh
            FROM power_data
            WHERE time_diff_seconds IS NOT NULL
        """)

        result = await session.execute(query, {
            "user_id": user_id,
            "inverter_id": inverter_id
        })

        row = result.first()
        energy_kwh = float(row.energy_kwh) if row and row.energy_kwh else 0.0

        logger.debug(
            "Calculated today's energy production",
            user_id=user_id,
            inverter_id=inverter_id,
            energy_kwh=energy_kwh
        )

        return energy_kwh

    except Exception as e:
        logger.warning(
            "Failed to calculate energy production, returning 0",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id
        )
        return 0.0


async def get_today_maximum_power(
    session: AsyncSession,
    user_id: int,
    inverter_id: int
) -> int:
    """
    Get maximum power for today.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        Maximum power in Watts for today
    """
    try:
        query = text("""
            SELECT COALESCE(MAX(total_output_power), 0) AS max_power
            FROM inverter_measurements
            WHERE user_id = :user_id
              AND inverter_id = :inverter_id
              AND time >= DATE_TRUNC('day', NOW())
        """)

        result = await session.execute(query, {
            "user_id": user_id,
            "inverter_id": inverter_id
        })

        row = result.first()
        max_power = int(row.max_power) if row and row.max_power else 0

        return max_power

    except Exception as e:
        logger.warning(
            "Failed to get max power, returning 0",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id
        )
        return 0


async def get_last_hour_average(
    session: AsyncSession,
    user_id: int,
    inverter_id: int
) -> int:
    """
    Get average power for the last hour.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        Average power in Watts for the last hour
    """
    try:
        query = text("""
            SELECT COALESCE(AVG(total_output_power)::int, 0) AS avg_power
            FROM inverter_measurements
            WHERE user_id = :user_id
              AND inverter_id = :inverter_id
              AND time > NOW() - INTERVAL '1 hour'
        """)

        result = await session.execute(query, {
            "user_id": user_id,
            "inverter_id": inverter_id
        })

        row = result.first()
        avg_power = int(row.avg_power) if row and row.avg_power else 0

        return avg_power

    except Exception as e:
        logger.warning(
            "Failed to get hourly average, returning 0",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id
        )
        return 0


async def set_rls_context(session: AsyncSession, user_id: int) -> None:
    """
    Set Row-Level Security context for the session.

    Args:
        session: Database session
        user_id: User ID to set in RLS context
    """
    await session.execute(text(f"SET app.current_user_id = {user_id}"))
    logger.debug("RLS context set", user_id=user_id)


async def reset_rls_context(session: AsyncSession) -> None:
    """Reset Row-Level Security context."""
    await session.execute(text("RESET app.current_user_id"))
    logger.debug("RLS context reset")
```

**Commit**:
```bash
git add solar_backend/utils/timeseries.py
git commit -m "feat: Add TimescaleDB time-series utilities"
```

---

## Phase 5: Update API Endpoints (2-3 hours)

### Step 5.1: Create Measurements API

**File**: `solar_backend/api/measurements.py` (NEW FILE)

**Content**:
```python
"""
API endpoints for receiving measurement data from inverters/collectors.
Replaces the InfluxDB write protocol with HTTP JSON API.
"""
import structlog
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from solar_backend.db import Inverter, User, get_async_session
from solar_backend.users import current_superuser_bearer
from solar_backend.utils.timeseries import write_measurement, TimeSeriesException

logger = structlog.get_logger()

router = APIRouter()


class MeasurementData(BaseModel):
    """Measurement data from inverter/collector."""
    serial: str = Field(..., description="Serial number of the data logger")
    timestamp: datetime = Field(..., description="Measurement timestamp (ISO 8601 with timezone)")
    measurements: dict = Field(..., description="Measurement values")

    class Config:
        json_schema_extra = {
            "example": {
                "serial": "ABC123456",
                "timestamp": "2025-10-17T10:30:00Z",
                "measurements": {
                    "total_output_power": 5420
                }
            }
        }


@router.post("/api/measurements", status_code=status.HTTP_201_CREATED)
async def post_measurement(
    data: MeasurementData,
    user: User = Depends(current_superuser_bearer),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Receive measurement data from external inverters/collectors.

    This endpoint replaces the InfluxDB write protocol. Collectors should:
    1. Authenticate using Bearer token (superuser)
    2. POST JSON with serial number, timestamp, and measurements
    3. System will route data to correct user's partition

    Args:
        data: Measurement data
        user: Authenticated superuser (collector)
        session: Database session

    Returns:
        Success confirmation with inverter_id

    Raises:
        404: Inverter not found
        500: Database write error
    """
    # Find inverter by serial number
    result = await session.execute(
        select(Inverter).where(Inverter.serial_logger == data.serial)
    )
    inverter = result.scalar_one_or_none()

    if not inverter:
        logger.warning(
            "Measurement received for unknown inverter",
            serial=data.serial,
            collector_user_id=user.id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inverter with serial {data.serial} not found"
        )

    # Extract power from measurements
    total_output_power = data.measurements.get("total_output_power")
    if total_output_power is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="measurements.total_output_power is required"
        )

    # Write to TimescaleDB
    try:
        await write_measurement(
            session=session,
            user_id=inverter.user_id,
            inverter_id=inverter.id,
            timestamp=data.timestamp,
            total_output_power=int(total_output_power)
        )

        logger.info(
            "Measurement stored",
            serial=data.serial,
            inverter_id=inverter.id,
            user_id=inverter.user_id,
            power=total_output_power
        )

        return {
            "status": "ok",
            "inverter_id": inverter.id,
            "user_id": inverter.user_id,
            "timestamp": data.timestamp.isoformat()
        }

    except TimeSeriesException as e:
        logger.error(
            "Failed to store measurement",
            error=str(e),
            serial=data.serial,
            inverter_id=inverter.id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store measurement"
        )
```

**Commit**:
```bash
git add solar_backend/api/measurements.py
git commit -m "feat: Add measurements API endpoint for data ingestion"
```

### Step 5.2: Update Dashboard API

**File**: `solar_backend/api/dashboard.py`

**Changes**:
1. Replace InfluxDB imports with TimescaleDB imports
2. Update queries to use new utilities
3. Add RLS context management

**Modified sections**:
```python
# At top of file - UPDATE IMPORTS
from solar_backend.utils.timeseries import (
    get_power_timeseries,
    get_today_energy_production,
    get_today_maximum_power,
    get_last_hour_average,
    set_rls_context,
    reset_rls_context,
    NoDataException,
    TimeSeriesException
)

# Remove old import:
# from solar_backend.utils.influx import InfluxManagement, NoValuesException, InfluxConnectionError


# UPDATE get_dashboard_data function:
@router.get("/api/dashboard/{inverter_id}/data")
async def get_dashboard_data(
    inverter_id: int,
    time_range: str = "24h",
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session)
):
    """
    API endpoint to fetch time-series data for dashboard graph.
    Returns JSON data for Plotly consumption.
    """
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    async with db_session as session:
        # Verify inverter belongs to user
        result = await session.execute(
            select(Inverter).where(
                Inverter.id == inverter_id,
                Inverter.user_id == user.id
            )
        )
        inverter = result.scalar_one_or_none()

        if not inverter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inverter not found"
            )

        # Validate time range
        valid_ranges = ["1h", "6h", "24h", "7d", "30d"]
        if time_range not in valid_ranges:
            time_range = "24h"

        try:
            # Set RLS context
            await set_rls_context(session, user.id)

            # Get time-series data
            data_points = await get_power_timeseries(
                session=session,
                user_id=user.id,
                inverter_id=inverter.id,
                time_range=time_range
            )

            # Get statistics
            try:
                max_today = await get_today_maximum_power(session, user.id, inverter.id)
            except Exception as e:
                logger.warning("Failed to get today's maximum power", error=str(e))
                max_today = 0

            try:
                today_kwh = await get_today_energy_production(session, user.id, inverter.id)
            except Exception as e:
                logger.warning("Failed to get today's energy production", error=str(e))
                today_kwh = 0.0

            try:
                avg_last_hour = await get_last_hour_average(session, user.id, inverter.id)
            except Exception as e:
                logger.warning("Failed to get last hour average", error=str(e))
                avg_last_hour = 0

            # Current power (latest value)
            current = data_points[-1]["power"] if data_points else 0

            stats = {
                "current": current,
                "max": max_today,
                "today_kwh": today_kwh,
                "avg_last_hour": avg_last_hour
            }

            logger.info(
                "Dashboard data retrieved",
                inverter_id=inverter_id,
                time_range=time_range,
                data_points=len(data_points)
            )

            return JSONResponse({
                "success": True,
                "data": data_points,
                "stats": stats,
                "inverter": {
                    "id": inverter.id,
                    "name": inverter.name,
                    "serial": inverter.serial_logger
                }
            })

        except NoDataException as e:
            logger.warning(
                "No data available for dashboard",
                inverter_id=inverter_id,
                time_range=time_range,
                error=str(e)
            )
            return JSONResponse({
                "success": False,
                "message": "Keine Daten verfügbar für den gewählten Zeitraum",
                "data": [],
                "stats": {"current": 0, "max": 0, "today_kwh": 0.0, "avg_last_hour": 0},
                "inverter": {
                    "id": inverter.id,
                    "name": inverter.name,
                    "serial": inverter.serial_logger
                }
            })
        except TimeSeriesException as e:
            logger.error(
                "Time-series query failed for dashboard",
                inverter_id=inverter_id,
                time_range=time_range,
                error=str(e)
            )
            return JSONResponse({
                "success": False,
                "message": "Fehler beim Abrufen der Daten",
                "data": [],
                "stats": {"current": 0, "max": 0, "today_kwh": 0.0, "avg_last_hour": 0},
                "inverter": {
                    "id": inverter.id,
                    "name": inverter.name,
                    "serial": inverter.serial_logger
                }
            })
        except Exception as e:
            logger.error(
                "Dashboard data retrieval failed",
                inverter_id=inverter_id,
                time_range=time_range,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Fehler beim Abrufen der Daten"
            )
        finally:
            # Always reset RLS context
            await reset_rls_context(session)
```

**Commit**:
```bash
git add solar_backend/api/dashboard.py
git commit -m "feat: Update dashboard to use TimescaleDB queries"
```

### Step 5.3: Update Inverter API

**File**: `solar_backend/api/inverter.py`

**Changes**:
1. Remove InfluxDB bucket creation/deletion
2. Remove `/influx_token` endpoint
3. Simplify inverter CRUD operations

**Key changes**:
```python
# Remove these imports:
# from solar_backend.inverter import create_influx_bucket, delete_influx_bucket
# from solar_backend.config import WEB_DEV_TESTING

# UPDATE post_add_inverter function - remove InfluxDB logic:
@router.post("/inverter")
async def post_add_inverter(
    inverter_to_add: InverterAdd,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
    csrf_protect: CsrfProtect = Depends(),
):
    if user is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    # Check if user is verified
    if not user.is_verified:
        logger.warning(
            "Unverified user attempted to add inverter",
            user_id=user.id,
            user_email=user.email
        )
        return HTMLResponse(
            "<p style='color:red;'>Bitte verifizieren Sie zuerst Ihre E-Mail-Adresse.</p>",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Create inverter object (no InfluxDB bucket needed)
    new_inverter_obj = Inverter(
        user_id=user.id,
        name=inverter_to_add.name,
        serial_logger=inverter_to_add.serial,
        sw_version="-",
    )

    # Insert into database
    try:
        session.add(new_inverter_obj)
        await session.commit()
        await session.refresh(new_inverter_obj)

        logger.info(
            "Inverter created",
            inverter_id=new_inverter_obj.id,
            user_id=user.id,
            serial=inverter_to_add.serial
        )
    except IntegrityError as e:
        await session.rollback()
        logger.error(
            "Inverter serial already exists",
            serial=inverter_to_add.serial,
            error=str(e),
        )
        return HTMLResponse(
            "<p style='color:red;'>Seriennummer existiert bereits</p>",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return HTMLResponse("""
        <div class="sm:mx-auto sm:w-full sm:max-w-sm">
        <h3 class="mt-10 text-3xl font-bold leading-9 tracking-tight"> Wechselrichter erfolgreich registriert</h3>
        <a href="/" hx-boost="false"><button class="btn">Weiter</button></a></div>""")


# UPDATE delete_inverter function - remove InfluxDB deletion:
@router.delete("/inverter/{inverter_id}", response_class=HTMLResponse)
async def delete_inverter(
    inverter_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete an inverter and its measurement data"""
    if user is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    inverter = await session.get(Inverter, inverter_id)

    # Verify ownership
    if inverter.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    await session.delete(inverter)
    await session.commit()

    logger.info(
        "Inverter deleted",
        inverter_id=inverter_id,
        user_id=user.id
    )
    # Note: Measurements are automatically deleted via CASCADE constraint

    return ""


# REMOVE /influx_token endpoint entirely:
# DELETE this function:
# @router.get("/influx_token")
# async def get_token(...):
#     ...
```

**Commit**:
```bash
git add solar_backend/api/inverter.py
git commit -m "feat: Simplify inverter API by removing InfluxDB operations"
```

### Step 5.4: Update Start/Homepage API

**File**: `solar_backend/api/start.py`

**Changes**:
1. Replace InfluxDB queries with TimescaleDB
2. Update `extend_current_powers` and `extend_summary_values`

**Modified sections**:
```python
# UPDATE imports:
from solar_backend.utils.timeseries import (
    get_latest_value,
    get_today_energy_production,
    set_rls_context,
    reset_rls_context,
    NoDataException,
    TimeSeriesException
)
# Remove: from solar_backend.inverter import extend_current_powers, extend_summary_values

# UPDATE get_start function to calculate current powers inline:
@router.get("/", response_class=HTMLResponse)
@htmx("start", "start")
async def get_start(
    request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)

    async with session:
        # Set RLS context
        await set_rls_context(session, user.id)

        try:
            result = await session.execute(select(Inverter).where(Inverter.user_id == user.id))
            inverters = list(result.scalars().all())

            # Extend with current power and last update
            for inverter in inverters:
                try:
                    time, power = await get_latest_value(session, user.id, inverter.id)
                    inverter.current_power = power
                    inverter.last_update = humanize.naturaltime(datetime.now(timezone.utc) - time)
                except NoDataException:
                    inverter.current_power = "-"
                    inverter.last_update = "Keine aktuellen Werte"
                except TimeSeriesException as e:
                    logger.warning("Failed to get latest value", error=str(e), inverter_id=inverter.id)
                    inverter.current_power = "-"
                    inverter.last_update = "Dienst vorübergehend nicht verfügbar"

            # Calculate summary values
            summary = {
                "total_power": "-",
                "total_production_today": "-"
            }

            total_power = 0
            total_production = 0.0
            power_available = False
            production_available = False

            for inverter in inverters:
                # Get current power
                if isinstance(inverter.current_power, int) and inverter.current_power >= 0:
                    total_power += inverter.current_power
                    power_available = True

                # Get today's energy
                try:
                    energy = await get_today_energy_production(session, user.id, inverter.id)
                    if energy >= 0:
                        total_production += energy
                        production_available = True
                except Exception as e:
                    logger.debug(f"Could not get production for inverter {inverter.name}", error=str(e))

            if power_available:
                summary["total_power"] = int(total_power)
            if production_available:
                summary["total_production_today"] = round(total_production, 2)

        finally:
            await reset_rls_context(session)

    return {
        "user": user,
        "inverters": inverters,
        "summary": summary
    }
```

**Commit**:
```bash
git add solar_backend/api/start.py
git commit -m "feat: Update homepage to use TimescaleDB queries"
```

### Step 5.5: Register Measurements Router

**File**: `solar_backend/app.py`

**Add router registration**:
```python
# Add import
from solar_backend.api import measurements

# Register router (add with other routers)
app.include_router(measurements.router, tags=["measurements"])
```

**Commit**:
```bash
git add solar_backend/app.py
git commit -m "feat: Register measurements API router"
```

---

## Phase 6: Update User Management (30 minutes)

### Step 6.1: Remove InfluxDB Provisioning

**File**: `solar_backend/users.py`

**Changes**:
1. Remove `on_after_verify` InfluxDB logic
2. Remove InfluxDB imports

**Modified code**:
```python
# REMOVE import:
# from solar_backend.utils.influx import InfluxManagement

# SIMPLIFY on_after_verify:
async def on_after_verify(self, user: User, request: Optional[Request] = None):
    logger.info(f"User {user.id} is verified.", user=user)
    # InfluxDB provisioning no longer needed
    # User can immediately start adding inverters
```

**Commit**:
```bash
git add solar_backend/users.py
git commit -m "feat: Remove InfluxDB user provisioning from verification flow"
```

---

## Phase 7: Cleanup Obsolete Code (30 minutes)

### Step 7.1: Delete InfluxDB Utilities

```bash
# Delete obsolete files
rm solar_backend/utils/influx.py
rm solar_backend/inverter.py

# Remove InfluxDB environment file
rm influxdb.env

# Commit deletions
git add -A
git commit -m "chore: Remove obsolete InfluxDB utilities and config"
```

### Step 7.2: Update Dependencies

**File**: `pyproject.toml`

**Remove**:
```toml
# DELETE this dependency:
# "influxdb-client>=1.38.0"
```

**Update dependencies**:
```bash
uv sync
```

**Commit**:
```bash
git add pyproject.toml uv.lock
git commit -m "chore: Remove influxdb-client dependency"
```

### Step 7.3: Update Configuration

**File**: `solar_backend/config.py`

**Remove InfluxDB settings**:
```python
# DELETE these settings:
# INFLUX_URL: str
# INFLUX_OPERATOR_TOKEN: str
# INFLUX_OPERATOR_ORG: str
# WEB_DEV_TESTING: bool = False  # Can remove if only used for InfluxDB
```

**Commit**:
```bash
git add solar_backend/config.py
git commit -m "chore: Remove InfluxDB configuration settings"
```

### Step 7.4: Clean Up Docker Compose

**File**: `docker-compose.yml`

**Remove InfluxDB service entirely**:
```yaml
# DELETE influxdb service section completely
# DELETE influxdb volume

volumes:
  pgdata:
  # Remove: influxdb:
```

**Commit**:
```bash
git add docker-compose.yml
git commit -m "chore: Remove InfluxDB from docker-compose"
```

---

## Phase 8: Testing (2-3 hours)

### Step 8.1: Update Test Fixtures

**File**: `tests/conftest.py`

**Changes**:
1. Remove `without_influx` fixture (no longer needed)
2. Add fixture for creating test measurements

**Add new fixture**:
```python
import pytest
from datetime import datetime, timezone

@pytest.fixture
async def sample_measurements(test_client, test_user, test_inverter):
    """Create sample measurements for testing."""
    from solar_backend.utils.timeseries import write_measurement
    from solar_backend.db import sessionmanager

    async with sessionmanager.session() as session:
        # Write 24 hours of sample data
        base_time = datetime.now(timezone.utc)
        for i in range(24 * 12):  # Every 5 minutes for 24 hours
            timestamp = base_time - timedelta(minutes=5 * i)
            power = 5000 + (i % 100) * 10  # Varying power

            await write_measurement(
                session=session,
                user_id=test_user.id,
                inverter_id=test_inverter.id,
                timestamp=timestamp,
                total_output_power=power
            )

    return True
```

### Step 8.2: Update Existing Tests

**Update tests that used InfluxDB mocks**:
- Replace `without_influx` fixture usage
- Update expectations for TimescaleDB responses
- Add tests for RLS (verify users can't see other users' data)

### Step 8.3: Add New Tests

**File**: `tests/test_timeseries.py` (NEW FILE)

**Content**:
```python
"""Tests for TimescaleDB time-series utilities."""
import pytest
from datetime import datetime, timezone, timedelta
from solar_backend.utils.timeseries import (
    write_measurement,
    get_latest_value,
    get_power_timeseries,
    get_today_energy_production,
    NoDataException
)


@pytest.mark.asyncio
async def test_write_and_read_measurement(test_client, test_user, test_inverter):
    """Test writing and reading a single measurement."""
    from solar_backend.db import sessionmanager

    async with sessionmanager.session() as session:
        timestamp = datetime.now(timezone.utc)
        power = 5420

        # Write measurement
        await write_measurement(
            session=session,
            user_id=test_user.id,
            inverter_id=test_inverter.id,
            timestamp=timestamp,
            total_output_power=power
        )

        # Read back
        time, read_power = await get_latest_value(
            session=session,
            user_id=test_user.id,
            inverter_id=test_inverter.id
        )

        assert read_power == power
        assert abs((time - timestamp).total_seconds()) < 1


@pytest.mark.asyncio
async def test_no_data_exception(test_client, test_user, test_inverter):
    """Test that NoDataException is raised when no data exists."""
    from solar_backend.db import sessionmanager

    async with sessionmanager.session() as session:
        with pytest.raises(NoDataException):
            await get_latest_value(
                session=session,
                user_id=test_user.id,
                inverter_id=test_inverter.id
            )


@pytest.mark.asyncio
async def test_time_series_query(test_client, test_user, test_inverter, sample_measurements):
    """Test time-series query with bucketing."""
    from solar_backend.db import sessionmanager

    async with sessionmanager.session() as session:
        data_points = await get_power_timeseries(
            session=session,
            user_id=test_user.id,
            inverter_id=test_inverter.id,
            time_range="24h"
        )

        assert len(data_points) > 0
        assert all("time" in dp and "power" in dp for dp in data_points)


@pytest.mark.asyncio
async def test_rls_isolation(test_client, test_user, test_user2, test_inverter, sample_measurements):
    """Test that RLS prevents users from seeing each other's data."""
    from solar_backend.db import sessionmanager
    from solar_backend.utils.timeseries import set_rls_context

    async with sessionmanager.session() as session:
        # Set RLS context to user2 (different user)
        await set_rls_context(session, test_user2.id)

        # Try to query user1's inverter data
        with pytest.raises(NoDataException):
            await get_latest_value(
                session=session,
                user_id=test_user.id,  # user1's data
                inverter_id=test_inverter.id
            )
```

### Step 8.4: Run All Tests

```bash
# Run full test suite
uv run pytest -v

# Run specific test markers
uv run pytest -m unit -v
uv run pytest -m integration -v

# Check test coverage
uv run pytest --cov=solar_backend --cov-report=html
```

**Expected Results**:
- All tests pass
- No InfluxDB connection errors
- Dashboard tests work with sample data

**Commit**:
```bash
git add tests/
git commit -m "test: Update tests for TimescaleDB architecture"
```

---

## Phase 9: Integration Testing (1-2 hours)

### Step 9.1: Manual Testing Checklist

Start the development server:
```bash
# Clean start
docker-compose down -v
docker-compose up -d

# Check logs
docker-compose logs -f backend
docker-compose logs -f db
```

**Test Flow**:
1. ✅ User registration
2. ✅ Email verification
3. ✅ Add inverter (no InfluxDB bucket creation)
4. ✅ POST measurement data via API
5. ✅ View dashboard (should show data)
6. ✅ Delete inverter (measurements cascade deleted)
7. ✅ Multi-user isolation (create 2 users, verify data separation)

### Step 9.2: Test Data Ingestion

**Create test script** `scripts/test_measurements.py`:
```python
"""
Test script to send measurements to the backend.
"""
import requests
from datetime import datetime, timezone

BASE_URL = "http://localhost:8001"

# 1. Get bearer token (replace with your superuser credentials)
response = requests.post(
    f"{BASE_URL}/auth/jwt/login",
    data={
        "username": "admin@example.com",
        "password": "your_admin_password"
    }
)
token = response.json()["access_token"]

# 2. Send measurement
headers = {"Authorization": f"Bearer {token}"}
measurement = {
    "serial": "ABC123456",  # Replace with your inverter serial
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "measurements": {
        "total_output_power": 5420
    }
}

response = requests.post(
    f"{BASE_URL}/api/measurements",
    json=measurement,
    headers=headers
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

Run:
```bash
uv run python scripts/test_measurements.py
```

### Step 9.3: Test Dashboard

1. Open browser: `http://localhost:8001`
2. Login with test user
3. Add inverter
4. Send measurements using script
5. View dashboard - should show data graph
6. Test different time ranges (1h, 24h, 7d)

### Step 9.4: Test RLS Isolation

```bash
# Create test script to verify RLS
docker-compose exec db psql -U deyehard -d deyehard << 'EOF'
-- Create two test users and inverters
-- Verify measurements are isolated

-- Set RLS context to user1
SET app.current_user_id = 1;
SELECT COUNT(*) FROM inverter_measurements;  -- Should see user1's data

-- Set RLS context to user2
SET app.current_user_id = 2;
SELECT COUNT(*) FROM inverter_measurements;  -- Should see user2's data only

RESET app.current_user_id;
EOF
```

---

## Phase 10: Documentation Updates (30 minutes)

### Step 10.1: Update CLAUDE.md

**File**: `CLAUDE.md`

**Major changes**:
1. Update "Technology Stack" section
2. Remove InfluxDB setup instructions
3. Update "Multi-Tenant Architecture" section
4. Update "Common Patterns" section
5. Remove "Initial InfluxDB Setup" section

**New sections to add**:
```markdown
### Multi-Tenant TimescaleDB Architecture

The application implements per-user data isolation using TimescaleDB:

1. **Time-Series Storage**:
   - All measurement data stored in `inverter_measurements` table
   - Multi-dimensional partitioning by time (7-day chunks) and user_id (4 space partitions)
   - Automatic compression after 7 days
   - 2-year retention policy

2. **Data Isolation**:
   - Row-Level Security (RLS) enforces user isolation at database level
   - Application sets `app.current_user_id` session variable
   - Queries automatically filtered by RLS policy

3. **Data Ingestion**:
   - External inverters POST measurements to `/api/measurements`
   - Requires superuser Bearer token authentication
   - Data routed to correct user partition by inverter serial number

### Working with Time-Series Data

- Always include `user_id` in queries for partition pruning
- Set RLS context using `set_rls_context(session, user_id)` before queries
- Reset RLS context with `reset_rls_context(session)` after queries
- Use utilities in `utils/timeseries.py` for common operations
```

### Step 10.2: Update README.md

Update installation instructions, remove InfluxDB references, add TimescaleDB setup.

### Step 10.3: Create Migration Notes

**File**: `docs/TIMESCALEDB_MIGRATION_NOTES.md`

Document:
- What changed
- Breaking changes for external systems
- How to update inverter collectors
- Performance characteristics
- Troubleshooting guide

**Commit**:
```bash
git add CLAUDE.md README.md docs/
git commit -m "docs: Update documentation for TimescaleDB architecture"
```

---

## Phase 11: Finalization (30 minutes)

### Step 11.1: Final Review

Review all changes:
```bash
# View all commits
git log --oneline feature/timescaledb-migration

# View diff from master
git diff master...feature/timescaledb-migration

# Check for any remaining InfluxDB references
grep -r "influx" solar_backend/ --exclude-dir=__pycache__
grep -r "Influx" solar_backend/ --exclude-dir=__pycache__
```

### Step 11.2: Clean Up

```bash
# Remove any debug code
# Remove commented-out code
# Ensure all TODOs are addressed

# Format code
uv run black solar_backend/
uv run isort solar_backend/

git add -A
git commit -m "chore: Code cleanup and formatting"
```

### Step 11.3: Final Testing

```bash
# Run full test suite one more time
uv run pytest -v

# Test docker-compose from scratch
docker-compose down -v
docker-compose up -d
docker-compose logs -f

# Manual smoke test of all features
```

---

## Phase 12: Deployment (variable)

### Step 12.1: Create Pull Request

```bash
# Push feature branch
git push origin feature/timescaledb-migration

# Create PR on GitHub/GitLab
# Add description:
# - Summary of changes
# - Migration steps
# - Breaking changes
# - Testing performed
```

### Step 12.2: Code Review

- Review with team
- Address feedback
- Update documentation as needed

### Step 12.3: Merge to Master

```bash
# After approval, merge
git checkout master
git merge feature/timescaledb-migration
git push origin master
```

---

## Rollback Plan

If issues are encountered:

### Quick Rollback (Git)
```bash
# Switch back to master
git checkout master

# Restore docker-compose with InfluxDB
git checkout master -- docker-compose.yml

# Restart services
docker-compose up -d
```

### Database Rollback
```bash
# Rollback migration
uv run alembic downgrade -1

# Restart with old InfluxDB setup
docker-compose -f docker-compose.yml.backup up -d
```

---

## Success Criteria

- [ ] All tests pass
- [ ] Dashboard displays time-series data correctly
- [ ] Users can add/delete inverters
- [ ] Measurements can be ingested via API
- [ ] Multi-user isolation verified
- [ ] No InfluxDB references remain in code
- [ ] Documentation updated
- [ ] Performance acceptable (<1s dashboard load)
- [ ] Docker setup works from scratch

---

## Performance Monitoring

After migration, monitor:
1. Query response times (dashboard)
2. Write throughput (measurements/sec)
3. Database size growth
4. CPU/Memory usage

Expected performance:
- Dashboard load: <500ms
- Measurement write: <50ms
- Storage: ~100MB per million measurements (compressed)

---

## External System Updates

**Important**: External inverter collectors need updates:

**Old InfluxDB Protocol**:
```
POST http://influxdb:8086/api/v2/write?org=...&bucket=...
Authorization: Token xyz123
Body: grid,serial=ABC123 total_output_power=5420 1697551200000000000
```

**New HTTP API**:
```
POST http://backend:8000/api/measurements
Authorization: Bearer xyz123
Content-Type: application/json

{
  "serial": "ABC123456",
  "timestamp": "2025-10-17T10:30:00Z",
  "measurements": {
    "total_output_power": 5420
  }
}
```

Update collector code accordingly.

---

## Contact & Support

If issues arise during migration:
1. Check logs: `docker-compose logs -f backend db`
2. Verify TimescaleDB extension: `docker-compose exec db psql -U deyehard -c "\dx"`
3. Test RLS: Check session variable setting
4. Review this document's troubleshooting section

---

## Appendix: Useful Commands

```bash
# View hypertable info
docker-compose exec db psql -U deyehard -d deyehard -c "
  SELECT * FROM timescaledb_information.hypertables;
"

# View chunks
docker-compose exec db psql -U deyehard -d deyehard -c "
  SELECT * FROM timescaledb_information.chunks;
"

# View compression stats
docker-compose exec db psql -U deyehard -d deyehard -c "
  SELECT * FROM timescaledb_information.compression_settings;
"

# Manual RLS test
docker-compose exec db psql -U deyehard -d deyehard -c "
  SET app.current_user_id = 1;
  SELECT COUNT(*) FROM inverter_measurements;
"

# View table size
docker-compose exec db psql -U deyehard -d deyehard -c "
  SELECT
    pg_size_pretty(pg_total_relation_size('inverter_measurements')) as total_size,
    pg_size_pretty(pg_relation_size('inverter_measurements')) as table_size;
"
```

---

**END OF MIGRATION PLAN**

Good luck with the migration! Remember to commit frequently and test thoroughly.
