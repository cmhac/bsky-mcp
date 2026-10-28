---

description: "Task list for batch follow"
---

# Tasks: Batch Follow

**Input**: Design documents from `/specs/003-batch-follow/`

**Tests**: Required (constitution: tests for any change to tools or the operation allowlist).

## Phase 1: Foundational

- [ ] T001 Move the 1-25 check out of `src/bsky_mcp/bluesky/lists.py` into `src/bsky_mcp/bluesky/core.py` as `MAX_ACTORS_PER_CALL = 25` and `validate_actor_batch(actors)`, raising `InvalidInputError("Provide between 1 and 25 accounts at a time.")`; make `add_to_list` use it and update any test asserting the old message
- [ ] T002 [P] Add the `ActorBatch` annotated type (`Annotated[list[str], Field(min_length=1, max_length=25, description="1-25 handles or DIDs.")]`) to `src/bsky_mcp/tools/__init__.py` and use it for `actors` in `add_to_list` in `src/bsky_mcp/tools/lists.py`
- [ ] T003 [P] Add `FollowResult` (`actor`, `status`, `handle` null, `record_uri` null, `message` null) and `FollowResults` (`results` list) to `src/bsky_mcp/bluesky/formatting.py` per data-model.md
- [ ] T004 In `_translate_error` in `src/bsky_mcp/bluesky/client.py`, map HTTP 429 to `BlueskyError("rate_limited", "Bluesky rate limit reached. Try again later.")`; check `src/bsky_mcp/tools/__init__.py` `run` surfaces unknown codes unchanged

## Phase 2: US1 Follow many accounts (P1)

- [ ] T005 [US1] Change the `follow` signature in the `BlueskyAPI` protocol and `SafeBlueskyClient` in `src/bsky_mcp/bluesky/client.py` to `follow(actors: list[str]) -> fmt.FollowResults`: call `validate_actor_batch`, then loop in request order using `_follow_state` and `ops.FOLLOW` creation; statuses `followed` / `already_following` / `not_found` (invalid handle/DID or `not_found` error) / `is_you` (profile DID equals `_own_did()`, nothing written)
- [ ] T006 [US1] Change the tool in `src/bsky_mcp/tools/engagement.py` to `follow(actors: ActorBatch) -> fmt.FollowResults` with a description covering FR-010 (25 per call, already-followed skipped, retry only `failed` and `not_attempted`, rate limit leaves the rest `not_attempted`); update the fake `follow` in `tests/conftest.py` to take `actors` and return `FollowResults`
- [ ] T007 [US1] Contract tests in `tests/contract/test_engagement_tools.py`: update the parametrized follow case (`actors` key, result shape); 25 accounts give 25 ordered results; mixed new/already/unknown/own-account batch; real-client test on `RecordingRequest` proving each write is `app.bsky.graph.follow` in the owner's repo and a one-element batch behaves like a larger one

## Phase 3: US2 Safe reruns and retries (P1)

- [ ] T008 [US2] In `follow` in `src/bsky_mcp/bluesky/client.py`, remember the DIDs handled in this call so a repeated entry (including handle plus DID of one account) is `already_following` with no second write; a per-account `BlueskyError` other than `rate_limited`, `bluesky_auth_failed`, `not_configured` becomes `failed` with its message and the loop continues; on `rate_limited` stop, mark every remaining entry `not_attempted` with a message, and make no further requests; auth/not-configured errors still abort the call
- [ ] T009 [US2] Tests in `tests/contract/test_engagement_tools.py`: identical batch twice gives all `already_following` and zero extra writes; duplicate entries and handle+DID produce one write; one `failed` account does not stop the rest; a 429 on the Nth account yields statuses for earlier accounts, `not_attempted` for the rest, and no request after the 429 (extend `tests/fake_transport.py` if it cannot return a 429 for a chosen handle)

## Phase 4: US3 Invalid requests (P2)

- [ ] T010 [US3] Tests in `tests/contract/test_engagement_tools.py`: empty list and 26 accounts are refused with the 1-25 message and no writes; a call with `actor` instead of `actors` is rejected; an invalid handle in a batch is `not_found` and the rest run

## Phase 5: Polish & cross-cutting

- [ ] T011 [P] Update the `follow` row in `README.md` and add a "superseded by spec 003" note for `follow` in `specs/001-bluesky-mcp-server/contracts/tools.md`
- [ ] T012 Confirm `tests/safety/test_no_publishing.py` and `tests/safety/test_operations_allowlist.py` pass with the tool set and operation allowlist unchanged (edit only if the tool-signature checks need it)
- [ ] T013 Run `uv run pre-commit run --all-files` and `uv run pytest`; fix all findings (including the 50-token duplicate check); mark tasks done in this file

## Dependencies

T001-T004 first (T002, T003 parallel). T005 → T006 → T007 (US1). T008 depends on T005. T009 and T010 depend on T008 and T006. T011-T013 last.

## Implementation strategy

MVP is US1 (T005-T007): a working batch follow. US2 adds the rerun, duplicate, failure and rate-limit behavior and must land with it before merge, since SC-002 and FR-008 are part of the feature.
