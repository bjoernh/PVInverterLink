"""
Repository for inverter-related database operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from solar_backend.db import Inverter
from solar_backend.schemas import InverterAdd, InverterAddMetadata


class InverterRepository:
    """
    Provides methods for inverter-related database operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the repository with a database session.

        Args:
            session: The database session.
        """
        self.session = session

    async def get_by_id(self, inverter_id: int) -> Inverter | None:
        return await self.session.get(Inverter, inverter_id)

    async def get_by_serial(self, serial_logger: str) -> Inverter | None:
        result = await self.session.execute(
            select(Inverter).where(Inverter.serial_logger == serial_logger)
        )
        return result.scalar_one_or_none()

    async def get_all_by_user_id(self, user_id: int) -> list[Inverter]:
        result = await self.session.execute(
            select(Inverter).where(Inverter.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create(self, user_id: int, inverter_to_add: InverterAdd) -> Inverter:
        new_inverter_obj = Inverter(
            user_id=user_id,
            name=inverter_to_add.name,
            serial_logger=inverter_to_add.serial,
            sw_version="-",
        )
        self.session.add(new_inverter_obj)
        await self.session.commit()
        await self.session.refresh(new_inverter_obj)
        return new_inverter_obj

    async def update(self, inverter: Inverter, inverter_update: InverterAdd) -> Inverter:
        inverter.name = inverter_update.name
        inverter.serial_logger = inverter_update.serial
        await self.session.commit()
        await self.session.refresh(inverter)
        return inverter

    async def delete(self, inverter: Inverter) -> None:
        await self.session.delete(inverter)
        await self.session.commit()

    async def update_metadata(self, inverter: Inverter, data: InverterAddMetadata) -> Inverter:
        inverter.rated_power = data.rated_power
        inverter.number_of_mppts = data.number_of_mppts
        await self.session.commit()
        await self.session.refresh(inverter)
        return inverter
