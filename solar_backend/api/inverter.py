import asyncpg
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from fastapi_users import BaseUserManager


from fastapi import APIRouter, Depends, Request, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_htmx import htmx

from solar_backend.db import User, get_async_session
from solar_backend.schemas import InverterAdd, InverterAddMetadata
from solar_backend.schemas import Inverter as InverterSchema
from solar_backend.users import current_active_user, current_superuser_bearer
from solar_backend.db import Inverter


logger = structlog.get_logger()

router = APIRouter()


@router.get("/add_inverter", response_class=HTMLResponse)
@htmx("add_inverter", "add_inverter")
async def get_add_inverter(request: Request, user: User = Depends(current_active_user)):
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)

    # Block unverified users
    if not user.is_verified:
        return HTMLResponse(
            """<div class="sm:mx-auto sm:w-full sm:max-w-sm">
                <div class="alert alert-warning shadow-lg mt-6">
                    <div>
                        <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <div>
                            <h3 class="font-bold">Email-Verifizierung erforderlich</h3>
                            <div class="text-sm">Bitte verifizieren Sie zuerst Ihre E-Mail-Adresse, bevor Sie einen Wechselrichter hinzufügen können.</div>
                        </div>
                    </div>
                </div>
                <a href="/" class="btn btn-primary mt-4" hx-boost="true">Zurück zur Übersicht</a>
            </div>""",
            status_code=status.HTTP_403_FORBIDDEN
        )

    return {"user": user}



from fastapi_csrf_protect import CsrfProtect


@router.post("/inverter")
async def post_add_inverter(
    inverter_to_add: InverterAdd,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
    csrf_protect: CsrfProtect = Depends(),
):
    if user is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    # Check if user is verified
    if not user.is_verified:
        logger.warning(
            "Unverified user attempted to add inverter",
            user_id=user.id,
            user_email=user.email
        )
        return HTMLResponse(
            "<p style='color:red;'>Bitte verifizieren Sie zuerst Ihre E-Mail-Adresse.</p>",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Create inverter object (no InfluxDB bucket needed)
    new_inverter_obj = Inverter(
        user_id=user.id,
        name=inverter_to_add.name,
        serial_logger=inverter_to_add.serial,
        sw_version="-",
    )

    # Insert into database
    try:
        session.add(new_inverter_obj)
        await session.commit()
        await session.refresh(new_inverter_obj)

        logger.info(
            "Inverter created",
            inverter_id=new_inverter_obj.id,
            user_id=user.id,
            serial=inverter_to_add.serial
        )
    except IntegrityError as e:
        await session.rollback()
        logger.error(
            "Inverter serial already exists",
            serial=inverter_to_add.serial,
            error=str(e),
        )
        return HTMLResponse(
            "<p style='color:red;'>Seriennummer existiert bereits</p>",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return HTMLResponse("""
                        <div class="sm:mx-auto sm:w-full sm:max-w-sm">
                        <h3 class="mt-10 text-3xl font-bold leading-9 tracking-tight"> Wechselrichter erfolgreich registriert</h3>
                        <a href="/" hx-boost="false"><button class="btn">Weiter</button></a></div>""")


@router.delete("/inverter/{inverter_id}", response_class=HTMLResponse)
async def delete_inverter(
    inverter_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete an inverter and its measurement data"""
    if user is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    inverter = await session.get(Inverter, inverter_id)

    # Verify ownership
    if inverter.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    await session.delete(inverter)
    await session.commit()

    logger.info(
        "Inverter deleted",
        inverter_id=inverter_id,
        user_id=user.id
    )
    # Note: Measurements are automatically deleted via CASCADE constraint

    return ""


@router.post("/inverter_metadata/{serial_logger}")
async def post_inverter_metadata(
    data: InverterAddMetadata,
    serial_logger: str,
    request: Request,
    user: User = Depends(current_superuser_bearer),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update metadata for an inverter identified by serial logger number.

    This endpoint is called by the collector (superuser) to update inverter
    metadata such as rated power and number of MPPTs after collecting this
    information from the inverter telemetry.

    Args:
        data: Metadata containing rated_power and number_of_mppts
        serial_logger: Unique serial number of the data logger

    Returns:
        Updated inverter data with metadata

    Raises:
        404: Inverter with given serial_logger not found
    """
    # Query inverter by serial_logger
    result = await session.execute(
        select(Inverter).where(Inverter.serial_logger == serial_logger)
    )
    inverter = result.scalar_one_or_none()

    if not inverter:
        logger.warning(
            "Inverter not found for metadata update",
            serial_logger=serial_logger
        )
        return HTMLResponse(
            content=f"Inverter with serial {serial_logger} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )

    # Update metadata fields
    inverter.rated_power = data.rated_power
    inverter.number_of_mppts = data.number_of_mppts

    await session.commit()
    await session.refresh(inverter)

    logger.info(
        "Inverter metadata updated",
        serial_logger=serial_logger,
        inverter_id=inverter.id,
        rated_power=data.rated_power,
        number_of_mppts=data.number_of_mppts
    )

    # Return success response with updated data
    return {
        "id": inverter.id,
        "serial_logger": inverter.serial_logger,
        "name": inverter.name,
        "rated_power": inverter.rated_power,
        "number_of_mppts": inverter.number_of_mppts,
        "sw_version": inverter.sw_version
    }
