"""
Tests for Victron measurements endpoint with API key authentication.
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_victron_measurement_with_api_key(client, test_user, db_session):
    """Test posting Victron measurement data using API key authentication."""
    from sqlalchemy import update

    from solar_backend.utils.api_keys import generate_api_key
    from tests.helpers import create_inverter_in_db

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Create an inverter with actual device serial
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="HQ22345ABCD",  # Actual device serial
        sw_version="v3.20",
        rated_power=3000,
        number_of_mppts=1,
    )

    # Test with API key - this should work with the user's API key
    response = await client.post(
        "/api/victron/measurements",
        json={
            "timestamp": "2025-10-30T14:32:15+01:00",
            "cerbo_serial": "HQ2345ABCDE",
            "devices": [
                {
                    "device_instance": 0,
                    "serial": "HQ22345ABCD",
                    "name": "SmartSolar MPPT 150/35",
                    "product_name": "SmartSolar MPPT 150/35",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1730297535,
                    "yield_power_w": 245.5,
                    "yield_total_kwh": 1234.56,
                    "trackers": [
                        {
                            "tracker": 0,
                            "name": "PV-1",
                            "voltage": 48.3,
                            "power": 245.5,
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
    assert data["cerbo_serial"] == "HQ2345ABCDE"
    assert data["results"][0]["device_identifier"] == "HQ22345ABCD"
    assert data["results"][0]["status"] == "ok"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_victron_measurement_without_api_key(client, test_user, db_session):
    """Test posting Victron measurement data without API key."""
    from tests.helpers import create_inverter_in_db

    # Create an inverter with actual device serial
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="HQ22345ABCD",
        sw_version="v3.20",
        rated_power=3000,
        number_of_mppts=1,
    )

    # Test without API key - should fail with 401
    response = await client.post(
        "/api/victron/measurements",
        json={
            "timestamp": "2025-10-30T14:32:15+01:00",
            "cerbo_serial": "HQ2345ABCDE",
            "devices": [
                {
                    "device_instance": 0,
                    "serial": "HQ22345ABCD",
                    "name": "SmartSolar MPPT 150/35",
                    "product_name": "SmartSolar MPPT 150/35",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1730297535,
                    "yield_power_w": 245.5,
                    "yield_total_kwh": 1234.56,
                    "trackers": [],
                }
            ],
        },
    )

    # This should fail without API key
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_victron_measurement_multiple_devices(client, test_user, db_session):
    """Test posting Victron measurement data with multiple devices from one Cerbo GX."""
    from sqlalchemy import update

    from solar_backend.utils.api_keys import generate_api_key
    from tests.helpers import create_inverter_in_db

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Create two solar chargers with their actual device serials
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="HQ22345ABCD",
        sw_version="v3.20",
        rated_power=3000,
        number_of_mppts=1,
    )
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="HQ22345ABCE",
        sw_version="v3.20",
        rated_power=3000,
        number_of_mppts=1,
    )

    # Post measurements for both devices
    response = await client.post(
        "/api/victron/measurements",
        json={
            "timestamp": "2025-10-30T14:32:15+01:00",
            "cerbo_serial": "HQ2345ABCDE",
            "devices": [
                {
                    "device_instance": 0,
                    "serial": "HQ22345ABCD",
                    "name": "SmartSolar MPPT 150/35 #1",
                    "product_name": "SmartSolar MPPT 150/35",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1730297535,
                    "yield_power_w": 245.5,
                    "yield_total_kwh": 1234.56,
                    "trackers": [],
                },
                {
                    "device_instance": 1,
                    "serial": "HQ22345ABCE",
                    "name": "SmartSolar MPPT 150/35 #2",
                    "product_name": "SmartSolar MPPT 150/35",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1730297535,
                    "yield_power_w": 312.8,
                    "yield_total_kwh": 987.65,
                    "trackers": [],
                },
            ],
        },
        headers={"X-API-Key": test_api_key},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success_count"] == 2
    assert data["error_count"] == 0
    assert data["total_devices"] == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_victron_measurement_with_multi_tracker(client, test_user, db_session):
    """Test posting Victron measurement with multiple MPPT trackers."""
    from sqlalchemy import update

    from solar_backend.utils.api_keys import generate_api_key
    from tests.helpers import create_inverter_in_db

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Create an inverter with multiple MPPTs
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="HQ22345ABCD",
        sw_version="v3.20",
        rated_power=5000,
        number_of_mppts=4,
    )

    # Post measurement with 4 trackers (MPPT RS model)
    response = await client.post(
        "/api/victron/measurements",
        json={
            "timestamp": "2025-10-30T14:32:15+01:00",
            "cerbo_serial": "HQ2345ABCDE",
            "devices": [
                {
                    "device_instance": 0,
                    "serial": "HQ22345ABCD",
                    "name": "SmartSolar MPPT RS 450/200",
                    "product_name": "SmartSolar MPPT RS 450/200",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1730297535,
                    "yield_power_w": 982.4,
                    "yield_total_kwh": 5432.1,
                    "trackers": [
                        {
                            "tracker": 0,
                            "name": "PV-1",
                            "voltage": 125.3,
                            "power": 245.5,
                        },
                        {
                            "tracker": 1,
                            "name": "PV-2",
                            "voltage": 127.1,
                            "power": 248.2,
                        },
                        {
                            "tracker": 2,
                            "name": "PV-3",
                            "voltage": 126.8,
                            "power": 243.1,
                        },
                        {
                            "tracker": 3,
                            "name": "PV-4",
                            "voltage": 128.0,
                            "power": 245.6,
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_victron_measurement_unknown_device(client, test_user, db_session):
    """Test posting Victron measurement for unknown device."""
    from sqlalchemy import update

    from solar_backend.utils.api_keys import generate_api_key

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Post measurement for device that doesn't exist in database
    response = await client.post(
        "/api/victron/measurements",
        json={
            "timestamp": "2025-10-30T14:32:15+01:00",
            "cerbo_serial": "HQ2345ABCDE",
            "devices": [
                {
                    "device_instance": 99,
                    "serial": "HQ99999ZZZZ",
                    "name": "Unknown Device",
                    "product_name": "Unknown",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1730297535,
                    "yield_power_w": 245.5,
                    "yield_total_kwh": 1234.56,
                    "trackers": [],
                }
            ],
        },
        headers={"X-API-Key": test_api_key},
    )

    # Should return 404 since device not found
    assert response.status_code == 404
    data = response.json()
    assert data["success_count"] == 0
    assert data["error_count"] == 1
    assert data["results"][0]["status"] == "error"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_victron_measurement_mixed_results(client, test_user, db_session):
    """Test posting Victron measurements with one valid and one invalid device (207 Multi-Status)."""
    from sqlalchemy import update

    from solar_backend.utils.api_keys import generate_api_key
    from tests.helpers import create_inverter_in_db

    # Generate and assign API key to test user
    test_api_key = generate_api_key()
    await db_session.execute(
        update(test_user.__class__).where(test_user.__class__.id == test_user.id).values(api_key=test_api_key)
    )
    await db_session.commit()

    # Create only one device
    await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        serial_logger="HQ22345ABCD",
        sw_version="v3.20",
        rated_power=3000,
        number_of_mppts=1,
    )

    # Post measurements for one valid and one invalid device
    response = await client.post(
        "/api/victron/measurements",
        json={
            "timestamp": "2025-10-30T14:32:15+01:00",
            "cerbo_serial": "HQ2345ABCDE",
            "devices": [
                {
                    "device_instance": 0,
                    "serial": "HQ22345ABCD",
                    "name": "Valid Device",
                    "product_name": "SmartSolar MPPT 150/35",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1730297535,
                    "yield_power_w": 245.5,
                    "yield_total_kwh": 1234.56,
                    "trackers": [],
                },
                {
                    "device_instance": 99,
                    "serial": "HQ99999ZZZZ",
                    "name": "Invalid Device",
                    "product_name": "Unknown",
                    "reachable": True,
                    "producing": True,
                    "last_update": 1730297535,
                    "yield_power_w": 100.0,
                    "yield_total_kwh": 500.0,
                    "trackers": [],
                },
            ],
        },
        headers={"X-API-Key": test_api_key},
    )

    # Should return 207 Multi-Status
    assert response.status_code == 207
    data = response.json()
    assert data["success_count"] == 1
    assert data["error_count"] == 1
    assert data["total_devices"] == 2
