import structlog
from sqladmin import ModelView
from solar_backend.db import Inverter, get_async_session
from solar_backend.influx import InfluxManagement
from solar_backend.db import User
from sqlalchemy import select

logger = structlog.get_logger()


class InverterAdmin(ModelView, model=Inverter):
    async def on_model_change(self, data, model, is_created):
        if is_created:
            session = self.session_maker()
            
            result = await session.execute(select(User).where(User.id == data['users']))
            user = result.one()[0]
            
            inflx = InfluxManagement(user.influx_url)
            inflx.connect(username=user.email, password=user.hashed_password)
            
            bucket = inflx.create_bucket(data['name'], user.influx_org_id)
            data['influx_bucked_id'] = bucket.id

            await session.close()

    column_list = [Inverter.id, Inverter.name]
    icon = "fa-solid fa-wifi"
    column_searchable_list = [Inverter.name]
    column_sortable_list = [Inverter.id, Inverter.name]

