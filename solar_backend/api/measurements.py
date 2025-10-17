"""
API endpoints for receiving measurement data from inverters/collectors.
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
    timestamp: datetime = Field(
        ..., description="Measurement timestamp (ISO 8601 with timezone)"
    )
    measurements: dict = Field(..., description="Measurement values")

    class Config:
        json_schema_extra = {
            "example": {
                "serial": "ABC123456",
                "timestamp": "2025-10-17T10:30:00Z",
                "measurements": {"total_output_power": 5420},
            }
        }


@router.post("/api/measurements", status_code=status.HTTP_201_CREATED)
async def post_measurement(
    data: MeasurementData,
    user: User = Depends(current_superuser_bearer),
    session: AsyncSession = Depends(get_async_session),
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
            collector_user_id=user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inverter with serial {data.serial} not found",
        )

    # Extract power from measurements
    total_output_power = data.measurements.get("total_output_power")
    if total_output_power is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="measurements.total_output_power is required",
        )

    # Write to TimescaleDB
    try:
        await write_measurement(
            session=session,
            user_id=inverter.user_id,
            inverter_id=inverter.id,
            timestamp=data.timestamp,
            total_output_power=int(total_output_power),
        )

        logger.info(
            "Measurement stored",
            serial=data.serial,
            inverter_id=inverter.id,
            user_id=inverter.user_id,
            power=total_output_power,
        )

        return {
            "status": "ok",
            "inverter_id": inverter.id,
            "user_id": inverter.user_id,
            "timestamp": data.timestamp.isoformat(),
        }

    except TimeSeriesException as e:
        logger.error(
            "Failed to store measurement",
            error=str(e),
            serial=data.serial,
            inverter_id=inverter.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store measurement",
        )
