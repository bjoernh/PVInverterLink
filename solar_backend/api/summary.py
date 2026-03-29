import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi_htmx import htmx

from solar_backend.config import settings
from solar_backend.constants import UNAUTHORIZED_MESSAGE
from solar_backend.db import User, get_async_session
from solar_backend.repositories.inverter_repository import InverterRepository
from solar_backend.users import current_active_user
from solar_backend.utils.timeseries import (
    EnergyPeriod,
    TimeRange,
    get_current_month_energy_production,
    get_current_week_energy_production,
    get_hourly_energy_production,
    get_last_hour_average,
    get_power_timeseries,
    get_today_energy_production,
    get_today_maximum_power,
    rls_context,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/dashboard/summary", response_class=HTMLResponse, response_model=None)
@htmx("summary", "summary")
async def get_summary(
    request: Request,
    time_range: str = "24 hours",
    user: User = Depends(current_active_user),
    db_session=Depends(get_async_session),
) -> dict | RedirectResponse:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_MESSAGE + " Please log in again.",
        )

    async with db_session as session:
        inverter_repo = InverterRepository(session)
        inverters = await inverter_repo.get_all_by_user_id(user.id)

    if len(inverters) <= 1:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

    try:
        time_range_enum = TimeRange(time_range)
    except ValueError:
        time_range_enum = TimeRange.default()
        time_range = time_range_enum.value

    logger.info(
        "Summary dashboard accessed",
        user_id=user.id,
        inverter_count=len(inverters),
        time_range=time_range,
    )

    return {
        "user": user,
        "inverters": inverters,
        "time_range": time_range,
        "valid_ranges": [tr.value for tr in TimeRange],
        "range_labels": {tr.value: tr.label for tr in TimeRange},
        "auto_refresh_rate": settings.AUTO_REFRESH_RATE,
    }


@router.get("/api/summary/data")
async def get_summary_data(
    time_range: str = "24 hours",
    user: User = Depends(current_active_user),
    db_session=Depends(get_async_session),
) -> JSONResponse:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_MESSAGE + " Please log in again.",
        )

    try:
        time_range_enum = TimeRange(time_range)
    except ValueError:
        time_range_enum = TimeRange.default()
        time_range = time_range_enum.value

    async with db_session as session:
        inverter_repo = InverterRepository(session)
        inverters = await inverter_repo.get_all_by_user_id(user.id)

        if not inverters:
            return JSONResponse(
                {
                    "success": False,
                    "message": "Keine Wechselrichter gefunden",
                    "stats": {"current": 0, "max": 0, "today_kwh": 0.0, "avg_last_hour": 0},
                    "total": [],
                    "per_inverter": [],
                }
            )

        per_inverter = []
        total_current = 0
        total_max = 0
        total_kwh = 0.0
        total_avg = 0

        async with rls_context(session, user.id):
            for inverter in inverters:
                try:
                    data_points = await get_power_timeseries(
                        session=session,
                        user_id=user.id,
                        inverter_id=inverter.id,
                        time_range=time_range,
                    )
                except Exception:
                    data_points = []

                per_inverter.append(
                    {
                        "id": inverter.id,
                        "name": inverter.name,
                        "data": data_points,
                    }
                )

                # Accumulate stats
                try:
                    max_today = await get_today_maximum_power(session, user.id, inverter.id)
                    total_max += max_today
                except Exception:
                    pass

                try:
                    today_kwh = await get_today_energy_production(session, user.id, inverter.id)
                    total_kwh += today_kwh
                except Exception:
                    pass

                try:
                    avg_last_hour = await get_last_hour_average(session, user.id, inverter.id)
                    total_avg += avg_last_hour
                except Exception:
                    pass

                # Current = last data point of this inverter's series
                if data_points:
                    total_current += data_points[-1].get("power", 0)

        # Build total series by merging time buckets across all inverters
        total_series = _merge_power_series([inv["data"] for inv in per_inverter])

        logger.info(
            "Summary data retrieved",
            user_id=user.id,
            inverter_count=len(inverters),
            time_range=time_range,
        )

        return JSONResponse(
            {
                "success": True,
                "stats": {
                    "current": total_current,
                    "max": total_max,
                    "today_kwh": round(total_kwh, 2),
                    "avg_last_hour": total_avg,
                },
                "total": total_series,
                "per_inverter": per_inverter,
            }
        )


@router.get("/api/summary/energy-data")
async def get_summary_energy_data(
    period: str = "day",
    user: User = Depends(current_active_user),
    db_session=Depends(get_async_session),
) -> JSONResponse:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHORIZED_MESSAGE + " Please log in again.",
        )

    try:
        period_enum = EnergyPeriod(period)
    except ValueError:
        period_enum = EnergyPeriod.default()
        period = period_enum.value

    async with db_session as session:
        inverter_repo = InverterRepository(session)
        inverters = await inverter_repo.get_all_by_user_id(user.id)

        if not inverters:
            return JSONResponse(
                {
                    "success": False,
                    "message": "Keine Wechselrichter gefunden",
                    "period": period,
                    "total": [],
                    "per_inverter": [],
                }
            )

        per_inverter = []

        async with rls_context(session, user.id):
            for inverter in inverters:
                try:
                    if period_enum == EnergyPeriod.DAY:
                        raw = await get_hourly_energy_production(session, user.id, inverter.id)
                        data_points = [
                            {"label": f"{item['hour']:02d}:00", "energy_kwh": round(item["energy_kwh"], 2)}
                            for item in raw
                        ]
                    elif period_enum == EnergyPeriod.MONTH:
                        raw = await get_current_month_energy_production(session, user.id, inverter.id)
                        data_points = _format_daily_energy(raw)
                    else:
                        raw = await get_current_week_energy_production(session, user.id, inverter.id)
                        data_points = _format_daily_energy(raw)
                except Exception:
                    data_points = []

                per_inverter.append(
                    {
                        "id": inverter.id,
                        "name": inverter.name,
                        "data": data_points,
                    }
                )

        total_series = _merge_energy_series([inv["data"] for inv in per_inverter])

        logger.info(
            "Summary energy data retrieved",
            user_id=user.id,
            inverter_count=len(inverters),
            period=period,
        )

        return JSONResponse(
            {
                "success": True,
                "period": period,
                "total": total_series,
                "per_inverter": per_inverter,
            }
        )


def _format_daily_energy(raw: list[dict]) -> list[dict]:
    """Convert YYYY-MM-DD date strings to German DD.MM. format."""
    result = []
    for item in raw:
        date_parts = item["date"].split("-")
        label = f"{date_parts[2]}.{date_parts[1]}."
        result.append({"label": label, "energy_kwh": round(item["energy_kwh"], 2)})
    return result


def _merge_power_series(all_series: list[list[dict]]) -> list[dict]:
    """
    Merge multiple per-inverter power time series into a single total series.
    Sums power values at matching timestamps.
    """
    totals: dict[str, int] = {}
    for series in all_series:
        for point in series:
            t = point["time"]
            totals[t] = totals.get(t, 0) + point.get("power", 0)
    return [{"time": t, "power": p} for t, p in sorted(totals.items())]


def _merge_energy_series(all_series: list[list[dict]]) -> list[dict]:
    """
    Merge multiple per-inverter energy series into a single total series.
    Sums energy_kwh values at matching labels.
    """
    totals: dict[str, float] = {}
    for series in all_series:
        for point in series:
            lbl = point["label"]
            totals[lbl] = totals.get(lbl, 0.0) + point.get("energy_kwh", 0.0)
    return [{"label": lbl, "energy_kwh": round(v, 2)} for lbl, v in totals.items()]
