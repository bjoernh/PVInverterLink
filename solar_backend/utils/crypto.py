import structlog
from cryptography.fernet import Fernet, InvalidToken

logger = structlog.get_logger()


class CryptoManager:
    """
    A manager for encrypting and decrypting data using Fernet symmetric encryption.
    """

    def __init__(self, key: str):
        """
        Initializes the CryptoManager with a Fernet key.

        Args:
            key: A URL-safe base64-encoded 32-byte key.
        """
        if not key:
            raise ValueError("An encryption key must be provided.")
        self.fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypts a plaintext string.

        Args:
            plaintext: The string to encrypt.

        Returns:
            The encrypted ciphertext as a string.
        """
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str | None:
        """
        Decrypts a ciphertext string.

        Args:
            ciphertext: The string to decrypt.

        Returns:
            The decrypted plaintext string, or None if decryption fails.
        """
        try:
            logger.debug("Attempting to decrypt ciphertext.")
            decrypted = self.fernet.decrypt(ciphertext.encode()).decode()
            logger.debug("Decryption successful.")
            return decrypted
        except InvalidToken:
            logger.error("Decryption failed: Invalid token.")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during decryption: {e}", exc_info=True)
            return None
