"""Secret redaction (T009, T053)."""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator

import pytest

from bsky_mcp.config import load_settings
from bsky_mcp.logging import REDACTED, configure_logging, get_logger
from tests.conftest import valid_env


@pytest.fixture
def captured(env: pytest.MonkeyPatch) -> Iterator[io.StringIO]:
    env.setenv("BLUESKY_HANDLE", "me.bsky.social")
    env.setenv("BLUESKY_APP_PASSWORD", "abcd-efgh-ijkl-mnop")
    stream = io.StringIO()
    configure_logging(load_settings(), stream=stream)
    yield stream
    logging.getLogger().handlers.clear()


SECRETS = [
    "abcd-efgh-ijkl-mnop",
    valid_env()["GITHUB_CLIENT_SECRET"],
    valid_env()["JWT_SIGNING_KEY"],
    valid_env()["STORAGE_ENCRYPTION_KEY"],
    valid_env()["REDIS_URL"],
]


@pytest.mark.parametrize("secret", SECRETS)
def test_secret_in_message_is_redacted(captured: io.StringIO, secret: str) -> None:
    get_logger("test").warning("value is %s", secret)
    out = captured.getvalue()
    assert secret not in out
    assert REDACTED in out


def test_secret_in_exception_is_redacted(captured: io.StringIO) -> None:
    try:
        raise RuntimeError(f"connect failed for {valid_env()['REDIS_URL']}")
    except RuntimeError:
        get_logger("test").exception("boom")
    assert valid_env()["REDIS_URL"] not in captured.getvalue()


def test_library_loggers_are_redacted(captured: io.StringIO) -> None:
    logging.getLogger("httpx").warning("auth %s", "abcd-efgh-ijkl-mnop")
    assert "abcd-efgh-ijkl-mnop" not in captured.getvalue()
