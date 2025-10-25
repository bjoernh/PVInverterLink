# solar_backend/constants.py

# HTTP Status descriptions
UNAUTHORIZED_MESSAGE = "Session expired or authentication required."
INVERTER_NOT_FOUND_MESSAGE = "Inverter not found."
UNAUTHORIZED_INVERTER_ACCESS_MESSAGE = "User does not have access to this inverter."
SERIAL_NUMBER_EXISTS_MESSAGE = "Serial number already exists."
EMAIL_VERIFICATION_REQUIRED_MESSAGE = "Please verify your email address first."

# Rate limits
DEFAULT_RATE_LIMIT = "10/minute"
