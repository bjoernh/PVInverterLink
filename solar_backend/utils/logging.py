import structlog
from structlog.processors import JSONRenderer, TimeStamper, format_exc_info, StackInfoRenderer, CallsiteParameterAdder, CallsiteParameter
from structlog.dev import ConsoleRenderer
from logging import INFO, DEBUG, WARNING, ERROR, CRITICAL

from solar_backend.config import settings

def configure_logging():
    """Configures structlog for consistent logging across the application."""

    shared_processors = [
        TimeStamper(fmt="iso"),
        StackInfoRenderer(),
        format_exc_info,
        CallsiteParameterAdder({
            CallsiteParameter.FILENAME,
            CallsiteParameter.LINENO,
            CallsiteParameter.FUNC_NAME,
        }),
    ]

    if settings.DEBUG:
        # Development configuration: human-readable, colored output
        structlog.configure(
            processors=shared_processors + [
                ConsoleRenderer(colors=True)
            ],
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )
    else:
        # Production configuration: JSON output for log aggregation
        structlog.configure(
            processors=shared_processors + [
                JSONRenderer()
            ],
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

    # Configure standard logging to use structlog
    # This ensures that logs from libraries also go through structlog
    import logging
    logging.basicConfig(level=INFO, handlers=[logging.StreamHandler()])
    logging.getLogger("uvicorn").handlers = [] # Remove default uvicorn handlers
    logging.getLogger("uvicorn.access").handlers = []

    # Set log level based on settings
    if settings.LOG_LEVEL == "DEBUG":
        logging.root.setLevel(DEBUG)
    elif settings.LOG_LEVEL == "INFO":
        logging.root.setLevel(INFO)
    elif settings.LOG_LEVEL == "WARNING":
        logging.root.setLevel(WARNING)
    elif settings.LOG_LEVEL == "ERROR":
        logging.root.setLevel(ERROR)
    elif settings.LOG_LEVEL == "CRITICAL":
        logging.root.setLevel(CRITICAL)
    else:
        logging.root.setLevel(INFO)

    # Suppress some chatty loggers
    logging.getLogger("httpx").setLevel(WARNING)
    logging.getLogger("httpcore").setLevel(WARNING)
    logging.getLogger("sqlalchemy").setLevel(WARNING)
    logging.getLogger("alembic").setLevel(WARNING)
