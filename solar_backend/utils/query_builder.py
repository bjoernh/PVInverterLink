"""
Time-series query builder for TimescaleDB.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from zoneinfo import ZoneInfo
import structlog

from solar_backend.config import settings

logger = structlog.get_logger()


class TimeSeriesQueryBuilder:
    """
    Builds and executes time-series queries for inverter data.
    """

    def __init__(self, session: AsyncSession, user_id: int, inverter_id: int):
        """
        Initialize the query builder.

        Args:
            session: The database session.
            user_id: The user's ID for RLS.
            inverter_id: The inverter's ID.
        """
        self.session = session
        self.user_id = user_id
        self.inverter_id = inverter_id
        self.tz = ZoneInfo(settings.TZ)

    async def get_energy_production(
        self, time_filter_clause: str, yield_threshold: int
    ) -> list[dict]:
        """
        Get daily energy production for a given time period.

        Prioritizes inverter-provided yield data, falling back to power integration.

        Args:
            time_filter_clause: The SQL WHERE clause for the time period.
            yield_threshold: The minimum number of days with yield data to use it.

        Returns:
            List of dicts with 'date' and 'energy_kwh'.
        """
        # Try to get yield_day_wh data first (most accurate)
        yield_query = self._build_yield_query(time_filter_clause)
        result = await self.session.execute(
            yield_query,
            {
                "user_id": self.user_id,
                "inverter_id": self.inverter_id,
                "timezone": str(self.tz),
            },
        )
        yield_data = [
            {
                "date": row.date.isoformat(),
                "energy_kwh": float(row.yield_day_wh) / 1000.0,
            }
            for row in result
        ]

        if len(yield_data) >= yield_threshold:
            logger.debug(
                "Using inverter yield data for daily energy",
                user_id=self.user_id,
                inverter_id=self.inverter_id,
                days_found=len(yield_data),
                source="inverter",
            )
            return yield_data

        # Fallback: Calculate from power measurements
        logger.debug(
            "Insufficient yield data, falling back to power integration",
            user_id=self.user_id,
            inverter_id=self.inverter_id,
            yield_days=len(yield_data),
        )
        integration_query = self._build_integration_query(time_filter_clause)
        result = await self.session.execute(
            integration_query,
            {
                "user_id": self.user_id,
                "inverter_id": self.inverter_id,
                "timezone": str(self.tz),
            },
        )
        integrated_data = [
            {"date": row.date.isoformat(), "energy_kwh": float(row.energy_kwh)}
            for row in result
        ]

        logger.debug(
            "Calculated daily energy from power integration",
            user_id=self.user_id,
            inverter_id=self.inverter_id,
            days_found=len(integrated_data),
            source="calculated",
        )
        return integrated_data

    def _build_yield_query(self, time_filter_clause: str):
        return text(f"""
            WITH last_daily_measurement AS (
                SELECT DISTINCT ON (DATE(time AT TIME ZONE :timezone))
                    DATE(time AT TIME ZONE :timezone) AS date,
                    yield_day_wh
                FROM inverter_measurements
                WHERE user_id = :user_id
                  AND inverter_id = :inverter_id
                  AND {time_filter_clause}
                  AND yield_day_wh IS NOT NULL
                ORDER BY DATE(time AT TIME ZONE :timezone), time DESC
            )
            SELECT date, yield_day_wh
            FROM last_daily_measurement
            WHERE yield_day_wh > 0
            ORDER BY date ASC
        """)

    def _build_integration_query(self, time_filter_clause: str):
        return text(f"""
            WITH power_data AS (
                SELECT
                    DATE(time AT TIME ZONE :timezone) AS date,
                    time,
                    total_output_power,
                    EXTRACT(EPOCH FROM time - LAG(time) OVER (PARTITION BY DATE(time AT TIME ZONE :timezone) ORDER BY time)) AS time_diff_seconds
                FROM inverter_measurements
                WHERE user_id = :user_id
                  AND inverter_id = :inverter_id
                  AND {time_filter_clause}
                ORDER BY time
            ),
            daily_energy AS (
                SELECT
                    date,
                    COALESCE(
                        SUM((total_output_power * time_diff_seconds) / 3600000.0),
                        0
                    ) AS energy_kwh
                FROM power_data
                WHERE time_diff_seconds IS NOT NULL
                GROUP BY date
                ORDER BY date ASC
            )
            SELECT date, energy_kwh
            FROM daily_energy
            WHERE energy_kwh > 0
        """)
