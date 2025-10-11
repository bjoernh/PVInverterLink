import asyncpg
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from solar_backend.inverter import create_influx_bucket, delete_influx_bucket
from solar_backend.config import WEB_DEV_TESTING


logger = structlog.get_logger()

router = APIRouter()


@router.get("/add_inverter", response_class=HTMLResponse)
@htmx("add_inverter", "add_inverter")
async def get_add_inverter(request: Request, user: User = Depends(current_active_user)):
    return {"user": user}


@router.post("/inverter")
async def post_add_inverter(
    inverter_to_add: InverterAdd,
    db_session=Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if user is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    async with db_session as session:
        # Create inverter object without bucket_id first
        new_inverter_obj = Inverter(
            user_id=user.id,
            name=inverter_to_add.name,
            serial_logger=inverter_to_add.serial,
            influx_bucked_id=None,  # Will be set after InfluxDB bucket creation
            sw_version="-",
        )

        # Insert into database first to ensure serial uniqueness
        try:
            session.add(new_inverter_obj)
            await session.commit()
            await session.refresh(new_inverter_obj)  # Get the ID
        except IntegrityError as e:
            # Handles both PostgreSQL (asyncpg) and SQLite unique constraint violations
            await session.rollback()  # Explicitly rollback after error
            logger.error(
                "Inverter serial already exists",
                serial=inverter_to_add.serial,
                error=str(e),
            )
            return HTMLResponse(
                "<p style='color:red;'>Seriennummer existiert bereits</p>",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # After successful DB insert, create InfluxDB bucket
        if not WEB_DEV_TESTING:
            try:
                bucket_id = await create_influx_bucket(user, inverter_to_add.name)
                new_inverter_obj.influx_bucked_id = bucket_id
                await session.commit()
            except Exception as e:
                # Rollback: delete the inverter we just created
                logger.error(
                    "Failed to create InfluxDB bucket, rolling back inverter creation",
                    error=str(e),
                    user_id=user.id,
                    inverter_id=new_inverter_obj.id,
                    bucket_name=inverter_to_add.name,
                )
                await session.delete(new_inverter_obj)
                await session.commit()
                return HTMLResponse(
                    "<p style='color:red;'>Fehler: InfluxDB ist nicht verfügbar. Bitte kontaktieren Sie den Administrator.</p>",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        else:
            # In dev/test mode, just set a dummy bucket_id
            new_inverter_obj.influx_bucked_id = "dev-test"
            await session.commit()

    return HTMLResponse("""
                        <div class="sm:mx-auto sm:w-full sm:max-w-sm">
                        <h3 class="mt-10 text-3xl font-bold leading-9 tracking-tight"> Wechselrichter erfolgreich registriert</h3>
                        <a href="/" hx-boost="false"><button class="btn">Weiter</button></a></div>""")


@router.delete("/inverter/{inverter_id}", response_class=HTMLResponse)
async def delete_inverter(
    inverter_id: int,
    request: Request,
    db_session=Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete a inverter"""
    if user is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    async with db_session as session:
        inverter = await session.get(Inverter, inverter_id)
        bucket_id = inverter.influx_bucked_id
        await session.delete(inverter)

        logger.info(f"inverter {inverter_id} deleted")

        if not WEB_DEV_TESTING:
            try:
                await delete_influx_bucket(user, bucket_id)
            except Exception as e:
                logger.error(
                    "Failed to delete InfluxDB bucket",
                    error=str(e),
                    user_id=user.id,
                    bucket_id=bucket_id,
                    inverter_id=inverter_id,
                )
                # Continue with database deletion even if InfluxDB fails
                # The bucket can be cleaned up manually later

        await session.commit()

    return ""


@router.get("/influx_token")
async def get_token(
    serial: str,
    request: Request,
    user: User = Depends(current_superuser_bearer),
    db_session=Depends(get_async_session),
):
    """Get all information related to a inverter with given serial number"""
    async with db_session as session:
        result = await session.execute(
            select(
                User.influx_token,
                Inverter.influx_bucked_id,
                Inverter.name,
                Inverter.rated_power,
                User.influx_org_id,
            )
            .join_from(User, Inverter)
            .where(Inverter.serial_logger == serial)
        )
        row = result.first()
    if row:
        return {
            "serial": serial,
            "token": row.influx_token,
            "bucket_id": row.influx_bucked_id,
            "bucket_name": row.name,
            "org_id": row.influx_org_id,
            "is_metadata_complete": row.rated_power is not None,
        }
    else:
        return HTMLResponse(status_code=status.HTTP_404_NOT_FOUND)


@router.post("/inverter_metadata/{serial_logger}", response_model=InverterSchema)
async def post_inverter_metadata(
    data: InverterAddMetadata,
    serial_logger: str,
    request: Request,
    user: User = Depends(current_superuser_bearer),
    db_session=Depends(get_async_session),
):
    """meta data for inverter"""
    async with db_session as session:
        print(select(Inverter))
        # SELECT abfrage gibt keinen inverter zurück, warum ?
        # result = await session.execute()
        # inverter = result.scalar()
        # if inverter:
        #     inverter.rated_power = data.rated_power
        #     inverter.number_of_mppts = data.number_of_mppts
        #     await session.commit()
        #     return inverter
        # else:
        #     return HTMLResponse(status_code=status.HTTP_404_NOT_FOUND)
