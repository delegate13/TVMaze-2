"""Structured JSON logging configuration."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STANDARD_LOG_RECORD_FIELDS = frozenset(
    logging.LogRecord(
        name="",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__
)


class JsonLogFormatter(logging.Formatter):
    """Format each log record as one structured JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize timestamp, level, message, and contextual fields."""
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in STANDARD_LOG_RECORD_FIELDS and not key.startswith("_")
            }
        )
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(
    log_path: Path, level: str = "INFO"
) -> logging.Logger:
    """Configure the application logger with a JSON file handler."""
    logger = logging.getLogger("tvmaze_show_finder")
    logger.setLevel(level)
    logger.propagate = False

    resolved_path = log_path.resolve()
    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename).resolve() == resolved_path
        for handler in logger.handlers
    ):
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(resolved_path, encoding="utf-8")
        file_handler.setFormatter(JsonLogFormatter())
        logger.addHandler(file_handler)

    for handler in logger.handlers:
        handler.setLevel(level)
    return logger
