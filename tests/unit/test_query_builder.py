"""
Unit tests for the TimeSeriesQueryBuilder.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from solar_backend.utils.query_builder import TimeSeriesQueryBuilder


class MockRow:
    def __init__(self, date, yield_day_wh=None, energy_kwh=None):
        self.date = date
        if yield_day_wh is not None:
            self.yield_day_wh = yield_day_wh
        if energy_kwh is not None:
            self.energy_kwh = energy_kwh


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_energy_production_uses_yield_data():
    """Test that get_energy_production uses yield data when threshold is met."""
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()

    builder = TimeSeriesQueryBuilder(session=mock_session, user_id=1, inverter_id=1)

    # Mock return value for the yield query
    mock_yield_data = [
        MockRow(date=date(2023, 1, 1), yield_day_wh=1000),
        MockRow(date=date(2023, 1, 2), yield_day_wh=1500),
    ]
    mock_result = MagicMock()
    mock_result.__iter__.return_value = iter(mock_yield_data)
    mock_session.execute.return_value = mock_result

    # Act
    # Set threshold to 2, which is met by the 2 rows of mock data
    energy_data = await builder.get_energy_production(
        time_filter_clause="time > now() - interval '7 days'", yield_threshold=2
    )

    # Assert
    # Should have called execute once for the yield query
    mock_session.execute.assert_called_once()

    # Check that the returned data is correctly transformed from yield data
    assert len(energy_data) == 2
    assert energy_data[0] == {"date": "2023-01-01", "energy_kwh": 1.0}
    assert energy_data[1] == {"date": "2023-01-02", "energy_kwh": 1.5}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_energy_production_falls_back_to_integration():
    """Test that get_energy_production falls back to power integration when yield threshold is not met."""
    # Arrange
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()

    builder = TimeSeriesQueryBuilder(session=mock_session, user_id=1, inverter_id=1)

    # Mock return value for the first (yield) query - only one row
    mock_yield_data = [MockRow(date=date(2023, 1, 1), yield_day_wh=1000)]
    mock_yield_result = MagicMock()
    mock_yield_result.__iter__.return_value = iter(mock_yield_data)

    # Mock return value for the second (integration) query
    mock_integration_data = [
        MockRow(date=date(2023, 1, 1), energy_kwh=1.1),
        MockRow(date=date(2023, 1, 2), energy_kwh=1.6),
    ]
    mock_integration_result = MagicMock()
    mock_integration_result.__iter__.return_value = iter(mock_integration_data)

    # Set up the side_effect to return the yield result first, then the integration result
    mock_session.execute.side_effect = [mock_yield_result, mock_integration_result]

    # Act
    # Set threshold to 2, which is NOT met by the 1 row of mock yield data
    energy_data = await builder.get_energy_production(
        time_filter_clause="time > now() - interval '7 days'", yield_threshold=2
    )

    # Assert
    # Should have called execute twice: once for yield, once for integration
    assert mock_session.execute.call_count == 2

    # Check that the returned data is correctly transformed from the integration data
    assert len(energy_data) == 2
    assert energy_data[0] == {"date": "2023-01-01", "energy_kwh": 1.1}
    assert energy_data[1] == {"date": "2023-01-02", "energy_kwh": 1.6}
