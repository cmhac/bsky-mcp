"""Engagement tools (User Story 3). Every action can be undone; blocking is not offered."""

from __future__ import annotations

from fastmcp import FastMCP

from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.tools import Actor, ActorBatch, ApiProvider, PostId, run

REVERSIBLE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def register(mcp: FastMCP, api: ApiProvider) -> None:
    @mcp.tool(annotations=REVERSIBLE)
    async def follow(actors: ActorBatch) -> fmt.FollowResults:
        """Follow 1-25 accounts in one call. Returns a result for each account, in order:
        followed, already_following (skipped), not_found, is_you, failed, or not_attempted.
        To retry, resend only the failed and not_attempted accounts. If Bluesky rate-limits the
        call, the remaining accounts are not_attempted: wait, then resend them."""
        return await run(api().follow(actors))

    @mcp.tool(annotations=REVERSIBLE)
    async def unfollow(actor: Actor) -> fmt.EngagementResult:
        """Unfollow an account. Reports 'nothing to undo' if the user doesn't follow it."""
        return await run(api().unfollow(actor))

    @mcp.tool(annotations=REVERSIBLE)
    async def like(post: PostId) -> fmt.EngagementResult:
        """Like a post. Does nothing if already liked."""
        return await run(api().like(post))

    @mcp.tool(annotations=REVERSIBLE)
    async def unlike(post: PostId) -> fmt.EngagementResult:
        """Remove the user's like from a post."""
        return await run(api().unlike(post))

    @mcp.tool(annotations=REVERSIBLE)
    async def repost(post: PostId) -> fmt.EngagementResult:
        """Repost a post. Does nothing if already reposted."""
        return await run(api().repost(post))

    @mcp.tool(annotations=REVERSIBLE)
    async def unrepost(post: PostId) -> fmt.EngagementResult:
        """Undo the user's repost of a post."""
        return await run(api().unrepost(post))
