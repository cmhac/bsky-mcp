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

# Collections the server may create records in. Posts are deliberately absent: the server cannot
# publish (Principle III). Blocks are absent (Principle II).
CREATABLE_COLLECTIONS = frozenset({FOLLOW, LIKE, REPOST})

# Collections the server may delete the owner's own records from (Principle II).
DELETABLE_COLLECTIONS = frozenset({FOLLOW, LIKE, REPOST, POST})

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
