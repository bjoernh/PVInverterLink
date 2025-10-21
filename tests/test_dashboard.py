"""
Tests for the real-time power dashboard feature (REQ-DASH-001).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from solar_backend.db import User, Inverter


@pytest.mark.asyncio
async def test_dashboard_page_loads(
    authenticated_client: AsyncClient, test_user: User, test_inverter: Inverter
):
    """Test that dashboard page loads for authenticated user."""
    response = await authenticated_client.get(f"/dashboard/{test_inverter.id}")

    assert response.status_code == 200
    assert test_inverter.name in response.text
    assert test_inverter.serial_logger in response.text
    assert "powerChart" in response.text  # Chart canvas exists


@pytest.mark.asyncio
async def test_dashboard_requires_authentication(
    async_client: AsyncClient, test_inverter: Inverter
):
    """Test that dashboard requires authentication."""
    response = await async_client.get(f"/dashboard/{test_inverter.id}")

    # Should redirect to login or return 401
    assert response.status_code in [401, 303]


@pytest.mark.asyncio
async def test_dashboard_nonexistent_inverter(
    authenticated_client: AsyncClient, test_user: User
):
    """Test dashboard with non-existent inverter ID."""
    response = await authenticated_client.get("/dashboard/999999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_time_range_parameter(
    authenticated_client: AsyncClient, test_inverter: Inverter
):
    """Test that time range parameter is accepted."""
    for time_range in ["1 hour", "6 hours", "24 hours", "7 days", "30 days"]:
        response = await authenticated_client.get(
            f"/dashboard/{test_inverter.id}?time_range={time_range}"
        )

        assert response.status_code == 200
        assert f"'{time_range}'" in response.text  # Check JS variable


@pytest.mark.asyncio
async def test_dashboard_invalid_time_range_defaults_to_24h(
    authenticated_client: AsyncClient, test_inverter: Inverter
):
    """Test that invalid time range defaults to 24h."""
    response = await authenticated_client.get(
        f"/dashboard/{test_inverter.id}?time_range=invalid"
    )

    assert response.status_code == 200
    assert "'24 hours'" in response.text  # Defaults to 24 hours


@pytest.mark.asyncio
async def test_dashboard_api_data_endpoint(
    authenticated_client: AsyncClient,
    test_user: User,
    test_inverter: Inverter,
    without_influx,
):
    """Test the API endpoint that returns dashboard data."""
    response = await authenticated_client.get(
        f"/api/dashboard/{test_inverter.id}/data?time_range=24 hours"
    )

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "success" in data
    assert "data" in data
    assert "stats" in data
    assert "inverter" in data

    # Check stats structure
    assert "current" in data["stats"]
    assert "max" in data["stats"]
    assert "today_kwh" in data["stats"]
    assert "avg_last_hour" in data["stats"]

    # Check inverter info
    assert data["inverter"]["id"] == test_inverter.id
    assert data["inverter"]["name"] == test_inverter.name
    assert data["inverter"]["serial"] == test_inverter.serial_logger


@pytest.mark.asyncio
async def test_dashboard_api_requires_authentication(
    async_client: AsyncClient, test_inverter: Inverter
):
    """Test that API endpoint requires authentication."""
    response = await async_client.get(f"/api/dashboard/{test_inverter.id}/data")

    # Should be unauthorized
    assert response.status_code in [401, 303]


@pytest.mark.asyncio
async def test_dashboard_api_all_time_ranges(
    authenticated_client: AsyncClient, test_inverter: Inverter, without_influx
):
    """Test that API accepts all valid time ranges."""
    time_ranges = ["1 hour", "6 hours", "24 hours", "7 days", "30 days"]

    for time_range in time_ranges:
        response = await authenticated_client.get(
            f"/api/dashboard/{test_inverter.id}/data?time_range={time_range}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data


@pytest.mark.asyncio
async def test_dashboard_api_invalid_time_range(
    authenticated_client: AsyncClient, test_inverter: Inverter, without_influx
):
    """Test that API handles invalid time range gracefully."""
    response = await authenticated_client.get(
        f"/api/dashboard/{test_inverter.id}/data?time_range=invalid"
    )

    # Should default to 24 hours and return success
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_shows_inverter_metadata(
    authenticated_client: AsyncClient,
    test_user: User,
    test_inverter: Inverter,
    db_session: AsyncSession,
):
    """Test that dashboard displays inverter metadata when available."""
    # Set metadata
    async with db_session as session:
        result = await session.execute(
            select(Inverter).where(Inverter.id == test_inverter.id)
        )
        inverter = result.scalar_one()
        inverter.rated_power = 600
        inverter.number_of_mppts = 2
        await session.commit()

    response = await authenticated_client.get(f"/dashboard/{test_inverter.id}")

    assert response.status_code == 200
    assert "600 W" in response.text  # Rated power displayed
    assert "Nennleistung" in response.text


@pytest.mark.asyncio
async def test_dashboard_page_includes_plotly(
    authenticated_client: AsyncClient, test_inverter: Inverter
):
    """Test that dashboard includes Plotly library."""
    response = await authenticated_client.get(f"/dashboard/{test_inverter.id}")

    assert response.status_code == 200
    assert "plotly" in response.text.lower()


@pytest.mark.asyncio
async def test_dashboard_time_range_selector_exists(
    authenticated_client: AsyncClient, test_inverter: Inverter
):
    """Test that dashboard has time range selector buttons."""
    response = await authenticated_client.get(f"/dashboard/{test_inverter.id}")

    assert response.status_code == 200
    # Check for all time range buttons
    for range_text in ["1H", "6H", "24H", "7D", "30D"]:
        assert range_text in response.text


@pytest.mark.asyncio
async def test_dashboard_has_statistics_cards(
    authenticated_client: AsyncClient, test_inverter: Inverter
):
    """Test that dashboard displays statistics cards."""
    response = await authenticated_client.get(f"/dashboard/{test_inverter.id}")

    assert response.status_code == 200
    # Check for stat labels
    assert "Aktuell" in response.text
    assert "Maximum heute" in response.text
    assert "Produktion Heute" in response.text
    assert "Durchschnitt (letzte Stunde)" in response.text


@pytest.mark.asyncio
async def test_dashboard_has_auto_refresh(
    authenticated_client: AsyncClient, test_inverter: Inverter
):
    """Test that dashboard includes auto-refresh functionality."""
    response = await authenticated_client.get(f"/dashboard/{test_inverter.id}")

    assert response.status_code == 200
    # Check for refresh functions in JavaScript
    assert "startAutoRefresh" in response.text
    assert "30000" in response.text  # 30 second interval


@pytest.mark.asyncio
async def test_dashboard_back_button_to_home(
    authenticated_client: AsyncClient, test_inverter: Inverter
):
    """Test that dashboard has back button to home."""
    response = await authenticated_client.get(f"/dashboard/{test_inverter.id}")

    assert response.status_code == 200
    assert 'href="/"' in response.text
    assert "Zurück" in response.text


@pytest.mark.asyncio
async def test_dashboard_api_nonexistent_inverter(
    authenticated_client: AsyncClient, without_influx
):
    """Test API with non-existent inverter."""
    response = await authenticated_client.get("/api/dashboard/999999/data")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_home_page_shows_dashboard_link(
    authenticated_client: AsyncClient, test_user: User, test_inverter: Inverter
):
    """Test that home page shows dashboard button for inverters."""
    response = await authenticated_client.get("/")

    assert response.status_code == 200
    # Check for dashboard link in home page
    assert f"/dashboard/{test_inverter.id}" in response.text
    assert "Dashboard" in response.text
