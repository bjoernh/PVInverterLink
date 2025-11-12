"""
Constants and Enums used throughout the solar_backend application.
"""

# --- HTTP Status Messages ---
UNAUTHORIZED_MESSAGE = "Session expired or authentication required."
FORBIDDEN_MESSAGE = "You do not have permission to access this resource."
NOT_FOUND_MESSAGE = "The requested resource was not found."
BAD_REQUEST_MESSAGE = "Invalid request data provided."
INTERNAL_SERVER_ERROR_MESSAGE = "An unexpected error occurred."

# --- Database Field Sizes ---
MAX_NAME_LENGTH = 255
MAX_SERIAL_LENGTH = 64
MAX_EMAIL_LENGTH = 255
MAX_PASSWORD_HASH_LENGTH = 255  # For bcrypt hashes

# --- Rate Limiting ---
DEFAULT_RATE_LIMIT = "10/minute"
LOGIN_RATE_LIMIT = "5/minute"
SIGNUP_RATE_LIMIT = "5/minute"
PASSWORD_RESET_RATE_LIMIT = "3/hour"

# --- Time Series ---
# Time ranges are often handled by enums or specific logic, but common intervals can be here
# e.g., BUCKET_INTERVAL_HOUR = "1 hour"

# --- API Keys ---
API_KEY_PREFIX = "sk-"
API_KEY_LENGTH = 32  # Excluding prefix

# --- Other ---
# Add any other magic strings or numbers found during refactoring
