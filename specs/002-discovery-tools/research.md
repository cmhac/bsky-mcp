# Phase 0 Research: Discovery Tools

**Date**: 2026-10-28 | **Plan**: [plan.md](./plan.md)

Endpoint names, parameters, response fields, and limits below were read from the installed AT
Protocol Python SDK (atproto 0.0.73) on 2026-10-28, which is generated from Bluesky's lexicons.

## R1. Search filters

- **Decision**: Pass through `since`, `until`, `lang`, `mentions`, `tag` (list), `domain`, and `url`
  on `app.bsky.feed.searchPosts`.
- **Rationale**: Bluesky's [searchPosts lexicon](https://raw.githubusercontent.com/bluesky-social/atproto/main/lexicons/app/bsky/feed/searchPosts.json)
  says `since` is inclusive and `until` exclusive, both accept a datetime or an ISO date; `tag`
  takes multiple values with AND matching and no `#`; `url` and `domain` match links in facets or
  embeds, with server-side normalization. The server validates dates (end after start) and strips a
  leading `#` from tags before sending.

## R2. Endpoints and limits

| Capability | Operation | Limit |
| --- | --- | --- |
| Quotes of a post | `app.bsky.feed.getQuotes` | 1–100 |
| Likes of a post | `app.bsky.feed.getLikes` | 1–100 |
| Reposts of a post | `app.bsky.feed.getRepostedBy` | 1–100 |
| Read a feed | `app.bsky.feed.getFeed` | 1–100 |
| Describe a feed | `app.bsky.feed.getFeedGenerator` | — |
| Account's feeds | `app.bsky.feed.getActorFeeds` | 1–100 |
| Suggested feeds | `app.bsky.feed.getSuggestedFeeds` | 1–100 |
| Popular feeds by keyword | `app.bsky.unspecced.getPopularFeedGenerators` | 1–100 |
| Follow suggestions | `app.bsky.actor.getSuggestions` | 1–100 |
| Similar accounts | `app.bsky.graph.getSuggestedFollowsByActor` | none |
| Trending topics | `app.bsky.unspecced.getTrendingTopics` | 1–25 |
| Search starter packs | `app.bsky.graph.searchStarterPacks` | 1–100 |
| Read a starter pack | `app.bsky.graph.getStarterPack` | — |
| Account's starter packs | `app.bsky.graph.getActorStarterPacks` | 1–100 |
| Account's lists | `app.bsky.graph.getLists` | 1–100 |
| List details and members | `app.bsky.graph.getList` | 1–100 |
| List feed | `app.bsky.feed.getListFeed` | 1–100 |
| Owner's lists with a given member | `app.bsky.graph.getListsWithMembership` | 1–100 |

- `getPopularFeedGenerators` and `getTrendingTopics` are in the `app.bsky.unspecced` namespace,
  which signals they are not part of the stable API. Trending gets an `unavailable` error path
  (spec FR-007); popular feeds fall back the same way.
- A starter pack references a list; full membership comes from `getList` on that list.

## R3. List writes

- **Decision**: Create `app.bsky.graph.list` records with `purpose = app.bsky.graph.defs#curatelist`
  only, and `app.bsky.graph.listitem` records whose `list` is in the owner's repo. Delete
  `listitem` and `list` records only in the owner's repo.
- **Enforcement in code** (extends `operations.check_operation`):
  - `createRecord` on `app.bsky.graph.list` is rejected unless the record's `purpose` is
    `#curatelist` (blocks `#modlist` and `#referencelist`).
  - `createRecord` on `app.bsky.graph.listitem` is rejected unless the record's `list` URI is in
    the owner's repo.
  - `app.bsky.graph.listblock` and the mute-list operations stay off the allowlist.
- **Constraints** (from the SDK's `app.bsky.graph.list` record model): name 1–64 characters,
  description at most 3000.
- **Duplicate and removal lookup**: `getListsWithMembership(actor=member)` returns the owner's
  lists with the membership record for that account, per its lexicon description ("Enumerates the
  lists created by the session user, and includes membership information about `actor`"). This
  avoids paging an entire list to check membership.
- **Delete list**: page through `getList` to collect `listitem` record URIs, delete each (all in the
  owner's repo), then delete the list record. If interrupted, the list still exists with fewer
  members and the call can be repeated.
- Guarded like `delete_post`: `confirm="delete"`, owner-only, owner-message-only description.

## R4. URL formats

bsky.app links map to AT-URIs as follows; the handle is resolved to a DID first:

| Link | AT-URI |
| --- | --- |
| `https://bsky.app/profile/{actor}/feed/{rkey}` | `at://{did}/app.bsky.feed.generator/{rkey}` |
| `https://bsky.app/profile/{actor}/lists/{rkey}` | `at://{did}/app.bsky.graph.list/{rkey}` |
| `https://bsky.app/starter-pack/{actor}/{rkey}` | `at://{did}/app.bsky.graph.starterpack/{rkey}` |

These patterns match the links the Bluesky web app produces; the quickstart verifies each with a
real link.

## R5. Code organization

- **Decision**: Split new Bluesky methods into `bluesky/discovery.py` and `bluesky/lists.py` as
  mixins on `SafeBlueskyClient`, and new tools into `tools/discovery.py` and `tools/lists.py`.
- **Rationale**: Keeps `client.py` reviewable and avoids CPD duplication across many similar
  paged reads by sharing one paging helper.
