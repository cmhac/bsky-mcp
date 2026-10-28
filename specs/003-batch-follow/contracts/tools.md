# Tool contract changes: Batch Follow

Only one tool changes. Every other tool keeps its contract from specs 001 and 002.

| Tool | Hints | Input | Behavior |
| --- | --- | --- | --- |
| `follow` | idempotent, non-destructive | `actors` (1-25 handles or DIDs) | Follows each account not already followed; per-account result `followed` / `already_following` / `not_found` / `is_you` / `failed` / `not_attempted` |

- **Replaces** `follow(actor)`. The `actor` input no longer exists; sending it is a validation error.
- **Description** (FR-010) says: up to 25 accounts per call; accounts already followed are skipped;
  retry by resending only `failed` and `not_attempted` accounts; if Bluesky rate-limits the call, the
  rest are `not_attempted`, so wait before resending them.
- **Errors for the whole call**: `invalid_input` for 0 or more than 25 accounts (nothing written);
  `bluesky_auth_failed` / `not_configured` as for every tool.
- **Unchanged**: `unfollow(actor)` stays single-account.
- `add_to_list`'s error message wording for a bad batch size now reads "Provide between 1 and 25
  accounts at a time." (shared validator).

Example response:

```json
{"results": [
  {"actor": "a.bsky.social", "status": "followed", "handle": "a.bsky.social", "record_uri": "at://.../app.bsky.graph.follow/3k..."},
  {"actor": "b.bsky.social", "status": "already_following", "handle": "b.bsky.social", "record_uri": "at://.../app.bsky.graph.follow/3j..."},
  {"actor": "nope.invalid", "status": "not_found"}
]}
```

## Still impossible

Unchanged: publishing, blocking, muting, moderation lists, draft deletion. `tests/safety` pins the
tool set (`follow` stays, no new name) and the operation allowlist (no new operation).
