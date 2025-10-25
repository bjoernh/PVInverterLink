class DomainException(Exception):
    """Base exception for domain errors."""
    pass

class InverterNotFoundException(DomainException):
    """Inverter not found."""
    pass

class UnauthorizedInverterAccessException(DomainException):
    """User doesn't have access to inverter."""
    pass
