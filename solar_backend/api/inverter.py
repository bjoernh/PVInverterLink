import asyncpg
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from fastapi_users import BaseUserManager


from fastapi import APIRouter, Depends, HTTPException, Request, status, Response
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


@router.get("/inverters", response_class=HTMLResponse)
@htmx("inverters", "inverters")
async def get_inverters(
    request: Request,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Display inverter management page with list of all user's inverters"""
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)

    # Fetch all inverters for this user
    result = await session.execute(
        select(Inverter).where(Inverter.user_id == user.id)
    )
    inverters = result.scalars().all()

    return {"user": user, "inverters": inverters}


from fastapi_csrf_protect import CsrfProtect


@router.post("/inverter")
async def post_add_inverter(
    inverter_to_add: InverterAdd,
    request: Request,
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

    # Check if request is from inverters management page
    hx_current_url = request.headers.get("HX-Current-URL", "")
    if "/inverters" in hx_current_url:
        # Return table row for inverters management page
        return HTMLResponse(f"""
            <tr id="inverter-row-{new_inverter_obj.id}">
                <td>
                    <span id="name-display-{new_inverter_obj.id}">{new_inverter_obj.name}</span>
                    <input id="name-edit-{new_inverter_obj.id}" type="text" value="{new_inverter_obj.name}" class="input input-bordered input-sm w-full hidden" />
                </td>
                <td>
                    <span id="serial-display-{new_inverter_obj.id}">{new_inverter_obj.serial_logger}</span>
                    <input id="serial-edit-{new_inverter_obj.id}" type="text" value="{new_inverter_obj.serial_logger}" class="input input-bordered input-sm w-full hidden" />
                </td>
                <td>{new_inverter_obj.sw_version}</td>
                <td class="text-right">
                    <div class="flex gap-2 justify-end">
                        <a href="/dashboard/{new_inverter_obj.id}" class="btn btn-sm btn-primary" title="Dashboard">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                        </a>
                        <button id="edit-btn-{new_inverter_obj.id}" class="btn btn-sm btn-info" onclick="editInverter({new_inverter_obj.id})" title="Bearbeiten">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                        </button>
                        <button id="save-btn-{new_inverter_obj.id}" class="btn btn-sm btn-success hidden"
                                hx-put="/inverter/{new_inverter_obj.id}"
                                hx-ext="json-enc"
                                hx-vals='js:{{name: document.getElementById("name-edit-{new_inverter_obj.id}").value, serial: document.getElementById("serial-edit-{new_inverter_obj.id}").value}}'
                                hx-target="#inverter-row-{new_inverter_obj.id}"
                                hx-swap="outerHTML"
                                title="Speichern">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                        </button>
                        <button id="cancel-btn-{new_inverter_obj.id}" class="btn btn-sm btn-ghost hidden" onclick="cancelEdit({new_inverter_obj.id})" title="Abbrechen">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                        <button id="delete-btn-{new_inverter_obj.id}" class="btn btn-sm btn-error"
                                hx-delete="/inverter/{new_inverter_obj.id}"
                                hx-swap="delete"
                                hx-target="#inverter-row-{new_inverter_obj.id}"
                                hx-confirm="Soll der Wechselrichter '{new_inverter_obj.name}' wirklich gelöscht werden? Alle gespeicherten Daten werden gelöscht!"
                                title="Löschen">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                        </button>
                    </div>
                </td>
            </tr>
        """)
    else:
        # Return success page for add_inverter page
        return HTMLResponse("""
                        <div class="sm:mx-auto sm:w-full sm:max-w-sm">
                        <h3 class="mt-10 text-3xl font-bold leading-9 tracking-tight"> Wechselrichter erfolgreich registriert</h3>
                        <a href="/" hx-boost="false"><button class="btn">Weiter</button></a></div>""")


@router.put("/inverter/{inverter_id}", response_class=HTMLResponse)
async def put_inverter(
    inverter_id: int,
    inverter_update: InverterAdd,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
    csrf_protect: CsrfProtect = Depends(),
):
    """Update an inverter's name and serial number"""
    if user is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    # Check if user is verified
    if not user.is_verified:
        logger.warning(
            "Unverified user attempted to edit inverter",
            user_id=user.id,
            user_email=user.email
        )
        return HTMLResponse(
            "<tr><td colspan='4' class='text-error'>Bitte verifizieren Sie zuerst Ihre E-Mail-Adresse.</td></tr>",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Store user_id before any session operations to avoid detachment issues
    user_id = user.id

    # Fetch the inverter
    inverter = await session.get(Inverter, inverter_id)

    if not inverter:
        return HTMLResponse(
            "<tr><td colspan='4' class='text-error'>Wechselrichter nicht gefunden.</td></tr>",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Verify ownership
    if inverter.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # Update inverter fields
    inverter.name = inverter_update.name
    inverter.serial_logger = inverter_update.serial

    try:
        await session.commit()
        await session.refresh(inverter)

        logger.info(
            "Inverter updated",
            inverter_id=inverter_id,
            user_id=user_id,
            new_name=inverter_update.name,
            new_serial=inverter_update.serial
        )
    except IntegrityError as e:
        await session.rollback()
        logger.error(
            "Inverter serial already exists during update",
            serial=inverter_update.serial,
            error=str(e),
        )
        return HTMLResponse(
            f"""<tr id="inverter-row-{inverter_id}">
                <td colspan="4" class="text-error">Seriennummer existiert bereits</td>
            </tr>""",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # Return updated table row
    return HTMLResponse(f"""
        <tr id="inverter-row-{inverter.id}">
            <td>
                <span id="name-display-{inverter.id}">{inverter.name}</span>
                <input id="name-edit-{inverter.id}" type="text" value="{inverter.name}" class="input input-bordered input-sm w-full hidden" />
            </td>
            <td>
                <span id="serial-display-{inverter.id}">{inverter.serial_logger}</span>
                <input id="serial-edit-{inverter.id}" type="text" value="{inverter.serial_logger}" class="input input-bordered input-sm w-full hidden" />
            </td>
            <td>{inverter.sw_version}</td>
            <td class="text-right">
                <div class="flex gap-2 justify-end">
                    <a href="/dashboard/{inverter.id}" class="btn btn-sm btn-primary" title="Dashboard">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                    </a>
                    <button id="edit-btn-{inverter.id}" class="btn btn-sm btn-info" onclick="editInverter({inverter.id})" title="Bearbeiten">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                    </button>
                    <button id="save-btn-{inverter.id}" class="btn btn-sm btn-success hidden"
                            hx-put="/inverter/{inverter.id}"
                            hx-ext="json-enc"
                            hx-vals='js:{{name: document.getElementById("name-edit-{inverter.id}").value, serial: document.getElementById("serial-edit-{inverter.id}").value}}'
                            hx-target="#inverter-row-{inverter.id}"
                            hx-swap="outerHTML"
                            title="Speichern">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                        </svg>
                    </button>
                    <button id="cancel-btn-{inverter.id}" class="btn btn-sm btn-ghost hidden" onclick="cancelEdit({inverter.id})" title="Abbrechen">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                    <button id="delete-btn-{inverter.id}" class="btn btn-sm btn-error"
                            hx-delete="/inverter/{inverter.id}"
                            hx-swap="delete"
                            hx-target="#inverter-row-{inverter.id}"
                            hx-confirm="Soll der Wechselrichter '{inverter.name}' wirklich gelöscht werden? Alle gespeicherten Daten werden gelöscht!"
                            title="Löschen">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                    </button>
                </div>
            </td>
        </tr>
    """)


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

    # Store user_id before any session operations to avoid detachment issues
    user_id = user.id

    inverter = await session.get(Inverter, inverter_id)

    # Verify ownership
    if inverter.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    await session.delete(inverter)
    await session.commit()

    logger.info(
        "Inverter deleted",
        inverter_id=inverter_id,
        user_id=user_id
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
