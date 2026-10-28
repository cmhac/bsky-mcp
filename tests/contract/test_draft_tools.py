"""Draft tool contracts (T029, User Story 2)."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from bsky_mcp.bluesky.client import DRAFT_DEVICE_NAME, DraftPostInput, SafeBlueskyClient
from tests.conftest import OTHER_POST_URL, FakeBluesky, ann, data
from tests.fake_transport import OWNER_HANDLE, RecordingRequest


async def test_create_single_post(client: Client, fake: FakeBluesky) -> None:
    result = await client.call_tool("create_draft", {"posts": [{"text": "hello world"}]})
    draft = data(result)
    assert draft["draft_id"] == "draft1"
    assert draft["posts"][0]["text"] == "hello world"
    assert "cannot publish" in draft["note"]


async def test_create_thread_with_quote_and_link(client: Client) -> None:
    posts = [
        {"text": "1/ a thread"},
        {"text": "2/ quoting", "quote": OTHER_POST_URL},
        {"text": "3/ link", "link_url": "https://www.washingtonpost.com/"},
    ]
    result = await client.call_tool("create_draft", {"posts": posts, "langs": ["en"]})
    assert len(data(result)["posts"]) == 3


async def test_at_most_300_graphemes(client: Client) -> None:
    await client.call_tool("create_draft", {"posts": [{"text": "a" * 300}]})
    with pytest.raises(ToolError, match=r"too_long: Post 2 has 301 graphemes"):
        await client.call_tool("create_draft", {"posts": [{"text": "ok"}, {"text": "a" * 301}]})


@pytest.mark.parametrize(
    ("posts", "langs", "match"),
    [
        ([], None, None),
        ([{"text": "x"}] * 101, None, None),
        ([{"text": "   "}], None, "invalid_input"),
        ([{"text": "x", "link_url": "http://insecure.example"}], None, "invalid_input"),
        ([{"text": "x", "quote": "https://example.com/p/1"}], None, "invalid_input"),
        ([{"text": "x"}], ["en", "es", "fr", "de"], None),
    ],
)
async def test_invalid_drafts_rejected(
    client: Client, posts: list[dict], langs: list[str] | None, match: str | None
) -> None:
    with pytest.raises(ToolError, match=match):
        await client.call_tool("create_draft", {"posts": posts, "langs": langs})


async def test_quote_must_exist(client: Client) -> None:
    with pytest.raises(ToolError, match="not_found"):
        await client.call_tool(
            "create_draft",
            {"posts": [{"text": "x", "quote": "https://bsky.app/profile/a.bsky.social/post/nope"}]},
        )


async def test_update_and_list(client: Client) -> None:
    await client.call_tool("create_draft", {"posts": [{"text": "v1"}]})
    updated = await client.call_tool(
        "update_draft", {"draft_id": "draft1", "posts": [{"text": "v2"}]}
    )
    assert data(updated)["posts"][0]["text"] == "v2"
    listed = await client.call_tool("list_drafts", {})
    assert [d["draft_id"] for d in data(listed)["drafts"]] == ["draft1"]


async def test_update_missing_draft(client: Client) -> None:
    with pytest.raises(ToolError, match="draft_not_found"):
        await client.call_tool("update_draft", {"draft_id": "nope", "posts": [{"text": "x"}]})


async def test_no_reply_target_accepted(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    for name in ("create_draft", "update_draft"):
        schema = json.dumps(tools[name].input_schema).lower()
        assert "reply" not in schema.replace("replies", ""), name
    with pytest.raises(ToolError):
        await client.call_tool(
            "create_draft", {"posts": [{"text": "x"}], "reply_to": OTHER_POST_URL}
        )


async def test_draft_annotations(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    assert ann(tools["create_draft"]).destructive_hint is False
    assert ann(tools["list_drafts"]).read_only_hint is True


async def test_real_client_sends_draft_with_device_name() -> None:
    request = RecordingRequest()
    client = SafeBlueskyClient(OWNER_HANDLE, "app-pass", "https://bsky.social", request=request)
    view = await client.create_draft([DraftPostInput(text="hello")], ["en"])
    assert view.draft_id == "3kdraft"
    sent = [body for nsid, _, body in request.calls if nsid == "app.bsky.draft.createDraft"]
    assert sent[0]["draft"]["deviceName"] == DRAFT_DEVICE_NAME
    assert sent[0]["draft"]["posts"][0]["text"] == "hello"


async def test_real_client_update_reports_missing_draft() -> None:
    request = RecordingRequest()
    client = SafeBlueskyClient(OWNER_HANDLE, "app-pass", "https://bsky.social", request=request)
    from bsky_mcp.bluesky.client import BlueskyError

    with pytest.raises(BlueskyError) as info:
        await client.update_draft("unknown-id", [DraftPostInput(text="x")], None)
    assert info.value.code == "draft_not_found"
