import structlog
from sqladmin import ModelView
from solar_backend.db import Inverter, get_async_session
from solar_backend.utils.influx import InfluxManagement
from solar_backend.db import User
from sqlalchemy import select

logger = structlog.get_logger()


async def create_influx_bucket(user: User, bucket_name: str):
    """create a bucket with given name and return the crated bucket id"""
    inflx = InfluxManagement(user.influx_url)
    inflx.connect(username=user.email, password=user.hashed_password)
    bucket = inflx.create_bucket(bucket_name, user.influx_org_id)
    return bucket.id


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

