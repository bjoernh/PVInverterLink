"""
API endpoints for receiving measurement data from Victron Venus OS devices.

Victron Venus OS (https://github.com/victronenergy/venus) runs on Cerbo GX and
other Victron GX devices. It monitors Victron solar chargers, inverters, and
other energy system components via D-Bus.

This endpoint receives data from a custom bridge script running on Venus OS that
reads values from D-Bus and posts them here.
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


class VictronTrackerData(BaseModel):
    """Per-MPPT tracker data from Victron solar charger."""

    tracker: int = Field(..., description="Tracker number (0-based index)")
    name: str = Field(..., description="Tracker name or identifier")
    voltage: float = Field(..., description="PV voltage in Volts")
    power: float = Field(..., description="PV power in Watts")


class VictronDeviceData(BaseModel):
    """Individual Victron device (solar charger/inverter) data."""

    device_instance: int = Field(..., description="Device instance ID from D-Bus")
    serial: str = Field(..., description="Device serial number")
    name: str = Field(..., description="Device name (CustomName or ProductName)")
    product_name: str = Field(..., description="Product model name")
    reachable: bool = Field(..., description="Device is reachable via D-Bus")
    producing: bool = Field(..., description="Device is currently producing power")
    last_update: int = Field(..., description="Unix timestamp of last D-Bus update")
    yield_power_w: float = Field(..., description="Total yield power in Watts")
    yield_total_kwh: float = Field(..., description="Lifetime energy yield in kWh")
    trackers: list[VictronTrackerData] = Field(
        default_factory=list, description="Per-tracker data (for multi-MPPT devices)"
    )


class VictronMeasurementData(BaseModel):
    """Measurement data from Victron Venus OS device."""

    timestamp: datetime = Field(..., description="Measurement timestamp (ISO 8601 with timezone)")
    cerbo_serial: str = Field(..., description="Serial number of the Cerbo GX device")
    devices: list[VictronDeviceData] = Field(..., description="Array of device data from Venus OS")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-10-30T14:32:15+01:00",
                "cerbo_serial": "HQ2345ABCDE",
                "devices": [
                    {
                        "device_instance": 0,
                        "serial": "HQ22345ABCD",
                        "name": "SmartSolar MPPT 150/35",
                        "product_name": "SmartSolar MPPT 150/35",
                        "reachable": True,
                        "producing": True,
                        "last_update": 1730297535,
                        "yield_power_w": 245.5,
                        "yield_total_kwh": 1234.56,
                        "trackers": [
                            {
                                "tracker": 0,
                                "name": "PV-1",
                                "voltage": 48.3,
                                "power": 245.5,
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
    Validate per-user API key by looking up the device identifier.

    This is a placeholder validator that will be called within the endpoint
    to validate API keys on a per-device basis.
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    return x_api_key


@router.post("/api/victron/measurements", status_code=status.HTTP_201_CREATED)
async def post_victron_measurement(
    data: VictronMeasurementData,
    x_api_key: str = Depends(validate_api_key),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Receive measurement data from Victron Venus OS devices.

    This endpoint receives data from a Cerbo GX (or other Venus OS device) which may
    monitor multiple solar chargers/inverters. Each device's data is stored separately.

    Device Identification:
        Devices are identified by their serial number from the device itself.
        serial_logger format: Device serial number (e.g., "HQ2208AXN7V")
        This is the actual serial number of the solar charger/inverter.

    Authentication:
        The API key in the header must match the api_key of the user who owns
        the device(s) in the payload.

    Args:
        data: Measurement data containing timestamp, Cerbo serial, and array of devices
        x_api_key: User's API key for authentication
        session: Database session

    Returns:
        Success confirmation with results for each device

    Raises:
        207: Multi-Status if some devices succeeded and others failed
        401: Unauthorized (API key doesn't match device owner)
        404: All devices not found
        500: Database write error
    """
    results = []
    success_count = 0
    error_count = 0

    # Initialize repository
    inverter_repo = InverterRepository(session)

    # Process each device in the payload
    for device_data in data.devices:
        try:
            # Use device serial as identifier
            device_identifier = device_data.serial

            # Find inverter by device serial
            inverter = await inverter_repo.get_by_serial(device_identifier)

            if not inverter:
                logger.warning(
                    "Measurement received for unknown device",
                    device_serial=device_identifier,
                    device_instance=device_data.device_instance,
                    cerbo_serial=data.cerbo_serial,
                )
                results.append(
                    {
                        "device_identifier": device_identifier,
                        "status": "error",
                        "error": f"Device {device_identifier} not found",
                    }
                )
                error_count += 1
                continue

            # Get the user who owns this inverter
            user = inverter.users

            # Validate API key matches the inverter's owner
            if not user.api_key or user.api_key != x_api_key:
                logger.warning(
                    "Unauthorized API key for device",
                    device_serial=device_identifier,
                    user_id=user.id,
                    cerbo_serial=data.cerbo_serial,
                )
                results.append(
                    {
                        "device_identifier": device_identifier,
                        "status": "error",
                        "error": "Unauthorized",
                    }
                )
                error_count += 1
                continue

            # Store IDs before write operation to avoid session detachment issues
            inverter_id = inverter.id
            user_id = user.id

            # Use yield_power_w as total_output_power (already in Watts)
            total_output_power = int(device_data.yield_power_w)

            # Yield total is provided directly in kWh
            yield_total_kwh = int(device_data.yield_total_kwh)

            # yield_day_wh will be calculated by aggregating from trackers if available
            yield_day_wh = None
            trackers_stored = 0

            if settings.STORE_DC_CHANNEL_DATA and device_data.trackers:
                # Write per-tracker measurements as DC channels
                tracker_power_sum = 0

                for tracker in device_data.trackers:
                    # Calculate current from power and voltage: I = P / V
                    current = tracker.power / tracker.voltage if tracker.voltage > 0 else 0

                    await write_dc_channel_measurement(
                        session=session,
                        user_id=user_id,
                        inverter_id=inverter_id,
                        timestamp=data.timestamp,
                        channel=tracker.tracker + 1,  # Convert 0-based to 1-based for storage
                        name=tracker.name,
                        power=tracker.power,
                        voltage=tracker.voltage,
                        current=current,
                        yield_day_wh=0.0,  # Not available from Victron per-tracker, use 0
                        yield_total_kwh=0.0,  # Not available from Victron per-tracker, use 0
                        irradiation=0.0,  # Not available from Victron, use 0
                    )
                    tracker_power_sum += tracker.power
                    trackers_stored += 1

                # Note: yield_day_wh remains None as it's not provided per-tracker by Victron
                # The backend can calculate daily yield from the yield_total_kwh over time

            # Write measurement to TimescaleDB
            await write_measurement(
                session=session,
                user_id=user_id,
                inverter_id=inverter_id,
                timestamp=data.timestamp,
                total_output_power=total_output_power,
                yield_day_wh=yield_day_wh,  # None - not available from Victron
                yield_total_kwh=yield_total_kwh,
            )

            logger.debug(
                "Victron measurements stored",
                device_serial=device_identifier,
                inverter_id=inverter_id,
                user_id=user_id,
                yield_power_w=total_output_power,
                yield_total_kwh=yield_total_kwh,
                trackers_stored=trackers_stored,
                trackers_available=len(device_data.trackers),
                dc_storage_enabled=settings.STORE_DC_CHANNEL_DATA,
                cerbo_serial=data.cerbo_serial,
            )

            results.append(
                {
                    "device_identifier": device_identifier,
                    "status": "ok",
                    "inverter_id": inverter_id,
                    "yield_power_w": total_output_power,
                }
            )
            success_count += 1

        except TimeSeriesException as e:
            logger.error(
                "Failed to store Victron measurement",
                error=str(e),
                device_serial=device_identifier,
                cerbo_serial=data.cerbo_serial,
            )
            results.append(
                {
                    "device_identifier": device_identifier,
                    "status": "error",
                    "error": "Failed to store measurement",
                }
            )
            error_count += 1

    # Return appropriate response based on results
    response_data = {
        "cerbo_serial": data.cerbo_serial,
        "timestamp": data.timestamp.isoformat(),
        "total_devices": len(data.devices),
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
