#!/usr/bin/env python3
"""
CLI tool for resetting user passwords.

Usage:
    ENV_FILE=solar_backend/backend.local.env uv run python reset_password.py user@example.com [new_password]

If no password is provided, a random password will be generated.
"""

import asyncio
import sys
import secrets
import string
from sqlalchemy import select, update
from solar_backend.db import sessionmanager, User
from solar_backend.config import settings
from fastapi_users.password import PasswordHelper


def generate_password(length: int = 16) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # Ensure at least one uppercase, one digit, and one special char
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    # Fill the rest randomly
    password += [secrets.choice(alphabet) for _ in range(length - 3)]
    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


async def reset_user_password(email: str, new_password: str | None = None):
    """Reset password for a user by email."""
    print(f"=== Password Reset Tool ===\n")

    # Initialize password helper (same as UserManager uses)
    password_helper = PasswordHelper()

    # Generate password if none provided
    if new_password is None:
        new_password = generate_password()
        print(f"Generated random password: {new_password}\n")
    else:
        print("Using provided password\n")

    # Initialize database connection
    sessionmanager.init(settings.DATABASE_URL)

    try:
        async with sessionmanager.session() as session:
            # Find user by email
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user:
                print(f"❌ Error: User with email '{email}' not found.")
                return False

            print(f"✓ Found user: {user.first_name} {user.last_name} (ID: {user.id})")

            # Hash the new password
            hashed_password = password_helper.hash(new_password)

            # Update user's password
            await session.execute(
                update(User)
                .where(User.id == user.id)
                .values(hashed_password=hashed_password)
            )
            await session.commit()

            print(f"✓ Password reset successful!")
            print(f"\nNew credentials:")
            print(f"  Email: {email}")
            print(f"  Password: {new_password}")
            print(f"\n⚠ Make sure to save this password - it won't be shown again!")

            return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        await sessionmanager.close()


def print_usage():
    """Print usage instructions."""
    print("Usage:")
    print("  ENV_FILE=solar_backend/backend.local.env uv run python reset_password.py user@example.com [new_password]")
    print("\nExamples:")
    print("  # Generate random password:")
    print("  ENV_FILE=solar_backend/backend.local.env uv run python reset_password.py john@example.com")
    print("\n  # Set specific password:")
    print("  ENV_FILE=solar_backend/backend.local.env uv run python reset_password.py john@example.com 'MyNewPass123!'")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Error: Email address is required.\n")
        print_usage()
        sys.exit(1)

    email = sys.argv[1]
    new_password = sys.argv[2] if len(sys.argv) > 2 else None

    success = asyncio.run(reset_user_password(email, new_password))
    sys.exit(0 if success else 1)
