"""Text validation and identifier parsing (T013)."""

from __future__ import annotations

import pytest

from bsky_mcp.bluesky.text import (
    InvalidInputError,
    TooLongError,
    count_graphemes,
    parse_actor,
    parse_https_url,
    parse_post,
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
