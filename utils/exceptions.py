"""Application-specific exceptions exposed to the presentation layer."""


class ApplicationError(Exception):
    """Base class for expected, user-displayable application failures."""


class ConfigurationError(ApplicationError):
    """Raised when configuration is missing or invalid."""


class ApiError(ApplicationError):
    """Raised when an API request or response cannot be handled."""


class ValidationError(ApplicationError):
    """Raised when user input or external data violates a contract."""
