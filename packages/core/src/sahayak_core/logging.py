import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json: bool = False) -> None:
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,  # pulls call_id etc. into every line
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if json:
        tail: list[structlog.types.Processor] = [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        tail = [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=[*shared, *tail],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
