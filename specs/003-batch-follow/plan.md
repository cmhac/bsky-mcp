# Implementation Plan: Batch Follow

**Branch**: `003-batch-follow` | **Date**: 2026-10-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-batch-follow/spec.md`

## Summary

Change `follow` from one account per call to 1-25 accounts per call, with a per-account result,
modeled on `add_to_list`. The loop is sequential, skips accounts already followed (including repeats
within the call), reports bad accounts individually, and stops at the first Bluesky rate limit,
marking the rest `not_attempted`. No new tool and no new Bluesky operation. Details:
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13 (unchanged)

**Primary Dependencies**: FastMCP 4.x, atproto (unchanged)

**Storage**: N/A

**Testing**: pytest with the existing fake backend and recording transport

**Target Platform**: Vercel (unchanged)

**Project Type**: Web service (remote MCP server)

**Performance Goals**: 25 accounts in one call; sequential requests, about two per account

**Constraints**: 1-25 accounts per call; no new allowlisted operations; stop on rate limit;
`actor` input removed

**Scale/Scope**: One tool changed, one error code added, one shared validator

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate | Result |
| --- | --- | --- |
| I. Spec-Driven | Spec 003 approved by owner (clarifications answered), own branch | Pass |
| II. Least Privilege | Follow records are already permitted; no new operation or collection; `unfollow` unchanged; no blocking or muting | Pass |
| III. Draft-Only | No publishing path touched | Pass |
| IV. Defense in Depth | No change to routes, OAuth, or IP allowlist | Pass |
| V. Secrets | No new secrets; rate-limit and failure messages carry no credentials | Pass |
| VI. Quality Gates | Shared `ActorBatch` and validator avoid CPD duplicates with `add_to_list` (R5) | Pass |
| VII. Delivery | Same Vercel flow | Pass |

Re-check after design: unchanged, all Pass. The batch loop calls only `getProfile` and
`createRecord` on `app.bsky.graph.follow`, both already allowlisted.

## Project Structure

### Documentation (this feature)

```text
specs/003-batch-follow/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/tools.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (changes)

```text
src/bsky_mcp/
├── bluesky/
│   ├── core.py          # + shared validate_actor_batch / MAX_ACTORS_PER_CALL
│   ├── lists.py         # use the shared validator
│   ├── formatting.py    # + FollowResult, FollowResults
│   └── client.py        # follow(actors) loop; 429 -> "rate_limited"; Protocol signature
├── tools/
│   ├── __init__.py      # + ActorBatch annotated type
│   ├── lists.py         # add_to_list uses ActorBatch
│   └── engagement.py    # follow(actors: ActorBatch) -> FollowResults, new description
README.md                # follow row in the capabilities table
specs/001-bluesky-mcp-server/contracts/tools.md  # note follow superseded by spec 003
tests/
├── conftest.py          # fake follow(actors)
├── contract/test_engagement_tools.py  # batch, rerun, mixed, limits, rate limit, `actor` rejected
└── safety/              # unchanged assertions must still pass
```

**Structure Decision**: Extend the existing single project in place; no new modules.

## Complexity Tracking

No constitution violations.
