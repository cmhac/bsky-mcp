"""Text validation and identifier parsing for Bluesky inputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

import regex

MAX_POST_GRAPHEMES = 300  # app.bsky.feed.post text maxGraphemes

_POST_URL = re.compile(
    r"^https://bsky\.app/profile/(?P<actor>[^/\s]+)/post/(?P<rkey>[A-Za-z0-9._:~-]+)/?$"
)
_AT_URI = re.compile(
    r"^at://(?P<repo>[^/\s]+)/(?P<collection>[a-zA-Z0-9.-]+)/(?P<rkey>[A-Za-z0-9._:~-]+)$"
)
_DID = re.compile(r"^did:[a-z]+:[A-Za-z0-9._:%-]+$")
_HANDLE = re.compile(
    r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
)

POST_COLLECTION = "app.bsky.feed.post"


class InvalidInputError(ValueError):
    code = "invalid_input"


class TooLongError(ValueError):
    code = "too_long"


def count_graphemes(text: str) -> int:
    return len(regex.findall(r"\X", text))


def validate_post_text(text: str, index: int = 0) -> None:
    """Raise TooLongError if text is over the published-post limit (at most 300 graphemes)."""
    count = count_graphemes(text)
    if count > MAX_POST_GRAPHEMES:
        raise TooLongError(
            f"Post {index + 1} has {count} graphemes; Bluesky allows at most {MAX_POST_GRAPHEMES}."
        )


@dataclass(frozen=True)
class PostRef:
    """A post identified by its author (handle or DID) and record key."""

    actor: str
    rkey: str

    def at_uri(self, did: str | None = None) -> str:
        return f"at://{did or self.actor}/{POST_COLLECTION}/{self.rkey}"


def parse_actor(value: str) -> str:
    """Return a normalized handle or DID. Accepts an optional leading '@'."""
    candidate = value.strip().removeprefix("@")
    if _DID.match(candidate):
        return candidate
    if _HANDLE.match(candidate):
        return candidate.lower()
    raise InvalidInputError("Expected a Bluesky handle (like name.bsky.social) or a DID.")


def parse_post(value: str) -> PostRef:
    """Parse a bsky.app post URL or an AT-URI for an app.bsky.feed.post record."""
    candidate = value.strip()
    if match := _POST_URL.match(candidate):
        return PostRef(actor=parse_actor(match["actor"]), rkey=match["rkey"])
    if match := _AT_URI.match(candidate):
        if match["collection"] != POST_COLLECTION:
            raise InvalidInputError("That AT-URI does not point to a post.")
        return PostRef(actor=parse_actor(match["repo"]), rkey=match["rkey"])
    raise InvalidInputError(
        "Expected a post URL like https://bsky.app/profile/name.bsky.social/post/abc123 "
        "or an at:// URI."
    )


def parse_https_url(value: str) -> str:
    candidate = value.strip()
    if not candidate.startswith("https://") or any(ch.isspace() for ch in candidate):
        raise InvalidInputError("Links must be https URLs.")
    return candidate


# -- spec 002: feed, list, and starter pack links; search dates ----------------------------------

FEED_COLLECTION = "app.bsky.feed.generator"
LIST_COLLECTION = "app.bsky.graph.list"
STARTER_PACK_COLLECTION = "app.bsky.graph.starterpack"

_RKEY = r"(?P<rkey>[A-Za-z0-9._:~-]+)"
_ACTOR = r"(?P<actor>[^/\s]+)"
_LINK_PATTERNS = {
    FEED_COLLECTION: re.compile(rf"^https://bsky\.app/profile/{_ACTOR}/feed/{_RKEY}/?$"),
    LIST_COLLECTION: re.compile(rf"^https://bsky\.app/profile/{_ACTOR}/lists/{_RKEY}/?$"),
    STARTER_PACK_COLLECTION: re.compile(rf"^https://bsky\.app/starter-pack/{_ACTOR}/{_RKEY}/?$"),
}
_LINK_LABELS = {
    FEED_COLLECTION: ("feed", "https://bsky.app/profile/name.bsky.social/feed/abc"),
    LIST_COLLECTION: ("list", "https://bsky.app/profile/name.bsky.social/lists/abc"),
    STARTER_PACK_COLLECTION: (
        "starter pack",
        "https://bsky.app/starter-pack/name.bsky.social/abc",
    ),
}


@dataclass(frozen=True)
class RecordRef:
    """A feed, list, or starter pack identified by its creator and record key."""

    actor: str
    collection: str
    rkey: str

    def at_uri(self, did: str | None = None) -> str:
        return f"at://{did or self.actor}/{self.collection}/{self.rkey}"


def parse_record_link(value: str, collection: str) -> RecordRef:
    """Parse a bsky.app link or an at:// URI for a feed, list, or starter pack."""
    candidate = value.strip()
    if match := _LINK_PATTERNS[collection].match(candidate):
        return RecordRef(parse_actor(match["actor"]), collection, match["rkey"])
    if (match := _AT_URI.match(candidate)) and match["collection"] == collection:
        return RecordRef(parse_actor(match["repo"]), collection, match["rkey"])
    label, example = _LINK_LABELS[collection]
    raise InvalidInputError(f"Expected a {label} link like {example} or an at:// URI.")


def parse_date_bound(value: str) -> datetime:
    """Accept an ISO date (YYYY-MM-DD) or an ISO datetime; naive values are treated as UTC."""
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise InvalidInputError(
            "Dates must be ISO 8601, like 2026-10-28 or 2026-10-28T14:00Z."
        ) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def validate_date_range(since: str | None, until: str | None) -> tuple[str | None, str | None]:
    """Normalize search dates to ISO strings and require until to be after since."""
    start = parse_date_bound(since) if since else None
    end = parse_date_bound(until) if until else None
    if start and end and end <= start:
        raise InvalidInputError("The end date must be after the start date.")
    return (
        start.isoformat().replace("+00:00", "Z") if start else None,
        end.isoformat().replace("+00:00", "Z") if end else None,
    )
