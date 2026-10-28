"""Shared pieces for the Bluesky client and its mixins (kept free of SDK-client imports)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel

type SortOrder = Literal["top", "latest"]


class BlueskyError(Exception):
    """An error safe to show to the caller. Messages never contain credentials."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SearchFilters(BaseModel):
    """Optional search_posts filters (spec 002 FR-001)."""

    since: str | None = None
    until: str | None = None
    lang: str | None = None
    mentions: str | None = None
    tags: list[str] | None = None
    domain: str | None = None
    url: str | None = None


class ClientCore:
    """Methods SafeBlueskyClient provides to its mixins. Each is overridden there."""

    __slots__ = ()

    async def _call(self, fn: Callable[[Any], Awaitable[Any]]) -> Any:
        raise NotImplementedError

    async def _own_did(self) -> str:
        raise NotImplementedError

    async def _resolve_did(self, actor: str) -> str:
        raise NotImplementedError

    async def _get_post(self, post: str) -> Any:
        raise NotImplementedError

    async def _create(self, collection: str, record: Any) -> str:
        raise NotImplementedError

    async def _delete_own(self, collection: str, record_uri: str) -> None:
        raise NotImplementedError
