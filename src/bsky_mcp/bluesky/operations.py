"""The single source of truth for which AT Protocol operations this server may call.

Every request the Bluesky client sends is checked against these sets before it leaves the process
(see ``client.GuardedAsyncClient``). Anything not listed is rejected. Constitution Principles II and
III depend on this file; changes require a spec and tests.
"""

from __future__ import annotations

from typing import Any

# Session management performed by the SDK itself.
SESSION_OPERATIONS = frozenset(
    {
        "com.atproto.server.createSession",
        "com.atproto.server.refreshSession",
        "com.atproto.server.getSession",
    }
)

READ_OPERATIONS = frozenset(
    {
        "app.bsky.actor.getProfile",
        "app.bsky.actor.searchActors",
        "app.bsky.feed.getAuthorFeed",
        "app.bsky.feed.getPostThread",
        "app.bsky.feed.getPosts",
        "app.bsky.feed.getTimeline",
        "app.bsky.feed.searchPosts",
        "app.bsky.graph.getFollowers",
        "app.bsky.graph.getFollows",
        "app.bsky.notification.listNotifications",
        "com.atproto.identity.resolveHandle",
        # Discovery (spec 002)
        "app.bsky.actor.getSuggestions",
        "app.bsky.feed.getActorFeeds",
        "app.bsky.feed.getFeed",
        "app.bsky.feed.getFeedGenerator",
        "app.bsky.feed.getLikes",
        "app.bsky.feed.getListFeed",
        "app.bsky.feed.getQuotes",
        "app.bsky.feed.getRepostedBy",
        "app.bsky.feed.getSuggestedFeeds",
        "app.bsky.graph.getActorStarterPacks",
        "app.bsky.graph.getList",
        "app.bsky.graph.getLists",
        "app.bsky.graph.getListsWithMembership",
        "app.bsky.graph.getStarterPack",
        "app.bsky.graph.getSuggestedFollowsByActor",
        "app.bsky.graph.searchStarterPacks",
        "app.bsky.unspecced.getPopularFeedGenerators",
        "app.bsky.unspecced.getTrendingTopics",
    }
)

# Drafts: create, read, update. Never delete.
DRAFT_OPERATIONS = frozenset(
    {
        "app.bsky.draft.createDraft",
        "app.bsky.draft.getDrafts",
        "app.bsky.draft.updateDraft",
    }
)

CREATE_RECORD = "com.atproto.repo.createRecord"
DELETE_RECORD = "com.atproto.repo.deleteRecord"

FOLLOW = "app.bsky.graph.follow"
LIKE = "app.bsky.feed.like"
REPOST = "app.bsky.feed.repost"
POST = "app.bsky.feed.post"
LIST = "app.bsky.graph.list"
LIST_ITEM = "app.bsky.graph.listitem"
CURATE_LIST_PURPOSE = "app.bsky.graph.defs#curatelist"

# Collections the server may create records in. Posts are deliberately absent: the server cannot
# publish (Principle III). Blocks and list blocks are absent (Principle II). Lists are limited to
# curation lists, and list items to lists in the owner's repo (checked below).
CREATABLE_COLLECTIONS = frozenset({FOLLOW, LIKE, REPOST, LIST, LIST_ITEM})

# Collections the server may delete the owner's own records from (Principle II).
DELETABLE_COLLECTIONS = frozenset({FOLLOW, LIKE, REPOST, POST, LIST, LIST_ITEM})

ALLOWED_OPERATIONS = (
    SESSION_OPERATIONS | READ_OPERATIONS | DRAFT_OPERATIONS | {CREATE_RECORD, DELETE_RECORD}
)


class ForbiddenOperationError(PermissionError):
    """Raised when code attempts an operation outside the allowlist."""

    code = "forbidden_operation"


def _field(data: Any, name: str) -> Any:
    if data is None:
        return None
    if isinstance(data, dict):
        return data.get(name)
    return getattr(data, name, None)


def check_operation(nsid: str, data: Any = None, own_did: str | None = None) -> None:
    """Raise ForbiddenOperationError unless this request is allowed.

    For record writes, the collection must be allowlisted and the target repo must be the
    signed-in account (``own_did``).
    """
    if nsid not in ALLOWED_OPERATIONS:
        raise ForbiddenOperationError(f"Operation {nsid} is not permitted by this server.")
    if nsid not in (CREATE_RECORD, DELETE_RECORD):
        return

    collection = _field(data, "collection")
    allowed = CREATABLE_COLLECTIONS if nsid == CREATE_RECORD else DELETABLE_COLLECTIONS
    if collection not in allowed:
        raise ForbiddenOperationError(f"{nsid} on collection {collection!r} is not permitted.")
    repo = _field(data, "repo")
    if own_did is None or repo != own_did:
        raise ForbiddenOperationError("Record writes are only permitted in the owner's own repo.")
    if nsid == CREATE_RECORD:
        _check_record_content(collection, _field(data, "record"), own_did)


def _check_record_content(collection: str, record: Any, own_did: str) -> None:
    """Content rules for records whose collection alone is not enough to judge."""
    if collection == LIST and _field(record, "purpose") != CURATE_LIST_PURPOSE:
        raise ForbiddenOperationError("Only curation lists may be created; no mute or block lists.")
    if collection == LIST_ITEM:
        list_uri = str(_field(record, "list") or "")
        if not list_uri.startswith(f"at://{own_did}/{LIST}/"):
            raise ForbiddenOperationError("List members may only be added to the owner's lists.")
