"""
Time-series data utilities for TimescaleDB.
"""

import contextlib
import structlog
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from solar_backend.config import settings
from solar_backend.utils.query_builder import TimeSeriesQueryBuilder

logger = structlog.get_logger()


class TimeRange(str, Enum):
    """Time range options with their corresponding bucket sizes."""

    ONE_HOUR = "1 hour"
    SIX_HOURS = "6 hours"
    TWENTY_FOUR_HOURS = "24 hours"
    SEVEN_DAYS = "7 days"
    THIRTY_DAYS = "30 days"

    @property
    def bucket(self) -> str:
        """Get the bucket size for this time range."""
        buckets = {
            self.ONE_HOUR: "1 minute",
            self.SIX_HOURS: "1 minutes",
            self.TWENTY_FOUR_HOURS: "5 minutes",
            self.SEVEN_DAYS: "15 minutes",
            self.THIRTY_DAYS: "1 hour",
        }
        return buckets[self]

    @property
    def label(self) -> str:
        """Get the short display label for this time range."""
        labels = {
            self.ONE_HOUR: "1H",
            self.SIX_HOURS: "6H",
            self.TWENTY_FOUR_HOURS: "24H",
            self.SEVEN_DAYS: "7D",
            self.THIRTY_DAYS: "30D",
        }
        return labels[self]

    @classmethod
    def default(cls) -> "TimeRange":
        """Get the default time range."""
        return cls.TWENTY_FOUR_HOURS


class EnergyPeriod(str, Enum):
    """Energy production time period options."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"

    @property
    def label(self) -> str:
        """Get the display label for this period."""
        labels = {
            self.DAY: "Tag",
            self.WEEK: "Woche",
            self.MONTH: "Monat",
        }
        return labels[self]

    @property
    def description(self) -> str:
        """Get the description text for this period."""
        descriptions = {
            self.DAY: "Stündliche Energieproduktion für heute",
            self.WEEK: "Tägliche Energieproduktion dieser Woche",
            self.MONTH: "Tägliche Energieproduktion dieses Monats",
        }
        return descriptions[self]

    @classmethod
    def default(cls) -> "EnergyPeriod":
        """Get the default energy period."""
        return cls.DAY


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
    yield_day_wh: Optional[int] = None,
    yield_total_kwh: Optional[int] = None,
) -> None:
    """
    Write a single measurement point to TimescaleDB.

    Args:
        session: Database session
        user_id: User ID (for partitioning and RLS)
        inverter_id: Inverter ID
        timestamp: Measurement timestamp (with timezone)
        total_output_power: Power in Watts
        yield_day_wh: Daily yield in Wh (optional, aggregated from DC channels)
        yield_total_kwh: Total lifetime yield in kWh (optional, aggregated from DC channels)

    Raises:
        TimeSeriesException: If write fails
    """
    try:
        stmt = text("""
            INSERT INTO inverter_measurements (time, user_id, inverter_id, total_output_power, yield_day_wh, yield_total_kwh)
            VALUES (:time, :user_id, :inverter_id, :power, :yield_day_wh, :yield_total_kwh)
            ON CONFLICT DO NOTHING
        """)

        await session.execute(
            stmt,
            {
                "time": timestamp,
                "user_id": user_id,
                "inverter_id": inverter_id,
                "power": total_output_power,
                "yield_day_wh": yield_day_wh,
                "yield_total_kwh": yield_total_kwh,
            },
        )
        await session.commit()

        logger.debug(
            "Measurement written",
            user_id=user_id,
            inverter_id=inverter_id,
            power=total_output_power,
            yield_day_wh=yield_day_wh,
            yield_total_kwh=yield_total_kwh,
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


async def write_dc_channel_measurement(
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
    timestamp: datetime,
    channel: int,
    name: str,
    power: float,
    voltage: float,
    current: float,
    yield_day_wh: float,
    yield_total_kwh: float,
    irradiation: float,
) -> None:
    """
    Write a single DC channel measurement point to TimescaleDB.

    Args:
        session: Database session
        user_id: User ID (for partitioning and RLS)
        inverter_id: Inverter ID
        timestamp: Measurement timestamp (with timezone)
        channel: DC channel number (MPPT)
        name: Channel name
        power: Power in Watts
        voltage: Voltage in V
        current: Current in A
        yield_day_wh: Daily yield in Wh
        yield_total_kwh: Total lifetime yield in kWh
        irradiation: Irradiation value

    Raises:
        TimeSeriesException: If write fails
    """
    try:
        stmt = text("""
            INSERT INTO dc_channel_measurements (
                time, user_id, inverter_id, channel, name,
                power, voltage, current, yield_day_wh, yield_total_kwh, irradiation
            )
            VALUES (
                :time, :user_id, :inverter_id, :channel, :name,
                :power, :voltage, :current, :yield_day_wh, :yield_total_kwh, :irradiation
            )
            ON CONFLICT DO NOTHING
        """)

        await session.execute(
            stmt,
            {
                "time": timestamp,
                "user_id": user_id,
                "inverter_id": inverter_id,
                "channel": channel,
                "name": name,
                "power": power,
                "voltage": voltage,
                "current": current,
                "yield_day_wh": yield_day_wh,
                "yield_total_kwh": yield_total_kwh,
                "irradiation": irradiation,
            },
        )
        await session.commit()

        logger.debug(
            "DC channel measurement written",
            user_id=user_id,
            inverter_id=inverter_id,
            channel=channel,
            yield_day_wh=yield_day_wh,
        )
    except Exception as e:
        await session.rollback()
        logger.error(
            "Failed to write DC channel measurement",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
            channel=channel,
        )
        raise TimeSeriesException(f"Failed to write DC channel measurement: {str(e)}") from e


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
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
    time_range: TimeRange | str = TimeRange.TWENTY_FOUR_HOURS,
) -> list[dict]:
    """
    Get time-series power data with automatic time bucketing.

    Args:
        session: Database session with RLS context set
        user_id: User ID (for partition pruning)
        inverter_id: Inverter ID
        time_range: Time range (TimeRange enum or string value)

    Returns:
        List of dicts with 'time' (ISO string) and 'power' (int)

    Raises:
        NoDataException: If no data found
        TimeSeriesException: On query error
    """
    # Convert string to enum if needed
    if isinstance(time_range, str):
        try:
            time_range = TimeRange(time_range)
        except ValueError:
            logger.warning(f"Invalid time range '{time_range}', using default")
            time_range = TimeRange.default()

    bucket = time_range.bucket
    interval = time_range.value

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
    Get today's energy production in kWh.

    Prioritizes inverter-provided yield data (more accurate), falls back to
    trapezoidal integration from power measurements if yield data unavailable.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        Energy produced today in kWh
    """
    try:
        # Try inverter-provided yield first (more accurate)
        total_yield_wh = await get_today_total_yield(session, user_id, inverter_id)
        if total_yield_wh is not None:
            energy_kwh = total_yield_wh / 1000.0  # Convert Wh to kWh
            logger.debug(
                "Using inverter-provided yield",
                user_id=user_id,
                inverter_id=inverter_id,
                energy_kwh=energy_kwh,
                source="inverter",
            )
            return energy_kwh

        # Fallback: Calculate from power measurements using trapezoidal integration
        logger.debug(
            "No inverter yield data, falling back to power integration",
            user_id=user_id,
            inverter_id=inverter_id,
        )

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
            "Calculated energy from power integration",
            user_id=user_id,
            inverter_id=inverter_id,
            energy_kwh=energy_kwh,
            source="calculated",
        )

        return energy_kwh

    except Exception as e:
        logger.warning(
            "Failed to get energy production, returning 0",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        return 0.0


async def get_today_total_yield(
    session: AsyncSession, user_id: int, inverter_id: int
) -> Optional[float]:
    """
    Get today's total yield from inverter-provided DC channel data.

    This queries the latest yield_day_wh from each DC channel and sums them.
    Returns None if no DC channel data is available (e.g., old measurements).

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        Total daily yield in Wh, or None if no data available
    """
    try:
        # Get the latest yield_day_wh from each channel for today
        query = text("""
            WITH latest_per_channel AS (
                SELECT DISTINCT ON (channel)
                    channel,
                    yield_day_wh,
                    time
                FROM dc_channel_measurements
                WHERE user_id = :user_id
                  AND inverter_id = :inverter_id
                  AND time >= DATE_TRUNC('day', NOW())
                ORDER BY channel, time DESC
            )
            SELECT COALESCE(SUM(yield_day_wh), 0) AS total_yield_wh
            FROM latest_per_channel
        """)

        result = await session.execute(
            query, {"user_id": user_id, "inverter_id": inverter_id}
        )

        row = result.first()
        if not row or row.total_yield_wh == 0:
            logger.debug(
                "No DC channel yield data available",
                user_id=user_id,
                inverter_id=inverter_id,
            )
            return None

        total_yield_wh = float(row.total_yield_wh)

        logger.debug(
            "Retrieved today's total yield from inverter",
            user_id=user_id,
            inverter_id=inverter_id,
            total_yield_wh=total_yield_wh,
        )

        return total_yield_wh

    except Exception as e:
        logger.warning(
            "Failed to get inverter yield data",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        return None


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


@contextlib.asynccontextmanager
async def rls_context(session: AsyncSession, user_id: int):
    """
    Async context manager for Row-Level Security.

    Automatically sets and resets RLS context, ensuring cleanup even on exceptions.

    Usage:
        async with rls_context(session, user_id):
            # RLS context is set
            data = await get_timeseries_data(session, user_id, inverter_id)
        # RLS context is automatically reset

    Args:
        session: Database session
        user_id: User ID for RLS context
    """
    try:
        await set_rls_context(session, user_id)
        yield
    finally:
        await reset_rls_context(session)


async def get_latest_dc_channels(
    session: AsyncSession, user_id: int, inverter_id: int
) -> list[dict]:
    """
    Get the latest DC channel measurements for an inverter.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        List of dicts with latest measurement for each channel:
        {
            'channel': int,
            'name': str,
            'power': float,
            'voltage': float,
            'current': float,
            'yield_day_wh': float,
            'yield_total_kwh': float,
            'irradiation': float,
            'time': datetime
        }
    """
    try:
        query = text("""
            SELECT DISTINCT ON (channel)
                channel,
                name,
                power,
                voltage,
                current,
                yield_day_wh,
                yield_total_kwh,
                irradiation,
                time
            FROM dc_channel_measurements
            WHERE user_id = :user_id
              AND inverter_id = :inverter_id
              AND time > NOW() - INTERVAL '1 hour'
            ORDER BY channel, time DESC
        """)

        result = await session.execute(
            query, {"user_id": user_id, "inverter_id": inverter_id}
        )

        # Get configured timezone
        tz = ZoneInfo(settings.TZ)

        channels = []
        for row in result:
            channels.append({
                "channel": row.channel,
                "name": row.name,
                "power": float(row.power),
                "voltage": float(row.voltage),
                "current": float(row.current),
                "yield_day_wh": float(row.yield_day_wh),
                "yield_total_kwh": float(row.yield_total_kwh),
                "irradiation": float(row.irradiation),
                "time": row.time.astimezone(tz),
            })

        logger.debug(
            "Retrieved latest DC channel data",
            user_id=user_id,
            inverter_id=inverter_id,
            channels_found=len(channels),
        )

        return channels

    except Exception as e:
        logger.warning(
            "Failed to get latest DC channel data",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        return []


async def get_dc_channel_timeseries(
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
    time_range: TimeRange | str = TimeRange.TWENTY_FOUR_HOURS,
) -> dict[int, list[dict]]:
    """
    Get time-series data for all DC channels of an inverter.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID
        time_range: Time range (TimeRange enum or string value)

    Returns:
        Dict mapping channel number to list of time-series data points:
        {
            1: [{'time': '...', 'power': 123, 'voltage': 30.5, ...}, ...],
            2: [{'time': '...', 'power': 145, 'voltage': 31.2, ...}, ...],
            ...
        }
    """
    # Convert string to enum if needed
    if isinstance(time_range, str):
        try:
            time_range = TimeRange(time_range)
        except ValueError:
            logger.warning(f"Invalid time range '{time_range}', using default")
            time_range = TimeRange.default()

    bucket = time_range.bucket
    interval = time_range.value

    try:
        query = text(f"""
            SELECT
                channel,
                time_bucket(INTERVAL '{bucket}', time) AS bucket_time,
                AVG(power)::float AS power,
                AVG(voltage)::float AS voltage,
                AVG(current)::float AS current,
                MAX(yield_day_wh)::float AS yield_day_wh,
                AVG(irradiation)::float AS irradiation
            FROM dc_channel_measurements
            WHERE user_id = :user_id
              AND inverter_id = :inverter_id
              AND time > NOW() - INTERVAL '{interval}'
            GROUP BY channel, bucket_time
            ORDER BY channel, bucket_time ASC
        """)

        result = await session.execute(
            query, {"user_id": user_id, "inverter_id": inverter_id}
        )

        # Get configured timezone
        tz = ZoneInfo(settings.TZ)

        # Organize data by channel
        channel_data = {}
        for row in result:
            channel = row.channel
            if channel not in channel_data:
                channel_data[channel] = []

            channel_data[channel].append({
                "time": row.bucket_time.astimezone(tz).isoformat(),
                "power": float(row.power) if row.power is not None else 0,
                "voltage": float(row.voltage) if row.voltage is not None else 0,
                "current": float(row.current) if row.current is not None else 0,
                "yield_day_wh": float(row.yield_day_wh) if row.yield_day_wh is not None else 0,
                "irradiation": float(row.irradiation) if row.irradiation is not None else 0,
            })

        logger.info(
            "Retrieved DC channel time-series data",
            user_id=user_id,
            inverter_id=inverter_id,
            time_range=time_range,
            channels=len(channel_data),
            total_points=sum(len(points) for points in channel_data.values()),
        )

        return channel_data

    except Exception as e:
        logger.error(
            "Failed to get DC channel time-series data",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
            time_range=time_range,
        )
        return {}


async def get_raw_measurements(
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """
    Get raw measurement data for a custom date range (no bucketing).

    Args:
        session: Database session with RLS context set
        user_id: User ID (for partition pruning)
        inverter_id: Inverter ID
        start_date: Start datetime (inclusive)
        end_date: End datetime (inclusive)

    Returns:
        List of dicts with 'time' (ISO string) and 'power' (int)

    Raises:
        NoDataException: If no data found
        TimeSeriesException: On query error
    """
    try:
        query = text("""
            SELECT time, total_output_power
            FROM inverter_measurements
            WHERE user_id = :user_id
              AND inverter_id = :inverter_id
              AND time >= :start_date
              AND time <= :end_date
            ORDER BY time ASC
        """)

        result = await session.execute(
            query,
            {
                "user_id": user_id,
                "inverter_id": inverter_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        # Get configured timezone
        tz = ZoneInfo(settings.TZ)

        data_points = [
            {
                "time": row.time.astimezone(tz).isoformat(),
                "power": row.total_output_power
                if row.total_output_power is not None
                else 0,
            }
            for row in result
        ]

        if not data_points:
            logger.warning(
                "No raw measurements found",
                user_id=user_id,
                inverter_id=inverter_id,
                start_date=start_date,
                end_date=end_date,
            )
            raise NoDataException(
                f"No measurements found between {start_date} and {end_date}"
            )

        logger.info(
            "Retrieved raw measurements",
            user_id=user_id,
            inverter_id=inverter_id,
            start_date=start_date,
            end_date=end_date,
            data_points=len(data_points),
        )

        return data_points

    except NoDataException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get raw measurements",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
            start_date=start_date,
            end_date=end_date,
        )
        raise TimeSeriesException(f"Failed to query raw measurements: {str(e)}") from e


from solar_backend.utils.query_builder import TimeSeriesQueryBuilder


async def get_daily_energy_production(
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
    days: int = 7,
) -> list[dict]:
    """
    Get daily energy production for the last N days.

    Prioritizes inverter-provided yield data (more accurate), falls back to
    trapezoidal integration from power measurements if yield data unavailable.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID
        days: Number of days to retrieve (default: 7)

    Returns:
        List of dicts with 'date' (YYYY-MM-DD string) and 'energy_kwh' (float)
    """
    try:
        builder = TimeSeriesQueryBuilder(session, user_id, inverter_id)
        time_filter = f"time >= NOW() - INTERVAL '{days} days'"
        yield_threshold = int(days * 0.7)  # At least 70% of days have data
        return await builder.get_energy_production(time_filter, yield_threshold)

    except Exception as e:
        logger.error(
            "Failed to get daily energy production",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
            days=days,
        )
        return []


async def get_hourly_energy_production(
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
) -> list[dict]:
    """
    Get hourly energy production for today.

    Uses trapezoidal integration of power measurements bucketed by hour.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        List of dicts with 'hour' (0-23 int) and 'energy_kwh' (float)
    """
    try:
        # Get configured timezone
        tz = ZoneInfo(settings.TZ)

        query = text("""
            WITH power_data AS (
                SELECT
                    EXTRACT(HOUR FROM time AT TIME ZONE :timezone)::int AS hour,
                    time,
                    total_output_power,
                    EXTRACT(EPOCH FROM time - LAG(time) OVER (PARTITION BY EXTRACT(HOUR FROM time AT TIME ZONE :timezone) ORDER BY time)) AS time_diff_seconds
                FROM inverter_measurements
                WHERE user_id = :user_id
                  AND inverter_id = :inverter_id
                  AND time >= DATE_TRUNC('day', NOW() AT TIME ZONE :timezone)
                ORDER BY time
            ),
            hourly_energy AS (
                SELECT
                    hour,
                    COALESCE(
                        SUM((total_output_power * time_diff_seconds) / 3600000.0),
                        0
                    ) AS energy_kwh
                FROM power_data
                WHERE time_diff_seconds IS NOT NULL
                GROUP BY hour
                ORDER BY hour ASC
            )
            SELECT hour, energy_kwh
            FROM hourly_energy
        """)

        result = await session.execute(
            query,
            {
                "user_id": user_id,
                "inverter_id": inverter_id,
                "timezone": str(tz),
            },
        )

        hourly_data = []
        for row in result:
            hourly_data.append({
                "hour": int(row.hour),
                "energy_kwh": float(row.energy_kwh),
            })

        logger.debug(
            "Retrieved hourly energy production",
            user_id=user_id,
            inverter_id=inverter_id,
            hours_found=len(hourly_data),
        )

        return hourly_data

    except Exception as e:
        logger.error(
            "Failed to get hourly energy production",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        return []


async def get_current_week_energy_production(
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
) -> list[dict]:
    """
    Get daily energy production for the current week (Monday to Sunday).

    Uses the same prioritization logic as get_daily_energy_production:
    inverter-provided yield data first, then power integration fallback.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        List of dicts with 'date' (YYYY-MM-DD string) and 'energy_kwh' (float)
    """
    try:
        builder = TimeSeriesQueryBuilder(session, user_id, inverter_id)
        time_filter = "time >= DATE_TRUNC('week', NOW() AT TIME ZONE :timezone)"
        yield_threshold = 3  # At least 3 days of data
        return await builder.get_energy_production(time_filter, yield_threshold)

    except Exception as e:
        logger.error(
            "Failed to get current week energy production",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        return []


async def get_current_month_energy_production(
    session: AsyncSession,
    user_id: int,
    inverter_id: int,
) -> list[dict]:
    """
    Get daily energy production for the current month (1st to today).

    Uses the same prioritization logic as get_daily_energy_production:
    inverter-provided yield data first, then power integration fallback.

    Args:
        session: Database session with RLS context set
        user_id: User ID
        inverter_id: Inverter ID

    Returns:
        List of dicts with 'date' (YYYY-MM-DD string) and 'energy_kwh' (float)
    """
    try:
        builder = TimeSeriesQueryBuilder(session, user_id, inverter_id)
        time_filter = "time >= DATE_TRUNC('month', NOW() AT TIME ZONE :timezone)"
        yield_threshold = 5  # At least 5 days of data
        return await builder.get_energy_production(time_filter, yield_threshold)

    except Exception as e:
        logger.error(
            "Failed to get current month energy production",
            error=str(e),
            user_id=user_id,
            inverter_id=inverter_id,
        )
        return []
