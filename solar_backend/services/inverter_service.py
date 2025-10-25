"""
Service layer for inverter-related operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import structlog

from solar_backend.db import Inverter, User
from solar_backend.schemas import InverterAdd, InverterAddMetadata

logger = structlog.get_logger()


from solar_backend.services.exceptions import (
    InverterNotFoundException,
    UnauthorizedInverterAccessException,
)


class InverterService:
    """
    Provides methods for inverter-related business logic.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the service with a database session.

        Args:
            session: The database session.
        """
        self.session = session

    async def get_inverters(self, user_id: int) -> list[Inverter]:
        result = await self.session.execute(
            select(Inverter).where(Inverter.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create_inverter(self, user_id: int, inverter_to_add: InverterAdd) -> Inverter:
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

    async def update_inverter(
        self, inverter_id: int, user_id: int, inverter_update: InverterAdd
    ) -> Inverter:
        inverter = await self.session.get(Inverter, inverter_id)
        if not inverter:
            raise InverterNotFoundException("Inverter not found")
        if inverter.user_id != user_id:
            raise UnauthorizedInverterAccessException(
                "User does not have access to this inverter"
            )

        inverter.name = inverter_update.name
        inverter.serial_logger = inverter_update.serial
        await self.session.commit()
        await self.session.refresh(inverter)
        return inverter

    async def delete_inverter(self, inverter_id: int, user_id: int) -> None:
        inverter = await self.session.get(Inverter, inverter_id)
        if not inverter:
            raise InverterNotFoundException("Inverter not found")
        if inverter.user_id != user_id:
            raise UnauthorizedInverterAccessException(
                "User does not have access to this inverter"
            )

        await self.session.delete(inverter)
        await self.session.commit()

    async def update_inverter_metadata(
        self, serial_logger: str, data: InverterAddMetadata
    ) -> Inverter:
        result = await self.session.execute(
            select(Inverter).where(Inverter.serial_logger == serial_logger)
        )
        inverter = result.scalar_one_or_none()

        if not inverter:
            raise InverterNotFoundException("Inverter not found")

        inverter.rated_power = data.rated_power
        inverter.number_of_mppts = data.number_of_mppts
        await self.session.commit()
        await self.session.refresh(inverter)
        return inverter
