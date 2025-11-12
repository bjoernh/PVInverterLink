import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_htmx import htmx
from sqlalchemy.ext.asyncio import AsyncSession

from solar_backend.config import settings
from solar_backend.constants import UNAUTHORIZED_MESSAGE
from solar_backend.db import User, get_async_session
from solar_backend.services.exceptions import InverterNotFoundException
from solar_backend.services.inverter_service import InverterService
from solar_backend.users import current_active_user
from solar_backend.utils.timeseries import (
    EnergyPeriod,
    NoDataException,
    TimeRange,
    TimeSeriesException,
    get_current_month_energy_production,
    get_current_week_energy_production,
    get_hourly_energy_production,
    get_last_hour_average,
    get_power_timeseries,
    get_today_energy_production,
    get_today_maximum_power,
    rls_context,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/dashboard/{inverter_id}", response_class=HTMLResponse)
@htmx("dashboard", "dashboard")
async def get_dashboard(
    inverter_id: int,
    request: Request,
    time_range: str = "24 hours",
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    Display real-time power dashboard for a specific inverter.

    Args:
        inverter_id: ID of the inverter to display
        time_range: Time range for graph (1 hour, 6 hours, 24 hours, 7 days, 30 days)
        user: Current authenticated user
        db_session: Database session

    Returns:
        HTML dashboard with power graph and statistics
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_MESSAGE + " Please log in again.",
        )

    async with db_session as session:
        inverter_service = InverterService(session)
        try:
            inverter = await inverter_service.get_user_inverter(user.id, inverter_id)
        except InverterNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inverter nicht gefunden oder keine Berechtigung",
            ) from e

    # Validate and convert time range
    try:
        time_range_enum = TimeRange(time_range)
    except ValueError:
        time_range_enum = TimeRange.default()
        time_range = time_range_enum.value

    logger.info(
        "Dashboard accessed",
        inverter_id=inverter_id,
        inverter_name=inverter.name,
        time_range=time_range,
        user_id=user.id,
    )

    return {
        "user": user,
        "inverter": inverter,
        "time_range": time_range,
        "valid_ranges": [tr.value for tr in TimeRange],
        "range_labels": {tr.value: tr.label for tr in TimeRange},
        "auto_refresh_rate": settings.AUTO_REFRESH_RATE,
    }


@router.get("/api/dashboard/{inverter_id}/data")
async def get_dashboard_data(
    inverter_id: int,
    time_range: str = "24 hours",
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> JSONResponse:
    """
    API endpoint to fetch time-series data for dashboard graph.
    Returns JSON data for Plotly consumption.

    Args:
        inverter_id: ID of the inverter
        time_range: Time range (1 hour, 6 hours, 24 hours, 7 days, 30 days)
        user: Current authenticated user
        db_session: Database session

    Returns:
        JSON with timestamps and power values
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_MESSAGE + " Please log in again.",
        )

    async with db_session as session:
        inverter_service = InverterService(session)
        try:
            inverter = await inverter_service.get_user_inverter(user.id, inverter_id)
        except InverterNotFoundException as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inverter not found") from e

        # Validate and convert time range
        try:
            time_range_enum = TimeRange(time_range)
        except ValueError:
            time_range_enum = TimeRange.default()
            time_range = time_range_enum.value

        try:
            async with rls_context(session, user.id):
                # Get time-series data
                data_points = await get_power_timeseries(
                    session=session,
                    user_id=user.id,
                    inverter_id=inverter.id,
                    time_range=time_range,
                )

                # Get current power (latest value)
                current = data_points[-1]["power"] if data_points else 0

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

                stats = {
                    "current": current,
                    "max": max_today,
                    "today_kwh": today_kwh,
                    "avg_last_hour": avg_last_hour,
                }

                logger.info(
                    "Dashboard data retrieved",
                    inverter_id=inverter_id,
                    time_range=time_range,
                    data_points=len(data_points),
                )

                return JSONResponse(
                    {
                        "success": True,
                        "data": data_points,
                        "stats": stats,
                        "inverter": {
                            "id": inverter.id,
                            "name": inverter.name,
                            "serial": inverter.serial_logger,
                        },
                    }
                )
        except NoDataException as e:
            logger.warning(
                "No data available for dashboard",
                inverter_id=inverter_id,
                time_range=time_range,
                error=str(e),
            )
            return JSONResponse(
                {
                    "success": False,
                    "message": "Keine Daten verfügbar für den gewählten Zeitraum",
                    "data": [],
                    "stats": {
                        "current": 0,
                        "max": 0,
                        "today_kwh": 0.0,
                        "avg_last_hour": 0,
                    },
                    "inverter": {
                        "id": inverter.id,
                        "name": inverter.name,
                        "serial": inverter.serial_logger,
                    },
                }
            )
        except TimeSeriesException as e:
            logger.error(
                "Time-series query failed for dashboard",
                inverter_id=inverter_id,
                time_range=time_range,
                error=str(e),
            )
            return JSONResponse(
                {
                    "success": False,
                    "message": "Fehler beim Abrufen der Daten",
                    "data": [],
                    "stats": {
                        "current": 0,
                        "max": 0,
                        "today_kwh": 0.0,
                        "avg_last_hour": 0,
                    },
                    "inverter": {
                        "id": inverter.id,
                        "name": inverter.name,
                        "serial": inverter.serial_logger,
                    },
                }
            )
        except Exception as e:
            logger.error(
                "Dashboard data retrieval failed",
                inverter_id=inverter_id,
                time_range=time_range,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Fehler beim Abrufen der Daten",
            ) from e


@router.get("/api/dashboard/{inverter_id}/energy-data")
async def get_dashboard_energy_data(
    inverter_id: int,
    period: str = "day",
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> JSONResponse:
    """
    API endpoint to fetch daily/hourly energy production data for bar chart.

    Args:
        inverter_id: ID of the inverter
        period: Time period (EnergyPeriod enum value)
        user: Current authenticated user
        db_session: Database session

    Returns:
        JSON with labels and energy values
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_MESSAGE + " Please log in again.",
        )

    async with db_session as session:
        inverter_service = InverterService(session)
        try:
            inverter = await inverter_service.get_user_inverter(user.id, inverter_id)
        except InverterNotFoundException as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inverter not found") from e

        # Validate and convert period to enum
        try:
            period_enum = EnergyPeriod(period)
        except ValueError:
            period_enum = EnergyPeriod.default()
            period = period_enum.value

        try:
            async with rls_context(session, user.id):
                # Get energy data based on period
                if period_enum == EnergyPeriod.DAY:
                    # Get hourly data for today
                    hourly_data = await get_hourly_energy_production(session, user.id, inverter.id)

                    # Format data for response
                    data_points = [
                        {
                            "label": f"{item['hour']:02d}:00",
                            "energy_kwh": round(item["energy_kwh"], 2),
                        }
                        for item in hourly_data
                    ]

                elif period_enum == EnergyPeriod.MONTH:
                    # Get daily data for current month
                    daily_data = await get_current_month_energy_production(session, user.id, inverter.id)

                    # Format data for response with German date format
                    data_points = []
                    for item in daily_data:
                        # Convert YYYY-MM-DD to DD.MM. format
                        date_parts = item["date"].split("-")
                        label = f"{date_parts[2]}.{date_parts[1]}."
                        data_points.append(
                            {
                                "label": label,
                                "energy_kwh": round(item["energy_kwh"], 2),
                            }
                        )

                else:  # Default to EnergyPeriod.WEEK
                    # Get daily data for current week (Monday-Sunday)
                    daily_data = await get_current_week_energy_production(session, user.id, inverter.id)

                    # Format data for response with German date format
                    data_points = []
                    for item in daily_data:
                        # Convert YYYY-MM-DD to DD.MM. format
                        date_parts = item["date"].split("-")
                        label = f"{date_parts[2]}.{date_parts[1]}."
                        data_points.append(
                            {
                                "label": label,
                                "energy_kwh": round(item["energy_kwh"], 2),
                            }
                        )

                logger.info(
                    "Energy data retrieved",
                    inverter_id=inverter_id,
                    period=period,
                    data_points=len(data_points),
                )

                return JSONResponse(
                    {
                        "success": True,
                        "period": period,
                        "data": data_points,
                        "inverter": {
                            "id": inverter.id,
                            "name": inverter.name,
                            "serial": inverter.serial_logger,
                        },
                    }
                )
        except Exception as e:
            logger.error(
                "Energy data retrieval failed",
                inverter_id=inverter_id,
                period=period,
                error=str(e),
                exc_info=True,
            )
            return JSONResponse(
                {
                    "success": False,
                    "period": period,
                    "data": [],
                    "message": "Fehler beim Abrufen der Energiedaten",
                }
            )
