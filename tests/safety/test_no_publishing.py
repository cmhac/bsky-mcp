"""The server cannot publish, and its instructions say so (T030, Principle III)."""

from __future__ import annotations

import inspect

from fastmcp import Client

from bsky_mcp import instructions
from bsky_mcp.bluesky import client as client_module
from bsky_mcp.bluesky import operations as ops
from bsky_mcp.server import create_server
from tests.conftest import FakeBluesky

EXPECTED_TOOLS = {
    "get_my_profile",
    "get_timeline",
    "get_notifications",
    "get_thread",
    "get_profile",
    "get_author_posts",
    "get_followers",
    "get_follows",
    "search_posts",
    "search_users",
    "create_draft",
    "update_draft",
    "list_drafts",
    "follow",
    "unfollow",
    "like",
    "unlike",
    "repost",
    "unrepost",
    "delete_post",
    # spec 002
    "get_quotes",
    "get_likes",
    "get_reposted_by",
    "get_feed",
    "get_feed_info",
    "get_account_feeds",
    "get_suggested_feeds",
    "search_feeds",
    "get_suggested_follows",
    "get_similar_accounts",
    "get_trending_topics",
    "search_starter_packs",
    "get_starter_pack",
    "get_account_starter_packs",
    "get_lists",
    "get_list",
    "get_list_feed",
    "create_list",
    "add_to_list",
    "remove_from_list",
    "delete_list",
}


async def test_tool_set_is_exactly_the_contract(client: Client) -> None:
    """Any new tool (e.g. a publish or block tool) fails this test until the spec changes."""
    assert {t.name for t in await client.list_tools()} == EXPECTED_TOOLS


def test_post_collection_not_creatable() -> None:
    assert ops.POST not in ops.CREATABLE_COLLECTIONS


def test_client_never_builds_a_post_record() -> None:
    source = inspect.getsource(client_module)
    assert "AppBskyFeedPost.Record" not in source
    assert "send_post" not in source
    assert "app.bsky.feed.post" not in source  # only operations.py names the collection


def test_server_instructions_state_rules() -> None:
    text = create_server(lambda: FakeBluesky()).instructions or ""
    assert "cannot publish" in text
    assert "Replies cannot be saved as drafts" in text
    assert "link to the post being replied to" in text
    assert instructions.DELETE_RULE in text


async def test_create_draft_description(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    description = tools["create_draft"].description or ""
    assert "cannot publish" in description
    assert "except replies" in description
    assert "300 graphemes" in description
