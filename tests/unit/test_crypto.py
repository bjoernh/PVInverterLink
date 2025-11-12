import pytest
from cryptography.fernet import Fernet

from solar_backend.utils.crypto import CryptoManager

KEY = Fernet.generate_key().decode()


@pytest.fixture
def crypto_manager() -> CryptoManager:
    return CryptoManager(key=KEY)


@pytest.mark.unit
def test_encrypt_decrypt_success(crypto_manager: CryptoManager):
    """Tests that a string can be successfully encrypted and decrypted."""
    original_text = "my-secret-password-123"
    encrypted_text = crypto_manager.encrypt(original_text)

    assert encrypted_text != original_text

    decrypted_text = crypto_manager.decrypt(encrypted_text)
    assert decrypted_text == original_text


@pytest.mark.unit
def test_decrypt_invalid_token(crypto_manager: CryptoManager):
    """Tests that decryption returns None for an invalid token."""
    invalid_ciphertext = "gAAAAABm_gX2r_...invalid..._8A="
    decrypted_text = crypto_manager.decrypt(invalid_ciphertext)
    assert decrypted_text is None


@pytest.mark.unit
def test_decrypt_tampered_token(crypto_manager: CryptoManager):
    """Tests that decryption fails if the ciphertext is tampered with."""
    original_text = "some data"
    encrypted_text = crypto_manager.encrypt(original_text)

    # Tamper with the token by replacing a character
    tampered_text = list(encrypted_text)
    # Flip a bit in the 11th character
    tampered_text[10] = chr(ord(tampered_text[10]) + 1)
    tampered_text = "".join(tampered_text)

    decrypted_text = crypto_manager.decrypt(tampered_text)
    assert decrypted_text is None


@pytest.mark.unit
def test_init_with_no_key():
    """Tests that CryptoManager raises an error if initialized with no key."""
    with pytest.raises(ValueError, match="An encryption key must be provided."):
        CryptoManager(key="")


@pytest.mark.unit
def test_decryption_with_different_key():
    """Tests that decryption fails when using a different key."""
    original_text = "super secret"

    # Encrypt with the first key
    manager1 = CryptoManager(key=KEY)
    encrypted_text = manager1.encrypt(original_text)

    # Try to decrypt with a different key
    different_key = Fernet.generate_key().decode()
    manager2 = CryptoManager(key=different_key)
    decrypted_text = manager2.decrypt(encrypted_text)

    assert decrypted_text is None
