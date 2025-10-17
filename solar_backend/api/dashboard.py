import structlog
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_htmx import htmx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from solar_backend.db import Inverter, User, get_async_session
from solar_backend.users import current_active_user
from solar_backend.utils.influx import InfluxManagement, NoValuesException, InfluxConnectionError

logger = structlog.get_logger()

router = APIRouter()


@router.get("/dashboard/{inverter_id}", response_class=HTMLResponse)
@htmx("dashboard", "dashboard")
async def get_dashboard(
    inverter_id: int,
    request: Request,
    time_range: str = "24h",
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session)
):
    """
    Display real-time power dashboard for a specific inverter.

    Args:
        inverter_id: ID of the inverter to display
        time_range: Time range for graph (1h, 6h, 24h, 7d, 30d)
        user: Current authenticated user
        db_session: Database session

    Returns:
        HTML dashboard with power graph and statistics
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
                detail="Inverter nicht gefunden oder keine Berechtigung"
            )

    # Validate time range
    valid_ranges = ["1h", "6h", "24h", "7d", "30d"]
    if time_range not in valid_ranges:
        time_range = "24h"

    logger.info(
        "Dashboard accessed",
        inverter_id=inverter_id,
        inverter_name=inverter.name,
        time_range=time_range,
        user_id=user.id
    )

    return {
        "user": user,
        "inverter": inverter,
        "time_range": time_range,
        "valid_ranges": valid_ranges
    }


@router.get("/api/dashboard/{inverter_id}/data")
async def get_dashboard_data(
    inverter_id: int,
    time_range: str = "24h",
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session)
):
    """
    API endpoint to fetch time-series data for dashboard graph.
    Returns JSON data for Chart.js consumption.

    Args:
        inverter_id: ID of the inverter
        time_range: Time range (1h, 6h, 24h, 7d, 30d)
        user: Current authenticated user
        db_session: Database session

    Returns:
        JSON with timestamps and power values
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
        async with InfluxManagement(user.influx_url) as inflx:
            inflx.connect(org=user.email, token=user.influx_token)

            # Get time-series data
            data_points = inflx.get_power_timeseries(
                user=user,
                bucket=inverter.name,
                time_range=time_range
            )

            # Get current power (latest value)
            current = 0
            if data_points:
                powers = [d["power"] for d in data_points]
                current = powers[-1] if powers else 0

            # Get today's maximum power (independent of time range)
            try:
                max_today = inflx.get_today_maximum_power(user=user, bucket=inverter.name)
            except Exception as e:
                logger.warning("Failed to get today's maximum power", error=str(e))
                max_today = 0

            # Get today's energy production (kWh)
            try:
                today_kwh = inflx.get_today_energy_production(user=user, bucket=inverter.name)
            except Exception as e:
                logger.warning("Failed to get today's energy production", error=str(e))
                today_kwh = 0.0

            # Get last hour average (always last hour, regardless of selected time range)
            try:
                avg_last_hour = inflx.get_last_hour_average(user=user, bucket=inverter.name)
            except Exception as e:
                logger.warning("Failed to get last hour average", error=str(e))
                avg_last_hour = 0

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

    except InfluxConnectionError as e:
        logger.error(
            "InfluxDB connection failed for dashboard",
            inverter_id=inverter_id,
            time_range=time_range,
            error=str(e)
        )
        return JSONResponse({
            "success": False,
            "message": "InfluxDB-Dienst ist vorübergehend nicht verfügbar. Bitte versuchen Sie es später erneut oder kontaktieren Sie den Administrator.",
            "data": [],
            "stats": {"current": 0, "max": 0, "today_kwh": 0.0, "avg_last_hour": 0},
            "inverter": {
                "id": inverter.id,
                "name": inverter.name,
                "serial": inverter.serial_logger
            }
        })
    except NoValuesException as e:
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
