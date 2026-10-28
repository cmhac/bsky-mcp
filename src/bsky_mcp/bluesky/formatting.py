"""Tool result models and conversion from atproto SDK objects."""

from __future__ import annotations

from typing import Any

from atproto_client.exceptions import ModelFieldNotFoundError
from pydantic import BaseModel

POST_URL_TEMPLATE = "https://bsky.app/profile/{handle}/post/{rkey}"
PROFILE_URL_TEMPLATE = "https://bsky.app/profile/{handle}"


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    value = getattr(obj, name, default)
    if value is default and hasattr(obj, "__getitem__"):
        try:
            return obj[name]
        except (KeyError, TypeError, ModelFieldNotFoundError):
            return default
    return value


def rkey_of(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def repo_of(uri: str) -> str:
    return uri.removeprefix("at://").split("/", 1)[0]


def post_url(handle: str, uri: str) -> str:
    return POST_URL_TEMPLATE.format(handle=handle, rkey=rkey_of(uri))


class PostView(BaseModel):
    uri: str
    url: str
    author_handle: str
    author_display_name: str | None = None
    text: str
    created_at: str | None = None
    reply_count: int | None = None
    repost_count: int | None = None
    like_count: int | None = None
    quote_count: int | None = None
    reply_parent_url: str | None = None
    viewer_liked: bool = False
    viewer_reposted: bool = False


class ProfileView(BaseModel):
    did: str
    handle: str
    url: str
    display_name: str | None = None
    description: str | None = None
    followers_count: int | None = None
    follows_count: int | None = None
    posts_count: int | None = None
    you_follow: bool = False
    follows_you: bool = False


class NotificationView(BaseModel):
    reason: str
    author_handle: str
    author_display_name: str | None = None
    subject_url: str | None = None
    text: str | None = None
    indexed_at: str
    is_read: bool


class PostPage(BaseModel):
    posts: list[PostView]
    cursor: str | None = None


class ProfilePage(BaseModel):
    profiles: list[ProfileView]
    cursor: str | None = None


class NotificationPage(BaseModel):
    notifications: list[NotificationView]
    cursor: str | None = None


class ThreadView(BaseModel):
    post: PostView
    parents: list[PostView]
    replies: list[ThreadReply]


class ThreadReply(BaseModel):
    post: PostView
    replies: list[ThreadReply]


class DraftPostView(BaseModel):
    text: str
    quote_uri: str | None = None
    link_url: str | None = None


class DraftView(BaseModel):
    draft_id: str
    posts: list[DraftPostView]
    created_at: str | None = None
    updated_at: str | None = None
    note: str = (
        "Saved to Bluesky Drafts. This server cannot publish; open Drafts in a Bluesky app to post."
    )


class DraftPage(BaseModel):
    drafts: list[DraftView]
    cursor: str | None = None


class EngagementResult(BaseModel):
    action: str
    subject: str
    record_uri: str | None = None
    changed: bool
    message: str


class DeletedPost(BaseModel):
    deleted: bool
    url: str
    text: str


ThreadView.model_rebuild()


def to_post(post: Any) -> PostView:
    author = _get(post, "author")
    handle = _get(author, "handle", "unknown")
    uri = _get(post, "uri", "")
    record = _get(post, "record")
    reply = _get(record, "reply")
    parent_uri = _get(_get(reply, "parent"), "uri")
    viewer = _get(post, "viewer")
    return PostView(
        uri=uri,
        url=post_url(handle, uri),
        author_handle=handle,
        author_display_name=_get(author, "display_name"),
        text=_get(record, "text", "") or "",
        created_at=_get(record, "created_at") or _get(post, "indexed_at"),
        reply_count=_get(post, "reply_count"),
        repost_count=_get(post, "repost_count"),
        like_count=_get(post, "like_count"),
        quote_count=_get(post, "quote_count"),
        reply_parent_url=(
            post_url(repo_of(parent_uri), parent_uri) if isinstance(parent_uri, str) else None
        ),
        viewer_liked=bool(_get(viewer, "like")),
        viewer_reposted=bool(_get(viewer, "repost")),
    )


def to_profile(profile: Any) -> ProfileView:
    handle = _get(profile, "handle", "unknown")
    viewer = _get(profile, "viewer")
    return ProfileView(
        did=_get(profile, "did", ""),
        handle=handle,
        url=PROFILE_URL_TEMPLATE.format(handle=handle),
        display_name=_get(profile, "display_name"),
        description=_get(profile, "description"),
        followers_count=_get(profile, "followers_count"),
        follows_count=_get(profile, "follows_count"),
        posts_count=_get(profile, "posts_count"),
        you_follow=bool(_get(viewer, "following")),
        follows_you=bool(_get(viewer, "followed_by")),
    )


def to_notification(notification: Any) -> NotificationView:
    author = _get(notification, "author")
    subject = _get(notification, "reason_subject") or _get(notification, "uri")
    subject_url = None
    if isinstance(subject, str) and "/app.bsky.feed.post/" in subject:
        subject_url = post_url(repo_of(subject), subject)
    return NotificationView(
        reason=_get(notification, "reason", ""),
        author_handle=_get(author, "handle", "unknown"),
        author_display_name=_get(author, "display_name"),
        subject_url=subject_url,
        text=_get(_get(notification, "record"), "text"),
        indexed_at=_get(notification, "indexed_at", ""),
        is_read=bool(_get(notification, "is_read")),
    )


def _thread_post(node: Any) -> PostView | None:
    post = _get(node, "post")
    return to_post(post) if post is not None else None


def to_thread_replies(node: Any) -> list[ThreadReply]:
    replies: list[ThreadReply] = []
    for child in _get(node, "replies") or []:
        post = _thread_post(child)
        if post is not None:
            replies.append(ThreadReply(post=post, replies=to_thread_replies(child)))
    return replies


def to_thread(thread: Any) -> ThreadView:
    post = _thread_post(thread)
    if post is None:
        raise LookupError("Thread not found or not visible.")
    parents: list[PostView] = []
    parent = _get(thread, "parent")
    while parent is not None:
        parent_post = _thread_post(parent)
        if parent_post is None:
            break
        parents.insert(0, parent_post)
        parent = _get(parent, "parent")
    return ThreadView(post=post, parents=parents, replies=to_thread_replies(thread))


def to_draft(draft_view: Any) -> DraftView:
    draft = _get(draft_view, "draft")
    posts = []
    for item in _get(draft, "posts") or []:
        records = _get(item, "embed_records") or []
        externals = _get(item, "embed_externals") or []
        posts.append(
            DraftPostView(
                text=_get(item, "text", ""),
                quote_uri=_get(_get(records[0], "record"), "uri") if records else None,
                link_url=_get(externals[0], "uri") if externals else None,
            )
        )
    return DraftView(
        draft_id=_get(draft_view, "id", ""),
        posts=posts,
        created_at=_get(draft_view, "created_at"),
        updated_at=_get(draft_view, "updated_at"),
    )


# -- spec 002: discovery and list models --------------------------------------------------------

BSKY_APP = "https://bsky.app"


class FeedView(BaseModel):
    uri: str
    url: str
    name: str
    creator_handle: str
    description: str | None = None
    like_count: int | None = None
    is_online: bool | None = None
    is_valid: bool | None = None


class FeedPage(BaseModel):
    feeds: list[FeedView]
    cursor: str | None = None


class ListInfo(BaseModel):
    uri: str
    url: str
    name: str
    purpose: str
    creator_handle: str
    description: str | None = None
    member_count: int | None = None


class ListPage(BaseModel):
    lists: list[ListInfo]
    cursor: str | None = None


class ListDetail(BaseModel):
    list: ListInfo
    members: list[ProfileView]
    cursor: str | None = None


class StarterPackInfo(BaseModel):
    uri: str
    url: str
    name: str
    creator_handle: str
    description: str | None = None
    joined_week_count: int | None = None
    joined_all_time_count: int | None = None


class StarterPackPage(BaseModel):
    starter_packs: list[StarterPackInfo]
    cursor: str | None = None


class StarterPackDetail(BaseModel):
    starter_pack: StarterPackInfo
    list_url: str | None = None
    members: list[ProfileView]
    cursor: str | None = None


class TrendingTopic(BaseModel):
    topic: str
    display_name: str | None = None
    description: str | None = None
    url: str


class TrendingPage(BaseModel):
    topics: list[TrendingTopic]


class FollowResult(BaseModel):
    actor: str
    status: str
    handle: str | None = None
    record_uri: str | None = None
    message: str | None = None


class FollowResults(BaseModel):
    results: list[FollowResult]


class ListMembershipResult(BaseModel):
    actor: str
    status: str


class ListMembershipResults(BaseModel):
    list_url: str
    results: list[ListMembershipResult]


class DeletedList(BaseModel):
    deleted: bool
    url: str
    name: str
    members_removed: int


def _creator_handle(view: Any) -> str:
    return _get(_get(view, "creator"), "handle", "unknown")


def to_feed(view: Any, is_online: bool | None = None, is_valid: bool | None = None) -> FeedView:
    uri = _get(view, "uri", "")
    handle = _creator_handle(view)
    return FeedView(
        uri=uri,
        url=f"{BSKY_APP}/profile/{handle}/feed/{rkey_of(uri)}",
        name=_get(view, "display_name", "") or "",
        creator_handle=handle,
        description=_get(view, "description"),
        like_count=_get(view, "like_count"),
        is_online=is_online,
        is_valid=is_valid,
    )


def to_list(view: Any) -> ListInfo:
    uri = _get(view, "uri", "")
    handle = _creator_handle(view)
    return ListInfo(
        uri=uri,
        url=f"{BSKY_APP}/profile/{handle}/lists/{rkey_of(uri)}",
        name=_get(view, "name", "") or "",
        purpose=str(_get(view, "purpose", "")).rsplit("#", 1)[-1],
        creator_handle=handle,
        description=_get(view, "description"),
        member_count=_get(view, "list_item_count"),
    )


def to_starter_pack(view: Any) -> StarterPackInfo:
    uri = _get(view, "uri", "")
    handle = _creator_handle(view)
    record = _get(view, "record")
    return StarterPackInfo(
        uri=uri,
        url=f"{BSKY_APP}/starter-pack/{handle}/{rkey_of(uri)}",
        name=_get(record, "name", "") or "",
        creator_handle=handle,
        description=_get(record, "description"),
        joined_week_count=_get(view, "joined_week_count"),
        joined_all_time_count=_get(view, "joined_all_time_count"),
    )


def to_trending(topic: Any) -> TrendingTopic:
    link = str(_get(topic, "link", "") or "")
    return TrendingTopic(
        topic=_get(topic, "topic", ""),
        display_name=_get(topic, "display_name"),
        description=_get(topic, "description"),
        url=link
        if link.startswith("http")
        else f"{BSKY_APP}{link if link.startswith('/') else '/' + link}",
    )
