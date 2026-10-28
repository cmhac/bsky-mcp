"""Discovery tool contracts (spec 002, User Stories 1-7)."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from bsky_mcp.bluesky.client import SafeBlueskyClient
from bsky_mcp.bluesky.core import BlueskyError, SearchFilters
from tests.conftest import OTHER_HANDLE, OTHER_POST_URL, FakeBluesky, ann, data
from tests.fake_discovery import FEED_URL, OTHER_LIST_URL, OWN_LIST_URL, STARTER_PACK_URL
from tests.fake_transport import (
    OTHER_DID,
    OWNER_DID,
    OWNER_HANDLE,
    RecordingRequest,
    default_routes,
)

DISCOVERY = [
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
]


async def test_discovery_tools_are_read_only(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    for name in DISCOVERY:
        assert ann(tools[name]).read_only_hint is True, name


# -- US1: search filters ----------------------------------------------------------------------


async def test_search_filters_are_normalized(client: Client, fake: FakeBluesky) -> None:
    await client.call_tool(
        "search_posts",
        {
            "query": "data",
            "since": "2026-10-01",
            "until": "2026-10-28T12:00:00Z",
            "tags": ["#dataviz", "maps"],
            "domain": "WashingtonPost.com",
            "url": "https://www.washingtonpost.com/story",
            "mentions": "@other.bsky.social",
            "lang": "en",
        },
    )
    f = fake.last_filters
    assert f is not None
    assert f.tags == ["dataviz", "maps"]
    assert f.domain == "washingtonpost.com"
    assert f.mentions == OTHER_HANDLE
    assert f.since is not None and f.since.startswith("2026-10-01T00:00:00")


@pytest.mark.parametrize(
    "args",
    [
        {"since": "2026-10-28", "until": "2026-10-01"},
        {"since": "not a date"},
        {"url": "http://example.com/insecure"},
    ],
)
async def test_bad_filters_are_rejected(client: Client, args: dict[str, Any]) -> None:
    with pytest.raises(ToolError, match="invalid_input"):
        await client.call_tool("search_posts", {"query": "data", **args})


async def test_search_without_filters_is_unchanged(client: Client, fake: FakeBluesky) -> None:
    await client.call_tool("search_posts", {"query": "data"})
    assert fake.last_filters == SearchFilters()


async def test_real_search_passes_filters_to_bluesky() -> None:
    routes = default_routes()
    routes["app.bsky.feed.searchPosts"] = lambda _: {"posts": []}
    request = RecordingRequest(routes)
    client = SafeBlueskyClient(OWNER_HANDLE, "pw", "https://bsky.social", request=request)
    filters = SearchFilters(tags=["#maps"], domain="WaPo.com", lang="en", since="2026-10-01")
    await client.search_posts("data", 10, None, "latest", None, filters)
    params = next(p for n, p, _ in request.calls if n == "app.bsky.feed.searchPosts")
    assert params["tag"] in ("maps", ["maps"])
    assert params["domain"] == "wapo.com"
    assert params["lang"] == "en"
    assert params["since"].startswith("2026-10-01")


# -- US2-US7 via the fake ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "args", "key"),
    [
        ("get_quotes", {"post": OTHER_POST_URL}, "posts"),
        ("get_likes", {"post": OTHER_POST_URL}, "profiles"),
        ("get_reposted_by", {"post": OTHER_POST_URL}, "profiles"),
        ("get_feed", {"feed": FEED_URL}, "posts"),
        ("get_account_feeds", {"actor": OTHER_HANDLE}, "feeds"),
        ("get_suggested_feeds", {}, "feeds"),
        ("search_feeds", {"query": "science"}, "feeds"),
        ("get_suggested_follows", {}, "profiles"),
        ("get_similar_accounts", {"actor": OTHER_HANDLE}, "profiles"),
        ("get_trending_topics", {}, "topics"),
        ("search_starter_packs", {"query": "data"}, "starter_packs"),
        ("get_starter_pack", {"starter_pack": STARTER_PACK_URL}, "members"),
        ("get_account_starter_packs", {"actor": OTHER_HANDLE}, "starter_packs"),
        ("get_lists", {}, "lists"),
        ("get_list", {"list": OWN_LIST_URL}, "members"),
        ("get_list_feed", {"list": OTHER_LIST_URL}, "posts"),
    ],
)
async def test_discovery_tools_return_results(
    client: Client, tool: str, args: dict[str, Any], key: str
) -> None:
    result = data(await client.call_tool(tool, args))
    assert result[key], tool


async def test_feed_info_reports_status(client: Client) -> None:
    result = data(await client.call_tool("get_feed_info", {"feed": FEED_URL}))
    assert result["url"] == FEED_URL
    assert result["is_online"] is True


async def test_lists_default_to_owner(client: Client, fake: FakeBluesky) -> None:
    await client.call_tool("get_lists", {})
    await client.call_tool("get_lists", {"actor": OTHER_HANDLE})
    assert fake.calls[-2:] == [f"lists:{OWNER_DID}", f"lists:{OTHER_DID}"]


@pytest.mark.parametrize("limit", [0, 26])
async def test_trending_limit_bounds(client: Client, limit: int) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("get_trending_topics", {"limit": limit})


async def test_wrong_link_type_is_rejected(client: Client) -> None:
    with pytest.raises(ToolError, match="invalid_input"):
        await client.call_tool("get_feed", {"feed": OWN_LIST_URL})


# -- unstable endpoints -----------------------------------------------------------------------


def _real(routes: dict[str, Any]) -> tuple[SafeBlueskyClient, RecordingRequest]:
    request = RecordingRequest(routes)
    return SafeBlueskyClient(OWNER_HANDLE, "pw", "https://bsky.social", request=request), request


async def test_trending_failure_is_unavailable_and_isolated() -> None:
    routes = default_routes()
    routes["app.bsky.unspecced.getTrendingTopics"] = lambda _: {"unexpected": "shape"}
    routes["app.bsky.actor.getSuggestions"] = lambda _: {"actors": []}
    client, _ = _real(routes)
    with pytest.raises(BlueskyError) as info:
        await client.trending_topics(10)
    assert info.value.code == "unavailable"
    assert (await client.suggested_follows(10, None)).profiles == []


async def test_real_trending_makes_links_absolute() -> None:
    routes = default_routes()
    routes["app.bsky.unspecced.getTrendingTopics"] = lambda _: {
        "topics": [{"topic": "maps", "link": "/profile/trending/topic/maps"}],
        "suggested": [],
    }
    client, _ = _real(routes)
    page = await client.trending_topics(5)
    assert page.topics[0].url == "https://bsky.app/profile/trending/topic/maps"


async def test_real_get_list_resolves_link_to_at_uri() -> None:
    routes = default_routes()
    routes["app.bsky.graph.getList"] = lambda p: {
        "list": _list_view(p["list"]),
        "items": [{"uri": "at://x/app.bsky.graph.listitem/i1", "subject": _actor(OTHER_DID)}],
    }
    client, request = _real(routes)
    detail = await client.list_detail(OTHER_LIST_URL, 10, None)
    params = next(p for n, p, _ in request.calls if n == "app.bsky.graph.getList")
    assert params["list"] == f"at://{OTHER_DID}/app.bsky.graph.list/otherlist"
    assert detail.members[0].did == OTHER_DID


def _actor(did: str) -> dict[str, Any]:
    return {"did": did, "handle": OWNER_HANDLE if did == OWNER_DID else OTHER_HANDLE}


def _list_view(uri: str) -> dict[str, Any]:
    did = uri.split("/")[2]
    return {
        "uri": uri,
        "cid": "bafylist",
        "name": "A list",
        "purpose": "app.bsky.graph.defs#curatelist",
        "creator": _actor(did),
        "indexedAt": "2026-10-28T00:00:00Z",
        "listItemCount": 1,
    }
