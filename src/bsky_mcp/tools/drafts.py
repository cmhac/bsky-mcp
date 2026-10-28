"""Draft tools (User Story 2). The server has no way to publish."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from bsky_mcp import instructions
from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.bluesky.client import DraftPostInput
from bsky_mcp.tools import READ_ONLY, ApiProvider, Cursor, Limit, run

DRAFT_WRITE = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}

Posts = Annotated[
    list[DraftPostInput],
    Field(min_length=1, max_length=100, description="One post, or several to make a thread."),
]
Langs = Annotated[
    list[str] | None,
    Field(max_length=3, description="Optional language codes, at most 3, e.g. ['en']."),
]


def register(mcp: FastMCP, api: ApiProvider) -> None:
    @mcp.tool(description=instructions.CREATE_DRAFT_DESCRIPTION, annotations=DRAFT_WRITE)
    async def create_draft(posts: Posts, langs: Langs = None) -> fmt.DraftView:
        return await run(api().create_draft(posts, langs))

    @mcp.tool(description=instructions.UPDATE_DRAFT_DESCRIPTION, annotations=DRAFT_WRITE)
    async def update_draft(
        draft_id: Annotated[str, Field(min_length=1, description="ID from create_draft.")],
        posts: Posts,
        langs: Langs = None,
    ) -> fmt.DraftView:
        return await run(api().update_draft(draft_id, posts, langs))

    @mcp.tool(annotations=READ_ONLY)
    async def list_drafts(limit: Limit = 25, cursor: Cursor = None) -> fmt.DraftPage:
        """List drafts saved in the user's Bluesky Drafts."""
        return await run(api().list_drafts(limit, cursor))
