"""
Structured logging utility for the monitoring system.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from backend.utils.config import get_settings


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for CloudWatch compatibility."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Include extra fields if present
        for key in ("service_id", "incident_id", "action"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry, default=str)


def get_logger(name: str) -> logging.Logger:
    """Creates a logger with JSON formatting."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        settings = get_settings()
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger
