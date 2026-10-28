"""Tests for structured log output."""

import json
import logging

from utils.logger import JsonLogFormatter, configure_logging


def test_json_formatter_includes_context_fields():
    """Encode contextual LogRecord attributes in a JSON event."""
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "search complete",
        (),
        None,
    )
    record.search_term = "Example"

    result = json.loads(JsonLogFormatter().format(record))

    assert result["level"] == "INFO"
    assert result["message"] == "search complete"
    assert result["search_term"] == "Example"


def test_configure_logging_creates_file_handler(tmp_path):
    """Create the configured log directory and attach a JSON file handler."""
    logger = configure_logging(tmp_path / "logs" / "application.log")

    assert any(isinstance(handler, logging.FileHandler) for handler in logger.handlers)
    assert (tmp_path / "logs").is_dir()
