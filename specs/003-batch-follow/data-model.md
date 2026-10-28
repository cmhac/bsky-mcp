# Data Model: Batch Follow

No stored data. These are the tool's request and response shapes.

## FollowResults (response)

| Field | Type | Notes |
| --- | --- | --- |
| `results` | list of FollowResult | One per requested entry, in request order, always the same length as the request |

## FollowResult

| Field | Type | Notes |
| --- | --- | --- |
| `actor` | string | The handle or DID exactly as the caller supplied it |
| `status` | string | See below |
| `handle` | string or null | Resolved handle when known |
| `record_uri` | string or null | The follow record (new or existing) for `followed` and `already_following` |
| `message` | string or null | Reason, for `failed`, `is_you`, and `not_attempted` |

## Status values

| Status | Meaning | Retry by resending? |
| --- | --- | --- |
| `followed` | A follow was created | No |
| `already_following` | The owner already followed it (or it repeated earlier in the call) | No |
| `not_found` | Not a valid handle or DID, or no such account | Only with a corrected handle |
| `is_you` | The owner's own account; nothing written | No |
| `failed` | Bluesky refused this account; `message` says why | Maybe |
| `not_attempted` | Skipped because Bluesky rate-limited the call earlier | Yes, after waiting |

## Request

`actors`: list of 1-25 strings (handle or DID). Empty or longer lists are refused before any
request. The old `actor` string is gone.
