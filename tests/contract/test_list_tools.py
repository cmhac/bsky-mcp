"""List management tool contracts (spec 002, User Story 8)."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from bsky_mcp import instructions
from bsky_mcp.bluesky.client import SafeBlueskyClient
from bsky_mcp.bluesky.core import BlueskyError
from tests.conftest import OTHER_HANDLE, FakeBluesky, ann, data
from tests.fake_discovery import OTHER_LIST_URL, OWN_LIST_URL
from tests.fake_transport import (
    OTHER_DID,
    OWNER_DID,
    OWNER_HANDLE,
    RecordingRequest,
    default_routes,
)

OWN_LIST_URI = f"at://{OWNER_DID}/app.bsky.graph.list/ownlist"


async def test_annotations(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    assert ann(tools["delete_list"]).destructive_hint is True
    for name in ("add_to_list", "remove_from_list"):
        assert ann(tools[name]).idempotent_hint is True, name
        assert ann(tools[name]).destructive_hint is False, name
    assert ann(tools["create_list"]).read_only_hint is False


async def test_delete_list_description_carries_rule(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    assert instructions.DELETE_LIST_RULE in (tools["delete_list"].description or "")
    server_text = instructions.SERVER_INSTRUCTIONS
    assert instructions.DELETE_LIST_RULE in server_text
    assert "Mute lists, block lists" in server_text


async def test_create_list(client: Client, fake: FakeBluesky) -> None:
    result = data(await client.call_tool("create_list", {"name": "  Data people  "}))
    assert result["name"] == "Data people"
    assert result["purpose"] == "curatelist"
    assert "create_list:Data people" in fake.calls


@pytest.mark.parametrize(
    "args", [{"name": ""}, {"name": "x" * 65}, {"name": "ok", "description": "d" * 3001}]
)
async def test_create_list_bounds(client: Client, args: dict[str, Any]) -> None:
    with pytest.raises(ToolError):
        await client.call_tool("create_list", args)


async def test_add_is_idempotent_and_reports_per_actor(client: Client) -> None:
    args = {"list": OWN_LIST_URL, "actors": [OWNER_HANDLE, "nobody.example"]}
    first = data(await client.call_tool("add_to_list", args))
    assert [r["status"] for r in first["results"]] == ["added", "not_found"]
    second = data(await client.call_tool("add_to_list", args))
    assert second["results"][0]["status"] == "already_member"


@pytest.mark.parametrize("count", [0, 26])
async def test_add_batch_bounds(client: Client, count: int) -> None:
    with pytest.raises(ToolError):
        await client.call_tool(
            "add_to_list", {"list": OWN_LIST_URL, "actors": [OTHER_HANDLE] * count}
        )


async def test_remove_then_nothing_to_undo(client: Client) -> None:
    args = {"list": OWN_LIST_URL, "actor": OTHER_HANDLE}
    assert data(await client.call_tool("remove_from_list", args))["changed"] is True
    second = data(await client.call_tool("remove_from_list", args))
    assert second["changed"] is False
    assert "Nothing to undo" in second["message"]


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("add_to_list", {"list": OTHER_LIST_URL, "actors": [OWNER_HANDLE]}),
        ("remove_from_list", {"list": OTHER_LIST_URL, "actor": OWNER_HANDLE}),
        ("delete_list", {"list": OTHER_LIST_URL, "confirm": "delete"}),
    ],
)
async def test_other_peoples_lists_are_refused(
    client: Client, tool: str, args: dict[str, Any]
) -> None:
    with pytest.raises(ToolError, match="not_owner"):
        await client.call_tool(tool, args)


@pytest.mark.parametrize("confirm", [None, "", "yes", "DELETE "])
async def test_delete_list_requires_confirmation(
    client: Client, fake: FakeBluesky, confirm: str | None
) -> None:
    args: dict[str, Any] = {"list": OWN_LIST_URL}
    if confirm is not None:
        args["confirm"] = confirm
    with pytest.raises(ToolError, match="confirmation_required"):
        await client.call_tool("delete_list", args)
    assert not any(c.startswith("delete_list") for c in fake.calls)


async def test_delete_list_with_confirmation(client: Client) -> None:
    result = data(
        await client.call_tool("delete_list", {"list": OWN_LIST_URL, "confirm": "delete"})
    )
    assert result["deleted"] is True
    assert result["members_removed"] == 1


# -- the real client against a recording transport --------------------------------------------


def _list_view(uri: str) -> dict[str, Any]:
    did = uri.split("/")[2]
    return {
        "uri": uri,
        "cid": "bafylist",
        "name": "Own list",
        "purpose": "app.bsky.graph.defs#curatelist",
        "creator": {"did": did, "handle": OWNER_HANDLE if did == OWNER_DID else OTHER_HANDLE},
        "indexedAt": "2026-10-28T00:00:00Z",
    }


def _routes(members: dict[str, str]) -> dict[str, Any]:
    """members maps member DID -> listitem URI on the owner's list."""
    routes = default_routes()
    routes["com.atproto.repo.createRecord"] = lambda _: {
        "uri": OWN_LIST_URI,
        "cid": "bafynew",
    }
    routes["app.bsky.graph.getList"] = lambda p: {
        "list": _list_view(p["list"]),
        "items": [
            {"uri": item, "subject": {"did": did, "handle": OTHER_HANDLE}}
            for did, item in members.items()
        ],
    }
    routes["app.bsky.graph.getListsWithMembership"] = lambda p: {
        "listsWithMembership": [
            {
                "list": _list_view(OWN_LIST_URI),
                "listItem": {
                    "uri": members[p["actor"]],
                    "subject": {"did": p["actor"], "handle": OTHER_HANDLE},
                },
            }
        ]
        if p["actor"] in members
        else [{"list": _list_view(OWN_LIST_URI)}]
    }
    return routes


def _real(members: dict[str, str]) -> tuple[SafeBlueskyClient, RecordingRequest]:
    request = RecordingRequest(_routes(members))
    return SafeBlueskyClient(OWNER_HANDLE, "pw", "https://bsky.social", request=request), request


def _writes(request: RecordingRequest, nsid: str) -> list[dict[str, Any]]:
    return [b for n, _, b in request.calls if n == nsid]


async def test_real_create_list_writes_curation_list_in_own_repo() -> None:
    client, request = _real({})
    info = await client.create_list("Data people", "Folks who chart")
    (body,) = _writes(request, "com.atproto.repo.createRecord")
    assert body["repo"] == OWNER_DID
    assert body["collection"] == "app.bsky.graph.list"
    assert body["record"]["purpose"] == "app.bsky.graph.defs#curatelist"
    assert info.url.endswith("/lists/ownlist")


async def test_real_add_skips_existing_members() -> None:
    item = f"at://{OWNER_DID}/app.bsky.graph.listitem/i1"
    client, request = _real({OTHER_DID: item})
    result = await client.add_to_list(OWN_LIST_URL, [OTHER_HANDLE])
    assert result.results[0].status == "already_member"
    assert _writes(request, "com.atproto.repo.createRecord") == []


async def test_real_add_writes_listitem_on_own_list() -> None:
    client, request = _real({})
    result = await client.add_to_list(OWN_LIST_URL, [OTHER_HANDLE])
    assert result.results[0].status == "added"
    (body,) = _writes(request, "com.atproto.repo.createRecord")
    assert body["repo"] == OWNER_DID
    assert body["collection"] == "app.bsky.graph.listitem"
    assert body["record"]["list"] == OWN_LIST_URI
    assert body["record"]["subject"] == OTHER_DID


async def test_real_add_refuses_other_peoples_lists() -> None:
    client, request = _real({})
    with pytest.raises(BlueskyError) as info:
        await client.add_to_list(OTHER_LIST_URL, [OTHER_HANDLE])
    assert info.value.code == "not_owner"
    assert _writes(request, "com.atproto.repo.createRecord") == []


async def test_real_remove_deletes_only_the_listitem() -> None:
    item = f"at://{OWNER_DID}/app.bsky.graph.listitem/i1"
    client, request = _real({OTHER_DID: item})
    result = await client.remove_from_list(OWN_LIST_URL, OTHER_HANDLE)
    assert result.changed is True
    (body,) = _writes(request, "com.atproto.repo.deleteRecord")
    assert body == {"repo": OWNER_DID, "collection": "app.bsky.graph.listitem", "rkey": "i1"}


async def test_real_delete_list_removes_members_then_list() -> None:
    items = {
        OTHER_DID: f"at://{OWNER_DID}/app.bsky.graph.listitem/i1",
        "did:plc:third": f"at://{OWNER_DID}/app.bsky.graph.listitem/i2",
    }
    client, request = _real(items)
    result = await client.delete_own_list(OWN_LIST_URL)
    assert result.members_removed == 2
    deletes = _writes(request, "com.atproto.repo.deleteRecord")
    assert [d["collection"] for d in deletes] == [
        "app.bsky.graph.listitem",
        "app.bsky.graph.listitem",
        "app.bsky.graph.list",
    ]
    assert all(d["repo"] == OWNER_DID for d in deletes)
    assert deletes[-1]["rkey"] == "ownlist"
