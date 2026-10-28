"""A fake atproto request layer that records every XRPC call and returns canned JSON.

Used by the safety tests to exercise the real SafeBlueskyClient and GuardedAsyncClient without a
network connection.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from typing import Any

from atproto_client.request import AsyncRequest, Response

OWNER_DID = "did:plc:owner"
OWNER_HANDLE = "owner.bsky.social"
OTHER_DID = "did:plc:other"


def _b64(data: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


def fake_jwt(did: str = OWNER_DID) -> str:
    now = int(time.time())
    header = _b64({"alg": "HS256", "typ": "JWT"})
    payload = _b64({"sub": did, "iat": now, "exp": now + 3600, "scope": "com.atproto.appPass"})
    return f"{header}.{payload}.sig"


def post_view(did: str, rkey: str, text: str, viewer: dict[str, Any] | None = None):
    handle = OWNER_HANDLE if did == OWNER_DID else "other.bsky.social"
    return {
        "uri": f"at://{did}/app.bsky.feed.post/{rkey}",
        "cid": "bafyreib2rxk3rh6kzwq",
        "author": {"did": did, "handle": handle},
        "record": {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": "2026-10-28T00:00:00Z",
        },
        "indexedAt": "2026-10-28T00:00:00Z",
        "viewer": viewer or {},
    }


def default_routes() -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    posts = {
        f"at://{OWNER_DID}/app.bsky.feed.post/own1": post_view(
            OWNER_DID,
            "own1",
            "mine",
            {
                "like": f"at://{OWNER_DID}/app.bsky.feed.like/l1",
                "repost": f"at://{OWNER_DID}/app.bsky.feed.repost/r1",
            },
        ),
        f"at://{OTHER_DID}/app.bsky.feed.post/other1": post_view(OTHER_DID, "other1", "theirs"),
    }
    return {
        "com.atproto.server.createSession": lambda _: {
            "accessJwt": fake_jwt(),
            "refreshJwt": fake_jwt(),
            "handle": OWNER_HANDLE,
            "did": OWNER_DID,
        },
        "app.bsky.actor.getProfile": lambda p: {
            "did": OWNER_DID if p.get("actor") in (OWNER_HANDLE, OWNER_DID) else OTHER_DID,
            "handle": p.get("actor") if "." in str(p.get("actor")) else OWNER_HANDLE,
            "viewer": {"following": f"at://{OWNER_DID}/app.bsky.graph.follow/f1"},
        },
        "com.atproto.identity.resolveHandle": lambda p: {
            "did": OWNER_DID if p.get("handle") == OWNER_HANDLE else OTHER_DID
        },
        "app.bsky.feed.getPosts": lambda p: {
            "posts": [posts[u] for u in _as_list(p.get("uris")) if u in posts]
        },
        "com.atproto.repo.createRecord": lambda _: {
            "uri": f"at://{OWNER_DID}/app.bsky.feed.like/new",
            "cid": "bafyreinew",
        },
        "com.atproto.repo.deleteRecord": lambda _: {},
        "app.bsky.draft.createDraft": lambda _: {"id": "3kdraft"},
        "app.bsky.draft.getDrafts": lambda _: {
            "drafts": [
                {
                    "id": "3kdraft",
                    "createdAt": "2026-10-28T00:00:00Z",
                    "updatedAt": "2026-10-28T00:00:00Z",
                    "draft": {"posts": [{"text": "hello"}]},
                }
            ]
        },
        "app.bsky.draft.updateDraft": lambda _: {},
    }


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class RecordingRequest(AsyncRequest):
    """Stands in for the HTTP layer. Records (nsid, params, body) for every request."""

    def __init__(self, routes=None) -> None:
        super().__init__()
        self.routes = routes or default_routes()
        self.calls: list[tuple[str, dict[str, Any], Any]] = []

    def _record(self, url: str, params: Any, data: Any) -> Response:
        nsid = url.rsplit("/xrpc/", 1)[-1]
        params = dict(params or {})
        body = json.loads(data) if isinstance(data, (str, bytes)) and data else data
        self.calls.append((nsid, params, body))
        handler = self.routes.get(nsid)
        if handler is None:
            raise AssertionError(f"unexpected request {nsid}")
        content = handler(params)
        return Response(success=True, status_code=200, content=content, headers={})

    async def get(self, *args: Any, **kwargs: Any) -> Response:
        return self._record(kwargs["url"], kwargs.get("params"), kwargs.get("content"))

    async def post(self, *args: Any, **kwargs: Any) -> Response:
        return self._record(kwargs["url"], kwargs.get("params"), kwargs.get("content"))

    def nsids(self) -> list[str]:
        return [c[0] for c in self.calls]
