# Research: Batch Follow

## R1. Where the batch logic lives

**Decision**: Rewrite `SafeBlueskyClient.follow` in `bluesky/client.py` to take `actors: list[str]`
and return a new `FollowResults` model. Keep `_follow_state` (one `getProfile` per account) and the
existing `ops.FOLLOW` create path.

**Rationale**: `add_to_list` resolves and writes one account at a time inside a loop. Doing the same
reuses code that is already allowlisted and tested, and keeps writes sequential, which the
rate-limit rule (FR-008) needs: the loop can stop at the first rate-limited request.

**Alternatives considered**:
- `app.bsky.actor.getProfiles` (up to 25 per read) to cut reads from 25 to 1. Rejected: it would add
  a read operation to the allowlist, the spec promises no new operation (FR-009), and a malformed
  or unknown handle in a batch can fail or silently drop the entry, which complicates per-account
  `not_found`.
- `com.atproto.repo.applyWrites` for one write per batch. Rejected: adds an operation to the
  write allowlist (Principle II), and partial-failure reporting is worse.
- Concurrent requests. Rejected: harder to stop cleanly on a rate limit and more likely to trigger
  one.

## R2. Detecting a rate limit

**Decision**: `_translate_error` currently maps HTTP 429 to
`BlueskyError("bluesky_unavailable", "Bluesky rate limit reached. Try again later.")`, the same
code used for timeouts. Give 429 its own code, `rate_limited`, with the same message. The batch loop
stops when it catches that code.

**Rationale**: The batch needs to tell a rate limit from a one-off failure without matching on
message text. No existing test asserts the old code for 429.

**Alternatives considered**: Subclass `BlueskyError`; matching the message string. Rejected as
heavier or fragile.

## R3. Per-account outcomes

**Decision**: Statuses `followed`, `already_following`, `not_found`, `is_you`, `failed` (with a
`message`), `not_attempted`.

- Unparseable handle or DID, or a "not found" reply: `not_found` (spec User Story 3 scenario 3).
- The owner's own DID: `is_you`, nothing written (FR-007).
- Any other per-account Bluesky refusal (account blocks the owner, takedown, transient upstream
  error): `failed`, with Bluesky's message, batch continues (FR-004).
- `rate_limited`: stop; every later account is `not_attempted` (FR-008).
- `bluesky_auth_failed` and `not_configured` are not per-account problems: they abort the call as
  they do for every other tool.

**Rationale**: matches the spec's "distinguishable" requirement and keeps the retry rule simple:
resend everything that is `failed` or `not_attempted`.

## R4. Duplicates and eventual consistency

**Decision**: Track the DIDs followed in this call. A later entry that resolves to a DID already
handled in the call is reported `already_following` without another write.

**Rationale**: `getProfile`'s `viewer.following` can lag a just-created follow, so relying on it
would double-follow a repeated entry or a handle plus the DID of the same account (FR-006).

## R5. Shared batch validation (CPD)

**Decision**: Move the 1-25 check from `lists.py` into a shared helper in `bluesky/text.py`
(`MAX_ACTORS_PER_CALL`, `validate_actor_batch(actors, verb)`), and define one `ActorBatch`
annotated type in `tools/__init__.py` used by both `add_to_list` and `follow`.

**Rationale**: Principle VI's 50-token duplicate check would otherwise flag two copies of the same
`Annotated[list[str], Field(min_length=1, max_length=25, ...)]` parameter and validator. The
existing `add_to_list` error text changes only in its verb.

## R6. Removing `actor`

**Decision**: `follow` takes only `actors`. The tool's input schema rejects unknown fields, so a
stale call with `actor` is refused rather than ignored (FR-011); a test pins this.
