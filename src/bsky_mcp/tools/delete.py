"""Guarded deletion of the user's own posts (User Story 4)."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from bsky_mcp import instructions
from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.tools import ApiProvider, PostId, run

CONFIRM_WORD = "delete"
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True}


def register(mcp: FastMCP, api: ApiProvider) -> None:
    @mcp.tool(description=instructions.DELETE_POST_DESCRIPTION, annotations=DESTRUCTIVE)
    async def delete_post(
        post: PostId,
        confirm: Annotated[
            str | None,
            Field(description='Must be exactly "delete", given only after the user asked.'),
        ] = None,
    ) -> fmt.DeletedPost:
        if confirm != CONFIRM_WORD:
            raise ToolError(
                'confirmation_required: pass confirm="delete" only after the user explicitly '
                "asked, in their own message, to delete this post."
            )
        return await run(api().delete_own_post(post))
