"""Read tool contracts (T025, User Story 1)."""

from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import OTHER_HANDLE, OWN_POST_URL, FakeBluesky, ann, data

READ_TOOLS = {
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
}


async def test_all_read_tools_registered_read_only(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    assert set(tools) >= READ_TOOLS
    for name in READ_TOOLS:
        assert ann(tools[name]).read_only_hint is True, name


async def test_timeline_defaults_and_fields(client: Client, fake: FakeBluesky) -> None:
    result = await client.call_tool("get_timeline", {})
    assert "timeline:25:None" in fake.calls
    post = data(result)["posts"][0]
    for key in ("uri", "url", "author_handle", "text", "like_count", "viewer_liked"):
        assert key in post
    assert post["url"].startswith("https://bsky.app/profile/")
    assert data(result)["cursor"] == "next"


@pytest.mark.parametrize("limit", [0, 101])
async def test_limit_bounds(client: Client, limit: int) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("get_timeline", {"limit": limit})


async def test_limit_upper_bound_accepted(client: Client, fake: FakeBluesky) -> None:
    await client.call_tool("get_timeline", {"limit": 100, "cursor": "abc"})
    assert "timeline:100:abc" in fake.calls


async def test_notifications_unread_only(client: Client) -> None:
    result = await client.call_tool("get_notifications", {"unread_only": True})
    items = data(result)["notifications"]
    assert items and all(not n["is_read"] for n in items)


async def test_thread_defaults_and_bounds(client: Client, fake: FakeBluesky) -> None:
    result = await client.call_tool("get_thread", {"post": OWN_POST_URL})
    assert "thread:6:10" in fake.calls
    assert data(result)["post"]["text"] == "my post"
    with pytest.raises(ToolError):
        await client.call_tool("get_thread", {"post": OWN_POST_URL, "depth": 11})
    with pytest.raises(ToolError):
        await client.call_tool("get_thread", {"post": OWN_POST_URL, "parent_height": 21})


async def test_thread_not_found(client: Client) -> None:
    with pytest.raises(ToolError, match="not_found"):
        await client.call_tool(
            "get_thread", {"post": f"https://bsky.app/profile/{OTHER_HANDLE}/post/missing"}
        )


async def test_invalid_post_identifier(client: Client) -> None:
    with pytest.raises(ToolError, match="invalid_input"):
        await client.call_tool("get_thread", {"post": "https://example.com/not-bluesky"})


async def test_profile_and_author_posts(client: Client, fake: FakeBluesky) -> None:
    profile = await client.call_tool("get_profile", {"actor": f"@{OTHER_HANDLE}"})
    assert data(profile)["handle"] == OTHER_HANDLE
    await client.call_tool("get_author_posts", {"actor": OTHER_HANDLE, "include_replies": True})
    assert "author_posts:True" in fake.calls


async def test_followers_default_to_owner(client: Client, fake: FakeBluesky) -> None:
    await client.call_tool("get_followers", {})
    assert "followers:None" in fake.calls


async def test_search(client: Client, fake: FakeBluesky) -> None:
    await client.call_tool("search_posts", {"query": "dagster", "sort": "top"})
    assert "search_posts:dagster:top:None" in fake.calls
    with pytest.raises(ToolError):
        await client.call_tool("search_posts", {"query": ""})
    with pytest.raises(ToolError):
        await client.call_tool("search_posts", {"query": "x", "sort": "random"})
    users = await client.call_tool("search_users", {"query": "other"})
    assert data(users)["profiles"][0]["handle"] == OTHER_HANDLE
