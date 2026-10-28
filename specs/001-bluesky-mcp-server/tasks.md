---

description: "Task list for the personal Bluesky MCP server"
---

# Tasks: Personal Bluesky MCP Server

**Input**: Design documents from `/specs/001-bluesky-mcp-server/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required. The spec mandates tests for forbidden operations and guards (FR-013, SC-006),
and the constitution requires tests for any change to tools, auth, IP filtering, or the operation
allowlist. Write each story's tests first and confirm they fail before implementing.

**Organization**: Tasks are grouped by user story (US numbers match spec.md) so each story can be
implemented and tested on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: The spec user story the task serves (US1–US6)

## Path Conventions

Single project: `src/bsky_mcp/`, `tests/`, `scripts/` at the repository root, per plan.md.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and local quality gates, so every later commit is checked.

- [X] T001 Create the package layout from plan.md: `src/bsky_mcp/{__init__,app,config,auth,ip_allowlist,instructions,logging}.py`, `src/bsky_mcp/bluesky/{__init__,client,operations,text,formatting}.py`, `src/bsky_mcp/tools/{__init__,read,drafts,engagement,delete}.py`, `tests/{contract,unit,safety}/__init__.py`, and `scripts/` (empty modules with docstrings only)
- [X] T002 Initialize `pyproject.toml` as a uv project: `requires-python = ">=3.13"`, runtime deps `fastmcp>=4.1,<5`, `atproto`, `py-key-value-aio[redis]`, a grapheme-cluster counting library, `pydantic-settings`; dev group `pytest`, `pytest-asyncio`, `ruff`, `ty`, `pre-commit`; `[tool.vercel] entrypoint = "bsky_mcp.app:app"`; run `uv lock` to create `uv.lock`
- [X] T003 [P] Add `.python-version` (`3.13`) and a `.gitignore` covering `.venv/`, `.env`, `.pmd/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`
- [X] T004 [P] Configure Ruff (lint rules incl. `E,F,I,B,UP,S,SIM`, line length 100) and ty in `pyproject.toml`
- [X] T005 [P] Write `scripts/cpd.sh`: download PMD **7.28.0** `pmd-dist-7.28.0-bin.zip` from the GitHub release into `.pmd/` if missing, verify a pinned SHA-256 (record the checksum computed on first download in the script), then run `pmd cpd --minimum-tokens 50 --language python --dir src --dir tests`; propagate CPD's exit code (4 = duplicates found)
- [X] T006 Create `.pre-commit-config.yaml` with pinned revs: `astral-sh/ruff-pre-commit` (`ruff-check --fix`, `ruff-format`), `astral-sh/ty-pre-commit` (`ty`), and a local `cpd` hook (`language: system`, `entry: scripts/cpd.sh`, `pass_filenames: false`, `types: [python]`); run `pre-commit run --all-files` and confirm it passes on the skeleton
- [X] T007 [P] Create `.env.example` listing every variable in contracts/configuration.md with empty values and a one-line comment each (mark Secret ones)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configuration, logging, the operation allowlist, the IP and user checks, and the app
entrypoint. Every user story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for the foundation (write first, confirm they fail)

- [X] T008 [P] Unit tests for settings in `tests/unit/test_config.py`: missing required vars fail startup; invalid CIDR fails; `JWT_SIGNING_KEY` shorter than 32 bytes fails; malformed Fernet key fails; non-HTTPS `BASE_URL` fails when `VERCEL_ENV=production`; `BLUESKY_HANDLE`/`BLUESKY_APP_PASSWORD` required only when `VERCEL_ENV=production`; `ALLOWED_IP_RANGES` defaults to `160.79.104.0/21`; `UNSAFE_DISABLE_*` default false
- [X] T009 [P] Unit tests for redaction in `tests/unit/test_logging.py`: no configured secret value (`BLUESKY_APP_PASSWORD`, `GITHUB_CLIENT_SECRET`, `JWT_SIGNING_KEY`, `STORAGE_ENCRYPTION_KEY`, `REDIS_URL`) ever appears in log output, including inside exception messages
- [X] T010 [P] Unit tests for the IP middleware in `tests/unit/test_ip_allowlist.py`: on Vercel, IP comes from `x-vercel-forwarded-for`; off Vercel, client-supplied forwarding headers are ignored and the ASGI peer is used; enforced routes return 403 outside the allowlist; exempt paths match exactly (no prefix matching, e.g. `/authorize/x` is enforced); `UNSAFE_DISABLE_IP_ALLOWLIST=true` bypasses and logs a warning
- [X] T011 [P] Unit tests for the user check in `tests/unit/test_auth_check.py`: token `sub` in `ALLOWED_GITHUB_USER_IDS` passes; any other ID, a missing token, or a matching `login` with a different `sub` fails; denied users see an empty tool list and tool calls raise authorization errors
- [X] T012 [P] Safety tests in `tests/safety/test_operations_allowlist.py`: the allowlist in `bluesky/operations.py` contains no `createRecord` for `app.bsky.feed.post`, no `app.bsky.draft.deleteDraft`, no block/unblock (`app.bsky.graph.block`), no list, mute, or chat operations; `deleteRecord` is allowed only for collections `app.bsky.graph.follow`, `app.bsky.feed.like`, `app.bsky.feed.repost`, `app.bsky.feed.post`; `SafeBlueskyClient`'s public attributes expose no raw atproto client and no method outside the allowlist; calling any non-allowlisted operation raises
- [X] T013 [P] Unit tests for text helpers in `tests/unit/test_text.py`: grapheme counting treats emoji and combining sequences as single graphemes; "at most 300 graphemes" passes at 300 and fails at 301; bsky.app post URLs and AT-URIs both parse; handles with/without `@` and DIDs parse; malformed inputs raise `invalid_input`

### Implementation for the foundation

- [X] T014 Implement typed settings in `src/bsky_mcp/config.py` per contracts/configuration.md (pydantic-settings; validation rules from T008; never include values in error messages)
- [X] T015 [P] Implement structured logging with secret redaction in `src/bsky_mcp/logging.py` (redacts every Secret-marked setting value; logs only whether a variable is set)
- [X] T016 [P] Implement `src/bsky_mcp/bluesky/text.py`: grapheme counting, `validate_post_text` ("at most 300 graphemes"), post-identifier parsing (AT-URI or `https://bsky.app/profile/{handle}/post/{rkey}`), actor parsing (handle or DID)
- [X] T017 Implement the operation allowlist in `src/bsky_mcp/bluesky/operations.py` as the single source of truth (reads; `app.bsky.draft.createDraft`, `getDrafts`, `updateDraft`; createRecord for follow/like/repost; deleteRecord for follow/like/repost/post in the session DID's repo only)
- [X] T018 Implement `SafeBlueskyClient` core in `src/bsky_mcp/bluesky/client.py`: holds the atproto client privately; logs in once per instance with the app password and refreshes the session on expiry (do not persist Bluesky tokens); every call routes through an `_invoke(operation, ...)` that rejects operations not in `operations.py`; 10 s timeout; maps errors to `bluesky_auth_failed`, `bluesky_unavailable`, `not_found`, `not_configured`
- [X] T019 Implement the IP allowlist ASGI middleware in `src/bsky_mcp/ip_allowlist.py` per contracts/http-routes.md (trusted IP source, CIDR check, exact-path exemptions from `IP_ALLOWLIST_EXEMPT_PATHS`, generic 403 body, log path + IP only)
- [X] T020 Implement auth in `src/bsky_mcp/auth.py`: `GitHubProvider` with `base_url=BASE_URL`, explicit `jwt_signing_key`, `client_storage=FernetEncryptionWrapper(RedisStore(url=REDIS_URL), fernet=...)`, `require_authorization_consent=True`, `allowed_client_redirect_uris` from settings; plus the `AuthMiddleware` check on the token's `sub` against `ALLOWED_GITHUB_USER_IDS`; honor `UNSAFE_DISABLE_OAUTH` with a cold-start warning
- [X] T021 Write the fixed safety texts in `src/bsky_mcp/instructions.py`: server instructions (the three rules in contracts/tools.md), and the `create_draft` and `delete_post` descriptions verbatim as required there
- [X] T022 Implement `src/bsky_mcp/app.py`: build the FastMCP server with `instructions`, auth, and middleware; register tool modules; export `app = mcp.http_app(path="/mcp", stateless_http=True, middleware=[IPAllowlistMiddleware])`; record the FastMCP consent-page path in contracts/http-routes.md and as the default in `IP_ALLOWLIST_EXEMPT_PATHS`
- [X] T023 Create test fixtures in `tests/conftest.py`: settings factory, a fake Bluesky backend implementing the allowlisted operations in memory (owner DID, other-author posts, drafts store), a FastMCP `Client(transport=mcp)` fixture with a fake access token for an allowed and a denied user, and an ASGI test client for middleware tests
- [ ] T024 (script written; owner run pending) Write `scripts/smoke_drafts.py` (quickstart step 3) and run it against the owner's real account to confirm an app password can call `createDraft`, `getDrafts`, and `updateDraft`; if refused, stop and report before Phase 4

**Checkpoint**: `pre-commit run --all-files` and `uv run pytest tests/unit tests/safety` pass.

---

## Phase 3: User Story 1 - Read my Bluesky from any Claude session (Priority: P1) 🎯 MVP

**Goal**: Claude can read the owner's timeline, notifications, threads, profiles, posts,
follows, and search results.

**Independent Test**: With the connector set up, "summarize my notifications" from the phone app
matches the Bluesky app (quickstart step 6).

### Tests for User Story 1

- [X] T025 [P] [US1] Contract tests in `tests/contract/test_read_tools.py` for all ten read tools in contracts/tools.md: input bounds (`limit` 1–100, default 25; `depth` 0–10, default 6; `parent_height` 0–20, default 10), paging cursors, `readOnlyHint: true`, PostView/ProfileView/NotificationView fields from data-model.md, and `not_found`/`invalid_input` errors

### Implementation for User Story 1

- [X] T026 [P] [US1] Implement response shaping in `src/bsky_mcp/bluesky/formatting.py`: PostView (incl. `url` as `https://bsky.app/profile/{handle}/post/{rkey}`, counts, `reply_parent_url`, `viewer_liked`, `viewer_reposted`), ProfileView, NotificationView
- [X] T027 [US1] Add read methods to `SafeBlueskyClient` in `src/bsky_mcp/bluesky/client.py` (timeline, notifications, thread, profile, author feed, followers, follows, search posts, search actors)
- [X] T028 [US1] Implement the read tools in `src/bsky_mcp/tools/read.py` (`get_my_profile`, `get_timeline`, `get_notifications`, `get_thread`, `get_profile`, `get_author_posts`, `get_followers`, `get_follows`, `search_posts`, `search_users`) with annotations and bounds from contracts/tools.md

**Checkpoint**: US1 contract tests pass; the server is useful read-only.

---

## Phase 4: User Story 2 - Draft posts into my Bluesky Drafts (Priority: P1)

**Goal**: Claude saves posts and threads to Bluesky Drafts and can revise and list them; it cannot
publish, and writes replies in chat.

**Independent Test**: "Write a post about my new story" creates a draft visible in the Bluesky app
and nothing on the public profile (quickstart step 6).

### Tests for User Story 2

- [X] T029 [P] [US2] Contract tests in `tests/contract/test_draft_tools.py`: `create_draft` with 1–100 posts; each post "at most 300 graphemes" (error names post index and count); empty post with no embed rejected; `quote` resolves to a strong reference; `link_url` must be https; `device_name` is `Claude (bsky-mcp)`; `langs` at most 3; `update_draft` re-reads and returns `draft_not_found` when missing; `list_drafts` paging; no tool accepts a reply target
- [X] T030 [P] [US2] Safety tests in `tests/safety/test_no_publishing.py`: no registered tool and no `SafeBlueskyClient` method can create an `app.bsky.feed.post` record; server instructions and the `create_draft` description contain the required draft-only and reply-in-chat wording from contracts/tools.md

### Implementation for User Story 2

- [X] T031 [US2] Add draft methods to `SafeBlueskyClient` in `src/bsky_mcp/bluesky/client.py` (`create_draft`, `update_draft` with re-read check, `get_drafts`; never `delete_draft`)
- [X] T032 [US2] Implement `create_draft`, `update_draft`, `list_drafts` in `src/bsky_mcp/tools/drafts.py` using the descriptions from `instructions.py`; responses include the note that the owner publishes from a Bluesky app

**Checkpoint**: US1 and US2 work independently.

---

## Phase 5: User Story 5 - Deploy and connect it myself, securely (Priority: P1)

**Goal**: One-click deploy, documented setup, and verified access control in a real deployment.

**Independent Test**: Someone following only the README ends with a working connector; a second
GitHub account and an outside IP are refused (quickstart steps 4–5).

### Tests for User Story 5

- [X] T033 [P] [US5] Integration tests in `tests/contract/test_http_routes.py` using the ASGI app: every route in contracts/http-routes.md has the stated IP rule (enforced vs exempt), unknown paths 404, `/mcp` without a token is rejected, and startup fails closed with missing required production settings

### Implementation for User Story 5

- [X] T034 [P] [US5] Add `vercel.json` (`$schema` only) and a `.vercelignore` excluding `tests/`, `specs/`, `.specify/`, `.claude/`, `.pmd/`, `.github/`, `scripts/` (a `functions` key was dropped because its path form for a `src/` package entrypoint is not documented)
- [X] T035 [US5] Write `README.md`: overview and safety model (cannot publish; delete guard relies on descriptions plus confirmation input and the server cannot verify who wrote an instruction — FR-025); "Deploy with Vercel" button using `https://vercel.com/new/clone?repository-url=…&env=…&envDescription=…&envLink=…` listing the required variables
- [X] T036 [US5] README section: create a Bluesky app password (Settings → App Passwords), never the main password, how to revoke it; link sources
- [X] T037 [US5] README section: create the GitHub OAuth app (homepage, callback `{BASE_URL}/auth/callback`), find your numeric GitHub user ID, set `ALLOWED_GITHUB_USER_IDS`; link FastMCP's GitHub integration docs
- [X] T038 [US5] README section: deploy securely to Vercel — add Upstash Redis from the Vercel Marketplace, generate `JWT_SIGNING_KEY` and `STORAGE_ENCRYPTION_KEY`, store every Secret from contracts/configuration.md as a Vercel Secret environment variable (link Vercel's docs saying Secret values are write-only), keep Standard Deployment Protection
- [X] T039 [US5] README section: IP allowlist — default `160.79.104.0/21`, link Anthropic's IP address page, list the exempt sign-in routes and why, explain `UNSAFE_DISABLE_*` as reducing security
- [X] T040 [US5] README section: add the Claude custom connector (`{BASE_URL}/mcp`, sign in with GitHub, approve consent); link Anthropic's custom connector article stating connector credentials are stored encrypted; note it works on web, mobile, and scheduled tasks
- [ ] T041 (owner setup pending) [US5] Deploy to Vercel production and run quickstart steps 4–5 (outside-IP 403s, owner sign-in shows tools, second GitHub account sees none); fix any discovered exempt-path or redirect-URI mismatch in settings defaults and contracts/http-routes.md

**Checkpoint**: The P1 MVP (read + draft, securely deployed) is live.

---

## Phase 6: User Story 3 - Engage: follow, like, repost, and undo them (Priority: P2)

**Goal**: Reversible engagement on the owner's behalf; blocking impossible.

**Independent Test**: Like, repost, and follow, confirm in the app, then undo each and confirm.

### Tests for User Story 3

- [ ] T042 [P] [US3] Contract tests in `tests/contract/test_engagement_tools.py`: `follow`/`like`/`repost` are idempotent (return the existing record); `unfollow`/`unlike`/`unrepost` remove only the owner's record and return "nothing to undo" when none exists; annotations `destructiveHint: false`, `idempotentHint: true`
- [ ] T043 [P] [US3] Safety test in `tests/safety/test_no_block.py`: no tool or client method can create or delete `app.bsky.graph.block` records; undo methods refuse record URIs outside the session DID's repo

### Implementation for User Story 3

- [ ] T044 [US3] Add engagement methods to `SafeBlueskyClient` in `src/bsky_mcp/bluesky/client.py` (create/delete follow, like, repost; locate the owner's record via viewer state; enforce the session-DID repo check)
- [ ] T045 [US3] Implement `follow`, `unfollow`, `like`, `unlike`, `repost`, `unrepost` in `src/bsky_mcp/tools/engagement.py`

**Checkpoint**: US3 works independently of US2 and US4.

---

## Phase 7: User Story 6 - Every change is checked and shipped automatically (Priority: P2)

**Goal**: The same checks on every PR, Vercel previews, production on merge.

**Independent Test**: A PR with a 60-token duplicate fails CI; after fixing, it passes, gets a
preview, and merging deploys production (quickstart step 7).

- [ ] T046 [US6] Create `.github/workflows/ci.yml` on `pull_request` and `push` to `main`: checkout, `actions/setup-java` (Temurin 17+), `astral-sh/setup-uv`, cache `.pmd/` and pre-commit, `pre-commit run --all-files --show-diff-on-failure`, `uv run pytest`
- [ ] T047 [US6] Connect the repository to the Vercel project via the Git integration (previews per PR, production from `main`) and confirm a preview URL appears on this PR
- [ ] T048 [US6] Make CI a required check on `main` (branch protection or ruleset); if the account is on GitHub Free with a private repo, document in README that merge blocking needs GitHub Pro or a public repo (research R9)
- [ ] T049 [US6] Prove the gate: push a temporary commit with a ≥50-token duplicated block, confirm the `cpd` check fails locally and in CI, then revert

**Checkpoint**: Delivery pipeline verified.

---

## Phase 8: User Story 4 - Delete my own post, only when I say so (Priority: P3)

**Goal**: Guarded deletion of the owner's own posts.

**Independent Test**: The owner typing "delete my post <url>" deletes it; a scheduled task saying
"delete my latest post" does not (quickstart step 6).

### Tests for User Story 4

- [ ] T050 [P] [US4] Contract tests in `tests/contract/test_delete_tool.py`: `confirm` missing or not exactly `"delete"` → `confirmation_required` and no deletion; another author's post → `not_owner`; unknown post → `not_found`; success returns the deleted post's URL and text; annotation `destructiveHint: true`; description contains server instruction 2 verbatim

### Implementation for User Story 4

- [ ] T051 [US4] Add `delete_own_post` to `SafeBlueskyClient` in `src/bsky_mcp/bluesky/client.py` (fetch post, verify author DID equals session DID, then `deleteRecord` for `app.bsky.feed.post`)
- [ ] T052 [US4] Implement `delete_post(post, confirm)` in `src/bsky_mcp/tools/delete.py` with the description from `instructions.py`

**Checkpoint**: All six stories implemented.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T053 [P] Review every tool error path for secret leakage; extend `tests/unit/test_logging.py` to cover tool error messages
- [ ] T054 [P] Confirm CPD, Ruff, and ty pass with no suppressions added; justify any `# noqa` or `# ty: ignore` inline
- [ ] T055 Run the full quickstart (steps 1–7) against production, including the SC-003 (20 prompts) and SC-004 (10 prompts) checks, and record results in `specs/001-bluesky-mcp-server/validation.md`
- [ ] T056 Update `CLAUDE.md` at the repo root with project commands (uv, pre-commit, pytest) and a pointer to the constitution and Spec Kit workflow

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; blocks all stories. T024 (drafts smoke test) must
  pass before Phase 4.
- **US1 (Phase 3)**, **US2 (Phase 4)**: depend only on Foundational.
- **US5 (Phase 5)**: depends on Foundational; its live deploy (T041) is most useful after US1 and US2.
- **US3 (Phase 6)**, **US4 (Phase 8)**: depend only on Foundational.
- **US6 (Phase 7)**: depends on Setup (hooks) and needs a Vercel project (T041).
- **Polish (Phase 9)**: after all stories.

### Within Each Story

Tests first and failing → client methods → tools → story checkpoint. Tasks touching
`src/bsky_mcp/bluesky/client.py` (T027, T031, T044, T051) are sequential with each other.

### Parallel Opportunities

- Setup: T003, T004, T005, T007.
- Foundational tests: T008–T013 all in parallel; then T015 and T016 in parallel with T014.
- Story test tasks marked [P] run in parallel with each other and with `formatting.py` (T026).
- After Foundational, US1, US2, US3, and US4 can proceed in parallel except for the shared
  `client.py` edits.

## Parallel Example: Foundational tests

```bash
Task: "Unit tests for settings in tests/unit/test_config.py"
Task: "Unit tests for redaction in tests/unit/test_logging.py"
Task: "Unit tests for the IP middleware in tests/unit/test_ip_allowlist.py"
Task: "Unit tests for the user check in tests/unit/test_auth_check.py"
Task: "Safety tests in tests/safety/test_operations_allowlist.py"
Task: "Unit tests for text helpers in tests/unit/test_text.py"
```

## Implementation Strategy

### MVP First

1. Phases 1–2 (setup, foundation, drafts smoke test).
2. Phase 3 (read) → validate with tests.
3. Phase 4 (drafts) → validate.
4. Phase 5 (deploy, README, live access checks) → MVP live: secure read + draft.

### Incremental Delivery

5. Phase 6 (engagement) and Phase 7 (CI/CD) in either order.
6. Phase 8 (guarded delete) last, as the only irreversible action.
7. Phase 9 polish and full quickstart validation; then merge PR #1.

## Notes

- Commit after each task or logical group; pre-commit runs on every commit.
- Live steps needing the owner: T024 (app password), T041 (Vercel, Upstash, GitHub OAuth app,
  Claude connector), T047–T048 (Vercel Git integration, branch protection), T055 (prompts from the
  phone app and a scheduled task).
