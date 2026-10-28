"""Blocking is unreachable and undo only touches the owner's records (T043, Principle II)."""

from __future__ import annotations

import pytest

from bsky_mcp.bluesky import operations as ops
from bsky_mcp.bluesky.client import BlueskyError, SafeBlueskyClient
from tests.fake_transport import (
    OTHER_DID,
    OWNER_DID,
    OWNER_HANDLE,
    RecordingRequest,
    default_routes,
    post_view,
)


def test_block_collection_never_writable() -> None:
    for nsid in (ops.CREATE_RECORD, ops.DELETE_RECORD):
        with pytest.raises(ops.ForbiddenOperationError):
            ops.check_operation(
                nsid, {"repo": OWNER_DID, "collection": "app.bsky.graph.block"}, OWNER_DID
            )


async def test_undo_refuses_record_outside_own_repo() -> None:
    """If Bluesky ever reported a viewer record in someone else's repo, undo must refuse it."""
    routes = default_routes()
    foreign = post_view(
        OTHER_DID, "other1", "theirs", {"like": f"at://{OTHER_DID}/app.bsky.feed.like/x"}
    )
    routes["app.bsky.feed.getPosts"] = lambda _: {"posts": [foreign]}
    request = RecordingRequest(routes)
    client = SafeBlueskyClient(OWNER_HANDLE, "app-pass", "https://bsky.social", request=request)
    with pytest.raises(BlueskyError) as info:
        await client.unlike(f"at://{OTHER_DID}/app.bsky.feed.post/other1")
    assert info.value.code == "not_owner"
    assert "com.atproto.repo.deleteRecord" not in request.nsids()
