"""Bluesky access restricted to the operations in ``operations.py``.

Two layers enforce the allowlist:

1. ``GuardedAsyncClient`` overrides the SDK's single request path (``invoke_query`` and
   ``invoke_procedure``), so any request outside the allowlist is rejected before it is sent, no
   matter which SDK method produced it.
2. ``SafeBlueskyClient`` exposes only the methods the tools need and keeps the SDK client private.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from atproto import AsyncClient, models
from atproto_client.exceptions import (
    BadRequestError,
    NetworkError,
    RequestErrorBase,
    UnauthorizedError,
)
from atproto_client.request import AsyncRequest
from pydantic import BaseModel, Field

from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.bluesky import operations as ops
from bsky_mcp.bluesky.text import (
    InvalidInputError,
    PostRef,
    parse_actor,
    parse_https_url,
    parse_post,
    validate_post_text,
)

REQUEST_TIMEOUT_SECONDS = 10.0
DRAFT_DEVICE_NAME = "Claude (bsky-mcp)"
MAX_DRAFT_POSTS = 100
MAX_LANGS = 3
DRAFT_SCAN_PAGES = 5


class BlueskyError(Exception):
    """An error safe to show to the caller. Messages never contain credentials."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DraftPostInput(BaseModel):
    """One post in a draft. A draft with several posts is a thread."""

    text: str = Field(default="", description="Post text, at most 300 graphemes.")
    quote: str | None = Field(
        default=None, description="Optional post to quote: a bsky.app post URL or at:// URI."
    )
    link_url: str | None = Field(default=None, description="Optional https link card.")


class BlueskyAPI(Protocol):
    """The operations tools may use. Implemented by SafeBlueskyClient and by test fakes."""

    async def me(self) -> fmt.ProfileView: ...
    async def timeline(self, limit: int, cursor: str | None) -> fmt.PostPage: ...
    async def notifications(
        self, limit: int, cursor: str | None, unread_only: bool
    ) -> fmt.NotificationPage: ...
    async def thread(self, post: str, depth: int, parent_height: int) -> fmt.ThreadView: ...
    async def profile(self, actor: str) -> fmt.ProfileView: ...
    async def author_posts(
        self, actor: str, limit: int, cursor: str | None, include_replies: bool
    ) -> fmt.PostPage: ...
    async def followers(
        self, actor: str | None, limit: int, cursor: str | None
    ) -> fmt.ProfilePage: ...
    async def follows(
        self, actor: str | None, limit: int, cursor: str | None
    ) -> fmt.ProfilePage: ...
    async def search_posts(
        self,
        query: str,
        limit: int,
        cursor: str | None,
        sort: Literal["top", "latest"],
        author: str | None,
    ) -> fmt.PostPage: ...
    async def search_users(self, query: str, limit: int, cursor: str | None) -> fmt.ProfilePage: ...
    async def create_draft(
        self, posts: list[DraftPostInput], langs: list[str] | None
    ) -> fmt.DraftView: ...
    async def update_draft(
        self, draft_id: str, posts: list[DraftPostInput], langs: list[str] | None
    ) -> fmt.DraftView: ...
    async def list_drafts(self, limit: int, cursor: str | None) -> fmt.DraftPage: ...
    async def follow(self, actor: str) -> fmt.EngagementResult: ...
    async def unfollow(self, actor: str) -> fmt.EngagementResult: ...
    async def like(self, post: str) -> fmt.EngagementResult: ...
    async def unlike(self, post: str) -> fmt.EngagementResult: ...
    async def repost(self, post: str) -> fmt.EngagementResult: ...
    async def unrepost(self, post: str) -> fmt.EngagementResult: ...
    async def delete_own_post(self, post: str) -> fmt.DeletedPost: ...


def validate_draft_posts(posts: list[DraftPostInput], langs: list[str] | None) -> None:
    """Shared draft validation: 1-100 posts, each at most 300 graphemes, non-empty, https links."""
    if not 1 <= len(posts) <= MAX_DRAFT_POSTS:
        raise InvalidInputError(f"A draft needs between 1 and {MAX_DRAFT_POSTS} posts.")
    if langs is not None and len(langs) > MAX_LANGS:
        raise InvalidInputError(f"At most {MAX_LANGS} languages are allowed.")
    for index, post in enumerate(posts):
        validate_post_text(post.text, index)
        if not post.text.strip() and not post.quote and not post.link_url:
            raise InvalidInputError(f"Post {index + 1} is empty and has nothing attached.")
        if post.link_url is not None:
            parse_https_url(post.link_url)
        if post.quote is not None:
            parse_post(post.quote)


class GuardedAsyncClient(AsyncClient):
    """atproto AsyncClient that refuses any request outside the operation allowlist."""

    own_did: str | None = None

    async def invoke_query(self, nsid: str, params: Any = None, data: Any = None, **kwargs: Any):
        ops.check_operation(nsid, data, self.own_did)
        return await super().invoke_query(nsid, params=params, data=data, **kwargs)

    async def invoke_procedure(
        self, nsid: str, params: Any = None, data: Any = None, **kwargs: Any
    ):
        ops.check_operation(nsid, data, self.own_did)
        return await super().invoke_procedure(nsid, params=params, data=data, **kwargs)

    async def _invoke(self, invoke_type: Any, **kwargs: Any):
        # The SDK's single request path. Checked again here so that any future SDK method that
        # skips invoke_query/invoke_procedure is still covered.
        nsid = str(kwargs.get("url", "")).rsplit("/xrpc/", 1)[-1]
        ops.check_operation(nsid, kwargs.get("data"), self.own_did)
        return await super()._invoke(invoke_type, **kwargs)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _result(
    action: str, subject: str, record_uri: str | None, changed: bool, message: str
) -> fmt.EngagementResult:
    return fmt.EngagementResult(
        action=action, subject=subject, record_uri=record_uri, changed=changed, message=message
    )


def _translate_error(exc: RequestErrorBase) -> BlueskyError:
    if isinstance(exc, UnauthorizedError):
        return BlueskyError("bluesky_auth_failed", "Bluesky rejected the app password or session.")
    if isinstance(exc, NetworkError):
        return BlueskyError("bluesky_unavailable", "Bluesky did not respond in time. Try again.")
    if isinstance(exc, BadRequestError):
        content = exc.response.content if exc.response is not None else None
        error = getattr(content, "error", None) or ""
        message = getattr(content, "message", None) or ""
        if "NotFound" in error or "not found" in message.lower():
            return BlueskyError("not_found", message or "Not found on Bluesky.")
        return BlueskyError("invalid_input", message or "Bluesky rejected the request.")
    status = exc.response.status_code if exc.response is not None else None
    if status == 429:
        return BlueskyError("bluesky_unavailable", "Bluesky rate limit reached. Try again later.")
    return BlueskyError("bluesky_unavailable", "Bluesky returned an error. Try again later.")


class SafeBlueskyClient:
    """The only Bluesky interface the tools use. Holds the SDK client privately."""

    __slots__ = ("__client", "__handle", "__password", "__lock", "__did")

    def __init__(
        self,
        handle: str | None,
        app_password: str | None,
        service: str,
        request: AsyncRequest | None = None,
    ) -> None:
        self.__client = GuardedAsyncClient(
            base_url=service, request=request or AsyncRequest(timeout=REQUEST_TIMEOUT_SECONDS)
        )
        self.__handle = handle
        self.__password = app_password
        self.__lock = asyncio.Lock()
        self.__did: str | None = None

    # -- session ---------------------------------------------------------------------------

    async def _session(self) -> GuardedAsyncClient:
        if not self.__handle or not self.__password:
            raise BlueskyError("not_configured", "Bluesky credentials are not configured here.")
        async with self.__lock:
            if self.__did is None:
                try:
                    profile = await self.__client.login(self.__handle, self.__password)
                except RequestErrorBase as exc:
                    raise _translate_error(exc) from None
                did = profile.did if profile is not None else None
                if did is None:
                    resolved = await self.__client.com.atproto.identity.resolve_handle(
                        {"handle": self.__handle}
                    )
                    did = resolved.did
                self.__client.own_did = did
                self.__did = did
        return self.__client

    async def _call[T](self, fn: Callable[[GuardedAsyncClient], Awaitable[T]]) -> T:
        client = await self._session()
        try:
            return await fn(client)
        except UnauthorizedError:
            # The session may have expired beyond refresh; sign in again on the next call.
            self.__did = None
            client.own_did = None
            raise _translate_error(UnauthorizedError()) from None
        except RequestErrorBase as exc:
            raise _translate_error(exc) from None

    async def _own_did(self) -> str:
        await self._session()
        return self._did

    @property
    def _did(self) -> str:
        if self.__did is None:
            raise BlueskyError("not_configured", "Not signed in to Bluesky.")
        return self.__did

    async def _resolve_did(self, actor: str) -> str:
        actor = parse_actor(actor)
        if actor.startswith("did:"):
            return actor
        resolved = await self._call(
            lambda c: c.com.atproto.identity.resolve_handle({"handle": actor})
        )
        return resolved.did

    async def _get_post(self, post: str) -> Any:
        ref: PostRef = parse_post(post)
        did = await self._resolve_did(ref.actor)
        uri = ref.at_uri(did)
        response = await self._call(lambda c: c.app.bsky.feed.get_posts({"uris": [uri]}))
        if not response.posts:
            raise BlueskyError("not_found", "That post was not found or is not visible.")
        return response.posts[0]

    # -- reads -----------------------------------------------------------------------------

    async def me(self) -> fmt.ProfileView:
        await self._session()
        return await self.profile(self._did)

    async def timeline(self, limit: int, cursor: str | None) -> fmt.PostPage:
        res = await self._call(
            lambda c: c.app.bsky.feed.get_timeline({"limit": limit, "cursor": cursor})
        )
        return fmt.PostPage(posts=[fmt.to_post(item.post) for item in res.feed], cursor=res.cursor)

    async def notifications(
        self, limit: int, cursor: str | None, unread_only: bool
    ) -> fmt.NotificationPage:
        res = await self._call(
            lambda c: c.app.bsky.notification.list_notifications({"limit": limit, "cursor": cursor})
        )
        items = [fmt.to_notification(n) for n in res.notifications]
        if unread_only:
            items = [n for n in items if not n.is_read]
        return fmt.NotificationPage(notifications=items, cursor=res.cursor)

    async def thread(self, post: str, depth: int, parent_height: int) -> fmt.ThreadView:
        ref = parse_post(post)
        did = await self._resolve_did(ref.actor)
        res = await self._call(
            lambda c: c.app.bsky.feed.get_post_thread(
                {"uri": ref.at_uri(did), "depth": depth, "parent_height": parent_height}
            )
        )
        try:
            return fmt.to_thread(res.thread)
        except LookupError as exc:
            raise BlueskyError("not_found", str(exc)) from None

    async def profile(self, actor: str) -> fmt.ProfileView:
        actor = parse_actor(actor)
        res = await self._call(lambda c: c.app.bsky.actor.get_profile({"actor": actor}))
        return fmt.to_profile(res)

    async def author_posts(
        self, actor: str, limit: int, cursor: str | None, include_replies: bool
    ) -> fmt.PostPage:
        actor = parse_actor(actor)
        feed_filter = "posts_with_replies" if include_replies else "posts_no_replies"
        res = await self._call(
            lambda c: c.app.bsky.feed.get_author_feed(
                {"actor": actor, "limit": limit, "cursor": cursor, "filter": feed_filter}
            )
        )
        return fmt.PostPage(posts=[fmt.to_post(item.post) for item in res.feed], cursor=res.cursor)

    async def _graph_page(
        self,
        kind: Literal["followers", "follows"],
        actor: str | None,
        limit: int,
        cursor: str | None,
    ) -> fmt.ProfilePage:
        target = parse_actor(actor) if actor else await self._own_did()
        if kind == "followers":
            followers_params = models.AppBskyGraphGetFollowers.Params(
                actor=target, limit=limit, cursor=cursor
            )
            res: Any = await self._call(lambda c: c.app.bsky.graph.get_followers(followers_params))
            profiles = res.followers
        else:
            follows_params = models.AppBskyGraphGetFollows.Params(
                actor=target, limit=limit, cursor=cursor
            )
            res = await self._call(lambda c: c.app.bsky.graph.get_follows(follows_params))
            profiles = res.follows
        return fmt.ProfilePage(profiles=[fmt.to_profile(p) for p in profiles], cursor=res.cursor)

    async def followers(self, actor: str | None, limit: int, cursor: str | None) -> fmt.ProfilePage:
        return await self._graph_page("followers", actor, limit, cursor)

    async def follows(self, actor: str | None, limit: int, cursor: str | None) -> fmt.ProfilePage:
        return await self._graph_page("follows", actor, limit, cursor)

    async def search_posts(
        self,
        query: str,
        limit: int,
        cursor: str | None,
        sort: Literal["top", "latest"],
        author: str | None,
    ) -> fmt.PostPage:
        params = models.AppBskyFeedSearchPosts.Params(
            q=query,
            limit=limit,
            cursor=cursor,
            sort=sort,
            author=parse_actor(author) if author else None,
        )
        res = await self._call(lambda c: c.app.bsky.feed.search_posts(params))
        return fmt.PostPage(posts=[fmt.to_post(p) for p in res.posts], cursor=res.cursor)

    async def search_users(self, query: str, limit: int, cursor: str | None) -> fmt.ProfilePage:
        res = await self._call(
            lambda c: c.app.bsky.actor.search_actors({"q": query, "limit": limit, "cursor": cursor})
        )
        return fmt.ProfilePage(profiles=[fmt.to_profile(p) for p in res.actors], cursor=res.cursor)

    # -- drafts ----------------------------------------------------------------------------

    async def _draft_model(
        self, posts: list[DraftPostInput], langs: list[str] | None
    ) -> models.AppBskyDraftDefs.Draft:
        validate_draft_posts(posts, langs)
        draft_posts = []
        for item in posts:
            records = None
            if item.quote:
                quoted = await self._get_post(item.quote)
                records = [
                    models.AppBskyDraftDefs.DraftEmbedRecord(
                        record=models.ComAtprotoRepoStrongRef.Main(uri=quoted.uri, cid=quoted.cid)
                    )
                ]
            externals = (
                [models.AppBskyDraftDefs.DraftEmbedExternal(uri=parse_https_url(item.link_url))]
                if item.link_url
                else None
            )
            draft_posts.append(
                models.AppBskyDraftDefs.DraftPost(
                    text=item.text, embed_records=records, embed_externals=externals
                )
            )
        return models.AppBskyDraftDefs.Draft(
            posts=draft_posts, device_name=DRAFT_DEVICE_NAME, langs=langs
        )

    async def _find_draft(self, draft_id: str) -> Any | None:
        cursor: str | None = None
        for _ in range(DRAFT_SCAN_PAGES):
            page = await self._call(
                lambda c, cur=cursor: c.app.bsky.draft.get_drafts({"limit": 100, "cursor": cur})
            )
            for view in page.drafts:
                if view.id == draft_id:
                    return view
            cursor = page.cursor
            if not cursor:
                return None
        return None

    async def create_draft(
        self, posts: list[DraftPostInput], langs: list[str] | None
    ) -> fmt.DraftView:
        draft = await self._draft_model(posts, langs)
        res = await self._call(
            lambda c: c.app.bsky.draft.create_draft(
                models.AppBskyDraftCreateDraft.Data(draft=draft)
            )
        )
        view = await self._find_draft(res.id)
        if view is None:
            return fmt.DraftView(
                draft_id=res.id,
                posts=[fmt.DraftPostView(text=p.text, link_url=p.link_url) for p in posts],
            )
        return fmt.to_draft(view)

    async def update_draft(
        self, draft_id: str, posts: list[DraftPostInput], langs: list[str] | None
    ) -> fmt.DraftView:
        draft = await self._draft_model(posts, langs)
        await self._call(
            lambda c: c.app.bsky.draft.update_draft(
                models.AppBskyDraftUpdateDraft.Data(
                    draft=models.AppBskyDraftDefs.DraftWithId(id=draft_id, draft=draft)
                )
            )
        )
        # updateDraft silently ignores unknown IDs, so confirm the draft exists.
        view = await self._find_draft(draft_id)
        if view is None:
            raise BlueskyError("draft_not_found", f"No draft with ID {draft_id} was found.")
        return fmt.to_draft(view)

    async def list_drafts(self, limit: int, cursor: str | None) -> fmt.DraftPage:
        res = await self._call(
            lambda c: c.app.bsky.draft.get_drafts({"limit": limit, "cursor": cursor})
        )
        return fmt.DraftPage(drafts=[fmt.to_draft(d) for d in res.drafts], cursor=res.cursor)

    # -- engagement ------------------------------------------------------------------------

    async def _create(self, collection: str, record: Any) -> str:
        res = await self._call(
            lambda c: c.com.atproto.repo.create_record(
                models.ComAtprotoRepoCreateRecord.Data(
                    repo=self._did, collection=collection, record=record
                )
            )
        )
        return res.uri

    async def _delete_own(self, collection: str, record_uri: str) -> None:
        if fmt.repo_of(record_uri) != self._did:
            raise BlueskyError("not_owner", "That record is not in your repository.")
        await self._call(
            lambda c: c.com.atproto.repo.delete_record(
                models.ComAtprotoRepoDeleteRecord.Data(
                    repo=self._did, collection=collection, rkey=fmt.rkey_of(record_uri)
                )
            )
        )

    async def _follow_state(self, actor: str) -> tuple[Any, str | None]:
        """The target profile and the owner's existing follow record URI, if any."""
        params = models.AppBskyActorGetProfile.Params(actor=parse_actor(actor))
        profile = await self._call(lambda c: c.app.bsky.actor.get_profile(params))
        return profile, fmt._get(profile.viewer, "following")

    async def follow(self, actor: str) -> fmt.EngagementResult:
        profile, existing = await self._follow_state(actor)
        if existing:
            return _result("follow", profile.handle, existing, False, "Already following.")
        uri = await self._create(
            ops.FOLLOW, models.AppBskyGraphFollow.Record(subject=profile.did, created_at=_now())
        )
        return _result("follow", profile.handle, uri, True, "Followed.")

    async def unfollow(self, actor: str) -> fmt.EngagementResult:
        profile, existing = await self._follow_state(actor)
        if not existing:
            return _result(
                "unfollow", profile.handle, None, False, "Nothing to undo: you don't follow them."
            )
        await self._delete_own(ops.FOLLOW, existing)
        return _result("unfollow", profile.handle, None, True, "Unfollowed.")

    async def _viewer_state(
        self, post: str, kind: Literal["like", "repost"]
    ) -> tuple[Any, str, str | None]:
        """The target post, its URL, and the owner's existing like/repost record URI, if any."""
        target = await self._get_post(post)
        return target, fmt.to_post(target).url, fmt._get(target.viewer, kind)

    async def _engage(self, post: str, kind: Literal["like", "repost"]) -> fmt.EngagementResult:
        target, url, existing = await self._viewer_state(post, kind)
        if existing:
            return _result(kind, url, existing, False, "Already done.")
        ref = models.ComAtprotoRepoStrongRef.Main(uri=target.uri, cid=target.cid)
        if kind == "like":
            record: Any = models.AppBskyFeedLike.Record(subject=ref, created_at=_now())
        else:
            record = models.AppBskyFeedRepost.Record(subject=ref, created_at=_now())
        uri = await self._create(ops.LIKE if kind == "like" else ops.REPOST, record)
        return _result(kind, url, uri, True, "Done.")

    async def _undo(self, post: str, kind: Literal["like", "repost"]) -> fmt.EngagementResult:
        _, url, existing = await self._viewer_state(post, kind)
        if not existing:
            return _result(f"un{kind}", url, None, False, f"Nothing to undo: no {kind}.")
        await self._delete_own(ops.LIKE if kind == "like" else ops.REPOST, existing)
        return _result(f"un{kind}", url, None, True, "Undone.")

    async def like(self, post: str) -> fmt.EngagementResult:
        return await self._engage(post, "like")

    async def unlike(self, post: str) -> fmt.EngagementResult:
        return await self._undo(post, "like")

    async def repost(self, post: str) -> fmt.EngagementResult:
        return await self._engage(post, "repost")

    async def unrepost(self, post: str) -> fmt.EngagementResult:
        return await self._undo(post, "repost")

    # -- guarded delete --------------------------------------------------------------------

    async def delete_own_post(self, post: str) -> fmt.DeletedPost:
        target = await self._get_post(post)
        if target.author.did != self._did:
            raise BlueskyError("not_owner", "You can only delete your own posts.")
        view = fmt.to_post(target)
        await self._delete_own(ops.POST, target.uri)
        return fmt.DeletedPost(deleted=True, url=view.url, text=view.text)
