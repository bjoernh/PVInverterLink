"""
Unit tests for the summary module helper functions.
"""

import pytest

from solar_backend.api.summary import _format_daily_energy, _merge_energy_series, _merge_power_series


@pytest.mark.unit
class TestMergePowerSeries:
    def test_empty_input(self):
        result = _merge_power_series([])
        assert result == []

    def test_single_series(self):
        series = [{"time": "2024-01-01T10:00:00", "power": 100}]
        result = _merge_power_series([series])
        assert result == [{"time": "2024-01-01T10:00:00", "power": 100}]

    def test_two_series_matching_timestamps(self):
        series1 = [
            {"time": "2024-01-01T10:00:00", "power": 300},
            {"time": "2024-01-01T11:00:00", "power": 400},
        ]
        series2 = [
            {"time": "2024-01-01T10:00:00", "power": 200},
            {"time": "2024-01-01T11:00:00", "power": 100},
        ]
        result = _merge_power_series([series1, series2])
        assert len(result) == 2
        by_time = {p["time"]: p["power"] for p in result}
        assert by_time["2024-01-01T10:00:00"] == 500
        assert by_time["2024-01-01T11:00:00"] == 500

    def test_two_series_disjoint_timestamps(self):
        series1 = [{"time": "2024-01-01T10:00:00", "power": 300}]
        series2 = [{"time": "2024-01-01T11:00:00", "power": 200}]
        result = _merge_power_series([series1, series2])
        assert len(result) == 2
        by_time = {p["time"]: p["power"] for p in result}
        assert by_time["2024-01-01T10:00:00"] == 300
        assert by_time["2024-01-01T11:00:00"] == 200

    def test_result_is_sorted_by_time(self):
        series1 = [
            {"time": "2024-01-01T12:00:00", "power": 100},
            {"time": "2024-01-01T10:00:00", "power": 200},
        ]
        result = _merge_power_series([series1])
        times = [p["time"] for p in result]
        assert times == sorted(times)

    def test_empty_series_in_list(self):
        series1 = [{"time": "2024-01-01T10:00:00", "power": 150}]
        result = _merge_power_series([series1, []])
        assert result == [{"time": "2024-01-01T10:00:00", "power": 150}]

    def test_missing_power_key_treated_as_zero(self):
        series = [{"time": "2024-01-01T10:00:00"}]
        result = _merge_power_series([series])
        assert result == [{"time": "2024-01-01T10:00:00", "power": 0}]


@pytest.mark.unit
class TestMergeEnergySeries:
    def test_empty_input(self):
        result = _merge_energy_series([])
        assert result == []

    def test_single_series(self):
        series = [{"label": "10:00", "energy_kwh": 1.5}]
        result = _merge_energy_series([series])
        assert result == [{"label": "10:00", "energy_kwh": 1.5}]

    def test_two_series_matching_labels(self):
        series1 = [{"label": "10:00", "energy_kwh": 1.0}, {"label": "11:00", "energy_kwh": 2.0}]
        series2 = [{"label": "10:00", "energy_kwh": 0.5}, {"label": "11:00", "energy_kwh": 1.5}]
        result = _merge_energy_series([series1, series2])
        assert len(result) == 2
        by_label = {p["label"]: p["energy_kwh"] for p in result}
        assert by_label["10:00"] == 1.5
        assert by_label["11:00"] == 3.5

    def test_rounding_to_two_decimals(self):
        series1 = [{"label": "10:00", "energy_kwh": 1.005}]
        series2 = [{"label": "10:00", "energy_kwh": 1.005}]
        result = _merge_energy_series([series1, series2])
        assert result[0]["energy_kwh"] == round(1.005 + 1.005, 2)

    def test_disjoint_labels(self):
        series1 = [{"label": "01.01.", "energy_kwh": 3.0}]
        series2 = [{"label": "02.01.", "energy_kwh": 2.0}]
        result = _merge_energy_series([series1, series2])
        assert len(result) == 2

    def test_empty_series_in_list(self):
        series1 = [{"label": "10:00", "energy_kwh": 2.0}]
        result = _merge_energy_series([series1, []])
        assert result == [{"label": "10:00", "energy_kwh": 2.0}]


@pytest.mark.unit
class TestFormatDailyEnergy:
    def test_basic_conversion(self):
        raw = [{"date": "2024-01-15", "energy_kwh": 3.456}]
        result = _format_daily_energy(raw)
        assert result == [{"label": "15.01.", "energy_kwh": 3.46}]

    def test_multiple_entries(self):
        raw = [
            {"date": "2024-01-01", "energy_kwh": 1.0},
            {"date": "2024-12-31", "energy_kwh": 2.0},
        ]
        result = _format_daily_energy(raw)
        assert result[0]["label"] == "01.01."
        assert result[1]["label"] == "31.12."

    def test_rounding_to_two_decimals(self):
        raw = [{"date": "2024-06-15", "energy_kwh": 1.2345}]
        result = _format_daily_energy(raw)
        assert result[0]["energy_kwh"] == 1.23

    def test_empty_input(self):
        result = _format_daily_energy([])
        assert result == []
