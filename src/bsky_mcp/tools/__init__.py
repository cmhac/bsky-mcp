"""MCP tool registration and shared error handling."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastmcp.exceptions import ToolError
from pydantic import Field

from bsky_mcp.bluesky.client import BlueskyAPI, BlueskyError
from bsky_mcp.bluesky.operations import ForbiddenOperationError
from bsky_mcp.bluesky.text import InvalidInputError, TooLongError
from bsky_mcp.logging import get_logger

_logger = get_logger("tools")

ApiProvider = Callable[[], BlueskyAPI]

Limit = Annotated[int, Field(ge=1, le=100, description="Number of results, 1-100.")]
Cursor = Annotated[str | None, Field(description="Paging cursor from a previous result.")]
PostId = Annotated[
    str, Field(description="A bsky.app post URL or an at:// URI of an app.bsky.feed.post record.")
]
Actor = Annotated[str, Field(description="A Bluesky handle (with or without @) or a DID.")]

READ_ONLY = {"readOnlyHint": True, "openWorldHint": True}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True}
CONFIRM_WORD = "delete"
Confirm = Annotated[
    str | None,
    Field(description='Must be exactly "delete", given only after the user asked.'),
]


def require_confirmation(confirm: str | None, what: str) -> None:
    """Guarded deletions (Principle II) refuse to run without the exact confirmation word."""
    if confirm != CONFIRM_WORD:
        raise ToolError(
            f'confirmation_required: pass confirm="delete" only after the user explicitly '
            f"asked, in their own message, to delete this {what}."
        )


async def run[T](call: Awaitable[T]) -> T:
    """Await a Bluesky call and turn expected failures into tool errors with a stable code."""
    try:
        return await call
    except BlueskyError as exc:
        raise ToolError(f"{exc.code}: {exc.message}") from None
    except (InvalidInputError, TooLongError) as exc:
        raise ToolError(f"{exc.code}: {exc}") from None
    except ForbiddenOperationError as exc:
        raise ToolError(f"{exc.code}: {exc}") from None
    except Exception as exc:
        _logger.exception("unexpected error in tool call")
        raise ToolError(f"internal_error: {type(exc).__name__}") from None
