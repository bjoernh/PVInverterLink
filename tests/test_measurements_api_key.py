"""
Tests for measurements endpoint with API key authentication.
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_measurement_with_api_key(client, test_user, db_session):
    """Test posting measurement data using API key authentication."""
    from sqlalchemy import update

    from solar_backend.utils.api_keys import generate_api_key
    from tests.helpers import create_inverter_in_db

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
                        "power_dc": 17,
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
                            "irradiation": 1.545455,
                        }
                    ],
                }
            ],
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
                        "power_dc": 17,
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
                            "irradiation": 1.545455,
                        }
                    ],
                }
            ],
        },
    )

    # This should fail without API key
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_measurement_multiple_inverters(client, test_user, db_session):
    """Test posting measurement data with multiple inverters."""
    from sqlalchemy import update

    from solar_backend.utils.api_keys import generate_api_key
    from tests.helpers import create_inverter_in_db

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
                        "power_dc": 17,
                    },
                    "dc_channels": [],
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
                        "power_dc": 26,
                    },
                    "dc_channels": [],
                },
            ],
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
    from sqlalchemy import update

    from solar_backend.utils.api_keys import generate_api_key
    from tests.helpers import create_inverter_in_db

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
                        "power_dc": 17,
                    },
                    "dc_channels": [],
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
                        "power_dc": 26,
                    },
                    "dc_channels": [],
                },
            ],
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
                        "power_dc": 17,
                    },
                    "dc_channels": [],
                }
            ],
        },
        headers={"X-API-Key": "test-api-key-here"},
    )

    # Should return 404 when all inverters not found
    assert response.status_code == 404
    data = response.json()
    assert data["success_count"] == 0
    assert data["error_count"] == 1
    assert data["results"][0]["status"] == "error"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_measurement_with_yield_aggregation(client, test_user, db_session):
    """Test that yield values from DC channels are aggregated into inverter_measurements."""
    from sqlalchemy import select, update

    from solar_backend.db import InverterMeasurement
    from solar_backend.utils.api_keys import generate_api_key
    from tests.helpers import create_inverter_in_db

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Create an inverter in the database for the test
    inverter = await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="116183771004",
        sw_version="v1.0.0",
        rated_power=5000,
        number_of_mppts=2,
    )

    # Test with multiple DC channels - yields should be aggregated
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
                        "power_ac": 100.0,
                        "voltage_ac": 229.8,
                        "current_ac": 0.4,
                        "frequency": 49.99,
                        "power_factor": 0.9,
                        "power_dc": 110,
                    },
                    "dc_channels": [
                        {
                            "channel": 1,
                            "name": "MPPT 1",
                            "power": 50.0,
                            "voltage": 30.4,
                            "current": 1.5,
                            "yield_day": 1000.0,  # 1000 Wh
                            "yield_total": 500.5,  # 500.5 kWh
                            "irradiation": 500.0,
                        },
                        {
                            "channel": 2,
                            "name": "MPPT 2",
                            "power": 50.0,
                            "voltage": 31.2,
                            "current": 1.6,
                            "yield_day": 800.0,  # 800 Wh
                            "yield_total": 400.3,  # 400.3 kWh
                            "irradiation": 450.0,
                        },
                    ],
                }
            ],
        },
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success_count"] == 1
    assert data["error_count"] == 0

    # Query the database to verify aggregated yield values were stored
    result = await db_session.execute(
        select(InverterMeasurement)
        .where(InverterMeasurement.inverter_id == inverter.id)
        .order_by(InverterMeasurement.time.desc())
        .limit(1)
    )
    measurement = result.scalar_one_or_none()

    assert measurement is not None
    assert measurement.total_output_power == 100
    # Yields should be summed from both DC channels (converted to int)
    assert measurement.yield_day_wh == 1800  # int(1000) + int(800)
    assert measurement.yield_total_kwh == 900  # int(500.5) + int(400.3)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_measurement_without_dc_channels(client, test_user, db_session):
    """Test that yield values are NULL when no DC channel data is provided."""
    from sqlalchemy import select, update

    from solar_backend.db import InverterMeasurement
    from solar_backend.utils.api_keys import generate_api_key
    from tests.helpers import create_inverter_in_db

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Create an inverter in the database for the test
    inverter = await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="116183771006",
        sw_version="v1.0.0",
        rated_power=5000,
        number_of_mppts=2,
    )

    # Test without DC channels
    response = await client.post(
        "/api/opendtu/measurements",
        json={
            "timestamp": "2025-10-19T17:54:43+02:00",
            "dtu_serial": "199980140256",
            "inverters": [
                {
                    "serial": "116183771006",
                    "name": "Windfang",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1760889277,
                    "measurements": {
                        "power_ac": 50.0,
                        "voltage_ac": 229.8,
                        "current_ac": 0.2,
                        "frequency": 49.99,
                        "power_factor": 0.9,
                        "power_dc": 55,
                    },
                    "dc_channels": [],  # Empty DC channels
                }
            ],
        },
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success_count"] == 1
    assert data["error_count"] == 0

    # Query the database to verify yield values are NULL
    result = await db_session.execute(
        select(InverterMeasurement)
        .where(InverterMeasurement.inverter_id == inverter.id)
        .order_by(InverterMeasurement.time.desc())
        .limit(1)
    )
    measurement = result.scalar_one_or_none()

    assert measurement is not None
    assert measurement.total_output_power == 50
    # Yields should be NULL when no DC data is provided
    assert measurement.yield_day_wh is None
    assert measurement.yield_total_kwh is None
