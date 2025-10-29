import structlog
from structlog.processors import JSONRenderer, TimeStamper, format_exc_info, StackInfoRenderer, CallsiteParameterAdder, CallsiteParameter
from structlog.dev import ConsoleRenderer
from structlog.stdlib import add_logger_name, add_log_level, PositionalArgumentsFormatter
from logging import INFO, DEBUG, WARNING, ERROR, CRITICAL
import logging

from solar_backend.config import settings

def configure_logging():
    """Configures structlog for consistent logging across the application."""

    # Map LOG_LEVEL string to logging level
    log_level_map = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
    }
    current_log_level = log_level_map.get(settings.LOG_LEVEL, INFO)

    shared_processors = [
        add_log_level,
        add_logger_name,
        TimeStamper(fmt="iso"),
        StackInfoRenderer(),
        format_exc_info,
        PositionalArgumentsFormatter(),
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
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=False,
        )
    else:
        # Production configuration: JSON output for log aggregation
        structlog.configure(
            processors=shared_processors + [
                JSONRenderer()
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=False,
        )

    # Configure standard logging
    logging.basicConfig(
        level=current_log_level,
        format="%(message)s",
        handlers=[logging.StreamHandler()]
    )
    logging.getLogger("uvicorn").handlers = [] # Remove default uvicorn handlers
    logging.getLogger("uvicorn.access").handlers = []

    # Set root logger level
    logging.root.setLevel(current_log_level)

    # Suppress some chatty loggers
    logging.getLogger("httpx").setLevel(WARNING)
    logging.getLogger("httpcore").setLevel(WARNING)
    logging.getLogger("sqlalchemy").setLevel(WARNING)
    logging.getLogger("alembic").setLevel(WARNING)
