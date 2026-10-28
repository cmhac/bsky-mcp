# Implementation Plan: Personal Bluesky MCP Server

**Branch**: `001-bluesky-mcp-server` | **Date**: 2026-10-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-bluesky-mcp-server/spec.md`

## Summary

A FastMCP server, deployed on Vercel, that gives the owner's Claude account read access to their
Bluesky account, draft-only content creation into Bluesky Drafts, reversible engagement (follow,
like, repost and their undos), and owner-guarded deletion of the owner's own posts. It cannot
publish or block. Access requires GitHub OAuth restricted to the owner's GitHub user ID **and** a
request IP inside Anthropic's published outbound range, except for the browser-facing sign-in
pages. OAuth state lives in an encrypted Redis-compatible store. Quality gates (Ruff, ty, PMD CPD at
50 tokens) run in pre-commit and identically on PRs; Vercel's Git integration handles preview and
production deploys. Details and sources: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: FastMCP 4.x (GitHubProvider OAuth proxy, AuthMiddleware), atproto
(Bluesky SDK), py-key-value-aio[redis] with FernetEncryptionWrapper, Starlette middleware (via
FastMCP), grapheme counting library (choice deferred to tasks; must count extended grapheme clusters)

**Storage**: Redis-compatible store over TLS (Upstash via Vercel Marketplace), application-encrypted;
used only for OAuth client registrations and tokens. Drafts live in Bluesky.

**Testing**: pytest, pytest-asyncio, FastMCP in-memory client, fake Bluesky backend

**Target Platform**: Vercel Python runtime (serverless), stateless HTTP transport at `/mcp`

**Project Type**: Web service (remote MCP server)

**Performance Goals**: 95% of read tool calls return in under 5 s under normal Bluesky conditions
(spec SC-002); Bluesky calls time out after 10 s

**Constraints**: Stateless across instances; no secrets in logs or tool output; fail closed on auth,
IP, and configuration errors; at most 300 graphemes per draft post

**Scale/Scope**: One owner, one Bluesky account, one Claude account; ~20 tools

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate | Pre-design | Post-design |
| --- | --- | --- | --- |
| I. Spec-Driven Development | Work traced to spec 001 on branch `001-bluesky-mcp-server` | Pass | Pass |
| II. Least-Privilege Access | No block; deletions limited to unfollow, unlike, un-repost, own-post delete; enforced by `SafeBlueskyClient` allowlist with tests | Pass | Pass ([contracts/tools.md](./contracts/tools.md), R7) |
| II. Guarded delete | `delete_post` requires `confirm="delete"`, own-author check, owner-message-only description | Pass | Pass (R8) |
| III. Draft-Only | No publish tool or code path; `createRecord` for posts unreachable; test enforces | Pass | Pass (R7) |
| IV. Defense in Depth | GitHub OAuth + user-ID allowlist; IP allowlist on all but browser sign-in routes; both on by default | Pass | Pass ([contracts/http-routes.md](./contracts/http-routes.md)) |
| V. Secrets Hygiene | Secrets only in Vercel Secret env vars; app password; encrypted token storage; redaction | Pass | Pass ([contracts/configuration.md](./contracts/configuration.md)) |
| VI. Quality Gates | Ruff, ty, CPD ≥50 tokens in pre-commit and on PRs | Pass, with caveat: merge blocking on a private repo needs GitHub Pro (R9) | Same |
| VII. Continuous Delivery | Vercel previews per PR, prod on `main`, Deploy button | Pass | Pass (R10) |
| Docs constraints | README covers all five required topics with source links | Pass | Pass ([quickstart.md](./quickstart.md)) |

No violations requiring Complexity Tracking. Two items need the owner (see "Open items").

## Project Structure

### Documentation (this feature)

```text
specs/001-bluesky-mcp-server/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── tools.md         # MCP tool contracts
│   ├── http-routes.md   # HTTP routes, auth and IP rules
│   └── configuration.md # Environment variables
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/bsky_mcp/
├── __init__.py
├── app.py               # ASGI entrypoint: builds FastMCP server + http_app, exports `app`
├── config.py            # Typed settings from env; fails closed on missing/invalid values
├── auth.py              # GitHubProvider setup, encrypted Redis storage, user-ID AuthMiddleware check
├── ip_allowlist.py      # ASGI middleware: trusted client IP, CIDR check, exempt paths
├── bluesky/
│   ├── client.py        # SafeBlueskyClient: allowlisted operations only; session handling
│   ├── operations.py    # The explicit operation allowlist (single source of truth)
│   ├── text.py          # Grapheme validation, URL/handle parsing
│   └── formatting.py    # Shapes SDK responses into tool result models
├── tools/
│   ├── read.py          # Timeline, notifications, thread, profiles, search, follows
│   ├── drafts.py        # create/update/list drafts
│   ├── engagement.py    # follow/unfollow, like/unlike, repost/unrepost
│   └── delete.py        # Guarded delete_post
├── instructions.py      # Server instructions text (draft-only, delete rule)
└── logging.py           # Structured logging with secret redaction

tests/
├── conftest.py          # In-memory FastMCP client, fake Bluesky backend, settings fixtures
├── contract/            # One module per tool group, against contracts/tools.md
├── unit/                # config, ip_allowlist, auth check, text validation, redaction
└── safety/              # Forbidden-operation and guard tests (Principles II, III)

scripts/
└── cpd.sh               # Downloads pinned PMD, verifies checksum, runs CPD at 50 tokens

.github/workflows/ci.yml # pre-commit run --all-files + pytest on pull_request and push to main
.pre-commit-config.yaml
pyproject.toml           # uv project, ruff/ty config, [tool.vercel] entrypoint
vercel.json              # Function config (excludeFiles for tests/specs)
.env.example             # Every variable from contracts/configuration.md, no values
README.md                # Deploy button, setup and security docs
```

**Structure Decision**: Single Python package under `src/` with one ASGI entrypoint, matching
Vercel's `tool.vercel.entrypoint` model. Safety-critical logic (`bluesky/operations.py`,
`ip_allowlist.py`, `auth.py`) is isolated in small modules so the safety tests can target them
directly.

## Key Design Points

1. **Request path**: Vercel → `IPAllowlistMiddleware` (skips only exempt sign-in routes) →
   FastMCP OAuth (GitHub token verification) → `AuthMiddleware` user-ID check → tool →
   `SafeBlueskyClient`.
2. **Bluesky session**: The app password is used to create a session on cold start; the session is
   cached in memory per instance and refreshed on expiry. Bluesky session tokens are not persisted.
   Login rate limits are stricter than other calls ([AT Protocol SDK auth guide](https://atproto.com/guides/sdk-auth)),
   so the client logs in once per instance, not per request.
3. **Fail closed**: Missing `ALLOWED_GITHUB_USER_IDS`, `ALLOWED_IP_RANGES`, `JWT_SIGNING_KEY`,
   `STORAGE_ENCRYPTION_KEY`, or `REDIS_URL` in production stops startup with a clear error.
   Disabling OAuth or the IP check needs `UNSAFE_DISABLE_OAUTH=true` or
   `UNSAFE_DISABLE_IP_ALLOWLIST=true`, logged as a warning on every cold start and documented in
   the README as reducing security.
4. **Tool descriptions are part of the safety model**: The draft, delete, and server-instruction
   texts are fixed strings in `instructions.py`, covered by tests that assert the required phrases.

## Open items for the owner

1. **Reply drafts** (blocks User Story 2, scenario 1): Bluesky's draft format has no reply-target
   field. Recommended: Claude writes replies in chat with the parent link (Option C in
   [research.md](./research.md#open-decision-for-the-owner-reply-drafts)). The spec will be updated
   once the owner chooses.
2. **Merge blocking on a private repo**: requires GitHub Pro, or making the repo public (R9).

## Complexity Tracking

No constitution violations to justify.
