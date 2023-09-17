from sqlalchemy import select
import structlog
from fastapi_users import BaseUserManager


from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_htmx import htmx

from solar_backend.db import User, get_async_session
from solar_backend.schemas import InverterAdd
from solar_backend.users import current_active_user
from solar_backend.db import Inverter
from solar_backend.inverter import create_influx_bucket
from solar_backend.config import DEV_TESTING


logger = structlog.get_logger()

router = APIRouter()

@router.get("/add_inverter", response_class=HTMLResponse)
@htmx("add_inverter", "add_inverter")
async def get_add_inverter(request: Request):
    return {}

@router.post("/add_inverter")
async def post_add_inverter(inverter_to_add: InverterAdd, db_session = Depends(get_async_session), user: User = Depends(current_active_user)):
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    
    if not DEV_TESTING:
        bucket_id = await create_influx_bucket(user, inverter_to_add.name)
    else:
        bucket_id = "dev-test"
    new_inverter_obj = Inverter(user_id=user.id, name=inverter_to_add.name, serial_logger=inverter_to_add.serial, influx_bucked_id=bucket_id, sw_version='-')
    
    # TODO: catch errors
    async with db_session as session:
        session.add(new_inverter_obj)
        await session.commit()

    
    return RedirectResponse('/', status_code=status.HTTP_303_SEE_OTHER)

@router.delete("/inverter/{inverter_id}", response_class=HTMLResponse)
@htmx("add_inverter", "add_inverter")
async def get_add_inverter(inverter_id: int, request: Request, db_session = Depends(get_async_session), user: User = Depends(current_active_user)):
    if user is None:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    
    async with db_session as session:
        inverter = await session.get(Inverter, inverter_id)
        await session.delete(inverter)
        await session.commit()
    
    logger.info(f"inverter {inverter_id} deleted")
    
    return ""