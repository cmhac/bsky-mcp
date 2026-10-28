"""Regression tests for issue #5: list endpoints return SDK models without the detailed counts."""

from __future__ import annotations

from typing import Any

import pytest
from atproto import models
from fastmcp.exceptions import ToolError

from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.bluesky.client import SafeBlueskyClient
from bsky_mcp.tools import run
from tests.fake_transport import (
    OTHER_DID,
    OWNER_DID,
    OWNER_HANDLE,
    RecordingRequest,
    default_routes,
)

CID = "bafyreigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
PROFILE = {"did": OTHER_DID, "handle": "other.bsky.social", "displayName": "Other"}


def _client(routes: dict[str, Any]) -> SafeBlueskyClient:
    return SafeBlueskyClient(
        OWNER_HANDLE, "pw", "https://bsky.social", request=RecordingRequest(routes)
    )


@pytest.mark.parametrize(
    "model",
    [
        models.AppBskyActorDefs.ProfileView(did=OTHER_DID, handle="o.bsky.social"),
        models.AppBskyActorDefs.ProfileViewBasic(did=OTHER_DID, handle="o.bsky.social"),
    ],
)
def test_to_profile_tolerates_models_without_counts(model: Any) -> None:
    profile = fmt.to_profile(model)
    assert profile.handle == "o.bsky.social"
    assert profile.followers_count is None
    assert profile.follows_count is None
    assert profile.posts_count is None


def test_to_notification_tolerates_records_without_text() -> None:
    author = models.AppBskyActorDefs.ProfileView(did=OTHER_DID, handle="o.bsky.social")
    subject = models.ComAtprotoRepoStrongRef.Main(
        uri=f"at://{OWNER_DID}/app.bsky.feed.post/1", cid=CID
    )
    like = models.AppBskyFeedLike.Record(subject=subject, created_at="2026-10-28T00:00:00Z")
    notification = models.AppBskyNotificationListNotifications.Notification(
        uri=f"at://{OTHER_DID}/app.bsky.feed.like/1",
        cid=CID,
        author=author,
        reason="like",
        record=like,
        is_read=False,
        indexed_at="2026-10-28T00:00:00Z",
    )
    view = fmt.to_notification(notification)
    assert view.reason == "like"
    assert view.text is None


async def test_list_endpoints_return_profile_pages() -> None:
    routes = default_routes()
    routes["app.bsky.actor.searchActors"] = lambda _: {"actors": [PROFILE], "cursor": "c1"}
    routes["app.bsky.graph.getFollows"] = lambda _: {
        "subject": PROFILE,
        "follows": [PROFILE],
        "cursor": "c2",
    }
    routes["app.bsky.graph.getFollowers"] = lambda _: {
        "subject": PROFILE,
        "followers": [PROFILE],
        "cursor": "c3",
    }
    client = _client(routes)
    pages = {
        "c1": await client.search_users("data journalist", 25, None),
        "c2": await client.follows(None, 10, None),
        "c3": await client.followers(None, 10, None),
    }
    for cursor, page in pages.items():
        assert isinstance(page, fmt.ProfilePage)
        assert page.cursor == cursor
        assert page.profiles[0].handle == "other.bsky.social"
        assert page.profiles[0].followers_count is None


async def test_unexpected_errors_surface_type_without_details() -> None:
    async def boom() -> None:
        raise RuntimeError("secret-token-123")

    with pytest.raises(ToolError) as info:
        await run(boom())
    assert str(info.value) == "internal_error: RuntimeError"
