"""Management of the owner's curation lists (spec 002, User Story 8). Mixed into the client.

Constitution v3.0.0 Principle II: curation lists only, writes only in the owner's repo, and list
deletion is a guarded action (the confirmation check lives in the tool).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from atproto import models

from bsky_mcp.bluesky import formatting as fmt
from bsky_mcp.bluesky import operations as ops
from bsky_mcp.bluesky.core import BlueskyError, ClientCore
from bsky_mcp.bluesky.text import (
    LIST_COLLECTION,
    InvalidInputError,
    parse_record_link,
    validate_actor_batch,
)

MAX_LIST_NAME = 64  # app.bsky.graph.list name maxLength
MAX_LIST_DESCRIPTION = 3000  # app.bsky.graph.list description maxLength
MEMBERSHIP_SCAN_PAGES = 5
DELETE_SCAN_PAGES = 50  # up to 5,000 members


class ListsAPI(Protocol):
    async def create_list(self, name: str, description: str | None) -> fmt.ListInfo: ...
    async def add_to_list(self, list_: str, actors: list[str]) -> fmt.ListMembershipResults: ...
    async def remove_from_list(self, list_: str, actor: str) -> fmt.EngagementResult: ...
    async def delete_own_list(self, list_: str) -> fmt.DeletedList: ...


def validate_list_fields(name: str, description: str | None) -> tuple[str, str | None]:
    clean = name.strip()
    if not 1 <= len(clean) <= MAX_LIST_NAME:
        raise InvalidInputError(f"List names must be 1-{MAX_LIST_NAME} characters.")
    if description is not None and len(description) > MAX_LIST_DESCRIPTION:
        raise InvalidInputError(
            f"List descriptions are limited to {MAX_LIST_DESCRIPTION} characters."
        )
    return clean, (description.strip() or None) if description else None


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ListsMixin(ClientCore):
    __slots__ = ()

    async def _list_view(self, list_uri: str) -> Any:
        params = models.AppBskyGraphGetList.Params(list=list_uri, limit=1)
        res = await self._call(lambda c: c.app.bsky.graph.get_list(params))
        return res.list

    async def _own_list(self, list_: str) -> tuple[str, Any]:
        """Resolve a list link and require it to belong to the owner."""
        ref = parse_record_link(list_, LIST_COLLECTION)
        did = await self._resolve_did(ref.actor)
        if did != await self._own_did():
            raise BlueskyError("not_owner", "You can only change your own lists.")
        uri = ref.at_uri(did)
        return uri, await self._list_view(uri)

    async def _membership(self, list_uri: str, member_did: str) -> str | None:
        """The owner's listitem record URI for this member of this list, if any."""
        cursor: str | None = None
        for _ in range(MEMBERSHIP_SCAN_PAGES):
            params = models.AppBskyGraphGetListsWithMembership.Params(
                actor=member_did, limit=100, cursor=cursor
            )
            res = await self._call(
                lambda c, p=params: c.app.bsky.graph.get_lists_with_membership(p)
            )
            for entry in res.lists_with_membership:
                if fmt._get(entry.list, "uri") == list_uri:
                    return fmt._get(entry.list_item, "uri")
            cursor = res.cursor
            if not cursor:
                break
        return None

    async def _member_did(self, actor: str) -> str | None:
        try:
            return await self._resolve_did(actor)
        except (BlueskyError, InvalidInputError):
            return None

    async def create_list(self, name: str, description: str | None) -> fmt.ListInfo:
        clean_name, clean_description = validate_list_fields(name, description)
        record = models.AppBskyGraphList.Record(
            name=clean_name,
            purpose=ops.CURATE_LIST_PURPOSE,
            description=clean_description,
            created_at=_now(),
        )
        uri = await self._create(ops.LIST, record)
        return fmt.to_list(await self._list_view(uri))

    async def add_to_list(self, list_: str, actors: list[str]) -> fmt.ListMembershipResults:
        validate_actor_batch(actors)
        list_uri, view = await self._own_list(list_)
        results: list[fmt.ListMembershipResult] = []
        for actor in actors:
            did = await self._member_did(actor)
            if did is None:
                status = "not_found"
            elif await self._membership(list_uri, did):
                status = "already_member"
            else:
                item = models.AppBskyGraphListitem.Record(
                    list=list_uri, subject=did, created_at=_now()
                )
                await self._create(ops.LIST_ITEM, item)
                status = "added"
            results.append(fmt.ListMembershipResult(actor=actor, status=status))
        return fmt.ListMembershipResults(list_url=fmt.to_list(view).url, results=results)

    async def remove_from_list(self, list_: str, actor: str) -> fmt.EngagementResult:
        list_uri, view = await self._own_list(list_)
        url = fmt.to_list(view).url
        did = await self._member_did(actor)
        item_uri = await self._membership(list_uri, did) if did else None
        if not item_uri:
            return fmt.EngagementResult(
                action="remove_from_list",
                subject=actor,
                changed=False,
                message=f"Nothing to undo: {actor} is not on {url}.",
            )
        await self._delete_own(ops.LIST_ITEM, item_uri)
        return fmt.EngagementResult(
            action="remove_from_list", subject=actor, changed=True, message=f"Removed from {url}."
        )

    async def delete_own_list(self, list_: str) -> fmt.DeletedList:
        list_uri, view = await self._own_list(list_)
        info = fmt.to_list(view)
        item_uris: list[str] = []
        cursor: str | None = None
        for _ in range(DELETE_SCAN_PAGES):
            params = models.AppBskyGraphGetList.Params(list=list_uri, limit=100, cursor=cursor)
            res = await self._call(lambda c, p=params: c.app.bsky.graph.get_list(p))
            item_uris.extend(item.uri for item in res.items)
            cursor = res.cursor
            if not cursor:
                break
        # Members first, then the list: if interrupted, the list still exists and can be retried.
        for item_uri in item_uris:
            await self._delete_own(ops.LIST_ITEM, item_uri)
        await self._delete_own(ops.LIST, list_uri)
        return fmt.DeletedList(
            deleted=True, url=info.url, name=info.name, members_removed=len(item_uris)
        )
