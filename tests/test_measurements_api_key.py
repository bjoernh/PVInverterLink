"""
Tests for measurements endpoint with API key authentication.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_measurement_with_api_key(client, test_user, db_session):
    """Test posting measurement data using API key authentication."""
    from tests.helpers import create_inverter_in_db
    from solar_backend.utils.api_keys import generate_api_key
    from sqlalchemy import update

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Create an inverter in the database for the test
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="116183771004",
        sw_version="v1.0.0",
        rated_power=5000,
        number_of_mppts=2,
    )

    # Test with API key - this should work with the user's API key
    response = await client.post(
        "/api/opendtu/measurements",
        json={
            "timestamp": "2025-10-19T17:54:43+02:00",
            "dtu_serial": "199980140256",
            "inverters": [
                {
                    "serial": "116183771004",
                    "name": "Windfang",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1760889277,
                    "measurements": {
                        "power_ac": 16.1,
                        "voltage_ac": 229.8,
                        "current_ac": 0.07,
                        "frequency": 49.99,
                        "power_factor": 0.617,
                        "power_dc": 17
                    },
                    "dc_channels": [
                        {
                            "channel": 1,
                            "name": "Hochbeet",
                            "power": 3.4,
                            "voltage": 30.4,
                            "current": 0.11,
                            "yield_day": 337,
                            "yield_total": 444.671,
                            "irradiation": 1.545455
                        }
                    ]
                }
            ]
        },
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success_count"] == 1
    assert data["error_count"] == 0
    assert data["dtu_serial"] == "199980140256"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_measurement_without_api_key(client, test_user, db_session):
    """Test posting measurement data without API key."""
    from tests.helpers import create_inverter_in_db

    # Create an inverter in the database for the test
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="116183771004",
        sw_version="v1.0.0",
        rated_power=5000,
        number_of_mppts=2,
    )

    # Test without API key - should fail with 401
    response = await client.post(
        "/api/opendtu/measurements",
        json={
            "timestamp": "2025-10-19T17:54:43+02:00",
            "dtu_serial": "199980140256",
            "inverters": [
                {
                    "serial": "116183771004",
                    "name": "Windfang",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1760889277,
                    "measurements": {
                        "power_ac": 16.1,
                        "voltage_ac": 229.8,
                        "current_ac": 0.07,
                        "frequency": 49.99,
                        "power_factor": 0.617,
                        "power_dc": 17
                    },
                    "dc_channels": [
                        {
                            "channel": 1,
                            "name": "Hochbeet",
                            "power": 3.4,
                            "voltage": 30.4,
                            "current": 0.11,
                            "yield_day": 337,
                            "yield_total": 444.671,
                            "irradiation": 1.545455
                        }
                    ]
                }
            ]
        },
    )

    # This should fail without API key
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_measurement_multiple_inverters(client, test_user, db_session):
    """Test posting measurement data with multiple inverters."""
    from tests.helpers import create_inverter_in_db
    from solar_backend.utils.api_keys import generate_api_key
    from sqlalchemy import update

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Create two inverters for the test
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="116183771004",
        name="Inverter 1",
    )
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="116183771005",
        name="Inverter 2",
    )

    # Test with multiple inverters
    response = await client.post(
        "/api/opendtu/measurements",
        json={
            "timestamp": "2025-10-19T17:54:43+02:00",
            "dtu_serial": "199980140256",
            "inverters": [
                {
                    "serial": "116183771004",
                    "name": "Inverter 1",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1760889277,
                    "measurements": {
                        "power_ac": 16.1,
                        "voltage_ac": 229.8,
                        "current_ac": 0.07,
                        "frequency": 49.99,
                        "power_factor": 0.617,
                        "power_dc": 17
                    },
                    "dc_channels": []
                },
                {
                    "serial": "116183771005",
                    "name": "Inverter 2",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1760889277,
                    "measurements": {
                        "power_ac": 25.5,
                        "voltage_ac": 230.1,
                        "current_ac": 0.11,
                        "frequency": 50.01,
                        "power_factor": 0.625,
                        "power_dc": 26
                    },
                    "dc_channels": []
                }
            ]
        },
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success_count"] == 2
    assert data["error_count"] == 0
    assert data["total_inverters"] == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_measurement_mixed_results(client, test_user, db_session):
    """Test posting measurement data where some inverters are found and others not."""
    from tests.helpers import create_inverter_in_db
    from solar_backend.utils.api_keys import generate_api_key
    from sqlalchemy import update

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Create only one inverter
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="116183771004",
        name="Inverter 1",
    )

    # Test with one known and one unknown inverter
    response = await client.post(
        "/api/opendtu/measurements",
        json={
            "timestamp": "2025-10-19T17:54:43+02:00",
            "dtu_serial": "199980140256",
            "inverters": [
                {
                    "serial": "116183771004",
                    "name": "Inverter 1",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1760889277,
                    "measurements": {
                        "power_ac": 16.1,
                        "voltage_ac": 229.8,
                        "current_ac": 0.07,
                        "frequency": 49.99,
                        "power_factor": 0.617,
                        "power_dc": 17
                    },
                    "dc_channels": []
                },
                {
                    "serial": "999999999999",
                    "name": "Unknown Inverter",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1760889277,
                    "measurements": {
                        "power_ac": 25.5,
                        "voltage_ac": 230.1,
                        "current_ac": 0.11,
                        "frequency": 50.01,
                        "power_factor": 0.625,
                        "power_dc": 26
                    },
                    "dc_channels": []
                }
            ]
        },
        headers={"X-API-Key": test_api_key},
    )

    # Should return 207 Multi-Status when some succeed and some fail
    assert response.status_code == 207
    data = response.json()
    assert data["success_count"] == 1
    assert data["error_count"] == 1
    assert data["total_inverters"] == 2

    # Check that results contain both success and error
    assert any(r["status"] == "ok" for r in data["results"])
    assert any(r["status"] == "error" for r in data["results"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_measurement_all_unknown_inverters(client, test_user, db_session):
    """Test posting measurement data where all inverters are unknown."""

    # Don't create any inverters

    # Test with unknown inverters
    response = await client.post(
        "/api/opendtu/measurements",
        json={
            "timestamp": "2025-10-19T17:54:43+02:00",
            "dtu_serial": "199980140256",
            "inverters": [
                {
                    "serial": "999999999999",
                    "name": "Unknown Inverter",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1760889277,
                    "measurements": {
                        "power_ac": 16.1,
                        "voltage_ac": 229.8,
                        "current_ac": 0.07,
                        "frequency": 49.99,
                        "power_factor": 0.617,
                        "power_dc": 17
                    },
                    "dc_channels": []
                }
            ]
        },
        headers={"X-API-Key": "test-api-key-here"},
    )

    # Should return 404 when all inverters not found
    assert response.status_code == 404
    data = response.json()
    assert data["success_count"] == 0
    assert data["error_count"] == 1
    assert data["results"][0]["status"] == "error"
