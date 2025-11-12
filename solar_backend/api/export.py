"""
API endpoints for exporting measurement data as CSV files.
"""

import csv
import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi_htmx import htmx
from sqlalchemy.ext.asyncio import AsyncSession

from solar_backend.config import settings
from solar_backend.constants import UNAUTHORIZED_MESSAGE
from solar_backend.db import User, get_async_session
from solar_backend.services.exceptions import InverterNotFoundException, UnauthorizedInverterAccessException
from solar_backend.services.inverter_service import InverterService
from solar_backend.users import current_active_user
from solar_backend.utils.timeseries import (
    NoDataException,
    TimeSeriesException,
    get_raw_measurements,
    rls_context,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/export/{inverter_id}", response_class=HTMLResponse)
@htmx("export", "export")
async def get_export_page(
    inverter_id: int,
    request: Request,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    Display the data export page for a specific inverter.

    Allows users to select a date range and download measurement data as CSV.

    Args:
        inverter_id: ID of the inverter to export data for
        request: Request object
        user: Current authenticated user
        db_session: Database session

    Returns:
        HTML export page
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_MESSAGE + " Please log in again."
        )

    async with db_session as session:
        # Verify inverter belongs to user
        inverter_service = InverterService(session)
        try:
            inverter = await inverter_service.get_user_inverter(user.id, inverter_id)
        except (InverterNotFoundException, UnauthorizedInverterAccessException) as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inverter nicht gefunden oder keine Berechtigung",
            ) from e

    logger.info(
        "Export page accessed",
        inverter_id=inverter_id,
        inverter_name=inverter.name,
        user_id=user.id,
    )

    # Default to last 7 days
    tz = ZoneInfo(settings.TZ)
    end_date = datetime.now(tz).date()
    start_date = end_date - timedelta(days=7)

    return {
        "user": user,
        "inverter": inverter,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "settings": settings,
    }


@router.get("/api/export/{inverter_id}/csv")
async def export_csv(
    inverter_id: int,
    start_date: str,
    end_date: str,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    """
    Generate and download measurement data as CSV file.

    Args:
        inverter_id: ID of the inverter to export
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
        user: Current authenticated user
        db_session: Database session

    Returns:
        CSV file as StreamingResponse
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_MESSAGE + " Please log in again."
        )

    # Parse and validate dates
    try:
        tz = ZoneInfo(settings.TZ)
        start_dt = datetime.fromisoformat(start_date).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)
        end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        ) from e

    # Validate date range
    if start_dt > end_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date",
        )

    if end_dt > datetime.now(tz):
        end_dt = datetime.now(tz)

    async with db_session as session:
        # Verify inverter belongs to user
        inverter_service = InverterService(session)
        try:
            inverter = await inverter_service.get_user_inverter(user.id, inverter_id)
        except (InverterNotFoundException, UnauthorizedInverterAccessException) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inverter not found") from e

        try:
            async with rls_context(session, user.id):
                # Get measurement data
                data_points = await get_raw_measurements(
                    session=session,
                    user_id=user.id,
                    inverter_id=inverter.id,
                    start_date=start_dt,
                    end_date=end_dt,
                )

                # Calculate statistics from exported data
                if data_points:
                    powers = [dp["power"] for dp in data_points]
                    data_max = max(powers)
                    data_avg = sum(powers) / len(powers)
                    data_min = min(powers)
                    data_count = len(data_points)
                else:
                    data_max = 0
                    data_avg = 0
                    data_min = 0
                    data_count = 0

                logger.info(
                    "Exporting measurement data to CSV",
                    inverter_id=inverter_id,
                    start_date=start_dt,
                    end_date=end_dt,
                    data_points=data_count,
                    user_id=user.id,
                )

                # Generate CSV content
                output = io.StringIO()
                writer = csv.writer(output)

                # Write header comments with metadata
                writer.writerow(
                    [
                        "# Messdaten-Export",
                        "Solar Inverter Measurement Export",
                    ]
                )
                writer.writerow(["# Wechselrichter", "Inverter"])
                writer.writerow([f"# {inverter.name}", f"# {inverter.name}"])
                writer.writerow([f"# Seriennummer: {inverter.serial_logger}"])
                writer.writerow([f"# Benutzer: {user.first_name} {user.last_name}"])
                writer.writerow([f"# Exportdatum: {datetime.now(tz).isoformat()}", "# Export Date"])
                writer.writerow([""])

                # Write date range info
                writer.writerow(
                    [
                        f"# Zeitraum: {start_dt.date()} bis {end_dt.date()}",
                        f"# Period: {start_dt.date()} to {end_dt.date()}",
                    ]
                )
                writer.writerow([f"# Anzahl Datenpunkte: {data_count}", "# Data Points"])
                writer.writerow([""])

                # Write statistics
                writer.writerow(
                    [
                        "# Statistiken",
                        "Statistics",
                    ]
                )
                writer.writerow([f"# Maximale Leistung: {data_max} W", f"# Max Power: {data_max} W"])
                writer.writerow(
                    [
                        f"# Durchschnittliche Leistung: {data_avg:.1f} W",
                        f"# Average Power: {data_avg:.1f} W",
                    ]
                )
                writer.writerow([f"# Minimale Leistung: {data_min} W", f"# Min Power: {data_min} W"])
                writer.writerow([""])

                # Write column headers
                writer.writerow(["Zeitstempel", "Leistung (W)"])

                # Write data rows
                for dp in data_points:
                    writer.writerow([dp["time"], dp["power"]])

                # Generate filename
                filename = f"solar_measurements_{inverter.name}_{start_date}_{end_date}.csv"
                # Remove invalid characters from filename
                filename = "".join(c for c in filename if c.isalnum() or c in ".-_ ")

                # Return as file download
                return StreamingResponse(
                    iter([output.getvalue()]),
                    media_type="text/csv; charset=utf-8-sig",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )
        except NoDataException as e:
            logger.warning(
                "No data available for export",
                inverter_id=inverter_id,
                start_date=start_dt,
                end_date=end_dt,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Keine Messdaten für den gewählten Zeitraum verfügbar",
            ) from e
        except TimeSeriesException as e:
            logger.error(
                "Time-series query failed for export",
                inverter_id=inverter_id,
                start_date=start_dt,
                end_date=end_dt,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Fehler beim Abrufen der Daten",
            ) from e
        except Exception as e:
            logger.error(
                "CSV export failed",
                inverter_id=inverter_id,
                start_date=start_dt,
                end_date=end_dt,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Fehler beim Generieren der CSV-Datei",
            ) from e
