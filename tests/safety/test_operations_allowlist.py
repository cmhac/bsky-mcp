"""Forbidden operations are unreachable (T012, Principles II and III)."""

from __future__ import annotations

import inspect

import pytest

from bsky_mcp.bluesky import operations as ops
from bsky_mcp.bluesky.client import GuardedAsyncClient, SafeBlueskyClient
from tests.fake_transport import OWNER_DID, OWNER_HANDLE, RecordingRequest

FORBIDDEN_NSIDS = [
    "app.bsky.draft.deleteDraft",
    "app.bsky.graph.muteActor",
    "app.bsky.graph.unmuteActor",
    "app.bsky.graph.muteActorList",
    "chat.bsky.convo.sendMessage",
    "chat.bsky.convo.listConvos",
    "com.atproto.repo.putRecord",
    "com.atproto.repo.applyWrites",
    "com.atproto.repo.uploadBlob",
    "com.atproto.server.deleteAccount",
    "com.atproto.server.createAppPassword",
    "app.bsky.actor.putPreferences",
]


def test_allowlist_contents() -> None:
    assert ops.POST not in ops.CREATABLE_COLLECTIONS
    assert "app.bsky.graph.block" not in ops.CREATABLE_COLLECTIONS
    assert "app.bsky.graph.block" not in ops.DELETABLE_COLLECTIONS
    graph_list = {ops.LIST, ops.LIST_ITEM}
    assert {ops.FOLLOW, ops.LIKE, ops.REPOST, ops.POST} | graph_list == ops.DELETABLE_COLLECTIONS
    assert {ops.FOLLOW, ops.LIKE, ops.REPOST} | graph_list == ops.CREATABLE_COLLECTIONS
    assert "app.bsky.draft.deleteDraft" not in ops.ALLOWED_OPERATIONS
    assert not any(n.startswith("chat.") for n in ops.ALLOWED_OPERATIONS)
    assert "app.bsky.graph.listblock" not in ops.CREATABLE_COLLECTIONS


@pytest.mark.parametrize("nsid", FORBIDDEN_NSIDS)
def test_unlisted_operations_rejected(nsid: str) -> None:
    with pytest.raises(ops.ForbiddenOperationError):
        ops.check_operation(nsid, None, OWNER_DID)


@pytest.mark.parametrize(
    ("nsid", "collection"),
    [
        (ops.CREATE_RECORD, ops.POST),  # publishing
        (ops.CREATE_RECORD, "app.bsky.graph.block"),
        (ops.DELETE_RECORD, "app.bsky.graph.block"),
        (ops.CREATE_RECORD, "app.bsky.graph.listblock"),
        (ops.DELETE_RECORD, "app.bsky.graph.listblock"),
        (ops.DELETE_RECORD, "app.bsky.actor.profile"),
        (ops.CREATE_RECORD, None),
    ],
)
def test_forbidden_record_writes_rejected(nsid: str, collection: str | None) -> None:
    with pytest.raises(ops.ForbiddenOperationError):
        ops.check_operation(nsid, {"repo": OWNER_DID, "collection": collection}, OWNER_DID)


@pytest.mark.parametrize("collection", sorted(ops.DELETABLE_COLLECTIONS))
def test_writes_outside_own_repo_rejected(collection: str) -> None:
    with pytest.raises(ops.ForbiddenOperationError):
        ops.check_operation(
            ops.DELETE_RECORD, {"repo": "did:plc:other", "collection": collection}, OWNER_DID
        )
    with pytest.raises(ops.ForbiddenOperationError):
        ops.check_operation(ops.DELETE_RECORD, {"repo": OWNER_DID, "collection": collection}, None)


def test_allowed_writes_pass() -> None:
    for collection in (ops.FOLLOW, ops.LIKE, ops.REPOST):
        ops.check_operation(
            ops.CREATE_RECORD, {"repo": OWNER_DID, "collection": collection}, OWNER_DID
        )
    for collection in ops.DELETABLE_COLLECTIONS:
        ops.check_operation(
            ops.DELETE_RECORD, {"repo": OWNER_DID, "collection": collection}, OWNER_DID
        )


async def _signed_in() -> tuple[SafeBlueskyClient, RecordingRequest]:
    request = RecordingRequest()
    client = SafeBlueskyClient(OWNER_HANDLE, "app-pass", "https://bsky.social", request=request)
    await client.me()
    return client, request


def _sdk_client(client: SafeBlueskyClient) -> GuardedAsyncClient:
    # Reach the private SDK client only to prove the guard holds even if code bypassed the wrapper.
    # getattr is needed to reach the name-mangled private attribute on purpose.
    sdk = getattr(client, "_SafeBlueskyClient__client")  # noqa: B009
    assert isinstance(sdk, GuardedAsyncClient)
    return sdk


async def test_sdk_cannot_publish_even_when_called_directly() -> None:
    client, request = await _signed_in()
    sdk = _sdk_client(client)
    before = len(request.calls)
    with pytest.raises(ops.ForbiddenOperationError):
        await sdk.send_post("this must never be published")
    with pytest.raises(ops.ForbiddenOperationError):
        await sdk.com.atproto.repo.create_record(
            {"repo": OWNER_DID, "collection": ops.POST, "record": {"text": "x"}}
        )
    assert len(request.calls) == before, "a forbidden request reached the network layer"


async def test_sdk_cannot_block_or_delete_drafts() -> None:
    client, request = await _signed_in()
    sdk = _sdk_client(client)
    before = len(request.calls)
    with pytest.raises(ops.ForbiddenOperationError):
        await sdk.com.atproto.repo.create_record(
            {"repo": OWNER_DID, "collection": "app.bsky.graph.block", "record": {}}
        )
    with pytest.raises(ops.ForbiddenOperationError):
        await sdk.app.bsky.draft.delete_draft({"id": "3kdraft"})
    with pytest.raises(ops.ForbiddenOperationError):
        await sdk.app.bsky.graph.mute_actor({"actor": "someone.bsky.social"})
    assert len(request.calls) == before


def test_wrapper_surface_has_no_forbidden_methods() -> None:
    public = {
        name
        for name, _ in inspect.getmembers(SafeBlueskyClient, inspect.isfunction)
        if not name.startswith("_")
    }
    assert public == {
        "me",
        "timeline",
        "notifications",
        "thread",
        "profile",
        "author_posts",
        "followers",
        "follows",
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
        "delete_own_post",
        # spec 002
        "quotes",
        "likes",
        "reposted_by",
        "feed",
        "feed_info",
        "account_feeds",
        "suggested_feeds",
        "search_feeds",
        "suggested_follows",
        "similar_accounts",
        "trending_topics",
        "search_starter_packs",
        "starter_pack",
        "account_starter_packs",
        "lists",
        "list_detail",
        "list_feed",
        "create_list",
        "add_to_list",
        "remove_from_list",
        "delete_own_list",
    }
    for banned in ("post", "publish", "send", "block", "delete_draft", "mute"):
        assert not any(name == banned or name.startswith(f"{banned}_") for name in public)


def test_sdk_client_is_not_exposed() -> None:
    client = SafeBlueskyClient(OWNER_HANDLE, "app-pass", "https://bsky.social")
    for name in dir(client):
        if name.startswith("_SafeBlueskyClient__"):
            continue
        try:
            value = getattr(client, name)
        except Exception:  # noqa: S112 - properties that need a session raise; that's fine
            continue
        assert not isinstance(value, GuardedAsyncClient), name


async def test_lowest_request_path_is_guarded() -> None:
    from atproto_client.client.base import InvokeType

    client, request = await _signed_in()
    sdk = _sdk_client(client)
    before = len(request.calls)
    with pytest.raises(ops.ForbiddenOperationError):
        await sdk._invoke(  # noqa: SLF001 - deliberately bypassing the public SDK methods
            InvokeType.PROCEDURE, url="https://bsky.social/xrpc/app.bsky.draft.deleteDraft"
        )
    assert len(request.calls) == before
