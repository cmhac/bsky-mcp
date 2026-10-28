"""Read-only discovery tools (spec 002, User Stories 2-7)."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from bsky_mcp import instructions
from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.tools import READ_ONLY, Actor, ApiProvider, Cursor, Limit, PostId, run

Query = Annotated[str, Field(min_length=1, description="Search terms.")]
FeedId = Annotated[
    str, Field(description="A bsky.app feed link (…/profile/<handle>/feed/<id>) or at:// URI.")
]
ListId = Annotated[
    str, Field(description="A bsky.app list link (…/profile/<handle>/lists/<id>) or at:// URI.")
]
StarterPackId = Annotated[
    str,
    Field(description="A bsky.app starter pack link (…/starter-pack/<handle>/<id>) or at:// URI."),
]
TrendingLimit = Annotated[int, Field(ge=1, le=25, description="Number of topics, 1-25.")]


def register(mcp: FastMCP, api: ApiProvider) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def get_quotes(post: PostId, limit: Limit = 25, cursor: Cursor = None) -> fmt.PostPage:
        """Get posts that quote a post."""
        return await run(api().quotes(post, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_likes(post: PostId, limit: Limit = 25, cursor: Cursor = None) -> fmt.ProfilePage:
        """Get the accounts that liked a post."""
        return await run(api().likes(post, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_reposted_by(
        post: PostId, limit: Limit = 25, cursor: Cursor = None
    ) -> fmt.ProfilePage:
        """Get the accounts that reposted a post."""
        return await run(api().reposted_by(post, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_feed(feed: FeedId, limit: Limit = 25, cursor: Cursor = None) -> fmt.PostPage:
        """Read the current posts in a custom feed."""
        return await run(api().feed(feed, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_feed_info(feed: FeedId) -> fmt.FeedView:
        """Describe a custom feed: name, creator, description, likes, and whether it's online."""
        return await run(api().feed_info(feed))

    @mcp.tool(annotations=READ_ONLY)
    async def get_account_feeds(
        actor: Actor, limit: Limit = 25, cursor: Cursor = None
    ) -> fmt.FeedPage:
        """List the custom feeds an account has created."""
        return await run(api().account_feeds(actor, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_suggested_feeds(limit: Limit = 25, cursor: Cursor = None) -> fmt.FeedPage:
        """Get custom feeds Bluesky suggests for the user."""
        return await run(api().suggested_feeds(limit, cursor))

    @mcp.tool(description=instructions.SEARCH_FEEDS_DESCRIPTION, annotations=READ_ONLY)
    async def search_feeds(query: Query, limit: Limit = 25, cursor: Cursor = None) -> fmt.FeedPage:
        return await run(api().search_feeds(query, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_suggested_follows(limit: Limit = 25, cursor: Cursor = None) -> fmt.ProfilePage:
        """Get accounts Bluesky suggests the user follow."""
        return await run(api().suggested_follows(limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_similar_accounts(actor: Actor) -> fmt.ProfilePage:
        """Get accounts Bluesky associates with a given account."""
        return await run(api().similar_accounts(actor))

    @mcp.tool(description=instructions.TRENDING_DESCRIPTION, annotations=READ_ONLY)
    async def get_trending_topics(limit: TrendingLimit = 10) -> fmt.TrendingPage:
        return await run(api().trending_topics(limit))

    @mcp.tool(annotations=READ_ONLY)
    async def search_starter_packs(
        query: Query, limit: Limit = 25, cursor: Cursor = None
    ) -> fmt.StarterPackPage:
        """Search Bluesky starter packs by topic."""
        return await run(api().search_starter_packs(query, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_starter_pack(
        starter_pack: StarterPackId, limit: Limit = 25, cursor: Cursor = None
    ) -> fmt.StarterPackDetail:
        """Get a starter pack's description and the accounts in it (paged)."""
        return await run(api().starter_pack(starter_pack, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_account_starter_packs(
        actor: Actor, limit: Limit = 25, cursor: Cursor = None
    ) -> fmt.StarterPackPage:
        """List the starter packs an account has created."""
        return await run(api().account_starter_packs(actor, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_lists(
        actor: Annotated[
            str | None, Field(description="Handle or DID. Defaults to the user.")
        ] = None,
        limit: Limit = 25,
        cursor: Cursor = None,
    ) -> fmt.ListPage:
        """List the lists an account has made (the user's by default)."""
        return await run(api().lists(actor, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_list(list: ListId, limit: Limit = 25, cursor: Cursor = None) -> fmt.ListDetail:  # noqa: A002
        """Get a list's details and members (paged)."""
        return await run(api().list_detail(list, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_list_feed(list: ListId, limit: Limit = 25, cursor: Cursor = None) -> fmt.PostPage:  # noqa: A002
        """Get recent posts from a list's members."""
        return await run(api().list_feed(list, limit, cursor))
