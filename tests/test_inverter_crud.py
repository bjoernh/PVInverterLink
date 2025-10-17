"""
Tests for inverter CRUD operations.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from solar_backend.db import Inverter
from tests.factories import InverterAddFactory


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_inverter(client, test_user, mocker, db_session):
    """Test creating a new inverter as authenticated user."""
    # Login first
    await client.post(
        "/login",
        data={"username": "testuser@example.com", "password": "testpassword123"}
    )

    # Mock InfluxDB bucket creation
    mock_bucket = mocker.patch(
        'solar_backend.api.inverter.create_influx_bucket',
        return_value="mock-bucket-id"
    )

    # Create inverter
    inverter_data = InverterAddFactory()
    response = await client.post(
        "/inverter",
        json={"name": inverter_data.name, "serial": inverter_data.serial}
    )

    assert response.status_code == 200
    assert "erfolgreich registriert" in response.text

    # Verify inverter was created in database
    async with db_session as session:
        result = await session.execute(
            select(Inverter).where(Inverter.serial_logger == inverter_data.serial)
        )
        inverter = result.scalar_one_or_none()
        assert inverter is not None
        assert inverter.name == inverter_data.name
        assert inverter.user_id == test_user.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_inverter_unauthenticated(client):
    """Test that unauthenticated user cannot create inverter."""
    inverter_data = InverterAddFactory()
    response = await client.post(
        "/inverter",
        json={"name": inverter_data.name, "serial": inverter_data.serial}
    )

    # Should redirect to login
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_inverter_duplicate_serial(client, test_user, test_inverter, mocker):
    """Test that creating inverter with duplicate serial fails."""
    # Login first
    await client.post(
        "/login",
        data={"username": "testuser@example.com", "password": "testpassword123"}
    )

    # Try to create inverter with same serial
    response = await client.post(
        "/inverter",
        json={"name": "Another Inverter", "serial": test_inverter.serial_logger}
    )

    assert response.status_code == 422
    assert "existiert bereits" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_user_inverters(client, test_user, test_inverter, mocker):
    """Test listing inverters for authenticated user."""
    # Mock InfluxDB operations
    mocker.patch(
        'solar_backend.inverter.extend_current_powers',
        return_value=None
    )

    # Login first
    await client.post(
        "/login",
        data={"username": "testuser@example.com", "password": "testpassword123"}
    )

    # Access start page which lists inverters
    response = await client.get("/")

    assert response.status_code == 200
    # The inverter name should appear in the response
    assert test_inverter.name in response.text or "Test Inverter" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_inverter(client, test_user, test_inverter, db_session):
    """Test deleting an inverter as owner."""
    # Login first
    await client.post(
        "/login",
        data={"username": "testuser@example.com", "password": "testpassword123"}
    )

    # Delete inverter
    response = await client.delete(f"/inverter/{test_inverter.id}")

    assert response.status_code == 200

    # Verify inverter was deleted from database
    async with db_session as session:
        result = await session.execute(
            select(Inverter).where(Inverter.id == test_inverter.id)
        )
        inverter = result.scalar_one_or_none()
        assert inverter is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_inverter_unauthenticated(client, test_inverter):
    """Test that unauthenticated user cannot delete inverter."""
    response = await client.delete(f"/inverter/{test_inverter.id}")

    # Should redirect to login
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_add_inverter_page(client, test_user):
    """Test GET request to add inverter page."""
    # Login first
    await client.post(
        "/login",
        data={"username": "testuser@example.com", "password": "testpassword123"}
    )

    response = await client.get("/add_inverter")
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_influx_bucket_created_on_inverter_creation(client, test_user, mocker):
    """Test that InfluxDB bucket is created when inverter is created."""
    # Store user ID before it potentially becomes detached
    user_id = test_user.id

    # Login first
    await client.post(
        "/login",
        data={"username": "testuser@example.com", "password": "testpassword123"}
    )

    # Mock InfluxDB bucket creation (don't use without_influx so function is actually called)
    mock_bucket = mocker.patch(
        'solar_backend.api.inverter.create_influx_bucket',
        return_value="new-bucket-id"
    )

    # Create inverter
    inverter_data = InverterAddFactory()
    response = await client.post(
        "/inverter",
        json={"name": inverter_data.name, "serial": inverter_data.serial}
    )

    assert response.status_code == 200
    # Check that create_influx_bucket was called once
    mock_bucket.assert_called_once()
    # Verify the bucket name (second argument) matches inverter name
    assert mock_bucket.call_args[0][1] == inverter_data.name
    # Verify first argument is a User object (without accessing its attributes to avoid DetachedInstanceError)
    from solar_backend.db import User
    assert isinstance(mock_bucket.call_args[0][0], User)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_influx_bucket_deleted_on_inverter_deletion(client, test_user, test_inverter, mocker):
    """Test that InfluxDB bucket is deleted when inverter is deleted."""
    # Store values before they potentially become detached
    user_id = test_user.id
    bucket_id = test_inverter.influx_bucked_id
    inverter_id = test_inverter.id

    # Login first
    await client.post(
        "/login",
        data={"username": "testuser@example.com", "password": "testpassword123"}
    )

    # Mock InfluxDB bucket deletion (don't use without_influx)
    mock_delete = mocker.patch(
        'solar_backend.api.inverter.delete_influx_bucket',
        return_value=None
    )

    # Delete inverter
    response = await client.delete(f"/inverter/{inverter_id}")

    assert response.status_code == 200
    # Check that delete_influx_bucket was called once
    mock_delete.assert_called_once()
    # Verify the bucket ID (second argument) matches
    assert mock_delete.call_args[0][1] == bucket_id
    # Verify first argument is a User object (without accessing its attributes to avoid DetachedInstanceError)
    from solar_backend.db import User
    assert isinstance(mock_delete.call_args[0][0], User)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_multiple_inverters(client, test_user, mocker, db_session):
    """Test creating multiple inverters for the same user."""
    # Login first
    await client.post(
        "/login",
        data={"username": "testuser@example.com", "password": "testpassword123"}
    )

    # Mock InfluxDB operations
    mocker.patch(
        'solar_backend.api.inverter.create_influx_bucket',
        return_value="mock-bucket-id"
    )

    # Create first inverter
    inverter1 = InverterAddFactory()
    response1 = await client.post(
        "/inverter",
        json={"name": inverter1.name, "serial": inverter1.serial}
    )
    assert response1.status_code == 200

    # Create second inverter
    inverter2 = InverterAddFactory()
    response2 = await client.post(
        "/inverter",
        json={"name": inverter2.name, "serial": inverter2.serial}
    )
    assert response2.status_code == 200

    # Verify both inverters exist for the user
    async with db_session as session:
        result = await session.execute(
            select(Inverter).where(Inverter.user_id == test_user.id)
        )
        inverters = result.scalars().all()
        assert len(inverters) == 2
