"""Read tools (User Story 1). All read-only."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.bluesky.core import SearchFilters
from bsky_mcp.tools import READ_ONLY, Actor, ApiProvider, Cursor, Limit, PostId, run


def register(mcp: FastMCP, api: ApiProvider) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def get_my_profile() -> fmt.ProfileView:
        """Get the user's own Bluesky profile."""
        return await run(api().me())

    @mcp.tool(annotations=READ_ONLY)
    async def get_timeline(limit: Limit = 25, cursor: Cursor = None) -> fmt.PostPage:
        """Get the user's home timeline, newest first."""
        return await run(api().timeline(limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_notifications(
        limit: Limit = 25,
        cursor: Cursor = None,
        unread_only: Annotated[bool, Field(description="Only unread notifications.")] = False,
    ) -> fmt.NotificationPage:
        """Get the user's notifications: likes, reposts, follows, mentions, replies, quotes."""
        return await run(api().notifications(limit, cursor, unread_only))

    @mcp.tool(annotations=READ_ONLY)
    async def get_thread(
        post: PostId,
        depth: Annotated[int, Field(ge=0, le=10, description="Reply depth, 0-10.")] = 6,
        parent_height: Annotated[
            int, Field(ge=0, le=20, description="Parent posts to include, 0-20.")
        ] = 10,
    ) -> fmt.ThreadView:
        """Get a post with its parent chain and replies."""
        return await run(api().thread(post, depth, parent_height))

    @mcp.tool(annotations=READ_ONLY)
    async def get_profile(actor: Actor) -> fmt.ProfileView:
        """Get any account's profile."""
        return await run(api().profile(actor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_author_posts(
        actor: Actor,
        limit: Limit = 25,
        cursor: Cursor = None,
        include_replies: Annotated[bool, Field(description="Include replies.")] = False,
    ) -> fmt.PostPage:
        """Get an account's recent posts."""
        return await run(api().author_posts(actor, limit, cursor, include_replies))

    @mcp.tool(annotations=READ_ONLY)
    async def get_followers(
        actor: Annotated[
            str | None, Field(description="Handle or DID. Defaults to the user.")
        ] = None,
        limit: Limit = 25,
        cursor: Cursor = None,
    ) -> fmt.ProfilePage:
        """List an account's followers (the user's by default)."""
        return await run(api().followers(actor, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def get_follows(
        actor: Annotated[
            str | None, Field(description="Handle or DID. Defaults to the user.")
        ] = None,
        limit: Limit = 25,
        cursor: Cursor = None,
    ) -> fmt.ProfilePage:
        """List the accounts an account follows (the user's by default)."""
        return await run(api().follows(actor, limit, cursor))

    @mcp.tool(annotations=READ_ONLY)
    async def search_posts(
        query: Annotated[str, Field(min_length=1, description="Search terms.")],
        limit: Limit = 25,
        cursor: Cursor = None,
        sort: Annotated[Literal["top", "latest"], Field(description="Ranking.")] = "latest",
        author: Annotated[
            str | None, Field(description="Only posts by this handle or DID.")
        ] = None,
        since: Annotated[
            str | None, Field(description="Posts on or after this ISO date or datetime.")
        ] = None,
        until: Annotated[
            str | None, Field(description="Posts before this ISO date or datetime.")
        ] = None,
        lang: Annotated[str | None, Field(description="Language code, e.g. 'en'.")] = None,
        mentions: Annotated[
            str | None, Field(description="Only posts mentioning this handle or DID.")
        ] = None,
        tags: Annotated[
            list[str] | None, Field(description="Hashtags (all must match), with or without #.")
        ] = None,
        domain: Annotated[
            str | None, Field(description="Only posts linking to this domain.")
        ] = None,
        url: Annotated[
            str | None,
            Field(description="Only posts linking to this https URL, e.g. a published story."),
        ] = None,
    ) -> fmt.PostPage:
        """Search Bluesky posts, optionally filtered by date, language, mentions, hashtags,
        linked domain, or a specific linked URL."""
        filters = SearchFilters(
            since=since,
            until=until,
            lang=lang,
            mentions=mentions,
            tags=tags,
            domain=domain,
            url=url,
        )
        return await run(api().search_posts(query, limit, cursor, sort, author, filters))

    @mcp.tool(annotations=READ_ONLY)
    async def search_users(
        query: Annotated[str, Field(min_length=1, description="Search terms.")],
        limit: Limit = 25,
        cursor: Cursor = None,
    ) -> fmt.ProfilePage:
        """Search Bluesky accounts."""
        return await run(api().search_users(query, limit, cursor))
