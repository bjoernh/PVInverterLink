"""
Tests for multi-tenant authorization and data isolation.
Ensures users can only access their own inverters and data.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from solar_backend.db import Inverter


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_cannot_delete_other_users_inverter(client, db_session):
    """Test that User A cannot delete User B's inverter."""
    from tests.helpers import create_user_in_db, create_inverter_in_db

    # Create two users
    user_a = await create_user_in_db(
        db_session,
        email="user_a@example.com",
        first_name="User",
        last_name="A"
    )

    user_b = await create_user_in_db(
        db_session,
        email="user_b@example.com",
        first_name="User",
        last_name="B"
    )

    # Create inverter for User B
    inverter_b = await create_inverter_in_db(
        db_session,
        user_id=user_b.id,
        serial_logger="USER-B-INVERTER"
    )

    # Login as User A
    await client.post(
        "/login",
        data={"username": "user_a@example.com", "password": "testpassword123"}
    )

    # Try to delete User B's inverter as User A
    response = await client.delete(f"/inverter/{inverter_b.id}")

    # Should return 403 Forbidden - User A cannot delete User B's inverter
    assert response.status_code == 403

    # Verify inverter was NOT deleted
    async with db_session as session:
        result = await session.execute(
            select(Inverter).where(Inverter.id == inverter_b.id)
        )
        inverter = result.scalar_one_or_none()
        assert inverter is not None  # Inverter should still exist


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_page_shows_only_user_inverters(client, db_session):
    """Test that start page only shows current user's inverters, not other users'."""
    from tests.helpers import create_user_in_db, create_inverter_in_db

    # Create two users with inverters
    user_a = await create_user_in_db(
        db_session,
        email="user_a@example.com"
    )

    user_b = await create_user_in_db(
        db_session,
        email="user_b@example.com"
    )

    inverter_a = await create_inverter_in_db(
        db_session,
        user_id=user_a.id,
        name="User A Inverter",
        serial_logger="SERIAL-A"
    )

    inverter_b = await create_inverter_in_db(
        db_session,
        user_id=user_b.id,
        name="User B Inverter",
        serial_logger="SERIAL-B"
    )

    # Login as User A
    await client.post(
        "/login",
        data={"username": "user_a@example.com", "password": "testpassword123"}
    )

    # Access start page
    response = await client.get("/")
    assert response.status_code == 200

    # User A should see their inverter
    assert "User A Inverter" in response.text or "SERIAL-A" in response.text

    # User A should NOT see User B's inverter
    assert "User B Inverter" not in response.text
    assert "SERIAL-B" not in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_cannot_create_inverter_for_another_user(client, db_session):
    """Test that authenticated user can only create inverters for themselves."""
    from tests.helpers import create_user_in_db
    from tests.factories import InverterAddFactory

    # Create User A
    user_a = await create_user_in_db(
        db_session,
        email="user_a@example.com"
    )

    # Login as User A
    await client.post(
        "/login",
        data={"username": "user_a@example.com", "password": "testpassword123"}
    )

    # Create inverter (should be automatically associated with logged-in user)
    inverter_data = InverterAddFactory()
    response = await client.post(
        "/inverter",
        json={"name": inverter_data.name, "serial": inverter_data.serial}
    )

    assert response.status_code == 200

    # Verify the inverter belongs to User A
    async with db_session as session:
        result = await session.execute(
            select(Inverter).where(Inverter.serial_logger == inverter_data.serial)
        )
        inverter = result.scalar_one()
        assert inverter.user_id == user_a.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_users_have_isolated_inverter_lists(client, db_session):
    """Test complete isolation: multiple users with multiple inverters each."""
    from tests.helpers import create_user_in_db, create_inverter_in_db

    # Create User 1 with 2 inverters
    user1 = await create_user_in_db(
        db_session,
        email="user1@example.com"
    )
    inv1_1 = await create_inverter_in_db(
        db_session,
        user_id=user1.id,
        name="User1 Inverter 1",
        serial_logger="U1-INV-1"
    )
    inv1_2 = await create_inverter_in_db(
        db_session,
        user_id=user1.id,
        name="User1 Inverter 2",
        serial_logger="U1-INV-2"
    )

    # Create User 2 with 2 inverters
    user2 = await create_user_in_db(
        db_session,
        email="user2@example.com"
    )
    inv2_1 = await create_inverter_in_db(
        db_session,
        user_id=user2.id,
        name="User2 Inverter 1",
        serial_logger="U2-INV-1"
    )
    inv2_2 = await create_inverter_in_db(
        db_session,
        user_id=user2.id,
        name="User2 Inverter 2",
        serial_logger="U2-INV-2"
    )

    # Login as User 1
    await client.post(
        "/login",
        data={"username": "user1@example.com", "password": "testpassword123"}
    )

    response1 = await client.get("/")
    assert response1.status_code == 200

    # User 1 should see only their inverters
    assert "User1 Inverter 1" in response1.text or "U1-INV-1" in response1.text
    assert "User1 Inverter 2" in response1.text or "U1-INV-2" in response1.text
    assert "User2 Inverter" not in response1.text
    assert "U2-INV" not in response1.text

    # Logout and login as User 2
    await client.get("/logout")
    await client.post(
        "/login",
        data={"username": "user2@example.com", "password": "testpassword123"}
    )

    response2 = await client.get("/")
    assert response2.status_code == 200

    # User 2 should see only their inverters
    assert "User2 Inverter 1" in response2.text or "U2-INV-1" in response2.text
    assert "User2 Inverter 2" in response2.text or "U2-INV-2" in response2.text
    assert "User1 Inverter" not in response2.text
    assert "U1-INV" not in response2.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_query_filters_by_user_id(db_session):
    """Test that database queries properly filter inverters by user_id."""
    from tests.helpers import create_user_in_db, create_inverter_in_db

    # Create two users
    user_a = await create_user_in_db(db_session, email="usera@example.com")
    user_b = await create_user_in_db(db_session, email="userb@example.com")

    # Create inverters for each user
    inv_a = await create_inverter_in_db(db_session, user_id=user_a.id, serial_logger="INV-A")
    inv_b = await create_inverter_in_db(db_session, user_id=user_b.id, serial_logger="INV-B")

    # Query User A's inverters
    async with db_session as session:
        result_a = await session.execute(
            select(Inverter).where(Inverter.user_id == user_a.id)
        )
        inverters_a = result_a.scalars().all()

        # User A should have only their inverter
        assert len(inverters_a) == 1
        assert inverters_a[0].serial_logger == "INV-A"

        # Query User B's inverters
        result_b = await session.execute(
            select(Inverter).where(Inverter.user_id == user_b.id)
        )
        inverters_b = result_b.scalars().all()

        # User B should have only their inverter
        assert len(inverters_b) == 1
        assert inverters_b[0].serial_logger == "INV-B"
