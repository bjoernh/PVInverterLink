"""
Service layer for inverter-related operations.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from solar_backend.db import Inverter
from solar_backend.repositories.inverter_repository import InverterRepository
from solar_backend.schemas import InverterAdd, InverterAddMetadata
from solar_backend.services.exceptions import (
    InverterNotFoundException,
    UnauthorizedInverterAccessException,
)

logger = structlog.get_logger()


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
        self.repo = InverterRepository(session)

    async def get_inverters(self, user_id: int) -> list[Inverter]:
        return await self.repo.get_all_by_user_id(user_id)

    async def create_inverter(self, user_id: int, inverter_to_add: InverterAdd) -> Inverter:
        return await self.repo.create(user_id, inverter_to_add)

    async def update_inverter(self, inverter_id: int, user_id: int, inverter_update: InverterAdd) -> Inverter:
        inverter = await self.repo.get_by_id(inverter_id)
        if not inverter:
            raise InverterNotFoundException("Inverter not found")
        if inverter.user_id != user_id:
            raise UnauthorizedInverterAccessException("User does not have access to this inverter")

        return await self.repo.update(inverter, inverter_update)

    async def delete_inverter(self, inverter_id: int, user_id: int) -> None:
        inverter = await self.repo.get_by_id(inverter_id)
        if not inverter:
            raise InverterNotFoundException("Inverter not found")
        if inverter.user_id != user_id:
            raise UnauthorizedInverterAccessException("User does not have access to this inverter")

        await self.repo.delete(inverter)

    async def get_user_inverter(self, user_id: int, inverter_id: int) -> Inverter:
        inverter = await self.repo.get_by_id(inverter_id)
        if not inverter or inverter.user_id != user_id:
            raise InverterNotFoundException(f"Inverter {inverter_id} not found or unauthorized access")
        return inverter

    async def update_inverter_metadata(self, serial_logger: str, data: InverterAddMetadata) -> Inverter:
        inverter = await self.repo.get_by_serial(serial_logger)

        if not inverter:
            raise InverterNotFoundException("Inverter not found")

        return await self.repo.update_metadata(inverter, data)
