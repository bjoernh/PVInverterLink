import structlog
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_htmx import htmx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from solar_backend.db import Inverter, User, get_async_session
from solar_backend.users import current_active_user
from solar_backend.utils.influx import InfluxManagement, NoValuesException

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
            data_points = inflx.get_power_timeseries(
                user=user,
                bucket=inverter.name,
                time_range=time_range
            )

        # Calculate statistics
        if data_points:
            powers = [d["power"] for d in data_points]
            stats = {
                "current": powers[-1] if powers else 0,
                "max": max(powers) if powers else 0,
                "min": min(powers) if powers else 0,
                "avg": int(sum(powers) / len(powers)) if powers else 0
            }
        else:
            stats = {"current": 0, "max": 0, "min": 0, "avg": 0}

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
            "stats": {"current": 0, "max": 0, "min": 0, "avg": 0},
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
