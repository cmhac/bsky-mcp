"""Engagement tool contracts (T042, User Story 3)."""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from typing import Any

import pytest
from atproto_client.exceptions import RateLimitExceededError
from atproto_client.request import Response
from fastmcp import Client
from fastmcp.exceptions import ToolError

from bsky_mcp.bluesky.client import SafeBlueskyClient
from tests.conftest import OTHER_HANDLE, OTHER_POST_URL, ann, data
from tests.fake_transport import OWNER_DID, OWNER_HANDLE, RecordingRequest, default_routes

ENGAGEMENT = ["follow", "unfollow", "like", "unlike", "repost", "unrepost"]


async def test_annotations(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    for name in ENGAGEMENT:
        hints = ann(tools[name])
        assert hints.destructive_hint is False, name
        assert hints.idempotent_hint is True, name


@pytest.mark.parametrize(
    ("do", "undo", "arg"),
    [
        ("follow", "unfollow", OTHER_HANDLE),
        ("like", "unlike", OTHER_POST_URL),
        ("repost", "unrepost", OTHER_POST_URL),
    ],
)
async def test_do_is_idempotent_and_undo_reports_nothing(
    client: Client, do: str, undo: str, arg: str
) -> None:
    if do == "follow":
        first = data(await client.call_tool("follow", {"actors": [arg]}))
        assert first["results"][0]["status"] == "followed"
        again = data(await client.call_tool("follow", {"actors": [arg]}))
        assert again["results"][0]["status"] == "already_following"
        key = "actor"
    else:
        key = "post"
        assert data(await client.call_tool(do, {key: arg}))["changed"] is True
        assert data(await client.call_tool(do, {key: arg}))["changed"] is False
    assert data(await client.call_tool(undo, {key: arg}))["changed"] is True
    second = data(await client.call_tool(undo, {key: arg}))
    assert second["changed"] is False
    assert "Nothing to undo" in second["message"]


def _client() -> tuple[SafeBlueskyClient, RecordingRequest]:
    request = RecordingRequest()
    return SafeBlueskyClient(
        OWNER_HANDLE, "app-pass", "https://bsky.social", request=request
    ), request


async def test_real_like_creates_record_in_own_repo() -> None:
    client, request = _client()
    result = await client.like(OTHER_POST_URL)
    assert result.changed is True
    writes = [(n, b) for n, _, b in request.calls if n == "com.atproto.repo.createRecord"]
    assert writes[0][1]["repo"] == OWNER_DID
    assert writes[0][1]["collection"] == "app.bsky.feed.like"


async def test_real_unlike_and_unrepost_delete_only_own_records() -> None:
    client, request = _client()
    own_post = f"https://bsky.app/profile/{OWNER_HANDLE}/post/own1"
    await client.unlike(own_post)
    await client.unrepost(own_post)
    deletes = [b for n, _, b in request.calls if n == "com.atproto.repo.deleteRecord"]
    assert [(d["collection"], d["rkey"], d["repo"]) for d in deletes] == [
        ("app.bsky.feed.like", "l1", OWNER_DID),
        ("app.bsky.feed.repost", "r1", OWNER_DID),
    ]


async def test_real_unfollow_deletes_follow_record() -> None:
    client, request = _client()
    result = await client.unfollow(OTHER_HANDLE)
    assert result.changed is True
    deletes = [b for n, _, b in request.calls if n == "com.atproto.repo.deleteRecord"]
    assert deletes == [{"repo": OWNER_DID, "collection": "app.bsky.graph.follow", "rkey": "f1"}]


# -- batch follow (spec 003) -------------------------------------------------------------------


def _follow_client(
    followed: AbstractSet[str] = frozenset(),
    missing: AbstractSet[str] = frozenset(),
    failing: AbstractSet[str] = frozenset(),
    limited: AbstractSet[str] = frozenset(),
) -> tuple[SafeBlueskyClient, RecordingRequest]:
    """Real client over a fake transport where each handle's account state is configurable."""

    def profile(params: dict[str, Any]) -> dict[str, Any]:
        actor = str(params["actor"])
        if actor in limited:
            raise RateLimitExceededError(
                Response(success=False, status_code=429, content=None, headers={})
            )
        if actor in missing:
            raise BadRequest(f"Profile not found: {actor}")
        if actor in failing:
            raise BadRequest(f"Account {actor} has blocked you")
        if actor in (OWNER_HANDLE, OWNER_DID):
            did = OWNER_DID
        elif actor.startswith("did:"):
            did = actor
        else:
            did = f"did:plc:{actor.split('.')[0]}"
        viewer = (
            {"following": f"at://{OWNER_DID}/app.bsky.graph.follow/old"}
            if actor in followed
            else {}
        )
        return {
            "did": did,
            "handle": actor if "." in actor else f"{actor}.example",
            "viewer": viewer,
        }

    routes = default_routes()
    routes["app.bsky.actor.getProfile"] = profile
    routes["com.atproto.repo.createRecord"] = lambda _: {
        "uri": f"at://{OWNER_DID}/app.bsky.graph.follow/new",
        "cid": "bafyreinew",
    }
    request = RecordingRequest(routes)
    return SafeBlueskyClient(
        OWNER_HANDLE, "app-pass", "https://bsky.social", request=request
    ), request


def BadRequest(message: str) -> Exception:  # noqa: N802
    from atproto_client.exceptions import BadRequestError
    from atproto_client.models.common import XrpcError

    return BadRequestError(
        Response(
            success=False,
            status_code=400,
            headers={},
            content=XrpcError(error="InvalidRequest", message=message),
        )
    )


def _follow_writes(request: RecordingRequest) -> list[dict[str, Any]]:
    return [
        b
        for n, _, b in request.calls
        if n == "com.atproto.repo.createRecord" and b["collection"] == "app.bsky.graph.follow"
    ]


def _statuses(result: Any) -> list[tuple[str, str]]:
    return [(r.actor, r.status) for r in result.results]


async def test_batch_of_25_follows_each_in_owner_repo_in_order() -> None:
    client, request = _follow_client()
    actors = [f"user{i}.example.com" for i in range(25)]
    result = await client.follow(actors)
    assert _statuses(result) == [(a, "followed") for a in actors]
    writes = _follow_writes(request)
    assert len(writes) == 25
    assert {w["repo"] for w in writes} == {OWNER_DID}
    assert [w["record"]["subject"] for w in writes] == [f"did:plc:user{i}" for i in range(25)]


async def test_single_account_batch_behaves_like_larger_batch() -> None:
    client, request = _follow_client()
    result = await client.follow(["solo.example.com"])
    assert _statuses(result) == [("solo.example.com", "followed")]
    assert len(_follow_writes(request)) == 1


async def test_mixed_batch_reports_each_account() -> None:
    client, request = _follow_client(
        followed={"old.example.com"}, missing={"gone.example.com"}, failing={"blocker.example.com"}
    )
    result = await client.follow(
        [
            "new.example.com",
            "old.example.com",
            "gone.example.com",
            OWNER_HANDLE,
            "not a handle!",
            "blocker.example.com",
            "after.example.com",
        ]
    )
    assert [r.status for r in result.results] == [
        "followed",
        "already_following",
        "not_found",
        "is_you",
        "not_found",
        "failed",
        "followed",
    ]
    assert "blocked you" in (result.results[5].message or "")
    assert [w["record"]["subject"] for w in _follow_writes(request)] == [
        "did:plc:new",
        "did:plc:after",
    ]


async def test_rerun_creates_nothing_new() -> None:
    actors = ["a.example.com", "b.example.com"]
    client, request = _follow_client(followed=set(actors))
    result = await client.follow(actors)
    assert [r.status for r in result.results] == ["already_following"] * 2
    assert _follow_writes(request) == []


async def test_repeated_entries_follow_once() -> None:
    client, request = _follow_client()
    result = await client.follow(["a.example.com", "a.example.com", "did:plc:a"])
    assert [r.status for r in result.results] == [
        "followed",
        "already_following",
        "already_following",
    ]
    assert len(_follow_writes(request)) == 1


@pytest.mark.parametrize("count", [0, 26])
async def test_wrong_batch_size_is_refused_before_any_write(count: int) -> None:
    client, request = _follow_client()
    from bsky_mcp.bluesky.text import InvalidInputError

    with pytest.raises(InvalidInputError, match="between 1 and 25"):
        await client.follow([f"u{i}.example.com" for i in range(count)])
    assert request.calls == []


async def test_rate_limit_stops_and_marks_the_rest_not_attempted() -> None:
    client, request = _follow_client(limited={"c.example.com"})
    actors = ["a.example.com", "b.example.com", "c.example.com", "d.example.com", "e.example.com"]
    result = await client.follow(actors)
    assert _statuses(result) == [
        ("a.example.com", "followed"),
        ("b.example.com", "followed"),
        ("c.example.com", "not_attempted"),
        ("d.example.com", "not_attempted"),
        ("e.example.com", "not_attempted"),
    ]
    assert len(_follow_writes(request)) == 2
    requested = [
        p.get("actor")
        for n, p, _ in request.calls
        if n == "app.bsky.actor.getProfile" and p.get("actor") != OWNER_HANDLE
    ]
    assert requested == ["a.example.com", "b.example.com", "c.example.com"]


async def test_tool_rejects_old_actor_input_and_bad_sizes(client: Client) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("follow", {"actor": OTHER_HANDLE})
    with pytest.raises(ToolError):
        await client.call_tool("follow", {"actors": []})
    with pytest.raises(ToolError):
        await client.call_tool("follow", {"actors": [f"u{i}.example.com" for i in range(26)]})
