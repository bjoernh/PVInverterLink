"""
Unit tests for timeseries utilities.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solar_backend.utils.timeseries import reset_rls_context, rls_context, set_rls_context


@pytest.mark.unit
@pytest.mark.asyncio
@patch("solar_backend.utils.timeseries.reset_rls_context", new_callable=AsyncMock)
@patch("solar_backend.utils.timeseries.set_rls_context", new_callable=AsyncMock)
async def test_rls_context_sets_and_resets(mock_set, mock_reset):
    """Test that rls_context calls set and reset functions correctly."""
    # Arrange
    mock_session = AsyncMock()
    user_id = 123

    # Act
    async with rls_context(mock_session, user_id):
        # Assert that set_rls_context was called inside the context
        mock_set.assert_called_once_with(mock_session, user_id)
        # Assert that reset_rls_context has not been called yet
        mock_reset.assert_not_called()

    # Assert that reset_rls_context was called upon exiting the context
    mock_reset.assert_called_once_with(mock_session)


@pytest.mark.unit
@pytest.mark.asyncio
@patch("solar_backend.utils.timeseries.reset_rls_context", new_callable=AsyncMock)
@patch("solar_backend.utils.timeseries.set_rls_context", new_callable=AsyncMock)
async def test_rls_context_resets_on_exception(mock_set, mock_reset):
    """Test that rls_context calls reset even if an exception occurs."""
    # Arrange
    mock_session = AsyncMock()
    user_id = 123

    # Act & Assert
    with pytest.raises(ValueError, match="Test exception"):
        async with rls_context(mock_session, user_id):
            # Assert that set_rls_context was called
            mock_set.assert_called_once_with(mock_session, user_id)
            raise ValueError("Test exception")

    # Assert that reset_rls_context was still called upon exiting the context
    mock_reset.assert_called_once_with(mock_session)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_rls_context_skips_for_sqlite():
    """Test that set_rls_context is skipped for SQLite connections."""
    # Arrange
    mock_session = MagicMock()
    # Mock the session bind URL to simulate a SQLite connection
    mock_session.bind.url = "sqlite:///test.db"
    mock_session.execute = AsyncMock()
    user_id = 456

    # Act
    await set_rls_context(mock_session, user_id)

    # Assert
    # The execute method should not be called for SQLite
    mock_session.execute.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reset_rls_context_skips_for_sqlite():
    """Test that reset_rls_context is skipped for SQLite connections."""
    # Arrange
    mock_session = MagicMock()
    mock_session.bind.url = "sqlite:///test.db"
    mock_session.execute = AsyncMock()

    # Act
    await reset_rls_context(mock_session)

    # Assert
    # The execute method should not be called for SQLite
    mock_session.execute.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_rls_context_executes_for_postgres():
    """Test that set_rls_context executes SQL for non-SQLite connections."""
    # Arrange
    mock_session = MagicMock()
    # Mock the session bind URL to simulate a PostgreSQL connection
    mock_session.bind.url = "postgresql://user:pass@host/db"
    mock_session.execute = AsyncMock()
    user_id = 789

    # Act
    await set_rls_context(mock_session, user_id)

    # Assert
    # The execute method should be called with the correct SQL
    mock_session.execute.assert_called_once()
    called_sql = mock_session.execute.call_args[0][0].text
    assert f"SET app.current_user_id = {user_id}" in called_sql
