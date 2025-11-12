"""
API endpoints for receiving measurement data from OpenDTU devices.

OpenDTU (https://github.com/tbnobody/OpenDTU) is an open-source firmware
for DTU (Data Transfer Unit) devices that monitor Hoymiles microinverters.
"""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from solar_backend.config import settings
from solar_backend.db import get_async_session
from solar_backend.repositories.inverter_repository import InverterRepository
from solar_backend.utils.timeseries import TimeSeriesException, write_dc_channel_measurement, write_measurement

logger = structlog.get_logger()

router = APIRouter()


class DCChannel(BaseModel):
    """DC channel/MPPT data."""

    channel: int
    name: str
    power: float
    voltage: float
    current: float
    yield_day: float
    yield_total: float
    irradiation: float


class InverterMeasurements(BaseModel):
    """AC measurements from inverter."""

    power_ac: float
    voltage_ac: float
    current_ac: float
    frequency: float
    power_factor: float
    power_dc: float


class InverterData(BaseModel):
    """Individual inverter data."""

    serial: str = Field(..., description="Serial number of the inverter")
    name: str
    reachable: bool
    producing: bool
    last_update: int
    measurements: InverterMeasurements
    dc_channels: list[DCChannel]


class MeasurementData(BaseModel):
    """Measurement data from OpenDTU device."""

    timestamp: datetime = Field(..., description="Measurement timestamp (ISO 8601 with timezone)")
    dtu_serial: str = Field(..., description="Serial number of the OpenDTU device")
    inverters: list[InverterData] = Field(..., description="Array of inverter data from OpenDTU")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-10-19T17:54:43+02:00",
                "dtu_serial": "199980140256",
                "inverters": [
                    {
                        "serial": "116183771004",
                        "name": "Windfang",
                        "reachable": True,
                        "producing": True,
                        "last_update": 1760889277,
                        "measurements": {
                            "power_ac": 16.1,
                            "voltage_ac": 229.8,
                            "current_ac": 0.07,
                            "frequency": 49.99,
                            "power_factor": 0.617,
                            "power_dc": 17,
                        },
                        "dc_channels": [
                            {
                                "channel": 1,
                                "name": "Hochbeet",
                                "power": 3.4,
                                "voltage": 30.4,
                                "current": 0.11,
                                "yield_day": 337,
                                "yield_total": 444.671,
                                "irradiation": 1.545455,
                            }
                        ],
                    }
                ],
            }
        }


async def validate_api_key(
    x_api_key: str = Header(None),
    session: AsyncSession = Depends(get_async_session),
) -> str:
    """
    Validate per-user API key by looking up the inverter serial.

    This is a placeholder validator that will be called within the endpoint
    to validate API keys on a per-inverter basis.
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    return x_api_key


@router.post("/api/opendtu/measurements", status_code=status.HTTP_201_CREATED)
async def post_opendtu_measurement(
    data: MeasurementData,
    x_api_key: str = Depends(validate_api_key),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Receive measurement data from OpenDTU devices.

    This endpoint receives data from OpenDTU (Data Transfer Unit) which may monitor
    multiple inverters. Each inverter's data is stored separately.

    Authentication is per-user: the API key in the header must match the api_key
    of the user who owns the inverter(s) in the payload.

    Args:
        data: Measurement data containing timestamp, DTU serial, and array of inverters
        x_api_key: User's API key for authentication
        session: Database session

    Returns:
        Success confirmation with results for each inverter

    Raises:
        207: Multi-Status if some inverters succeeded and others failed
        401: Unauthorized (API key doesn't match inverter owner)
        404: All inverters not found
        500: Database write error
    """
    results = []
    success_count = 0
    error_count = 0

    # Initialize repository
    inverter_repo = InverterRepository(session)

    # Process each inverter in the payload
    for inverter_data in data.inverters:
        try:
            # Find inverter by serial number
            inverter = await inverter_repo.get_by_serial(inverter_data.serial)

            if not inverter:
                logger.warning(
                    "Measurement received for unknown inverter",
                    serial=inverter_data.serial,
                    dtu_serial=data.dtu_serial,
                )
                results.append(
                    {
                        "serial": inverter_data.serial,
                        "status": "error",
                        "error": f"Inverter with serial {inverter_data.serial} not found",
                    }
                )
                error_count += 1
                continue

            # Get the user who owns this inverter
            user = inverter.users

            # Validate API key matches the inverter's owner
            if not user.api_key or user.api_key != x_api_key:
                logger.warning(
                    "Unauthorized API key for inverter",
                    serial=inverter_data.serial,
                    user_id=user.id,
                    dtu_serial=data.dtu_serial,
                )
                results.append(
                    {
                        "serial": inverter_data.serial,
                        "status": "error",
                        "error": "Unauthorized",
                    }
                )
                error_count += 1
                continue

            # Store IDs before write operation to avoid session detachment issues
            inverter_id = inverter.id
            user_id = user.id

            # Use power_ac as total_output_power (convert W to W, already in watts)
            total_output_power = int(inverter_data.measurements.power_ac)

            # Calculate aggregated yield values from DC channels if available
            yield_day_wh = None
            yield_total_kwh = None
            dc_channels_stored = 0

            if settings.STORE_DC_CHANNEL_DATA and inverter_data.dc_channels:
                # Write DC channel measurements
                yield_day_sum = 0
                yield_total_sum = 0

                for dc_channel in inverter_data.dc_channels:
                    await write_dc_channel_measurement(
                        session=session,
                        user_id=user_id,
                        inverter_id=inverter_id,
                        timestamp=data.timestamp,
                        channel=dc_channel.channel,
                        name=dc_channel.name,
                        power=dc_channel.power,
                        voltage=dc_channel.voltage,
                        current=dc_channel.current,
                        yield_day_wh=dc_channel.yield_day,
                        yield_total_kwh=dc_channel.yield_total,
                        irradiation=dc_channel.irradiation,
                    )
                    # Aggregate yield values
                    yield_day_sum += int(dc_channel.yield_day)
                    yield_total_sum += int(dc_channel.yield_total)
                    dc_channels_stored += 1

                # Set aggregated yields
                yield_day_wh = yield_day_sum
                yield_total_kwh = yield_total_sum

            # Write AC measurement to TimescaleDB with aggregated yield data
            await write_measurement(
                session=session,
                user_id=user_id,
                inverter_id=inverter_id,
                timestamp=data.timestamp,
                total_output_power=total_output_power,
                yield_day_wh=yield_day_wh,
                yield_total_kwh=yield_total_kwh,
            )

            logger.debug(
                "Measurements stored",
                serial=inverter_data.serial,
                inverter_id=inverter_id,
                user_id=user_id,
                power_ac=total_output_power,
                yield_day_wh=yield_day_wh,
                yield_total_kwh=yield_total_kwh,
                dc_channels_stored=dc_channels_stored,
                dc_channels_available=len(inverter_data.dc_channels),
                dc_storage_enabled=settings.STORE_DC_CHANNEL_DATA,
                dtu_serial=data.dtu_serial,
            )

            results.append(
                {
                    "serial": inverter_data.serial,
                    "status": "ok",
                    "inverter_id": inverter_id,
                    "power_ac": total_output_power,
                }
            )
            success_count += 1

        except TimeSeriesException as e:
            logger.error(
                "Failed to store measurement",
                error=str(e),
                serial=inverter_data.serial,
                dtu_serial=data.dtu_serial,
            )
            results.append(
                {
                    "serial": inverter_data.serial,
                    "status": "error",
                    "error": "Failed to store measurement",
                }
            )
            error_count += 1

    # Return appropriate response based on results
    response_data = {
        "dtu_serial": data.dtu_serial,
        "timestamp": data.timestamp.isoformat(),
        "total_inverters": len(data.inverters),
        "success_count": success_count,
        "error_count": error_count,
        "results": results,
    }

    if error_count > 0 and success_count > 0:
        # Mixed results - use 207 Multi-Status
        return JSONResponse(status_code=status.HTTP_207_MULTI_STATUS, content=response_data)
    elif error_count > 0 and success_count == 0:
        # All failed
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=response_data)
    else:
        # All succeeded
        return response_data
