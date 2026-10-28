# Implementation Plan: Discovery Tools

**Branch**: `002-discovery-tools` | **Date**: 2026-10-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-discovery-tools/spec.md`

## Summary

Add 21 tools to the existing server: richer filters on `search_posts`, read-only discovery (post
engagement, feeds, account suggestions, trending, starter packs, lists), and management of the
owner's curation lists (create, add, remove, guarded delete). Every new Bluesky call goes through
the existing operation allowlist, which gains read operations plus list and list-item writes
restricted to curation lists in the owner's repo. Details and sources: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13 (unchanged)

**Primary Dependencies**: FastMCP 4.x, atproto (unchanged)

**Storage**: N/A (lists live in Bluesky)

**Testing**: pytest with the existing fake backend and recording transport

**Target Platform**: Vercel (unchanged)

**Project Type**: Web service (remote MCP server)

**Performance Goals**: Discovery reads under 5 s for 95% of calls (SC-003)

**Constraints**: Same paging contract (1–100, default 25; trending 1–25); no publishing; no
blocking or muting; list writes only in the owner's repo

**Scale/Scope**: 21 new tools, 41 total

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate | Result |
| --- | --- | --- |
| I. Spec-Driven | Spec 002 approved, on its own branch | Pass |
| II. Least Privilege (v3.0.0) | New writes limited to curation `list` and `listitem` in owner's repo; `listblock`, mute operations, modlists remain impossible; list deletion guarded | Pass (R3) |
| III. Draft-Only | No publishing path added; tool-set pin updated deliberately | Pass |
| IV. Defense in Depth | No change to routes, OAuth, or IP allowlist | Pass |
| V. Secrets | No new secrets | Pass |
| VI. Quality Gates | Same hooks and CI; CPD risk addressed by shared paging helper | Pass |
| VII. Delivery | Same Vercel flow | Pass |

## Project Structure

### Documentation (this feature)

```text
specs/002-discovery-tools/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/tools.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (changes)

```text
src/bsky_mcp/
├── bluesky/
│   ├── operations.py    # + read ops, + list/listitem create/delete with content checks
│   ├── text.py          # + feed/list/starter-pack URL parsing, date validation
│   ├── formatting.py    # + FeedView, ListInfo, StarterPack, TrendingTopic and page models
│   ├── discovery.py     # NEW: DiscoveryMixin (US1–US7 reads)
│   ├── lists.py         # NEW: ListsMixin (US8 writes)
│   └── client.py        # SafeBlueskyClient(DiscoveryMixin, ListsMixin, ...); search filters
├── tools/
│   ├── read.py          # search_posts gains filters
│   ├── discovery.py     # NEW: discovery tools
│   └── lists.py         # NEW: list tools incl. guarded delete_list
├── instructions.py      # + DELETE_LIST_RULE, trending description
└── server.py            # register new tool modules
tests/
├── contract/test_discovery_tools.py, test_list_tools.py
├── safety/test_list_safety.py; test_no_publishing.py (tool set update)
└── unit/test_text.py (new parsers)
```

**Structure Decision**: Extend the existing package; mixins keep the client file small.

## Complexity Tracking

No constitution violations.
