import structlog
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_htmx import htmx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from solar_backend.db import Inverter, User, get_async_session
from solar_backend.users import current_active_user
from solar_backend.utils.timeseries import (
    TimeRange,
    get_latest_dc_channels,
    get_dc_channel_timeseries,
    set_rls_context,
    reset_rls_context,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/dc-channels/{inverter_id}", response_class=HTMLResponse)
@htmx("dc_channels", "dc_channels")
async def get_dc_channels_page(
    inverter_id: int,
    request: Request,
    time_range: str = "24 hours",
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
):
    """
    Display DC channel details page for a specific inverter.

    Args:
        inverter_id: ID of the inverter to display
        time_range: Time range for graph (1 hour, 6 hours, 24 hours, 7 days, 30 days)
        user: Current authenticated user
        db_session: Database session

    Returns:
        HTML page with DC channel cards and comparison chart
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or authentication required. Please log in again."
        )

    async with db_session as session:
        # Verify inverter belongs to user
        result = await session.execute(
            select(Inverter).where(
                Inverter.id == inverter_id, Inverter.user_id == user.id
            )
        )
        inverter = result.scalar_one_or_none()

        if not inverter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inverter nicht gefunden oder keine Berechtigung",
            )

    # Validate and convert time range
    try:
        time_range_enum = TimeRange(time_range)
    except ValueError:
        time_range_enum = TimeRange.default()
        time_range = time_range_enum.value

    logger.info(
        "DC Channels page accessed",
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
    }


@router.get("/api/dc-channels/{inverter_id}/data")
async def get_dc_channels_data(
    inverter_id: int,
    time_range: str = "24 hours",
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
):
    """
    API endpoint to fetch DC channel data.
    Returns JSON data for cards and chart.

    Args:
        inverter_id: ID of the inverter
        time_range: Time range (1 hour, 6 hours, 24 hours, 7 days, 30 days)
        user: Current authenticated user
        db_session: Database session

    Returns:
        JSON with channel data and time-series
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or authentication required. Please log in again."
        )

    async with db_session as session:
        # Verify inverter belongs to user
        result = await session.execute(
            select(Inverter).where(
                Inverter.id == inverter_id, Inverter.user_id == user.id
            )
        )
        inverter = result.scalar_one_or_none()

        if not inverter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inverter not found"
            )

        # Validate and convert time range
        try:
            time_range_enum = TimeRange(time_range)
        except ValueError:
            time_range_enum = TimeRange.default()
            time_range = time_range_enum.value

        try:
            # Set RLS context
            await set_rls_context(session, user.id)

            # Get latest channel data (for cards)
            latest_channels = await get_latest_dc_channels(
                session=session,
                user_id=user.id,
                inverter_id=inverter.id,
            )

            # Get time-series data (for chart)
            channel_timeseries = await get_dc_channel_timeseries(
                session=session,
                user_id=user.id,
                inverter_id=inverter.id,
                time_range=time_range,
            )

            # Calculate time since last update
            time_ago = "Keine Daten"
            if latest_channels:
                latest_time = max(ch["time"] for ch in latest_channels)
                delta = datetime.now(latest_time.tzinfo) - latest_time
                if delta.total_seconds() < 60:
                    time_ago = "vor einer Minute"
                elif delta.total_seconds() < 3600:
                    minutes = int(delta.total_seconds() / 60)
                    time_ago = f"vor {minutes} Minuten"
                elif delta.total_seconds() < 86400:
                    hours = int(delta.total_seconds() / 3600)
                    time_ago = f"vor {hours} Stunden"
                else:
                    days = int(delta.total_seconds() / 86400)
                    time_ago = f"vor {days} Tagen"

            # Format channel data for response
            channels_data = []
            for ch in latest_channels:
                channels_data.append({
                    "channel": ch["channel"],
                    "name": ch["name"],
                    "power": round(ch["power"], 1),
                    "voltage": round(ch["voltage"], 1),
                    "current": round(ch["current"], 2),
                    "yield_day_wh": round(ch["yield_day_wh"], 1),
                    "yield_total_kwh": round(ch["yield_total_kwh"], 1),
                    "irradiation": round(ch["irradiation"], 3),
                    "time_ago": time_ago,
                })

            logger.info(
                "DC Channels data retrieved",
                inverter_id=inverter_id,
                time_range=time_range,
                channels_count=len(channels_data),
            )

            return JSONResponse(
                {
                    "success": True,
                    "channels": channels_data,
                    "timeseries": channel_timeseries,
                    "inverter": {
                        "id": inverter.id,
                        "name": inverter.name,
                        "serial": inverter.serial_logger,
                    },
                }
            )

        except Exception as e:
            logger.error(
                "DC Channels data retrieval failed",
                inverter_id=inverter_id,
                time_range=time_range,
                error=str(e),
                exc_info=True,
            )
            return JSONResponse(
                {
                    "success": False,
                    "message": "Fehler beim Abrufen der DC Channel Daten",
                    "channels": [],
                    "timeseries": {},
                },
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            # Always reset RLS context
            await reset_rls_context(session)
