"""Discovery and list methods for the in-memory FakeBluesky (spec 002)."""

from __future__ import annotations

from typing import Any

from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.bluesky.core import BlueskyError
from bsky_mcp.bluesky.lists import validate_list_fields
from bsky_mcp.bluesky.text import (
    FEED_COLLECTION,
    LIST_COLLECTION,
    STARTER_PACK_COLLECTION,
    parse_actor,
    parse_record_link,
    validate_actor_batch,
)

OWNER_DID = "did:plc:owner"
OWNER_HANDLE = "owner.bsky.social"
OTHER_DID = "did:plc:other"
OTHER_HANDLE = "other.bsky.social"
HANDLES = {OWNER_DID: OWNER_HANDLE, OTHER_DID: OTHER_HANDLE}
DIDS = {v: k for k, v in HANDLES.items()}

OWN_LIST_URL = f"https://bsky.app/profile/{OWNER_HANDLE}/lists/ownlist"
OTHER_LIST_URL = f"https://bsky.app/profile/{OTHER_HANDLE}/lists/otherlist"
FEED_URL = f"https://bsky.app/profile/{OTHER_HANDLE}/feed/hot"
STARTER_PACK_URL = f"https://bsky.app/starter-pack/{OTHER_HANDLE}/pack1"


def _did(actor: str) -> str:
    actor = parse_actor(actor)
    did = DIDS.get(actor, actor)
    if did not in HANDLES:
        raise BlueskyError("not_found", "Account not found.")
    return did


def _profile(did: str) -> fmt.ProfileView:
    handle = HANDLES[did]
    return fmt.ProfileView(did=did, handle=handle, url=f"https://bsky.app/profile/{handle}")


class FakeDiscovery:
    """Mixed into FakeBluesky. Uses self.calls and self._view/_find from it."""

    calls: list[str]

    def _page(self) -> fmt.PostPage:  # provided by FakeBluesky
        raise NotImplementedError

    def _find(self, post: str) -> dict[str, Any]:  # provided by FakeBluesky
        raise NotImplementedError

    @property
    def fake_lists(self) -> dict[str, dict[str, Any]]:
        if not hasattr(self, "_fake_lists"):
            self._fake_lists = {
                f"at://{OWNER_DID}/{LIST_COLLECTION}/ownlist": {
                    "name": "Own list",
                    "owner": OWNER_DID,
                    "members": {OTHER_DID},
                },
                f"at://{OTHER_DID}/{LIST_COLLECTION}/otherlist": {
                    "name": "Their list",
                    "owner": OTHER_DID,
                    "members": set(),
                },
            }
        return self._fake_lists

    def _uri(self, value: str, collection: str) -> str:
        ref = parse_record_link(value, collection)
        return ref.at_uri(_did(ref.actor))

    def _info(self, uri: str) -> fmt.ListInfo:
        entry = self.fake_lists.get(uri)
        if entry is None:
            raise BlueskyError("not_found", "List not found.")
        handle = HANDLES[entry["owner"]]
        return fmt.ListInfo(
            uri=uri,
            url=f"https://bsky.app/profile/{handle}/lists/{fmt.rkey_of(uri)}",
            name=entry["name"],
            purpose="curatelist",
            creator_handle=handle,
            member_count=len(entry["members"]),
        )

    def _posts(self) -> fmt.PostPage:
        return self._page()

    def _people(self) -> fmt.ProfilePage:
        return fmt.ProfilePage(profiles=[_profile(OTHER_DID)])

    def _feed_view(self) -> fmt.FeedView:
        return fmt.FeedView(
            uri="at://x/app.bsky.feed.generator/hot",
            url=FEED_URL,
            name="Hot",
            creator_handle=OTHER_HANDLE,
        )

    # reads
    async def quotes(self, post, limit, cursor):
        self._find(post)
        self.calls.append(f"quotes:{limit}")
        return self._posts()

    async def likes(self, post, limit, cursor):
        self._find(post)
        return self._people()

    async def reposted_by(self, post, limit, cursor):
        self._find(post)
        return self._people()

    async def feed(self, feed, limit, cursor):
        self.calls.append(f"feed:{self._uri(feed, FEED_COLLECTION)}")
        return self._posts()

    async def feed_info(self, feed):
        self._uri(feed, FEED_COLLECTION)
        return self._feed_view().model_copy(update={"is_online": True, "is_valid": True})

    async def account_feeds(self, actor, limit, cursor):
        _did(actor)
        return fmt.FeedPage(feeds=[self._feed_view()])

    async def suggested_feeds(self, limit, cursor):
        return fmt.FeedPage(feeds=[self._feed_view()])

    async def search_feeds(self, query, limit, cursor):
        self.calls.append(f"search_feeds:{query}")
        return fmt.FeedPage(feeds=[self._feed_view()])

    async def suggested_follows(self, limit, cursor):
        return self._people()

    async def similar_accounts(self, actor):
        _did(actor)
        return self._people()

    async def trending_topics(self, limit):
        self.calls.append(f"trending:{limit}")
        return fmt.TrendingPage(
            topics=[
                fmt.TrendingTopic(
                    topic="dataviz", url="https://bsky.app/profile/trending/topic/dataviz"
                )
            ]
        )

    async def search_starter_packs(self, query, limit, cursor):
        return fmt.StarterPackPage(starter_packs=[self._pack()])

    def _pack(self) -> fmt.StarterPackInfo:
        return fmt.StarterPackInfo(
            uri="at://x/app.bsky.graph.starterpack/pack1",
            url=STARTER_PACK_URL,
            name="Data people",
            creator_handle=OTHER_HANDLE,
        )

    async def starter_pack(self, starter_pack, limit, cursor):
        self._uri(starter_pack, STARTER_PACK_COLLECTION)
        return fmt.StarterPackDetail(starter_pack=self._pack(), members=[_profile(OTHER_DID)])

    async def account_starter_packs(self, actor, limit, cursor):
        _did(actor)
        return fmt.StarterPackPage(starter_packs=[self._pack()])

    async def lists(self, actor, limit, cursor):
        owner = _did(actor) if actor else OWNER_DID
        self.calls.append(f"lists:{owner}")
        return fmt.ListPage(
            lists=[self._info(u) for u, e in self.fake_lists.items() if e["owner"] == owner]
        )

    async def list_detail(self, list_, limit, cursor):
        uri = self._uri(list_, LIST_COLLECTION)
        info = self._info(uri)
        return fmt.ListDetail(
            list=info, members=[_profile(d) for d in self.fake_lists[uri]["members"]]
        )

    async def list_feed(self, list_, limit, cursor):
        self._info(self._uri(list_, LIST_COLLECTION))
        return self._posts()

    # writes
    def _own(self, list_: str) -> str:
        uri = self._uri(list_, LIST_COLLECTION)
        if self.fake_lists.get(uri, {}).get("owner", OWNER_DID) != OWNER_DID or not uri.startswith(
            f"at://{OWNER_DID}/"
        ):
            raise BlueskyError("not_owner", "You can only change your own lists.")
        self._info(uri)
        return uri

    async def create_list(self, name, description):
        clean, _ = validate_list_fields(name, description)
        uri = f"at://{OWNER_DID}/{LIST_COLLECTION}/new{len(self.fake_lists)}"
        self.fake_lists[uri] = {"name": clean, "owner": OWNER_DID, "members": set()}
        self.calls.append(f"create_list:{clean}")
        return self._info(uri)

    async def add_to_list(self, list_, actors):
        validate_actor_batch(actors)
        uri = self._own(list_)
        members = self.fake_lists[uri]["members"]
        results = []
        for actor in actors:
            try:
                did = _did(actor)
            except BlueskyError:
                results.append(fmt.ListMembershipResult(actor=actor, status="not_found"))
                continue
            status = "already_member" if did in members else "added"
            members.add(did)
            results.append(fmt.ListMembershipResult(actor=actor, status=status))
        return fmt.ListMembershipResults(list_url=self._info(uri).url, results=results)

    async def remove_from_list(self, list_, actor):
        uri = self._own(list_)
        did = _did(actor)
        members = self.fake_lists[uri]["members"]
        changed = did in members
        members.discard(did)
        message = "Removed." if changed else "Nothing to undo: not on the list."
        return fmt.EngagementResult(
            action="remove_from_list", subject=actor, changed=changed, message=message
        )

    async def delete_own_list(self, list_):
        uri = self._own(list_)
        info = self._info(uri)
        entry = self.fake_lists.pop(uri)
        self.calls.append(f"delete_list:{uri}")
        return fmt.DeletedList(
            deleted=True, url=info.url, name=info.name, members_removed=len(entry["members"])
        )
