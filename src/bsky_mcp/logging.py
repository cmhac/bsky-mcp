"""Logging with secret redaction.

Every configured secret value is replaced with ``[REDACTED]`` in formatted log records, including
exception text, before anything is written.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterable

from bsky_mcp.config import SECRET_FIELDS, Settings

REDACTED = "[REDACTED]"
LOGGER_NAME = "bsky_mcp"


def secret_values(settings: Settings) -> list[str]:
    values: list[str] = []
    for name in SECRET_FIELDS:
        secret = getattr(settings, name, None)
        if secret is not None:
            value = secret.get_secret_value()
            if value:
                values.append(value)
    return values


def redact(text: str, secrets: Iterable[str]) -> str:
    # Longest first so a secret that contains another is fully removed.
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            text = text.replace(secret, REDACTED)
    return text


class RedactingFormatter(logging.Formatter):
    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")
        self._secrets = list(secrets)

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record), self._secrets)


def configure_logging(settings: Settings, stream=None) -> logging.Logger:
    """Attach a redacting handler to the root logger so library logs are covered too."""
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(RedactingFormatter(secret_values(settings)))
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    return logging.getLogger(LOGGER_NAME)


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)
