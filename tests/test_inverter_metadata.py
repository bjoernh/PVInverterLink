"""
Tests for inverter metadata endpoint.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from solar_backend.db import Inverter, User


@pytest.mark.asyncio
async def test_update_inverter_metadata_success(
    async_client: AsyncClient,
    test_user: User,
    test_inverter: Inverter,
    superuser_token_headers: dict,
):
    """Test successful metadata update for existing inverter."""
    # Initial state: test_inverter has default values from fixture
    # We'll update them to different values

    # Update metadata
    metadata = {"rated_power": 600, "number_of_mppts": 2}

    response = await async_client.post(
        f"/inverter_metadata/{test_inverter.serial_logger}", json=metadata, headers=superuser_token_headers
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_inverter.id
    assert data["serial_logger"] == test_inverter.serial_logger
    assert data["name"] == test_inverter.name
    assert data["rated_power"] == 600
    assert data["number_of_mppts"] == 2


@pytest.mark.asyncio
async def test_update_inverter_metadata_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict,
):
    """Test metadata update for non-existent inverter."""
    metadata = {"rated_power": 600, "number_of_mppts": 2}

    response = await async_client.post(
        "/inverter_metadata/9999999999",  # Non-existent serial
        json=metadata,
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
    assert "not found" in response.text.lower()


@pytest.mark.asyncio
async def test_update_inverter_metadata_unauthorized(
    async_client: AsyncClient,
    test_inverter: Inverter,
    user_token_headers: dict,
):
    """Test that regular users cannot update metadata."""
    metadata = {"rated_power": 600, "number_of_mppts": 2}

    response = await async_client.post(
        f"/inverter_metadata/{test_inverter.serial_logger}", json=metadata, headers=user_token_headers
    )

    # Should be forbidden (403) since only superusers can update metadata
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_inverter_metadata_no_auth(
    async_client: AsyncClient,
    test_inverter: Inverter,
):
    """Test that unauthenticated requests are rejected."""
    metadata = {"rated_power": 600, "number_of_mppts": 2}

    response = await async_client.post(f"/inverter_metadata/{test_inverter.serial_logger}", json=metadata)

    # Should be unauthorized (401)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_inverter_metadata_multiple_times(
    async_client: AsyncClient,
    test_inverter: Inverter,
    superuser_token_headers: dict,
    db_session: AsyncSession,
):
    """Test that metadata can be updated multiple times."""
    # First update
    metadata1 = {"rated_power": 300, "number_of_mppts": 1}

    response1 = await async_client.post(
        f"/inverter_metadata/{test_inverter.serial_logger}", json=metadata1, headers=superuser_token_headers
    )

    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["rated_power"] == 300
    assert data1["number_of_mppts"] == 1

    # Second update (overwrite)
    metadata2 = {"rated_power": 600, "number_of_mppts": 2}

    response2 = await async_client.post(
        f"/inverter_metadata/{test_inverter.serial_logger}", json=metadata2, headers=superuser_token_headers
    )

    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["rated_power"] == 600
    assert data2["number_of_mppts"] == 2

    # Verify in database by querying fresh
    result = await db_session.execute(select(Inverter).where(Inverter.serial_logger == test_inverter.serial_logger))
    updated_inverter = result.scalar_one()
    assert updated_inverter.rated_power == 600
    assert updated_inverter.number_of_mppts == 2


@pytest.mark.asyncio
async def test_update_inverter_metadata_invalid_data(
    async_client: AsyncClient,
    test_inverter: Inverter,
    superuser_token_headers: dict,
):
    """Test validation of metadata fields."""
    # Missing required field
    metadata_missing = {
        "rated_power": 600
        # missing number_of_mppts
    }

    response = await async_client.post(
        f"/inverter_metadata/{test_inverter.serial_logger}", json=metadata_missing, headers=superuser_token_headers
    )

    assert response.status_code == 422  # Unprocessable Entity


@pytest.mark.asyncio
async def test_update_inverter_metadata_zero_values(
    async_client: AsyncClient,
    test_inverter: Inverter,
    superuser_token_headers: dict,
):
    """Test that zero values are accepted (edge case)."""
    metadata = {"rated_power": 0, "number_of_mppts": 0}

    response = await async_client.post(
        f"/inverter_metadata/{test_inverter.serial_logger}", json=metadata, headers=superuser_token_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["rated_power"] == 0
    assert data["number_of_mppts"] == 0


@pytest.mark.asyncio
async def test_update_inverter_metadata_typical_values(
    async_client: AsyncClient,
    test_inverter: Inverter,
    superuser_token_headers: dict,
):
    """Test typical metadata values for Deye inverters."""
    test_cases = [
        {"rated_power": 300, "number_of_mppts": 1},  # SUN300G3
        {"rated_power": 600, "number_of_mppts": 2},  # SUN600G3
        {"rated_power": 800, "number_of_mppts": 2},  # SUN800G3
        {"rated_power": 1200, "number_of_mppts": 4},  # SUN1200G3
    ]

    for metadata in test_cases:
        response = await async_client.post(
            f"/inverter_metadata/{test_inverter.serial_logger}", json=metadata, headers=superuser_token_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rated_power"] == metadata["rated_power"]
        assert data["number_of_mppts"] == metadata["number_of_mppts"]
