import structlog
from datetime import datetime, timezone, timedelta
from pprint import pprint
from pydantic import ValidationError
import humanize

from fastapi import APIRouter, Depends, Request, status

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_htmx import htmx
from solar_backend.db import Inverter, User, get_async_session

from sqlalchemy import select
from solar_backend.users import current_active_user
from solar_backend.utils.timeseries import (
    get_latest_value,
    get_today_energy_production,
    set_rls_context,
    reset_rls_context,
    NoDataException,
    TimeSeriesException,
)
from solar_backend.schemas import UserCreate
from fastapi_users import models, exceptions

logger = structlog.get_logger()

# Activate German locale for humanize
_t = humanize.i18n.activate("de_DE")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@htmx("start", "start")
async def get_start(
    request: Request,
    user: User = Depends(current_active_user),
    db_session=Depends(get_async_session),
):
    if user is None:
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    async with db_session as session:
        # Set RLS context
        await set_rls_context(session, user.id)

        try:
            result = await session.execute(
                select(Inverter).where(Inverter.user_id == user.id)
            )
            inverters = list(result.scalars().all())

            # Define 5-minute threshold for "current" power values
            now = datetime.now(timezone.utc)
            five_minutes_ago = now - timedelta(minutes=5)

            # Extend with current power and last update
            for inverter in inverters:
                try:
                    time, power = await get_latest_value(session, user.id, inverter.id)
                    inverter.last_update_time = (
                        time  # Store timestamp for later filtering
                    )

                    # Only show power if within last 5 minutes
                    if time >= five_minutes_ago:
                        inverter.current_power = power
                        inverter.last_update = humanize.naturaltime(now - time)
                    else:
                        inverter.current_power = "-"
                        inverter.last_update = "Keine aktuellen Werte"
                except NoDataException:
                    inverter.current_power = "-"
                    inverter.last_update = "Keine aktuellen Werte"
                    inverter.last_update_time = None
                except TimeSeriesException as e:
                    logger.warning(
                        "Failed to get latest value",
                        error=str(e),
                        inverter_id=inverter.id,
                    )
                    inverter.current_power = "-"
                    inverter.last_update = "Dienst vorübergehend nicht verfügbar"
                    inverter.last_update_time = None

            # Calculate summary values
            summary = {"total_power": "-", "total_production_today": "-"}

            total_power = 0
            total_production = 0.0
            power_available = False
            production_available = False

            for inverter in inverters:
                # Get current power - only include if within last 5 minutes
                if (
                    isinstance(inverter.current_power, int)
                    and inverter.current_power >= 0
                    and inverter.last_update_time is not None
                    and inverter.last_update_time >= five_minutes_ago
                ):
                    total_power += inverter.current_power
                    power_available = True

                # Get today's energy
                try:
                    energy = await get_today_energy_production(
                        session, user.id, inverter.id
                    )
                    if energy >= 0:
                        total_production += energy
                        production_available = True
                except Exception as e:
                    logger.debug(
                        f"Could not get production for inverter {inverter.name}",
                        error=str(e),
                    )

            if power_available:
                summary["total_power"] = int(total_power)
            if production_available:
                summary["total_production_today"] = round(total_production, 2)

        finally:
            await reset_rls_context(session)

    return {"user": user, "inverters": inverters, "summary": summary}


@router.get("/test", response_class=HTMLResponse)
@htmx("test", "test")
async def get_test(request: Request):
    return {"user": None}


@router.post("/post_test")
async def post_test():
    return HTMLResponse("""<a href="/" hx-boost="false">weiter</a>""")
    # extra_headers = {"HX-Redirect": "/", "HX-Refresh":"true"}
    return RedirectResponse("/", status_code=status.HTTP_200_OK, headers=extra_headers)
    # return HTMLResponse("", headers=extra_headers)
    # return HTMLResponse("Seriennummer existiert bereits", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
