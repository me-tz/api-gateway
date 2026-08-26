"""structlog configuration."""
from __future__ import annotations

import logging
import sys

import structlog

from gateway.config.settings import settings


def configure_logging() -> None:
    """Configure structlog and stdlib logging based on settings.
    Discrete events, human/machine readable. 'Request X hit route Y and returned 502.'"""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.log_level)
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
    )