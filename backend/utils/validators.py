"""
Input validation and sanitization utilities.
"""

import re
import uuid
from urllib.parse import urlparse
from typing import Optional
from datetime import datetime, timezone


def validate_url(url: str) -> bool:
    """Validates that a URL is well-formed and uses HTTP/HTTPS."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def validate_service_name(name: str) -> bool:
    """Validates service name: 1-100 chars, alphanumeric with spaces/hyphens/underscores."""
    if not name or len(name) > 100:
        return False
    return bool(re.match(r"^[a-zA-Z0-9\s\-_]+$", name))


def validate_http_method(method: str) -> bool:
    """Validates HTTP method."""
    return method.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS")


def validate_status_code(code: int) -> bool:
    """Validates HTTP status code range."""
    return 100 <= code <= 599


def validate_check_interval(interval: int) -> bool:
    """Validates check interval in seconds (min 10s, max 1 hour)."""
    return 10 <= interval <= 3600


def sanitize_log_content(content: str, max_length: int = 2000) -> str:
    """
    Sanitizes log content before sending to external AI services.
    Removes potential secrets, truncates to max_length.
    """
    if not content:
        return ""

    secret_patterns = [
        r"(?i)(api[_-]?key|secret|password|token|authorization|bearer)\s*[:=]\s*\S+",
        r"(?i)AWS[A-Z_]*\s*[:=]\s*\S+",
        r"(?i)(access[_-]?key|secret[_-]?key)\s*[:=]\s*\S+",
        r"\b[A-Z0-9]{20,}\b",
    ]

    sanitized = content
    for pattern in secret_patterns:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized)

    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... [TRUNCATED]"

    return sanitized


def sanitize_input(value: str, max_length: int = 500) -> str:
    """Sanitizes general user input."""
    if not value:
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return cleaned[:max_length].strip()


def generate_service_id(name: str = "svc") -> str:
    """Generates a clean service ID slug."""
    clean_name = re.sub(r"[^a-zA-Z0-9]", "-", name.lower()).strip("-")
    clean_name = clean_name[:20] or "svc"
    short_uuid = uuid.uuid4().hex[:6]
    return f"{clean_name}-{short_uuid}"


def generate_incident_id() -> str:
    """Generates a human-readable incident ID."""
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"INC-{now.strftime('%Y%m%d')}-{short_uuid}"


def generate_analysis_id() -> str:
    """Generates an AI analysis record ID."""
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:6].lower()
    return f"ai-{now.strftime('%Y%m%d%H%M%S')}-{short_uuid}"
