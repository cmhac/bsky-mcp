---

description: "Task list for discovery tools and list management"
---

# Tasks: Discovery Tools

**Input**: Design documents from `/specs/002-discovery-tools/`

**Tests**: Required (constitution: tests for any change to tools or the operation allowlist).

## Phase 1: Foundational

- [X] T001 Add read operations from research R2 and list/listitem create/delete rules from R3 to `src/bsky_mcp/bluesky/operations.py`, including record-content checks (list purpose must be `app.bsky.graph.defs#curatelist`; listitem `list` must be in the owner's repo)
- [X] T002 [P] Safety tests in `tests/safety/test_list_safety.py`: modlist/referencelist creation rejected; listitem pointing at another repo rejected; `listblock`, `muteActorList`, `muteActor` unreachable; list/listitem deletes outside own repo rejected; new read operations allowed
- [X] T003 [P] Add feed, list, and starter-pack link parsing and date validation to `src/bsky_mcp/bluesky/text.py` with tests in `tests/unit/test_text.py`
- [X] T004 [P] Add result models from data-model.md to `src/bsky_mcp/bluesky/formatting.py`
- [X] T005 Extend `BlueskyAPI` in `src/bsky_mcp/bluesky/client.py` with the new methods; add a shared paging helper; extend the test fake in `tests/conftest.py`

## Phase 2: US1 Precise post search (P1)

- [X] T006 [US1] Add `since`, `until`, `lang`, `mentions`, `tags`, `domain`, `url` to `search_posts` in `src/bsky_mcp/tools/read.py` and the client; contract tests in `tests/contract/test_discovery_tools.py` (date order check, `#` stripped, https URL, existing calls unchanged)

## Phase 3: US2 Engagement on a post (P1)

- [X] T007 [US2] `get_quotes`, `get_likes`, `get_reposted_by` in `src/bsky_mcp/bluesky/discovery.py` and `src/bsky_mcp/tools/discovery.py`, with contract tests

## Phase 4: US3 Feeds, US4 Accounts (P2)

- [X] T008 [US3] `get_feed`, `get_feed_info`, `get_account_feeds`, `get_suggested_feeds`, `search_feeds` (unstable endpoint → `unavailable`), with contract tests
- [X] T009 [US4] `get_suggested_follows`, `get_similar_accounts`, with contract tests

## Phase 5: US8 Manage lists (P2)

- [X] T010 [US8] `create_list`, `add_to_list`, `remove_from_list`, guarded `delete_list` in `src/bsky_mcp/bluesky/lists.py` and `src/bsky_mcp/tools/lists.py`; add `DELETE_LIST_RULE` to `src/bsky_mcp/instructions.py`
- [X] T011 [US8] Contract tests in `tests/contract/test_list_tools.py` (name 1–64, description ≤3000, add 1–25 accounts, idempotency, confirmation, not_owner) and real-client tests against the recording transport proving every write targets the owner's repo and deletion removes members then the list

## Phase 6: US5 Trending, US6 Starter packs, US7 Lists (P3)

- [X] T012 [US5] `get_trending_topics` (limit 1–25; absolute links; `unavailable` on failure without affecting other tools), with tests
- [X] T013 [US6] `search_starter_packs`, `get_starter_pack` (members via its list), `get_account_starter_packs`, with tests
- [X] T014 [US7] `get_lists`, `get_list`, `get_list_feed`, with tests

## Phase 7: Polish

- [X] T015 Update the pinned tool set in `tests/safety/test_no_publishing.py` to the 41 tools; register new modules in `src/bsky_mcp/server.py`
- [X] T016 [P] Update `README.md` capability table and safety section (lists, guarded list deletion, no moderation lists)
- [ ] T017 Run all gates; push; confirm CI and the Vercel preview build
- [ ] T018 (owner, after merge) Run [quickstart.md](./quickstart.md) from the phone app against production
