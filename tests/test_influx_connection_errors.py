"""
Tests for InfluxDB connection error handling.

These tests verify that the application handles InfluxDB connection failures
gracefully without returning 500 errors to users.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from httpx import AsyncClient

from solar_backend.db import User, Inverter
from solar_backend.utils.influx import InfluxManagement, InfluxConnectionError, NoValuesException
from solar_backend.inverter import extend_current_powers


@pytest.mark.asyncio
async def test_home_page_loads_when_influx_down(
    authenticated_client: AsyncClient,
    test_user: User,
    test_inverter: Inverter
):
    """Test that home page loads and shows inverters even when InfluxDB is down."""
    with patch('solar_backend.inverter.InfluxManagement') as mock_influx:
        # Simulate InfluxDB connection failure
        mock_instance = MagicMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.connect.side_effect = InfluxConnectionError("Connection refused")
        mock_influx.return_value = mock_instance

        response = await authenticated_client.get("/")

        # Page should load successfully
        assert response.status_code == 200
        # Inverter should be shown
        assert test_inverter.name in response.text
        # Should show service unavailable message
        assert "vorübergehend nicht verfügbar" in response.text or "Dienst" in response.text


@pytest.mark.asyncio
async def test_dashboard_shows_friendly_error_when_influx_down(
    authenticated_client: AsyncClient,
    test_inverter: Inverter,
    test_user: User
):
    """Test that dashboard shows friendly error when InfluxDB is down."""
    with patch('solar_backend.api.dashboard.InfluxManagement') as mock_influx:
        # Simulate InfluxDB connection failure
        mock_instance = MagicMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.connect.side_effect = InfluxConnectionError("Connection refused")
        mock_influx.return_value = mock_instance

        response = await authenticated_client.get(
            f"/api/dashboard/{test_inverter.id}/data"
        )

        # Should return 200 with error message, not 500
        assert response.status_code == 200
        data = response.json()

        assert data["success"] == False
        assert "InfluxDB" in data["message"]
        assert "vorübergehend nicht verfügbar" in data["message"]
        assert data["data"] == []
        assert data["stats"] == {"current": 0, "max": 0, "today_kwh": 0.0, "avg_last_hour": 0}


@pytest.mark.asyncio
async def test_extend_current_powers_handles_connection_error():
    """Test that extend_current_powers sets default values when InfluxDB is down."""
    # Create mock user and inverters
    mock_user = Mock()
    mock_user.influx_url = "http://localhost:8086"
    mock_user.email = "test@example.com"
    mock_user.influx_token = "test-token"
    mock_user.id = 1

    mock_inverter1 = Mock()
    mock_inverter1.name = "Inverter 1"
    mock_inverter1.current_power = None
    mock_inverter1.last_update = None

    mock_inverter2 = Mock()
    mock_inverter2.name = "Inverter 2"
    mock_inverter2.current_power = None
    mock_inverter2.last_update = None

    inverters = [mock_inverter1, mock_inverter2]

    with patch('solar_backend.inverter.InfluxManagement') as mock_influx:
        # Simulate InfluxDB connection failure
        mock_instance = MagicMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.connect.side_effect = InfluxConnectionError("Connection refused")
        mock_influx.return_value = mock_instance

        # Call the function
        await extend_current_powers(mock_user, inverters)

        # All inverters should have default "unavailable" values
        assert mock_inverter1.current_power == "-"
        assert "vorübergehend nicht verfügbar" in mock_inverter1.last_update
        assert mock_inverter2.current_power == "-"
        assert "vorübergehend nicht verfügbar" in mock_inverter2.last_update


@pytest.mark.asyncio
async def test_influx_connect_validates_health():
    """Test that InfluxManagement.connect() validates health check."""
    influx = InfluxManagement("http://localhost:8086")

    with patch('solar_backend.utils.influx.InfluxDBClient') as mock_client_class:
        mock_client = Mock()
        mock_health = Mock()
        mock_health.status = "fail"  # Unhealthy
        mock_health.message = "Database not ready"
        mock_client.health.return_value = mock_health
        mock_client_class.return_value = mock_client

        influx._client = mock_client

        # connect() should raise InfluxConnectionError for unhealthy database
        with pytest.raises(InfluxConnectionError) as exc_info:
            influx.connect(org="test-org", token="test-token")

        assert "not healthy or not reachable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_influx_get_latest_values_connection_error():
    """Test that get_latest_values raises InfluxConnectionError on connection failure."""
    influx = InfluxManagement("http://localhost:8086")
    influx._client = Mock()

    mock_user = Mock()
    mock_user.email = "test@example.com"

    # Simulate connection error
    influx._client.query_api.return_value.query.side_effect = ConnectionError("Connection refused")

    with pytest.raises(InfluxConnectionError) as exc_info:
        influx.get_latest_values(mock_user, "test-bucket")

    assert "Cannot reach InfluxDB for query" in str(exc_info.value)


@pytest.mark.asyncio
async def test_influx_get_latest_values_no_data():
    """Test that get_latest_values raises NoValuesException when no data found."""
    influx = InfluxManagement("http://localhost:8086")
    influx._client = Mock()

    mock_user = Mock()
    mock_user.email = "test@example.com"

    # Simulate empty query result
    influx._client.query_api.return_value.query.return_value = []

    with pytest.raises(NoValuesException) as exc_info:
        influx.get_latest_values(mock_user, "test-bucket")

    assert "no data" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_influx_get_power_timeseries_connection_error():
    """Test that get_power_timeseries raises InfluxConnectionError on connection failure."""
    influx = InfluxManagement("http://localhost:8086")
    influx._client = Mock()

    mock_user = Mock()
    mock_user.email = "test@example.com"

    # Simulate timeout error
    influx._client.query_api.return_value.query.side_effect = TimeoutError("Request timeout")

    with pytest.raises(InfluxConnectionError) as exc_info:
        influx.get_power_timeseries(mock_user, "test-bucket", "24h")

    assert "Cannot reach InfluxDB for query" in str(exc_info.value)


@pytest.mark.asyncio
async def test_influx_create_bucket_connection_error():
    """Test that create_bucket raises InfluxConnectionError on connection failure."""
    influx = InfluxManagement("http://localhost:8086")
    influx._client = Mock()

    # Simulate connection error
    influx._client.buckets_api.return_value.create_bucket.side_effect = OSError("Network unreachable")

    with pytest.raises(InfluxConnectionError) as exc_info:
        influx.create_bucket("test-bucket", "org-id-123")

    assert "Cannot reach InfluxDB to create bucket" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dashboard_distinguishes_no_data_from_connection_error(
    authenticated_client: AsyncClient,
    test_inverter: Inverter,
    test_user: User
):
    """Test that dashboard shows different messages for no data vs connection error."""
    # Test with mocked InfluxDB that returns empty data (not connection error)
    with patch('solar_backend.api.dashboard.InfluxManagement') as mock_influx:
        mock_instance = MagicMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.connect.return_value = None
        # Simulate query returning no data
        mock_instance.get_power_timeseries.side_effect = NoValuesException("No data in query")
        mock_influx.return_value = mock_instance

        response = await authenticated_client.get(
            f"/api/dashboard/{test_inverter.id}/data"
        )

        assert response.status_code == 200
        data = response.json()
        # Message should mention "keine Daten" not "nicht verfügbar"
        assert "Keine Daten" in data["message"] or "keine Daten" in data["message"].lower()
        # Should NOT be about service unavailability
        assert "InfluxDB-Dienst" not in data["message"]


@pytest.mark.asyncio
async def test_context_manager_closes_client_on_error():
    """Test that InfluxManagement context manager closes client even on error."""
    influx = InfluxManagement("http://localhost:8086")

    mock_client = Mock()
    influx._client = mock_client

    try:
        async with influx:
            raise ValueError("Some error during operation")
    except ValueError:
        pass

    # Client should be closed even though an error occurred
    mock_client.close.assert_called_once()
