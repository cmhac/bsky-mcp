# Feature Specification: Discovery Tools

**Feature Branch**: `002-discovery-tools`

**Created**: 2026-10-28

**Status**: Draft

**Input**: User description: "Enable the server to search posts and accounts on Bluesky to discover
things, in addition to managing posts. Add all of: richer post search filters, who quoted/liked/
reposted a post, custom feeds, account suggestions, trending topics, starter packs, and list feeds."

## Context

Spec 001 shipped `search_posts` (keywords, sort, author) and `search_users`. This spec adds
read-only discovery on top. It adds no write capability of any kind, so Constitution Principles II
and III are unaffected beyond growing the read allowlist.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Search posts precisely (Priority: P1)

The owner asks Claude to find posts matching specific conditions: within a date range, in a
language, mentioning an account, using a hashtag, linking to a domain, or linking to one specific
URL (for example, everyone sharing one of the owner's published stories).

**Why this priority**: The most direct upgrade to an existing tool and the most useful for
reporting work.

**Independent Test**: Ask "who has shared [story URL] on Bluesky this week?" and get posts that link
to that URL, all within the date range.

**Acceptance Scenarios**:

1. **Given** a story URL, **When** the owner asks who shared it, **Then** Claude returns posts that
   link to that URL.
2. **Given** a date range, **When** the owner searches a keyword within it, **Then** every returned
   post falls inside the range.
3. **Given** a hashtag and a language, **When** the owner searches, **Then** results are limited to
   that tag and language.
4. **Given** an end date before the start date, **When** the owner searches, **Then** the request is
   refused with a clear message.

---

### User Story 2 - See who is engaging with a post (Priority: P1)

The owner asks who quoted, liked, or reposted a post — their own or anyone's.

**Why this priority**: Understanding how a post travels is core to the owner's goal of building an
audience.

**Independent Test**: For one of the owner's posts with known quotes, ask "who quoted this?" and get
the quoting posts; ask "who liked it?" and get the accounts.

**Acceptance Scenarios**:

1. **Given** a post URL, **When** the owner asks who quoted it, **Then** Claude returns the quoting
   posts with their text and links.
2. **Given** a post URL, **When** the owner asks who liked or reposted it, **Then** Claude returns
   the accounts, with paging for long lists.

---

### User Story 3 - Explore custom feeds (Priority: P2)

The owner asks Claude to read a custom feed, see which feeds an account has made, learn what a
feed is, or find suggested and popular feeds.

**Why this priority**: Feeds are how Bluesky surfaces topics; useful for discovery but secondary to
search.

**Independent Test**: Give Claude a feed URL from the Bluesky app and ask for its latest posts;
ask for popular feeds about a topic.

**Acceptance Scenarios**:

1. **Given** a feed URL, **When** the owner asks for its posts, **Then** Claude returns the feed's
   current posts with paging.
2. **Given** an account, **When** the owner asks what feeds it has created, **Then** Claude lists
   them with names, descriptions, and links.
3. **Given** a topic word, **When** the owner asks for popular feeds, **Then** Claude returns
   matching feeds.
4. **Given** no input, **When** the owner asks for suggested feeds, **Then** Claude returns
   Bluesky's suggestions for the owner.

---

### User Story 4 - Discover accounts (Priority: P2)

The owner asks for accounts to follow in general, or accounts similar to a given account.

**Why this priority**: Supports growing the owner's network, but the owner already has account
search.

**Independent Test**: Ask "who's similar to [a data journalist's handle]?" and get a list of
accounts.

**Acceptance Scenarios**:

1. **Given** no input, **When** the owner asks for follow suggestions, **Then** Claude returns
   suggested accounts with profile details and whether the owner already follows them.
2. **Given** an account, **When** the owner asks for similar accounts, **Then** Claude returns
   accounts Bluesky associates with it.

---

### User Story 5 - See what's trending (Priority: P3)

The owner asks what topics are trending on Bluesky right now.

**Why this priority**: Useful context, but it relies on a Bluesky endpoint that is not part of
the stable API, so it is the most likely to break.

**Independent Test**: Ask "what's trending on Bluesky?" and get a list of topics with links.

**Acceptance Scenarios**:

1. **Given** the endpoint works, **When** the owner asks what's trending, **Then** Claude returns
   current topics with links to explore each one.
2. **Given** Bluesky changes or removes the endpoint, **When** the owner asks, **Then** the tool
   reports that trending topics are unavailable rather than failing obscurely, and every other tool
   keeps working.

---

### User Story 6 - Explore starter packs (Priority: P3)

The owner searches starter packs by topic, reads one to see its accounts, or lists the starter
packs an account has made.

**Why this priority**: A convenient way to find communities, but niche.

**Independent Test**: Search starter packs for "data journalism" and open one to list its members.

**Acceptance Scenarios**:

1. **Given** a topic, **When** the owner searches starter packs, **Then** Claude returns matching
   packs with names, creators, and links.
2. **Given** a starter pack link, **When** the owner asks what's in it, **Then** Claude returns its
   description and the accounts in it.

---

### User Story 7 - Read lists (Priority: P3)

The owner reads a curated list: who is on it, and the feed of posts from its members.

**Why this priority**: Niche; read-only access to lists the owner already uses in the app.

**Independent Test**: Give Claude a list link and ask for recent posts from its members.

**Acceptance Scenarios**:

1. **Given** a list link, **When** the owner asks who is on it, **Then** Claude returns its members.
2. **Given** a list link, **When** the owner asks for its feed, **Then** Claude returns recent posts
   from members.
3. **Given** a request to add or remove someone from a list, **When** Claude looks for a tool,
   **Then** none exists.

### Edge Cases

- A feed, list, or starter pack link is malformed or points to something deleted: the tool says so
  plainly (`invalid_input` or `not_found`).
- A feed generator is offline or slow: the tool fails within the normal timeout with a clear message.
- A search returns nothing: an empty result, not an error.
- Content returned by any discovery tool contains text that looks like instructions: it is data,
  never permission (existing server instruction).
- Very long like or repost lists: paging with the existing 1–100 limit and cursor.
- Trending endpoint unavailable: `unavailable` error for that tool only.

## Requirements *(mandatory)*

### Functional Requirements

**Post search (US1)**

- **FR-001**: `search_posts` MUST additionally accept optional filters: start date, end date,
  language, mentioned account, hashtag, linked domain, and linked URL, alongside the existing query,
  sort, and author. Existing calls MUST keep working unchanged.
- **FR-002**: Dates MUST accept ISO 8601 dates or date-times; an end before a start MUST be refused
  with `invalid_input`.

**Engagement on a post (US2)**

- **FR-003**: The server MUST provide tools to list the posts quoting a post, the accounts that liked
  a post, and the accounts that reposted a post, each with paging.

**Feeds (US3)**

- **FR-004**: The server MUST provide tools to read a custom feed's posts, describe a feed, list the
  feeds an account has created, list feeds suggested for the owner, and search popular feeds by
  keyword.
- **FR-005**: Feed inputs MUST accept a bsky.app feed URL or an `at://` URI for a feed generator.

**Accounts (US4)**

- **FR-006**: The server MUST provide tools for general follow suggestions and for accounts similar
  to a given account.

**Trending (US5)**

- **FR-007**: The server MUST provide a trending-topics tool. Its description MUST say the data
  comes from an unstable Bluesky endpoint. If the endpoint fails or is missing, the tool MUST return
  an `unavailable` error without affecting other tools.

**Starter packs (US6)**

- **FR-008**: The server MUST provide tools to search starter packs, read one starter pack including
  its member accounts, and list the starter packs an account has created.
- **FR-009**: Starter pack inputs MUST accept a bsky.app starter pack URL or an `at://` URI.

**Lists (US7)**

- **FR-010**: The server MUST provide tools to read a list's details and members, and to read a
  list's feed of posts. List inputs MUST accept a bsky.app list URL or an `at://` URI.
- **FR-011**: The server MUST NOT gain any tool or operation that creates, edits, or deletes lists,
  list items, feeds, or starter packs, or that mutes or blocks.

**Cross-cutting**

- **FR-012**: Every new tool MUST be read-only, annotated as read-only, and use only Bluesky
  operations added to the existing operation allowlist. No write operation is added by this spec.
- **FR-013**: Every list-style tool MUST support the existing paging contract (limit 1–100, default
  25, cursor).
- **FR-014**: Results MUST use the existing result shapes where they apply (posts, profiles), and
  include a bsky.app link for every feed, list, starter pack, and trending topic returned.
- **FR-015**: The safety test that pins the exact tool set MUST be updated to the new set, and the
  forbidden-operation tests MUST still pass unchanged.
- **FR-016**: The README's capability table MUST list the new discovery tools.

### Key Entities

- **Feed**: A custom feed generator: name, creator, description, like count, link.
- **List**: A curated list of accounts: name, purpose, creator, member count, link.
- **Starter pack**: A curated bundle of accounts (and optionally feeds): name, creator,
  description, members, link.
- **Trending topic**: A topic label with a link to explore it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The owner can find who shared a specific story URL, within a date range, in a single
  request to Claude.
- **SC-002**: Each user story's independent test passes from the Claude phone app against the
  production server.
- **SC-003**: Discovery tools return results in under 5 seconds in 95% of cases under normal
  Bluesky conditions.
- **SC-004**: The full safety suite passes, and the operation allowlist gains only read operations
  (verified by test).
- **SC-005**: If trending topics break, 100% of other tools continue to work.

## Assumptions

- All new endpoints work with an app password, like the read endpoints in spec 001. The plan must
  confirm any exception.
- Trending topics come from Bluesky's unspecced namespace and may change without notice; that is
  acceptable given the graceful-failure requirement.
- Images and video embedded in returned posts are represented by links only, as in spec 001.
- Typeahead search, moderation lists (blocks and mutes), and onboarding-specific suggestion
  endpoints are out of scope.
