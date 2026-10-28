"""Engagement tool contracts (T042, User Story 3)."""

from __future__ import annotations

import pytest
from fastmcp import Client

from bsky_mcp.bluesky.client import SafeBlueskyClient
from tests.conftest import OTHER_HANDLE, OTHER_POST_URL, ann, data
from tests.fake_transport import OWNER_DID, OWNER_HANDLE, RecordingRequest

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
    key = "actor" if do == "follow" else "post"
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
