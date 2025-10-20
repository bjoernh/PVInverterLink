"""Utilities for generating and managing API keys."""

import secrets
import string


def generate_api_key(length: int = 16) -> str:
    """
    Generate a human-friendly API key.

    Args:
        length: Total length of the key (default 16)

    Returns:
        A human-friendly API key in format: xxxx-xxxx-xxxx-xxxx
    """
    # Use alphanumeric characters (no confusing chars like 0/O, 1/l, etc.)
    alphabet = string.ascii_uppercase + string.digits
    # Remove confusing characters
    alphabet = alphabet.replace("0", "").replace("O", "").replace("1", "").replace("I", "").replace("L", "")

    # Generate random key
    key = "".join(secrets.choice(alphabet) for _ in range(length))

    # Format with hyphens for readability: xxxx-xxxx-xxxx-xxxx
    parts = [key[i:i+4] for i in range(0, len(key), 4)]
    return "-".join(parts)
