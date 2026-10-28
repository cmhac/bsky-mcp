# Data Model: Personal Bluesky MCP Server

The server stores no Bluesky content of its own. Bluesky holds posts, drafts, and engagement
records; the server stores only OAuth state. Entities below are the shapes the server validates and
returns.

## Settings (from environment)

Defined in [contracts/configuration.md](./contracts/configuration.md). Loaded once per instance and
validated at startup; invalid or missing required values stop startup.

## AllowedUser

| Field | Type | Rules |
| --- | --- | --- |
| github_user_id | int | From `ALLOWED_GITHUB_USER_IDS` (comma-separated). At least one required. |

A request passes the user check only if the verified token's `sub` claim equals one of these IDs.

## IPRange

| Field | Type | Rules |
| --- | --- | --- |
| network | IPv4 or IPv6 CIDR | From `ALLOWED_IP_RANGES` (comma-separated). Default `160.79.104.0/21`. Invalid CIDR stops startup. |

## Draft (Bluesky `app.bsky.draft`)

| Field | Type | Rules |
| --- | --- | --- |
| id | string (TID) | Assigned by Bluesky on create. |
| posts | list of DraftPost | 1–100 items; more than one means a thread. |
| device_name | string | Always `Claude (bsky-mcp)` for drafts this server creates. |
| langs | list of language codes | Optional, at most 3. |
| created_at / updated_at | datetime | From Bluesky. |

### DraftPost

| Field | Type | Rules |
| --- | --- | --- |
| text | string | Required unless a quote or link card is attached; at most 300 graphemes (published-post limit). |
| quote_uri | AT-URI or bsky.app URL | Optional; resolved to a strong reference (URI + CID). |
| link_url | https URL | Optional; stored as an external embed. |

**State transitions**: `created` → `updated` (any number of times). The server has no delete or
publish transition; the owner publishes or deletes drafts in a Bluesky app.

## PostView (returned by read tools)

| Field | Type |
| --- | --- |
| uri | AT-URI |
| url | `https://bsky.app/profile/{handle}/post/{rkey}` |
| author_handle, author_display_name | string |
| text | string |
| created_at | datetime |
| reply_count, repost_count, like_count, quote_count | int or null |
| reply_parent_url | string or null |
| viewer_liked, viewer_reposted | bool (whether the owner has liked/reposted) |

## ProfileView, NotificationView

- **ProfileView**: handle, display name, description, follower/following/post counts, whether the
  owner follows them, profile URL.
- **NotificationView**: reason (like, repost, follow, mention, reply, quote), author handle, subject
  post URL if any, indexed time, read flag.

## EngagementRecord

| Field | Type | Rules |
| --- | --- | --- |
| kind | follow, like, repost | |
| subject | DID (follow) or post URI (like, repost) | |
| record_uri | AT-URI | Must be in the owner's own repo to be undone. |

Undo tools locate the owner's record via the subject's viewer state; if none exists, they return
"nothing to undo" (spec edge case).

## OAuth state (encrypted Redis)

Managed by FastMCP's OAuth proxy: client registrations, transactions, upstream GitHub tokens, and
issued JWT metadata. Every value is Fernet-encrypted by the application before it reaches Redis.
Keys are namespaced by collection. The server never reads these directly.
