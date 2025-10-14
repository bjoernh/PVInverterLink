import structlog
from sqladmin import ModelView
from solar_backend.db import Inverter, get_async_session
from solar_backend.utils.influx import InfluxManagement, NoValuesException, InfluxConnectionError
from solar_backend.db import User
from datetime import datetime, timezone
import humanize
from sqlalchemy import select
import random

logger = structlog.get_logger()

_t = humanize.i18n.activate("de_DE")

async def create_influx_bucket(user: User, bucket_name: str):
    """
    Create a bucket with given name and return the created bucket id.

    Raises:
        InfluxConnectionError: If InfluxDB is not reachable
    """
    async with InfluxManagement(user.influx_url) as inflx:
        inflx.connect(org=user.email, token=user.influx_token)
        bucket = inflx.create_bucket(bucket_name, user.influx_org_id)
        return bucket.id

async def delete_influx_bucket(user: User, bucket_id: str):
    """
    Delete an InfluxDB bucket.

    Raises:
        InfluxConnectionError: If InfluxDB is not reachable
    """
    async with InfluxManagement(user.influx_url) as inflx:
        inflx.connect(org=user.email, token=user.influx_token)
        inflx.delete_bucket(bucket_id)

async def extend_current_powers(user: User, inverters: list[Inverter]):
    """
    Extend inverter objects with current power values from InfluxDB.

    Args:
        user: User object
        inverters: List of inverter objects to extend

    Note:
        If InfluxDB is unavailable, sets default values for all inverters
        instead of failing.
    """
    try:
        async with InfluxManagement(user.influx_url) as inflx:
            inflx.connect(org=user.email, token=user.influx_token)
            for i in inverters:
                try:
                    time, power = inflx.get_latest_values(user, i.name)
                    i.current_power = power
                    i.last_update = humanize.naturaltime(datetime.now(timezone.utc) - time)
                except NoValuesException:
                    i.current_power = "-"
                    i.last_update = "Keine aktuellen Werte"
    except InfluxConnectionError as e:
        logger.warning("InfluxDB connection failed in extend_current_powers", error=str(e), user_id=user.id)
        # Set unavailable state for all inverters
        for i in inverters:
            i.current_power = "-"
            i.last_update = "Dienst vorübergehend nicht verfügbar"



class InverterAdmin(ModelView, model=Inverter):
    async def on_model_change(self, data, model, is_created):
        if is_created:
            session = self.session_maker()
            result = await session.execute(select(User).where(User.id == data['users']))
            user = result.one()[0]
            data['influx_bucked_id'] = await create_influx_bucket(user, data['name'])
            await session.close()

    column_list = [Inverter.id, Inverter.name]
    icon = "fa-solid fa-wifi"
    column_searchable_list = [Inverter.name]
    column_sortable_list = [Inverter.id, Inverter.name]

