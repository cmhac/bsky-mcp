# Feature Specification: Batch Follow

**Feature Branch**: `003-batch-follow`

**Created**: 2026-10-28

**Status**: Draft

**Input**: User description: "Batch follow tool: change the `follow` tool so it can follow multiple
accounts in one call, modeled on `add_to_list` (accepts an `actors` array of 1-25 handles or DIDs
per call, returns per-account results such as "followed", "already following", "not found").
Motivation: following 686 accounts one call at a time is too slow; the list was populated in 29
`add_to_list` calls. Reruns should be safe: already-followed accounts are skipped and failures can
be retried individually."

## Context

`add_to_list` (spec 002) takes 1-25 accounts per call and reports a result for each. `follow`
(spec 001) takes exactly one account per call. When the owner asked Claude to follow 686 accounts,
the list took 29 calls but the follows would have taken 686, so the work was stopped after 25.

This spec makes `follow` work the way `add_to_list` does. It adds no new kind of Bluesky write:
follow records are already permitted by Constitution v3.0.0 Principle II, and this feature only
changes how many can be requested in one call. Publishing, blocking, and muting stay impossible.

## Clarifications

### Session 2026-10-28

- Q: Should a rerun of the same batch be safe? → A: Yes. Accounts the owner already follows are
  skipped and reported, never followed twice.
- Q: Should one bad account fail the whole batch? → A: No. Each account gets its own result, as in
  `add_to_list`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Follow many accounts in one call (Priority: P1)

The owner gives Claude a list of accounts (handles or DIDs) to follow. Claude follows up to 25 of
them in a single call and gets back a result for every account, so a list of hundreds is done in a
handful of calls instead of hundreds.

**Why this priority**: This is the whole feature. Without it, bulk following is impractical.

**Independent Test**: Call `follow` with 25 accounts the owner does not follow. All 25 become
followed and the response has 25 results, each "followed".

**Acceptance Scenarios**:

1. **Given** 25 valid accounts the owner does not follow, **When** Claude follows them in one call,
   **Then** the owner follows all 25 and the response lists each as "followed".
2. **Given** a single account, **When** Claude calls `follow` with a one-element batch, **Then** it
   is followed and reported exactly as in a larger batch.
3. **Given** a mix of new, already-followed, and nonexistent accounts, **When** Claude follows them
   in one call, **Then** the new ones are followed, the already-followed ones are untouched, the
   nonexistent ones create nothing, and each account's result says which happened.
4. **Given** 686 accounts, **When** Claude works through them in batches of at most 25, **Then**
   it finishes in 28 calls or fewer.

---

### User Story 2 - Rerun a batch safely and retry failures (Priority: P1)

A long follow job is interrupted, or some accounts fail. The owner (or Claude) reruns the same
accounts without creating duplicates, and can retry only the ones that failed.

**Why this priority**: Large jobs get interrupted. If a rerun double-follows or loses track of what
happened, the owner cannot trust the tool for bulk work.

**Independent Test**: Run the same 25-account batch twice. The second run changes nothing and
reports every account as already followed.

**Acceptance Scenarios**:

1. **Given** a batch that was followed completely, **When** the identical batch is sent again,
   **Then** no follow is created and every account is reported "already following".
2. **Given** a batch where some accounts failed, **When** Claude resends only those accounts,
   **Then** they are attempted again and the accounts that succeeded before are not touched.
3. **Given** the same account appears twice in one batch, **When** the batch runs, **Then** the
   owner ends up following it once.

---

### User Story 3 - Invalid requests are refused clearly (Priority: P2)

The owner or Claude sends an empty batch, a batch larger than the limit, or a malformed entry, and
gets a clear message instead of a partial or silent result.

**Why this priority**: Protects the account from accidental oversized or empty calls, and tells
Claude how to correct itself.

**Independent Test**: Send 26 accounts. The call is refused with a message stating the 1-25 limit,
and no follows are created.

**Acceptance Scenarios**:

1. **Given** an empty list, **When** Claude calls `follow`, **Then** the call is refused and nothing
   changes.
2. **Given** 26 or more accounts, **When** Claude calls `follow`, **Then** the whole call is
   refused with a message giving the limit, and none of the 26 are followed.
3. **Given** an entry that is not a valid handle or DID, **When** the batch runs, **Then** that
   entry is reported as not found and the rest of the batch still runs.

---

### Edge Cases

- The owner's own account appears in a batch: it is not followed, and its result says why.
- An account is deactivated, suspended, or blocks the owner: it is reported with a result that
  distinguishes it from success, and does not stop the rest of the batch.
- A handle that was valid when listed has since changed: it is reported "not found" and can be
  retried with its new handle.
- Bluesky rate-limits or becomes unavailable partway through a batch: see FR-008.
- A DID and a handle for the same account appear in one batch: the owner ends up following the
  account once.
- The owner already follows an account via an old follow the tool did not create: it is reported
  "already following".

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `follow` tool MUST accept a list of 1-25 accounts, each a handle or DID, and
  follow every account in it that is not already followed. [NEEDS CLARIFICATION: size limit stays
  at 25 to match `add_to_list`, or should it be raised, e.g. to 100, so 686 accounts take 7 calls
  instead of 28?]
- **FR-002**: The tool MUST return one result per requested account, in request order, each naming
  the account as the caller supplied it and one status: "followed", "already_following", or
  "not_found" (matching the `added` / `already_member` / `not_found` pattern of `add_to_list`).
- **FR-003**: An account the owner already follows MUST be left unchanged and reported
  "already_following"; the tool MUST NOT create a second follow for it.
- **FR-004**: A problem with one account MUST NOT prevent the remaining accounts from being
  processed or hide the results of those that succeeded.
- **FR-005**: A batch with zero accounts or more than the maximum MUST be refused before any follow
  is created, with a message stating the allowed range.
- **FR-006**: Accounts repeated within one batch, including a handle and the DID of the same
  account, MUST result in a single follow.
- **FR-007**: The owner's own account MUST NOT be followed, and its result MUST say so.
- **FR-008**: If Bluesky refuses or fails some accounts for reasons other than "not found" (for
  example a rate limit), the response MUST still report every account, marking the ones that were
  not completed so the caller can retry exactly those. [NEEDS CLARIFICATION: when Bluesky rate-
  limits partway through, should the tool stop at once and mark the remaining accounts "not
  attempted", or keep trying each remaining account and mark failures individually?]
- **FR-009**: `follow` MUST remain a reversible, engagement-level action: `unfollow` is unchanged,
  and no new Bluesky operation, collection, or tool is added beyond what Principle II already
  permits. Tests that pin the exact tool set and operation allowlist MUST still pass.
- **FR-010**: The tool description MUST tell Claude the per-call limit, that already-followed
  accounts are skipped, and that failures can be retried by resending only those accounts.
- **FR-011**: The README and the tool contract documents MUST describe the new `follow` input and
  results. [NEEDS CLARIFICATION: should the old one-account `actor` input keep working alongside
  `actors` for existing callers, or be replaced outright, as `add_to_list` has only `actors`?]
- **FR-012**: No account identifiers beyond what the caller supplied and the resolved handle MAY be
  logged, and secrets MUST NOT appear in results or errors (Principle V).

### Key Entities

- **Follow request batch**: An ordered list of 1-25 accounts, each given as a handle or DID.
- **Follow result**: For one requested account, the account as supplied and a status: "followed",
  "already_following", or "not_found" (plus whatever additional status FR-007 and FR-008 settle).
- **Follow (record)**: The owner's existing relationship to an account on Bluesky; one per account.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Following 686 accounts takes no more than 28 calls at the default limit (25), down
  from 686.
- **SC-002**: Running an identical batch a second time creates zero new follows and reports every
  account as already followed.
- **SC-003**: In a batch mixing new, already-followed, and nonexistent accounts, 100% of accounts
  receive a result that correctly says what happened to them.
- **SC-004**: A batch containing one bad account still follows every valid new account in it.
- **SC-005**: An empty or oversized batch changes nothing on the owner's account and tells the
  caller the allowed range.
- **SC-006**: The set of tools and Bluesky operations the server can reach is unchanged, apart from
  the new shape of the `follow` input.

## Assumptions

- The owner is the only user; they trust Claude to follow accounts they have asked for, which is
  already true for single follows.
- The 25-account limit mirrors `add_to_list` unless the owner chooses otherwise (FR-001).
- Results use the same status-word style as `add_to_list` (`already_following` mirrors
  `already_member`).
- Accounts are processed in request order; there is no requirement that a batch be all-or-nothing.
- Following a very large number of accounts at once can look like spam to Bluesky. Pacing and
  deciding what to follow remain Claude's and the owner's responsibility; this feature only
  removes the one-call-per-account overhead.
- This feature does not add batch `unfollow`, batch `like`, or any other batch operation.
