"""
Unit tests for the InverterService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from solar_backend.services.inverter_service import InverterService
from solar_backend.services.exceptions import InverterNotFoundException, UnauthorizedInverterAccessException
from solar_backend.db import Inverter, User
from solar_backend.schemas import InverterAdd
from tests.factories import InverterAddFactory, UserDBFactory, InverterDBFactory

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_inverters_for_user():
    """Test retrieving inverters for a specific user."""
    # Arrange
    user_id = 1
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()

    # Mock the result of the database query
    mock_inverters = [
        Inverter(id=1, name="Inverter 1", user_id=user_id, serial_logger="SN1"),
        Inverter(id=2, name="Inverter 2", user_id=user_id, serial_logger="SN2"),
    ]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_inverters
    mock_session.execute.return_value = mock_result

    service = InverterService(session=mock_session)

    # Act
    inverters = await service.get_inverters(user_id=user_id)

    # Assert
    assert len(inverters) == 2
    assert inverters[0].name == "Inverter 1"
    assert mock_session.execute.call_count == 1

@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_inverter():
    """Test creating a new inverter."""
    # Arrange
    user_id = 1
    inverter_data = InverterAddFactory(name="New Inverter", serial="NEWSN")
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    service = InverterService(session=mock_session)

    # Act
    new_inverter = await service.create_inverter(user_id=user_id, inverter_to_add=inverter_data)

    # Assert
    assert new_inverter.user_id == user_id
    assert new_inverter.name == "New Inverter"
    assert new_inverter.serial_logger == "NEWSN"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_inverter_success():
    """Test successfully updating an inverter."""
    # Arrange
    user_id = 1
    inverter_id = 1
    inverter_update_data = InverterAddFactory(name="Updated Name", serial="UPDATEDSN")

    mock_inverter = Inverter(id=inverter_id, name="Old Name", user_id=user_id, serial_logger="OLDSN")

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_inverter)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    service = InverterService(session=mock_session)

    # Act
    updated_inverter = await service.update_inverter(inverter_id=inverter_id, user_id=user_id, inverter_update=inverter_update_data)

    # Assert
    assert updated_inverter.name == "Updated Name"
    assert updated_inverter.serial_logger == "UPDATEDSN"
    mock_session.get.assert_called_once_with(Inverter, inverter_id)
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_inverter_not_found():
    """Test updating an inverter that does not exist."""
    # Arrange
    user_id = 1
    inverter_id = 99
    inverter_update_data = InverterAddFactory()

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()

    service = InverterService(session=mock_session)

    # Act & Assert
    with pytest.raises(InverterNotFoundException):
        await service.update_inverter(inverter_id=inverter_id, user_id=user_id, inverter_update=inverter_update_data)

    mock_session.get.assert_called_once_with(Inverter, inverter_id)
    mock_session.commit.assert_not_called()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_inverter_unauthorized():
    """Test updating an inverter that belongs to another user."""
    # Arrange
    owner_user_id = 1
    attacker_user_id = 2
    inverter_id = 1
    inverter_update_data = InverterAddFactory()

    mock_inverter = Inverter(id=inverter_id, name="Owner's Inverter", user_id=owner_user_id, serial_logger="SN1")

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_inverter)
    mock_session.commit = AsyncMock()

    service = InverterService(session=mock_session)

    # Act & Assert
    with pytest.raises(UnauthorizedInverterAccessException):
        await service.update_inverter(inverter_id=inverter_id, user_id=attacker_user_id, inverter_update=inverter_update_data)

    mock_session.get.assert_called_once_with(Inverter, inverter_id)
    mock_session.commit.assert_not_called()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_inverter_success():
    """Test successfully deleting an inverter."""
    # Arrange
    user_id = 1
    inverter_id = 1

    mock_inverter = Inverter(id=inverter_id, name="To Be Deleted", user_id=user_id, serial_logger="DELSN")

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_inverter)
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()

    service = InverterService(session=mock_session)

    # Act
    await service.delete_inverter(inverter_id=inverter_id, user_id=user_id)

    # Assert
    mock_session.get.assert_called_once_with(Inverter, inverter_id)
    mock_session.delete.assert_called_once_with(mock_inverter)
    mock_session.commit.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_inverter_not_found():
    """Test deleting an inverter that does not exist."""
    # Arrange
    user_id = 1
    inverter_id = 99

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_session.delete = AsyncMock()

    service = InverterService(session=mock_session)

    # Act & Assert
    with pytest.raises(InverterNotFoundException):
        await service.delete_inverter(inverter_id=inverter_id, user_id=user_id)

    mock_session.get.assert_called_once_with(Inverter, inverter_id)
    mock_session.delete.assert_not_called()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_inverter_unauthorized():
    """Test deleting an inverter that belongs to another user."""
    # Arrange
    owner_user_id = 1
    attacker_user_id = 2
    inverter_id = 1

    mock_inverter = Inverter(id=inverter_id, name="Owner's Inverter", user_id=owner_user_id, serial_logger="SN1")

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_inverter)
    mock_session.delete = AsyncMock()

    service = InverterService(session=mock_session)

    # Act & Assert
    with pytest.raises(UnauthorizedInverterAccessException):
        await service.delete_inverter(inverter_id=inverter_id, user_id=attacker_user_id)

    mock_session.get.assert_called_once_with(Inverter, inverter_id)
    mock_session.delete.assert_not_called()
