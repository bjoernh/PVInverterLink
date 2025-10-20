"""
Time-series data utilities for TimescaleDB.
"""

import structlog
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from solar_backend.config import settings

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
    total_output_power: int,
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

        await session.execute(
            stmt,
            {
                "time": timestamp,
                "user_id": user_id,
                "inverter_id": inverter_id,
                "power": total_output_power,
            },
        )
        await session.commit()

        logger.debug(
            "Measurement written",
            user_id=user_id,
            inverter_id=inverter_id,
            power=total_output_power,
        )
    except Exception as e:
        await session.rollback()
        logger.error(
            "Failed to write measurement",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        raise TimeSeriesException(f"Failed to write measurement: {str(e)}") from e


async def get_latest_value(
    session: AsyncSession, user_id: int, inverter_id: int
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

        result = await session.execute(
            query, {"user_id": user_id, "inverter_id": inverter_id}
        )

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
            inverter_id=inverter_id,
        )
        raise TimeSeriesException(f"Failed to query latest value: {str(e)}") from e


async def get_power_timeseries(
    session: AsyncSession, user_id: int, inverter_id: int, time_range: str = "24h"
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
    # Map time range to bucket size and PostgreSQL interval
    time_range_config = {
        "1h": {"bucket": "1 minute", "interval": "1 hour"},
        "6h": {"bucket": "5 minutes", "interval": "6 hours"},
        "24h": {"bucket": "10 minutes", "interval": "24 hours"},
        "7d": {"bucket": "1 hour", "interval": "7 days"},
        "30d": {"bucket": "4 hours", "interval": "30 days"},
    }

    config = time_range_config.get(
        time_range, {"bucket": "5 minutes", "interval": "24 hours"}
    )
    bucket = config["bucket"]
    interval = config["interval"]

    try:
        # Note: We can't use parameter placeholders for INTERVAL in PostgreSQL,
        # so we safely use the pre-validated interval strings from our mapping.
        # The values are validated against a whitelist, so this is safe from SQL injection.
        query = text(f"""
            SELECT
                time_bucket(INTERVAL '{bucket}', time) AS bucket_time,
                AVG(total_output_power)::int AS power
            FROM inverter_measurements
            WHERE user_id = :user_id
              AND inverter_id = :inverter_id
              AND time > NOW() - INTERVAL '{interval}'
            GROUP BY bucket_time
            ORDER BY bucket_time ASC
        """)

        result = await session.execute(
            query, {"user_id": user_id, "inverter_id": inverter_id}
        )

        # Get configured timezone
        tz = ZoneInfo(settings.TZ)

        data_points = [
            {
                "time": row.bucket_time.astimezone(tz).isoformat(),
                "power": row.power if row.power is not None else 0,
            }
            for row in result
        ]

        if not data_points:
            logger.warning(
                "No time-series data found",
                user_id=user_id,
                inverter_id=inverter_id,
                time_range=time_range,
            )
            raise NoDataException(f"No data for time range {time_range}")

        logger.info(
            "Retrieved time-series data",
            user_id=user_id,
            inverter_id=inverter_id,
            time_range=time_range,
            data_points=len(data_points),
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
            time_range=time_range,
        )
        raise TimeSeriesException(f"Failed to query time-series: {str(e)}") from e


async def get_today_energy_production(
    session: AsyncSession, user_id: int, inverter_id: int
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

        result = await session.execute(
            query, {"user_id": user_id, "inverter_id": inverter_id}
        )

        row = result.first()
        energy_kwh = float(row.energy_kwh) if row and row.energy_kwh else 0.0

        logger.debug(
            "Calculated today's energy production",
            user_id=user_id,
            inverter_id=inverter_id,
            energy_kwh=energy_kwh,
        )

        return energy_kwh

    except Exception as e:
        logger.warning(
            "Failed to calculate energy production, returning 0",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        return 0.0


async def get_today_maximum_power(
    session: AsyncSession, user_id: int, inverter_id: int
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

        result = await session.execute(
            query, {"user_id": user_id, "inverter_id": inverter_id}
        )

        row = result.first()
        max_power = int(row.max_power) if row and row.max_power else 0

        return max_power

    except Exception as e:
        logger.warning(
            "Failed to get max power, returning 0",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        return 0


async def get_last_hour_average(
    session: AsyncSession, user_id: int, inverter_id: int
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

        result = await session.execute(
            query, {"user_id": user_id, "inverter_id": inverter_id}
        )

        row = result.first()
        avg_power = int(row.avg_power) if row and row.avg_power else 0

        return avg_power

    except Exception as e:
        logger.warning(
            "Failed to get hourly average, returning 0",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        return 0


async def set_rls_context(session: AsyncSession, user_id: int) -> None:
    """
    Set Row-Level Security context for the session.

    Skips setting RLS context for SQLite (used in tests).

    Args:
        session: Database session
        user_id: User ID to set in RLS context
    """
    # Skip RLS context for SQLite (used in tests)
    db_url = str(session.bind.url) if session.bind else ""
    if "sqlite" in db_url.lower():
        logger.debug("Skipping RLS context for SQLite", user_id=user_id)
        return

    await session.execute(text(f"SET app.current_user_id = {user_id}"))
    logger.debug("RLS context set", user_id=user_id)


async def reset_rls_context(session: AsyncSession) -> None:
    """
    Reset Row-Level Security context.

    Skips resetting RLS context for SQLite (used in tests).
    """
    # Skip RLS context for SQLite (used in tests)
    db_url = str(session.bind.url) if session.bind else ""
    if "sqlite" in db_url.lower():
        logger.debug("Skipping RLS context reset for SQLite")
        return

    await session.execute(text("RESET app.current_user_id"))
    logger.debug("RLS context reset")
