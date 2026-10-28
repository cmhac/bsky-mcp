"""Shared fixtures: settings, a fake Bluesky backend, and an in-memory MCP client."""

from __future__ import annotations

import base64
import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

import pytest
from fastmcp import Client

from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.bluesky.client import BlueskyError, DraftPostInput, validate_draft_posts
from bsky_mcp.bluesky.text import parse_actor, parse_post
from bsky_mcp.server import create_server

OWNER_DID = "did:plc:owner"
OWNER_HANDLE = "owner.bsky.social"
OTHER_DID = "did:plc:other"
OTHER_HANDLE = "other.bsky.social"

ENV_KEYS = (
    "BLUESKY_HANDLE",
    "BLUESKY_APP_PASSWORD",
    "BLUESKY_SERVICE",
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "ALLOWED_GITHUB_USER_IDS",
    "BASE_URL",
    "JWT_SIGNING_KEY",
    "STORAGE_ENCRYPTION_KEY",
    "REDIS_URL",
    "ALLOWED_IP_RANGES",
    "IP_ALLOWLIST_EXEMPT_PATHS",
    "ALLOWED_CLIENT_REDIRECT_URIS",
    "UNSAFE_DISABLE_OAUTH",
    "UNSAFE_DISABLE_IP_ALLOWLIST",
    "LOG_LEVEL",
    "VERCEL_ENV",
    "VERCEL",
)


def valid_env() -> dict[str, str]:
    return {
        "GITHUB_CLIENT_ID": "client-id",
        "GITHUB_CLIENT_SECRET": "github-secret-value-123",
        "ALLOWED_GITHUB_USER_IDS": "49451910",
        "BASE_URL": "https://bsky-mcp.example.test",
        "JWT_SIGNING_KEY": base64.b64encode(b"k" * 32).decode(),
        "STORAGE_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"f" * 32).decode(),
        "REDIS_URL": "rediss://default:redis-token-xyz@localhost:6379",
    }


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key in list(os.environ):
        if key.startswith("VERCEL"):
            monkeypatch.delenv(key, raising=False)
    yield monkeypatch


@pytest.fixture
def env(clean_env: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for key, value in valid_env().items():
        clean_env.setenv(key, value)
    return clean_env


def _post(did: str, handle: str, rkey: str, text: str) -> dict[str, Any]:
    return {
        "uri": f"at://{did}/app.bsky.feed.post/{rkey}",
        "cid": f"cid-{rkey}",
        "author": {"did": did, "handle": handle},
        "text": text,
    }


@dataclass
class FakeBluesky:
    """In-memory implementation of BlueskyAPI for tool contract tests."""

    posts: dict[str, dict[str, Any]] = field(default_factory=dict)
    drafts: dict[str, list[DraftPostInput]] = field(default_factory=dict)
    following: set[str] = field(default_factory=set)
    likes: set[str] = field(default_factory=set)
    reposts: set[str] = field(default_factory=set)
    calls: list[str] = field(default_factory=list)
    next_draft: int = 1

    def __post_init__(self) -> None:
        for post in (
            _post(OWNER_DID, OWNER_HANDLE, "own1", "my post"),
            _post(OTHER_DID, OTHER_HANDLE, "other1", "their post"),
        ):
            self.posts[post["uri"]] = post

    def _view(self, post: dict[str, Any]) -> fmt.PostView:
        return fmt.PostView(
            uri=post["uri"],
            url=fmt.post_url(post["author"]["handle"], post["uri"]),
            author_handle=post["author"]["handle"],
            text=post["text"],
            viewer_liked=post["uri"] in self.likes,
            viewer_reposted=post["uri"] in self.reposts,
        )

    def _find(self, post: str) -> dict[str, Any]:
        ref = parse_post(post)
        did = {OWNER_HANDLE: OWNER_DID, OTHER_HANDLE: OTHER_DID}.get(ref.actor, ref.actor)
        found = self.posts.get(ref.at_uri(did))
        if found is None:
            raise BlueskyError("not_found", "That post was not found or is not visible.")
        return found

    def _profile(self, actor: str) -> fmt.ProfileView:
        actor = parse_actor(actor)
        handle = {OWNER_DID: OWNER_HANDLE, OTHER_DID: OTHER_HANDLE}.get(actor, actor)
        if handle not in (OWNER_HANDLE, OTHER_HANDLE):
            raise BlueskyError("not_found", "Profile not found.")
        return fmt.ProfileView(
            did=OWNER_DID if handle == OWNER_HANDLE else OTHER_DID,
            handle=handle,
            url=f"https://bsky.app/profile/{handle}",
            you_follow=handle in self.following,
        )

    def _page(self) -> fmt.PostPage:
        return fmt.PostPage(posts=[self._view(p) for p in self.posts.values()], cursor="next")

    async def me(self) -> fmt.ProfileView:
        self.calls.append("me")
        return self._profile(OWNER_HANDLE)

    async def timeline(self, limit: int, cursor: str | None) -> fmt.PostPage:
        self.calls.append(f"timeline:{limit}:{cursor}")
        return self._page()

    async def notifications(
        self, limit: int, cursor: str | None, unread_only: bool
    ) -> fmt.NotificationPage:
        self.calls.append(f"notifications:{limit}:{unread_only}")
        items = [
            fmt.NotificationView(
                reason="like", author_handle=OTHER_HANDLE, indexed_at="2026-10-28", is_read=False
            ),
            fmt.NotificationView(
                reason="follow", author_handle=OTHER_HANDLE, indexed_at="2026-10-27", is_read=True
            ),
        ]
        if unread_only:
            items = [i for i in items if not i.is_read]
        return fmt.NotificationPage(notifications=items, cursor=None)

    async def thread(self, post: str, depth: int, parent_height: int) -> fmt.ThreadView:
        self.calls.append(f"thread:{depth}:{parent_height}")
        return fmt.ThreadView(post=self._view(self._find(post)), parents=[], replies=[])

    async def profile(self, actor: str) -> fmt.ProfileView:
        return self._profile(actor)

    async def author_posts(
        self, actor: str, limit: int, cursor: str | None, include_replies: bool
    ) -> fmt.PostPage:
        parse_actor(actor)
        self.calls.append(f"author_posts:{include_replies}")
        return self._page()

    async def followers(self, actor: str | None, limit: int, cursor: str | None) -> fmt.ProfilePage:
        self.calls.append(f"followers:{actor}")
        return fmt.ProfilePage(profiles=[self._profile(OTHER_HANDLE)])

    async def follows(self, actor: str | None, limit: int, cursor: str | None) -> fmt.ProfilePage:
        self.calls.append(f"follows:{actor}")
        return fmt.ProfilePage(profiles=[self._profile(h) for h in self.following])

    async def search_posts(
        self,
        query: str,
        limit: int,
        cursor: str | None,
        sort: Literal["top", "latest"],
        author: str | None,
    ) -> fmt.PostPage:
        self.calls.append(f"search_posts:{query}:{sort}:{author}")
        return self._page()

    async def search_users(self, query: str, limit: int, cursor: str | None) -> fmt.ProfilePage:
        self.calls.append(f"search_users:{query}")
        return fmt.ProfilePage(profiles=[self._profile(OTHER_HANDLE)])

    def _draft_view(self, draft_id: str) -> fmt.DraftView:
        return fmt.DraftView(
            draft_id=draft_id,
            posts=[
                fmt.DraftPostView(text=p.text, quote_uri=p.quote, link_url=p.link_url)
                for p in self.drafts[draft_id]
            ],
        )

    async def create_draft(
        self, posts: list[DraftPostInput], langs: list[str] | None
    ) -> fmt.DraftView:
        validate_draft_posts(posts, langs)
        for p in posts:
            if p.quote:
                self._find(p.quote)
        draft_id = f"draft{self.next_draft}"
        self.next_draft += 1
        self.drafts[draft_id] = list(posts)
        return self._draft_view(draft_id)

    async def update_draft(
        self, draft_id: str, posts: list[DraftPostInput], langs: list[str] | None
    ) -> fmt.DraftView:
        validate_draft_posts(posts, langs)
        if draft_id not in self.drafts:
            raise BlueskyError("draft_not_found", f"No draft with ID {draft_id} was found.")
        self.drafts[draft_id] = list(posts)
        return self._draft_view(draft_id)

    async def list_drafts(self, limit: int, cursor: str | None) -> fmt.DraftPage:
        return fmt.DraftPage(drafts=[self._draft_view(d) for d in self.drafts][:limit])

    def _result(self, action: str, subject: str, changed: bool) -> fmt.EngagementResult:
        msg = "Done." if changed else "Nothing to undo." if action.startswith("un") else "Already."
        return fmt.EngagementResult(action=action, subject=subject, changed=changed, message=msg)

    async def follow(self, actor: str) -> fmt.EngagementResult:
        handle = self._profile(actor).handle
        changed = handle not in self.following
        self.following.add(handle)
        return self._result("follow", handle, changed)

    async def unfollow(self, actor: str) -> fmt.EngagementResult:
        handle = self._profile(actor).handle
        changed = handle in self.following
        self.following.discard(handle)
        return self._result("unfollow", handle, changed)

    async def _toggle(self, post: str, store: set[str], action: str, add: bool):
        uri = self._find(post)["uri"]
        changed = (uri not in store) if add else (uri in store)
        (store.add if add else store.discard)(uri)
        return self._result(action, uri, changed)

    async def like(self, post: str) -> fmt.EngagementResult:
        return await self._toggle(post, self.likes, "like", True)

    async def unlike(self, post: str) -> fmt.EngagementResult:
        return await self._toggle(post, self.likes, "unlike", False)

    async def repost(self, post: str) -> fmt.EngagementResult:
        return await self._toggle(post, self.reposts, "repost", True)

    async def unrepost(self, post: str) -> fmt.EngagementResult:
        return await self._toggle(post, self.reposts, "unrepost", False)

    async def delete_own_post(self, post: str) -> fmt.DeletedPost:
        found = self._find(post)
        if found["author"]["did"] != OWNER_DID:
            raise BlueskyError("not_owner", "You can only delete your own posts.")
        del self.posts[found["uri"]]
        self.calls.append(f"delete:{found['uri']}")
        view = self._view(found)
        return fmt.DeletedPost(deleted=True, url=view.url, text=view.text)


OWN_POST_URL = f"https://bsky.app/profile/{OWNER_HANDLE}/post/own1"
OTHER_POST_URL = f"https://bsky.app/profile/{OTHER_HANDLE}/post/other1"


@pytest.fixture
def fake() -> FakeBluesky:
    return FakeBluesky()


@pytest.fixture
async def client(fake: FakeBluesky) -> AsyncIterator[Client]:
    mcp = create_server(lambda: fake)
    async with Client(mcp) as c:
        yield c
