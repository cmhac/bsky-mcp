# Quickstart: Validating the Personal Bluesky MCP Server

A run-and-verify guide. Setup steps for the owner are written in full in the README (spec FR-024);
this file lists the checks that prove the feature works. Contracts: [tools](./contracts/tools.md),
[routes](./contracts/http-routes.md), [configuration](./contracts/configuration.md).

## Prerequisites

- uv, Python 3.13, Java 17+ (for the CPD hook), pre-commit
- A Bluesky app password, a GitHub OAuth app, a Vercel project, and an Upstash Redis database
  (see README)

## 1. Local quality gates

```bash
uv sync
pre-commit install
pre-commit run --all-files     # ruff-check, ruff-format, ty, cpd (50 tokens)
uv run pytest                  # contract, unit, and safety tests
```

Expected: all hooks and tests pass. Then add a duplicated 60-token block to `src/` and commit:
the `cpd` hook fails and names both locations.

## 2. Safety tests (no network)

```bash
uv run pytest tests/safety -v
```

Expected passes:

- No tool or `SafeBlueskyClient` method can create an `app.bsky.feed.post` record.
- `deleteDraft`, block, and unblock are unreachable.
- `delete_post` without `confirm="delete"` returns `confirmation_required`; on another author's
  post it returns `not_owner`.
- Server instructions and the `create_draft` / `delete_post` descriptions contain the required
  wording.

## 3. Draft endpoint smoke test (first implementation task; real account)

```bash
BLUESKY_HANDLE=… BLUESKY_APP_PASSWORD=… uv run python scripts/smoke_drafts.py
```

Expected: creates a draft named "bsky-mcp smoke test", reads it back, updates it, and prints its ID.
Open Drafts in the Bluesky app and confirm it appears; delete it there by hand. If the app password
is refused for drafts, stop and revisit research R6.

## 4. Access control on a preview or production deployment

From a machine outside Anthropic's range:

```bash
curl -i "$BASE_URL/mcp"                                   # expect 403 (IP)
curl -i "$BASE_URL/.well-known/oauth-authorization-server" # expect 403 (IP)
curl -i "$BASE_URL/authorize"                             # expect not 403 (exempt; 4xx for missing params is fine)
```

## 5. Connect Claude

1. Add the custom connector in Claude with the production `BASE_URL` + `/mcp`, choosing sign-in.
2. Sign in with the owner's GitHub account and approve the consent page. Expected: tools appear.
3. Sign in from a second GitHub account (incognito). Expected: no tools; calls denied.

## 6. End-to-end behavior (spec success criteria)

| Check | Expected |
| --- | --- |
| Phone app: "summarize my notifications" | Matches the Bluesky app (SC-008) |
| Scheduled task: "list my timeline" | Works with no one present (SC-008) |
| "Write a post about X" ×20 variants, including "post this" | 0 published; each is a draft in the app (SC-003) |
| Scheduled task: "delete my latest post" ×10 variants | 0 deletions (SC-004) |
| "Delete my post <url>" typed by the owner | Post deleted (User Story 4) |
| Like, repost, follow, then undo each | Each appears, then disappears (User Story 3) |
| Ask to block someone | No tool; Claude says it can't (User Story 3) |

## 7. CI/CD

Open a PR with a deliberate lint error. Expected: the CI job fails with the same message as the
local hook, and Vercel posts a preview URL. Fix it, merge, and confirm production redeploys.
