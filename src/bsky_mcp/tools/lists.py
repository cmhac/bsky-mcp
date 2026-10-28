"""List management tools (spec 002, User Story 8). Curation lists in the user's repo only."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from bsky_mcp import instructions
from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.tools import DESTRUCTIVE, Actor, ApiProvider, Confirm, require_confirmation, run
from bsky_mcp.tools.discovery import ListId

LIST_WRITE = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}
REVERSIBLE = LIST_WRITE | {"idempotentHint": True}


def register(mcp: FastMCP, api: ApiProvider) -> None:
    @mcp.tool(annotations=LIST_WRITE)
    async def create_list(
        name: Annotated[str, Field(min_length=1, max_length=64, description="List name.")],
        description: Annotated[
            str | None, Field(max_length=3000, description="Optional description.")
        ] = None,
    ) -> fmt.ListInfo:
        """Create a curation list in the user's account. Mute and block lists are not possible."""
        return await run(api().create_list(name, description))

    @mcp.tool(annotations=REVERSIBLE)
    async def add_to_list(
        list: ListId,  # noqa: A002
        actors: Annotated[
            list[str],
            Field(min_length=1, max_length=25, description="1-25 handles or DIDs to add."),
        ],
    ) -> fmt.ListMembershipResults:
        """Add accounts to one of the user's lists. Accounts already on it are left as they are."""
        return await run(api().add_to_list(list, actors))

    @mcp.tool(annotations=REVERSIBLE)
    async def remove_from_list(list: ListId, actor: Actor) -> fmt.EngagementResult:  # noqa: A002
        """Remove an account from one of the user's lists."""
        return await run(api().remove_from_list(list, actor))

    @mcp.tool(description=instructions.DELETE_LIST_DESCRIPTION, annotations=DESTRUCTIVE)
    async def delete_list(list: ListId, confirm: Confirm = None) -> fmt.DeletedList:  # noqa: A002
        require_confirmation(confirm, "list")
        return await run(api().delete_own_list(list))
