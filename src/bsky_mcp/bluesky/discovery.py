"""Read-only discovery (spec 002, User Stories 2-7). Mixed into SafeBlueskyClient."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from atproto import models

from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.bluesky.core import BlueskyError, ClientCore
from bsky_mcp.bluesky.text import (
    FEED_COLLECTION,
    LIST_COLLECTION,
    STARTER_PACK_COLLECTION,
    parse_actor,
    parse_record_link,
)

UNSTABLE_MESSAGE = (
    "Bluesky's {what} endpoint is unavailable right now. It is not part of Bluesky's stable API "
    "and may have changed."
)


class DiscoveryAPI(Protocol):
    async def quotes(self, post: str, limit: int, cursor: str | None) -> fmt.PostPage: ...
    async def likes(self, post: str, limit: int, cursor: str | None) -> fmt.ProfilePage: ...
    async def reposted_by(self, post: str, limit: int, cursor: str | None) -> fmt.ProfilePage: ...
    async def feed(self, feed: str, limit: int, cursor: str | None) -> fmt.PostPage: ...
    async def feed_info(self, feed: str) -> fmt.FeedView: ...
    async def account_feeds(self, actor: str, limit: int, cursor: str | None) -> fmt.FeedPage: ...
    async def suggested_feeds(self, limit: int, cursor: str | None) -> fmt.FeedPage: ...
    async def search_feeds(self, query: str, limit: int, cursor: str | None) -> fmt.FeedPage: ...
    async def suggested_follows(self, limit: int, cursor: str | None) -> fmt.ProfilePage: ...
    async def similar_accounts(self, actor: str) -> fmt.ProfilePage: ...
    async def trending_topics(self, limit: int) -> fmt.TrendingPage: ...
    async def search_starter_packs(
        self, query: str, limit: int, cursor: str | None
    ) -> fmt.StarterPackPage: ...
    async def starter_pack(
        self, starter_pack: str, limit: int, cursor: str | None
    ) -> fmt.StarterPackDetail: ...
    async def account_starter_packs(
        self, actor: str, limit: int, cursor: str | None
    ) -> fmt.StarterPackPage: ...
    async def lists(self, actor: str | None, limit: int, cursor: str | None) -> fmt.ListPage: ...
    async def list_detail(self, list_: str, limit: int, cursor: str | None) -> fmt.ListDetail: ...
    async def list_feed(self, list_: str, limit: int, cursor: str | None) -> fmt.PostPage: ...


async def unstable[T](what: str, call: Awaitable[T]) -> T:
    """Turn any non-auth failure of an unspecced endpoint into a clear 'unavailable' error."""
    try:
        return await call
    except BlueskyError as exc:
        if exc.code in ("bluesky_auth_failed", "not_configured"):
            raise
        raise BlueskyError("unavailable", UNSTABLE_MESSAGE.format(what=what)) from None
    except Exception:  # SDK model changes surface as parsing errors; contain them here.
        raise BlueskyError("unavailable", UNSTABLE_MESSAGE.format(what=what)) from None


class DiscoveryMixin(ClientCore):
    __slots__ = ()

    async def _record_uri(self, value: str, collection: str) -> str:
        ref = parse_record_link(value, collection)
        return ref.at_uri(await self._resolve_did(ref.actor))

    async def _post_ref(self, post: str) -> tuple[str, str]:
        target = await self._get_post(post)
        return target.uri, target.cid

    async def _fetch(self, call: Callable[[Any], Awaitable[Any]]) -> Any:
        return await self._call(call)

    # -- engagement on a post (US2) --------------------------------------------------------

    async def quotes(self, post: str, limit: int, cursor: str | None) -> fmt.PostPage:
        uri, cid = await self._post_ref(post)
        params = models.AppBskyFeedGetQuotes.Params(uri=uri, cid=cid, limit=limit, cursor=cursor)
        res = await self._fetch(lambda c: c.app.bsky.feed.get_quotes(params))
        return fmt.PostPage(posts=[fmt.to_post(p) for p in res.posts], cursor=res.cursor)

    async def likes(self, post: str, limit: int, cursor: str | None) -> fmt.ProfilePage:
        uri, cid = await self._post_ref(post)
        params = models.AppBskyFeedGetLikes.Params(uri=uri, cid=cid, limit=limit, cursor=cursor)
        res = await self._fetch(lambda c: c.app.bsky.feed.get_likes(params))
        return fmt.ProfilePage(
            profiles=[fmt.to_profile(like.actor) for like in res.likes], cursor=res.cursor
        )

    async def reposted_by(self, post: str, limit: int, cursor: str | None) -> fmt.ProfilePage:
        uri, cid = await self._post_ref(post)
        params = models.AppBskyFeedGetRepostedBy.Params(
            uri=uri, cid=cid, limit=limit, cursor=cursor
        )
        res = await self._fetch(lambda c: c.app.bsky.feed.get_reposted_by(params))
        return fmt.ProfilePage(
            profiles=[fmt.to_profile(p) for p in res.reposted_by], cursor=res.cursor
        )

    # -- feeds (US3) -----------------------------------------------------------------------

    async def feed(self, feed: str, limit: int, cursor: str | None) -> fmt.PostPage:
        uri = await self._record_uri(feed, FEED_COLLECTION)
        params = models.AppBskyFeedGetFeed.Params(feed=uri, limit=limit, cursor=cursor)
        res = await self._fetch(lambda c: c.app.bsky.feed.get_feed(params))
        return fmt.PostPage(posts=[fmt.to_post(item.post) for item in res.feed], cursor=res.cursor)

    async def feed_info(self, feed: str) -> fmt.FeedView:
        uri = await self._record_uri(feed, FEED_COLLECTION)
        params = models.AppBskyFeedGetFeedGenerator.Params(feed=uri)
        res = await self._fetch(lambda c: c.app.bsky.feed.get_feed_generator(params))
        return fmt.to_feed(res.view, is_online=res.is_online, is_valid=res.is_valid)

    async def account_feeds(self, actor: str, limit: int, cursor: str | None) -> fmt.FeedPage:
        params = models.AppBskyFeedGetActorFeeds.Params(
            actor=parse_actor(actor), limit=limit, cursor=cursor
        )
        res = await self._fetch(lambda c: c.app.bsky.feed.get_actor_feeds(params))
        return fmt.FeedPage(feeds=[fmt.to_feed(f) for f in res.feeds], cursor=res.cursor)

    async def suggested_feeds(self, limit: int, cursor: str | None) -> fmt.FeedPage:
        params = models.AppBskyFeedGetSuggestedFeeds.Params(limit=limit, cursor=cursor)
        res = await self._fetch(lambda c: c.app.bsky.feed.get_suggested_feeds(params))
        return fmt.FeedPage(feeds=[fmt.to_feed(f) for f in res.feeds], cursor=res.cursor)

    async def search_feeds(self, query: str, limit: int, cursor: str | None) -> fmt.FeedPage:
        params = models.AppBskyUnspeccedGetPopularFeedGenerators.Params(
            query=query, limit=limit, cursor=cursor
        )
        res = await unstable(
            "popular feeds",
            self._fetch(lambda c: c.app.bsky.unspecced.get_popular_feed_generators(params)),
        )
        return fmt.FeedPage(feeds=[fmt.to_feed(f) for f in res.feeds], cursor=res.cursor)

    # -- accounts (US4) --------------------------------------------------------------------

    async def suggested_follows(self, limit: int, cursor: str | None) -> fmt.ProfilePage:
        params = models.AppBskyActorGetSuggestions.Params(limit=limit, cursor=cursor)
        res = await self._fetch(lambda c: c.app.bsky.actor.get_suggestions(params))
        return fmt.ProfilePage(profiles=[fmt.to_profile(p) for p in res.actors], cursor=res.cursor)

    async def similar_accounts(self, actor: str) -> fmt.ProfilePage:
        params = models.AppBskyGraphGetSuggestedFollowsByActor.Params(actor=parse_actor(actor))
        res = await self._fetch(lambda c: c.app.bsky.graph.get_suggested_follows_by_actor(params))
        return fmt.ProfilePage(profiles=[fmt.to_profile(p) for p in res.suggestions])

    # -- trending (US5) --------------------------------------------------------------------

    async def trending_topics(self, limit: int) -> fmt.TrendingPage:
        params = models.AppBskyUnspeccedGetTrendingTopics.Params(limit=limit)
        res = await unstable(
            "trending topics",
            self._fetch(lambda c: c.app.bsky.unspecced.get_trending_topics(params)),
        )
        return fmt.TrendingPage(topics=[fmt.to_trending(t) for t in res.topics])

    # -- starter packs (US6) ---------------------------------------------------------------

    async def search_starter_packs(
        self, query: str, limit: int, cursor: str | None
    ) -> fmt.StarterPackPage:
        params = models.AppBskyGraphSearchStarterPacks.Params(q=query, limit=limit, cursor=cursor)
        res = await self._fetch(lambda c: c.app.bsky.graph.search_starter_packs(params))
        return fmt.StarterPackPage(
            starter_packs=[fmt.to_starter_pack(p) for p in res.starter_packs], cursor=res.cursor
        )

    async def starter_pack(
        self, starter_pack: str, limit: int, cursor: str | None
    ) -> fmt.StarterPackDetail:
        uri = await self._record_uri(starter_pack, STARTER_PACK_COLLECTION)
        params = models.AppBskyGraphGetStarterPack.Params(starter_pack=uri)
        res = await self._fetch(lambda c: c.app.bsky.graph.get_starter_pack(params))
        pack = res.starter_pack
        list_view = fmt._get(pack, "list")
        if list_view is None:
            return fmt.StarterPackDetail(starter_pack=fmt.to_starter_pack(pack), members=[])
        members = await self._list_members(fmt._get(list_view, "uri"), limit, cursor)
        return fmt.StarterPackDetail(
            starter_pack=fmt.to_starter_pack(pack),
            list_url=fmt.to_list(list_view).url,
            members=members.members,
            cursor=members.cursor,
        )

    async def account_starter_packs(
        self, actor: str, limit: int, cursor: str | None
    ) -> fmt.StarterPackPage:
        params = models.AppBskyGraphGetActorStarterPacks.Params(
            actor=parse_actor(actor), limit=limit, cursor=cursor
        )
        res = await self._fetch(lambda c: c.app.bsky.graph.get_actor_starter_packs(params))
        return fmt.StarterPackPage(
            starter_packs=[fmt.to_starter_pack(p) for p in res.starter_packs], cursor=res.cursor
        )

    # -- lists (US7) -----------------------------------------------------------------------

    async def _list_members(self, list_uri: str, limit: int, cursor: str | None) -> fmt.ListDetail:
        params = models.AppBskyGraphGetList.Params(list=list_uri, limit=limit, cursor=cursor)
        res = await self._fetch(lambda c: c.app.bsky.graph.get_list(params))
        return fmt.ListDetail(
            list=fmt.to_list(res.list),
            members=[fmt.to_profile(item.subject) for item in res.items],
            cursor=res.cursor,
        )

    async def lists(self, actor: str | None, limit: int, cursor: str | None) -> fmt.ListPage:
        target = parse_actor(actor) if actor else await self._own_did()
        params = models.AppBskyGraphGetLists.Params(actor=target, limit=limit, cursor=cursor)
        res = await self._fetch(lambda c: c.app.bsky.graph.get_lists(params))
        return fmt.ListPage(lists=[fmt.to_list(v) for v in res.lists], cursor=res.cursor)

    async def list_detail(self, list_: str, limit: int, cursor: str | None) -> fmt.ListDetail:
        return await self._list_members(
            await self._record_uri(list_, LIST_COLLECTION), limit, cursor
        )

    async def list_feed(self, list_: str, limit: int, cursor: str | None) -> fmt.PostPage:
        uri = await self._record_uri(list_, LIST_COLLECTION)
        params = models.AppBskyFeedGetListFeed.Params(list=uri, limit=limit, cursor=cursor)
        res = await self._fetch(lambda c: c.app.bsky.feed.get_list_feed(params))
        return fmt.PostPage(posts=[fmt.to_post(item.post) for item in res.feed], cursor=res.cursor)
