"""Text validation and identifier parsing (T013)."""

from __future__ import annotations

import pytest

from bsky_mcp.bluesky.text import (
    FEED_COLLECTION,
    LIST_COLLECTION,
    STARTER_PACK_COLLECTION,
    InvalidInputError,
    TooLongError,
    count_graphemes,
    parse_actor,
    parse_https_url,
    parse_post,
    parse_record_link,
    validate_date_range,
    validate_post_text,
)


def test_emoji_and_combining_sequences_are_single_graphemes() -> None:
    assert count_graphemes("👍🏽") == 1  # emoji + skin tone modifier
    assert count_graphemes("👨‍👩‍👧") == 1  # ZWJ family
    assert count_graphemes("é") == 1  # e + combining acute accent
    assert count_graphemes("abc") == 3


def test_limit_is_at_most_300_graphemes() -> None:
    validate_post_text("a" * 300)
    validate_post_text("👍🏽" * 300)
    with pytest.raises(TooLongError, match="301"):
        validate_post_text("a" * 301)


def test_too_long_names_post_index() -> None:
    with pytest.raises(TooLongError, match="Post 3"):
        validate_post_text("a" * 400, index=2)


@pytest.mark.parametrize(
    ("value", "actor", "rkey"),
    [
        ("https://bsky.app/profile/alice.bsky.social/post/3kabc", "alice.bsky.social", "3kabc"),
        ("https://bsky.app/profile/did:plc:abc123/post/3kabc/", "did:plc:abc123", "3kabc"),
        ("at://did:plc:abc123/app.bsky.feed.post/3kabc", "did:plc:abc123", "3kabc"),
    ],
)
def test_parse_post(value: str, actor: str, rkey: str) -> None:
    ref = parse_post(value)
    assert (ref.actor, ref.rkey) == (actor, rkey)


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/post/1",
        "at://did:plc:abc/app.bsky.feed.like/3k",
        "not a url",
        "https://bsky.app/profile/alice.bsky.social",
    ],
)
def test_parse_post_rejects(value: str) -> None:
    with pytest.raises(InvalidInputError):
        parse_post(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("@Alice.bsky.social", "alice.bsky.social"),
        ("alice.bsky.social", "alice.bsky.social"),
        ("did:plc:abc123", "did:plc:abc123"),
    ],
)
def test_parse_actor(value: str, expected: str) -> None:
    assert parse_actor(value) == expected


@pytest.mark.parametrize("value", ["", "no spaces allowed.com x", "@", "localhost"])
def test_parse_actor_rejects(value: str) -> None:
    with pytest.raises(InvalidInputError):
        parse_actor(value)


def test_links_must_be_https() -> None:
    assert parse_https_url(" https://example.com/a ") == "https://example.com/a"
    with pytest.raises(InvalidInputError):
        parse_https_url("http://example.com")
    with pytest.raises(InvalidInputError):
        parse_https_url("javascript:alert(1)")


# -- spec 002 parsers -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "collection", "actor", "rkey"),
    [
        (
            "https://bsky.app/profile/a.bsky.social/feed/hot",
            FEED_COLLECTION,
            "a.bsky.social",
            "hot",
        ),
        ("https://bsky.app/profile/did:plc:x/lists/3k", LIST_COLLECTION, "did:plc:x", "3k"),
        (
            "https://bsky.app/starter-pack/a.bsky.social/p1",
            STARTER_PACK_COLLECTION,
            "a.bsky.social",
            "p1",
        ),
        ("at://did:plc:x/app.bsky.graph.list/3k", LIST_COLLECTION, "did:plc:x", "3k"),
    ],
)
def test_parse_record_link(value: str, collection: str, actor: str, rkey: str) -> None:
    ref = parse_record_link(value, collection)
    assert (ref.actor, ref.collection, ref.rkey) == (actor, collection, rkey)
    assert ref.at_uri("did:plc:y") == f"at://did:plc:y/{collection}/{rkey}"


@pytest.mark.parametrize(
    ("value", "collection"),
    [
        ("https://bsky.app/profile/a.bsky.social/lists/3k", FEED_COLLECTION),
        ("at://did:plc:x/app.bsky.graph.listblock/3k", LIST_COLLECTION),
        ("https://example.com/profile/a/feed/hot", FEED_COLLECTION),
        ("", LIST_COLLECTION),
    ],
)
def test_parse_record_link_rejects_wrong_kind(value: str, collection: str) -> None:
    with pytest.raises(InvalidInputError):
        parse_record_link(value, collection)


def test_validate_date_range() -> None:
    since, until = validate_date_range("2026-10-01", "2026-10-28T12:00:00-04:00")
    assert since is not None and since.startswith("2026-10-01T00:00:00")
    assert until is not None and until.startswith("2026-10-28T12:00:00-04:00")
    assert validate_date_range(None, None) == (None, None)
    with pytest.raises(InvalidInputError):
        validate_date_range("2026-10-28", "2026-10-28")
    with pytest.raises(InvalidInputError):
        validate_date_range("yesterday", None)
