"""List writes are limited to curation lists in the owner's repo (T002, Principle II v3.0.0)."""

from __future__ import annotations

import pytest

from bsky_mcp.bluesky import operations as ops
from tests.fake_transport import OTHER_DID, OWNER_DID

OWN_LIST = f"at://{OWNER_DID}/app.bsky.graph.list/l1"
OTHER_LIST = f"at://{OTHER_DID}/app.bsky.graph.list/l1"


def _create(collection: str, record: dict, repo: str = OWNER_DID) -> None:
    ops.check_operation(
        ops.CREATE_RECORD, {"repo": repo, "collection": collection, "record": record}, OWNER_DID
    )


def test_curation_list_allowed() -> None:
    _create(ops.LIST, {"purpose": ops.CURATE_LIST_PURPOSE, "name": "x"})


@pytest.mark.parametrize(
    "purpose",
    ["app.bsky.graph.defs#modlist", "app.bsky.graph.defs#referencelist", None, ""],
)
def test_other_list_purposes_rejected(purpose: str | None) -> None:
    with pytest.raises(ops.ForbiddenOperationError):
        _create(ops.LIST, {"purpose": purpose, "name": "x"})


def test_list_item_only_on_own_lists() -> None:
    _create(ops.LIST_ITEM, {"list": OWN_LIST, "subject": OTHER_DID})
    with pytest.raises(ops.ForbiddenOperationError):
        _create(ops.LIST_ITEM, {"list": OTHER_LIST, "subject": OTHER_DID})
    with pytest.raises(ops.ForbiddenOperationError):
        _create(ops.LIST_ITEM, {"list": "", "subject": OTHER_DID})
    with pytest.raises(ops.ForbiddenOperationError):  # lookalike collection in own repo
        _create(
            ops.LIST_ITEM,
            {"list": f"at://{OWNER_DID}/app.bsky.graph.listblock/l1", "subject": OTHER_DID},
        )


def test_list_writes_in_other_repo_rejected() -> None:
    with pytest.raises(ops.ForbiddenOperationError):
        _create(ops.LIST, {"purpose": ops.CURATE_LIST_PURPOSE}, repo=OTHER_DID)
    for collection in (ops.LIST, ops.LIST_ITEM):
        with pytest.raises(ops.ForbiddenOperationError):
            ops.check_operation(
                ops.DELETE_RECORD, {"repo": OTHER_DID, "collection": collection}, OWNER_DID
            )


@pytest.mark.parametrize(
    "nsid",
    [
        "app.bsky.graph.muteActorList",
        "app.bsky.graph.unmuteActorList",
        "app.bsky.graph.muteActor",
        "app.bsky.graph.getListBlocks",
        "app.bsky.graph.getListMutes",
        "com.atproto.repo.putRecord",
    ],
)
def test_mute_and_edit_operations_unreachable(nsid: str) -> None:
    with pytest.raises(ops.ForbiddenOperationError):
        ops.check_operation(nsid, None, OWNER_DID)


def test_list_block_record_unreachable() -> None:
    with pytest.raises(ops.ForbiddenOperationError):
        _create("app.bsky.graph.listblock", {"subject": OTHER_LIST})


def test_new_reads_are_allowed() -> None:
    for nsid in (
        "app.bsky.feed.getQuotes",
        "app.bsky.feed.getFeed",
        "app.bsky.graph.getList",
        "app.bsky.unspecced.getTrendingTopics",
    ):
        ops.check_operation(nsid, None, OWNER_DID)
