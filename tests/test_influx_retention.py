"""
Tests for InfluxDB bucket retention policy implementation.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from solar_backend.utils.influx import InfluxManagement


def test_create_bucket_with_default_retention():
    """Test that create_bucket applies 2-year retention policy by default."""
    influx = InfluxManagement("http://localhost:8086")

    # Mock the client and bucket API
    mock_client = Mock()
    mock_bucket_api = Mock()
    mock_bucket = Mock()
    mock_bucket.name = "test-bucket"

    mock_bucket_api.create_bucket.return_value = mock_bucket
    mock_client.buckets_api.return_value = mock_bucket_api

    influx._client = mock_client

    # Call create_bucket (should use default 2-year retention)
    result = influx.create_bucket("test-bucket", "test-org-id")

    # Verify create_bucket was called with retention rules
    mock_bucket_api.create_bucket.assert_called_once()
    call_args = mock_bucket_api.create_bucket.call_args

    assert call_args[1]["bucket_name"] == "test-bucket"
    assert call_args[1]["org_id"] == "test-org-id"
    assert "retention_rules" in call_args[1]
    assert call_args[1]["retention_rules"] == [{"type": "expire", "everySeconds": 63072000}]
    assert result == mock_bucket


def test_create_bucket_with_custom_retention():
    """Test that create_bucket accepts custom retention period."""
    influx = InfluxManagement("http://localhost:8086")

    # Mock the client and bucket API
    mock_client = Mock()
    mock_bucket_api = Mock()
    mock_bucket = Mock()
    mock_bucket.name = "test-bucket"

    mock_bucket_api.create_bucket.return_value = mock_bucket
    mock_client.buckets_api.return_value = mock_bucket_api

    influx._client = mock_client

    # Call create_bucket with custom 1-year retention
    one_year_seconds = 31536000  # 365 days
    result = influx.create_bucket("test-bucket", "test-org-id", retention_seconds=one_year_seconds)

    # Verify create_bucket was called with custom retention
    mock_bucket_api.create_bucket.assert_called_once()
    call_args = mock_bucket_api.create_bucket.call_args

    assert call_args[1]["retention_rules"] == [{"type": "expire", "everySeconds": one_year_seconds}]


def test_update_bucket_retention_success():
    """Test updating retention policy for existing bucket."""
    influx = InfluxManagement("http://localhost:8086")

    # Mock the client and bucket API
    mock_client = Mock()
    mock_bucket_api = Mock()
    mock_bucket = Mock()
    mock_bucket.id = "test-bucket-id"
    mock_bucket.name = "test-bucket"
    mock_bucket.retention_rules = []

    mock_bucket_api.find_bucket_by_id.return_value = mock_bucket
    mock_client.buckets_api.return_value = mock_bucket_api

    influx._client = mock_client

    # Call update_bucket_retention
    influx.update_bucket_retention("test-bucket-id", retention_seconds=63072000)

    # Verify bucket was found and updated
    mock_bucket_api.find_bucket_by_id.assert_called_once_with("test-bucket-id")
    mock_bucket_api.update_bucket.assert_called_once_with(mock_bucket)
    assert mock_bucket.retention_rules == [{"type": "expire", "everySeconds": 63072000}]


def test_update_bucket_retention_not_found():
    """Test updating retention policy when bucket doesn't exist."""
    influx = InfluxManagement("http://localhost:8086")

    # Mock the client and bucket API
    mock_client = Mock()
    mock_bucket_api = Mock()
    mock_bucket_api.find_bucket_by_id.return_value = None  # Bucket not found
    mock_client.buckets_api.return_value = mock_bucket_api

    influx._client = mock_client

    # Call update_bucket_retention should raise ValueError
    with pytest.raises(ValueError, match="Bucket test-bucket-id not found"):
        influx.update_bucket_retention("test-bucket-id")

    # Verify update_bucket was never called
    mock_bucket_api.update_bucket.assert_not_called()


def test_retention_period_calculation():
    """Test that 2 years equals 63,072,000 seconds."""
    # 2 years = 730 days * 24 * 60 * 60
    expected_seconds = 730 * 24 * 60 * 60
    assert expected_seconds == 63072000

    # Verify this equals 730 days (2 years)
    days = expected_seconds / 86400
    assert days == 730.0
