"""Guarded deletion of the user's own posts (User Story 4)."""

from __future__ import annotations

from fastmcp import FastMCP

from bsky_mcp import instructions
from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.tools import DESTRUCTIVE, ApiProvider, Confirm, PostId, require_confirmation, run


def register(mcp: FastMCP, api: ApiProvider) -> None:
    @mcp.tool(description=instructions.DELETE_POST_DESCRIPTION, annotations=DESTRUCTIVE)
    async def delete_post(post: PostId, confirm: Confirm = None) -> fmt.DeletedPost:
        require_confirmation(confirm, "post")
        return await run(api().delete_own_post(post))
