"""Guarded delete contract (T050, User Story 4)."""

from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from bsky_mcp import instructions
from bsky_mcp.bluesky.client import BlueskyError, SafeBlueskyClient
from tests.conftest import OTHER_POST_URL, OWN_POST_URL, FakeBluesky, ann, data
from tests.fake_transport import OTHER_DID, OWNER_DID, OWNER_HANDLE, RecordingRequest


@pytest.mark.parametrize("confirm", [None, "", "yes", "DELETE", "delete "])
async def test_requires_exact_confirmation(
    client: Client, fake: FakeBluesky, confirm: str | None
) -> None:
    args = {"post": OWN_POST_URL} | ({"confirm": confirm} if confirm is not None else {})
    with pytest.raises(ToolError, match="confirmation_required"):
        await client.call_tool("delete_post", args)
    assert not any(c.startswith("delete:") for c in fake.calls)


async def test_deletes_own_post(client: Client, fake: FakeBluesky) -> None:
    result = data(
        await client.call_tool("delete_post", {"post": OWN_POST_URL, "confirm": "delete"})
    )
    assert result == {"deleted": True, "url": OWN_POST_URL, "text": "my post"}
    assert f"delete:at://{OWNER_DID}/app.bsky.feed.post/own1" in fake.calls


async def test_refuses_other_authors(client: Client) -> None:
    with pytest.raises(ToolError, match="not_owner"):
        await client.call_tool("delete_post", {"post": OTHER_POST_URL, "confirm": "delete"})


async def test_unknown_post(client: Client) -> None:
    with pytest.raises(ToolError, match="not_found"):
        await client.call_tool(
            "delete_post",
            {"post": f"https://bsky.app/profile/{OWNER_HANDLE}/post/gone", "confirm": "delete"},
        )


async def test_description_and_annotations(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    tool = tools["delete_post"]
    assert ann(tool).destructive_hint is True
    assert instructions.DELETE_RULE in (tool.description or "")


async def test_real_client_refuses_other_author_without_request() -> None:
    request = RecordingRequest()
    client = SafeBlueskyClient(OWNER_HANDLE, "app-pass", "https://bsky.social", request=request)
    with pytest.raises(BlueskyError) as info:
        await client.delete_own_post(f"at://{OTHER_DID}/app.bsky.feed.post/other1")
    assert info.value.code == "not_owner"
    assert "com.atproto.repo.deleteRecord" not in request.nsids()


async def test_real_client_deletes_own_post_record() -> None:
    request = RecordingRequest()
    client = SafeBlueskyClient(OWNER_HANDLE, "app-pass", "https://bsky.social", request=request)
    await client.delete_own_post(f"https://bsky.app/profile/{OWNER_HANDLE}/post/own1")
    deletes = [b for n, _, b in request.calls if n == "com.atproto.repo.deleteRecord"]
    assert deletes == [{"repo": OWNER_DID, "collection": "app.bsky.feed.post", "rkey": "own1"}]
