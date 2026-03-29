"""
Tests for the summary dashboard feature (aggregated metrics across all inverters).
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.orm import make_transient

from tests.helpers import create_inverter_in_db


@pytest_asyncio.fixture
async def second_inverter(db_session, test_user):
    """Create a second test inverter for the test user."""
    inverter = await create_inverter_in_db(
        db_session,
        user_id=test_user.id,
        name="Second Inverter",
        serial_logger="TEST-456",
    )
    _ = (inverter.id, inverter.name, inverter.serial_logger)
    make_transient(inverter)
    return inverter


@pytest.fixture
def without_timeseries(mocker):
    """
    Mock all time-series query functions used by the summary endpoints.
    """
    mocker.patch("solar_backend.utils.timeseries.get_power_timeseries", return_value=[])
    mocker.patch("solar_backend.utils.timeseries.get_today_energy_production", return_value=0.0)
    mocker.patch("solar_backend.utils.timeseries.get_today_maximum_power", return_value=0)
    mocker.patch("solar_backend.utils.timeseries.get_last_hour_average", return_value=0)
    mocker.patch("solar_backend.utils.timeseries.get_hourly_energy_production", return_value=[])
    mocker.patch("solar_backend.utils.timeseries.get_current_month_energy_production", return_value=[])
    mocker.patch("solar_backend.utils.timeseries.get_current_week_energy_production", return_value=[])


# --- /dashboard/summary page tests ---


@pytest.mark.asyncio
async def test_summary_page_redirects_with_single_inverter(authenticated_client: AsyncClient, test_inverter):
    """Summary page should redirect to / when user has only one inverter."""
    response = await authenticated_client.get("/dashboard/summary", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


@pytest.mark.asyncio
async def test_summary_page_loads_with_multiple_inverters(
    authenticated_client: AsyncClient, test_inverter, second_inverter
):
    """Summary page should load when user has two or more inverters."""
    response = await authenticated_client.get("/dashboard/summary")

    assert response.status_code == 200
    assert "Gesamtübersicht" in response.text
    assert "Alle 2 Wechselrichter" in response.text


@pytest.mark.asyncio
async def test_summary_page_requires_authentication(async_client: AsyncClient):
    """Summary page should require authentication."""
    response = await async_client.get("/dashboard/summary", follow_redirects=False)

    assert response.status_code in [401, 303]


@pytest.mark.asyncio
async def test_summary_page_time_range_parameter(authenticated_client: AsyncClient, test_inverter, second_inverter):
    """Summary page should accept and reflect valid time range parameter."""
    response = await authenticated_client.get("/dashboard/summary?time_range=7 days")

    assert response.status_code == 200
    assert "'7 days'" in response.text


@pytest.mark.asyncio
async def test_summary_page_invalid_time_range_defaults(
    authenticated_client: AsyncClient, test_inverter, second_inverter
):
    """Summary page should default to 24 hours for invalid time range."""
    response = await authenticated_client.get("/dashboard/summary?time_range=invalid")

    assert response.status_code == 200
    assert "'24 hours'" in response.text


@pytest.mark.asyncio
async def test_summary_page_has_time_range_buttons(authenticated_client: AsyncClient, test_inverter, second_inverter):
    """Summary page should display time range selector buttons."""
    response = await authenticated_client.get("/dashboard/summary")

    assert response.status_code == 200
    for label in ["1H", "6H", "24H", "7D", "30D"]:
        assert label in response.text


@pytest.mark.asyncio
async def test_summary_page_has_auto_refresh(authenticated_client: AsyncClient, test_inverter, second_inverter):
    """Summary page should include auto-refresh functionality."""
    response = await authenticated_client.get("/dashboard/summary")

    assert response.status_code == 200
    assert "startAutoRefresh" in response.text


# --- /api/summary/data tests ---


@pytest.mark.asyncio
async def test_summary_data_api_requires_authentication(async_client: AsyncClient):
    """Summary data API should require authentication."""
    response = await async_client.get("/api/summary/data")

    assert response.status_code in [401, 303]


@pytest.mark.asyncio
async def test_summary_data_api_no_inverters(authenticated_client: AsyncClient, without_timeseries):
    """Summary data API should return success=False when user has no inverters."""
    response = await authenticated_client.get("/api/summary/data")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "stats" in data
    assert data["stats"]["current"] == 0


@pytest.mark.asyncio
async def test_summary_data_api_returns_correct_structure(
    authenticated_client: AsyncClient, test_inverter, second_inverter, without_timeseries
):
    """Summary data API should return correct response structure."""
    response = await authenticated_client.get("/api/summary/data")

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "stats" in data
    assert "total" in data
    assert "per_inverter" in data

    # Stats fields
    assert "current" in data["stats"]
    assert "max" in data["stats"]
    assert "today_kwh" in data["stats"]
    assert "avg_last_hour" in data["stats"]

    # Per-inverter entries
    assert len(data["per_inverter"]) == 2
    names = {inv["name"] for inv in data["per_inverter"]}
    assert test_inverter.name in names
    assert second_inverter.name in names


@pytest.mark.asyncio
async def test_summary_data_api_accepts_all_time_ranges(
    authenticated_client: AsyncClient, test_inverter, second_inverter, without_timeseries
):
    """Summary data API should accept all valid time ranges."""
    for time_range in ["1 hour", "6 hours", "24 hours", "7 days", "30 days"]:
        response = await authenticated_client.get(f"/api/summary/data?time_range={time_range}")

        assert response.status_code == 200
        assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_summary_data_api_invalid_time_range_defaults(
    authenticated_client: AsyncClient, test_inverter, second_inverter, without_timeseries
):
    """Summary data API should handle invalid time range gracefully."""
    response = await authenticated_client.get("/api/summary/data?time_range=invalid")

    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_summary_data_api_aggregates_stats(
    authenticated_client: AsyncClient, test_inverter, second_inverter, mocker
):
    """Summary data API should aggregate stats across all inverters."""
    mocker.patch("solar_backend.api.summary.get_power_timeseries", return_value=[])
    mocker.patch("solar_backend.api.summary.get_today_maximum_power", return_value=500)
    mocker.patch("solar_backend.api.summary.get_today_energy_production", return_value=2.5)
    mocker.patch("solar_backend.api.summary.get_last_hour_average", return_value=300)

    response = await authenticated_client.get("/api/summary/data")

    assert response.status_code == 200
    data = response.json()

    # Two inverters each returning 500W max → total 1000W
    assert data["stats"]["max"] == 1000
    # Two inverters each returning 2.5 kWh → total 5.0 kWh
    assert data["stats"]["today_kwh"] == 5.0
    # Two inverters each returning 300W avg → total 600W
    assert data["stats"]["avg_last_hour"] == 600


# --- /api/summary/energy-data tests ---


@pytest.mark.asyncio
async def test_summary_energy_data_api_requires_authentication(async_client: AsyncClient):
    """Summary energy data API should require authentication."""
    response = await async_client.get("/api/summary/energy-data")

    assert response.status_code in [401, 303]


@pytest.mark.asyncio
async def test_summary_energy_data_api_no_inverters(authenticated_client: AsyncClient, without_timeseries):
    """Summary energy data API should return success=False with no inverters."""
    response = await authenticated_client.get("/api/summary/energy-data")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "total" in data
    assert "per_inverter" in data


@pytest.mark.asyncio
async def test_summary_energy_data_api_returns_correct_structure(
    authenticated_client: AsyncClient, test_inverter, second_inverter, without_timeseries
):
    """Summary energy data API should return correct response structure."""
    response = await authenticated_client.get("/api/summary/energy-data")

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "period" in data
    assert "total" in data
    assert "per_inverter" in data
    assert len(data["per_inverter"]) == 2


@pytest.mark.asyncio
async def test_summary_energy_data_api_all_periods(
    authenticated_client: AsyncClient, test_inverter, second_inverter, without_timeseries
):
    """Summary energy data API should accept all valid periods."""
    for period in ["day", "week", "month"]:
        response = await authenticated_client.get(f"/api/summary/energy-data?period={period}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["period"] == period


@pytest.mark.asyncio
async def test_summary_energy_data_api_invalid_period_defaults(
    authenticated_client: AsyncClient, test_inverter, second_inverter, without_timeseries
):
    """Summary energy data API should default to 'day' for invalid period."""
    response = await authenticated_client.get("/api/summary/energy-data?period=invalid")

    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "day"
