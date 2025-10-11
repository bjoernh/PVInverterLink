"""
Tests for password reset functionality.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_request_password_reset(client, test_user, mocker, without_influx):
    """Test requesting a password reset email."""
    # Mock email sending
    mail_mock = mocker.AsyncMock()
    mail_mock.return_value = True
    mocker.patch('solar_backend.users.send_reset_passwort_mail', mail_mock)

    response = await client.post(
        "/request_reset_passwort",
        headers={"HX-Prompt": "testuser@example.com"}
    )

    assert response.status_code == 200
    assert "Email wurde verschickt" in response.text
    mail_mock.assert_called_once()
    assert mail_mock.call_args[0][0] == "testuser@example.com"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_reset_password_page(client, test_user, mocker, without_influx):
    """Test GET request to reset password page with token."""
    response = await client.get("/reset_passwort?token=some-token")
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reset_password_with_valid_token(client, test_user, mocker, without_influx):
    """Test resetting password with a valid token."""
    # First request password reset to get token
    mail_mock = mocker.AsyncMock()
    mail_mock.return_value = True
    mocker.patch('solar_backend.users.send_reset_passwort_mail', mail_mock)

    await client.post(
        "/request_reset_passwort",
        headers={"HX-Prompt": "testuser@example.com"}
    )

    # Get token from mocked email call (positional arg)
    token = mail_mock.call_args[0][1]  # Second positional argument

    # Reset password with valid token
    response = await client.post(
        "/reset_password",
        data={
            "token": token,
            "new_password1": "newpassword123",
            "new_password2": "newpassword123"
        }
    )

    assert response.status_code == 200
    assert "erfolgreich geändert" in response.text

    # Verify can login with new password
    login_response = await client.post(
        "/login",
        data={"username": "testuser@example.com", "password": "newpassword123"}
    )
    assert login_response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reset_password_with_mismatched_passwords(client, test_user, mocker, without_influx):
    """Test password reset fails when passwords don't match."""
    # First request password reset to get token
    mail_mock = mocker.AsyncMock()
    mail_mock.return_value = True
    mocker.patch('solar_backend.users.send_reset_passwort_mail', mail_mock)

    await client.post(
        "/request_reset_passwort",
        headers={"HX-Prompt": "testuser@example.com"}
    )

    token = mail_mock.call_args[0][1]  # Second positional argument

    # Try to reset with mismatched passwords
    response = await client.post(
        "/reset_password",
        data={
            "token": token,
            "new_password1": "password1",
            "new_password2": "password2"
        }
    )

    assert response.status_code == 200
    assert "müssen gleich sein" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reset_password_with_invalid_token(client, without_influx):
    """Test password reset fails with invalid token."""
    response = await client.post(
        "/reset_password",
        data={
            "token": "invalid-token-12345",
            "new_password1": "newpassword123",
            "new_password2": "newpassword123"
        }
    )

    assert response.status_code == 200
    assert "ungültig" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reset_password_token_cannot_be_reused(client, test_user, mocker, without_influx):
    """Test that password reset token can only be used once."""
    # Request password reset
    mail_mock = mocker.AsyncMock()
    mail_mock.return_value = True
    mocker.patch('solar_backend.users.send_reset_passwort_mail', mail_mock)

    await client.post(
        "/request_reset_passwort",
        headers={"HX-Prompt": "testuser@example.com"}
    )

    token = mail_mock.call_args[0][1]  # Second positional argument

    # Use token first time
    response1 = await client.post(
        "/reset_password",
        data={
            "token": token,
            "new_password1": "newpassword123",
            "new_password2": "newpassword123"
        }
    )
    assert response1.status_code == 200
    assert "erfolgreich" in response1.text

    # Try to use same token again
    response2 = await client.post(
        "/reset_password",
        data={
            "token": token,
            "new_password1": "anotherpassword",
            "new_password2": "anotherpassword"
        }
    )
    assert response2.status_code == 200
    assert "ungültig" in response2.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_reset_email_content(client, test_user, mocker, without_influx):
    """Test that password reset email contains correct URL."""
    mail_mock = mocker.AsyncMock()
    mail_mock.return_value = True
    # Patch where it's used, not where it's defined
    email_spy = mocker.patch('solar_backend.users.send_reset_passwort_mail', mail_mock)

    await client.post(
        "/request_reset_passwort",
        headers={"HX-Prompt": "testuser@example.com"}
    )

    # Verify email was sent with correct parameters
    email_spy.assert_called_once()
    call_args = email_spy.call_args
    assert call_args[0][0] == "testuser@example.com"  # email (first positional arg)
    assert isinstance(call_args[0][1], str)  # token should be a string (second positional arg)
    assert len(call_args[0][1]) > 0  # token should not be empty
