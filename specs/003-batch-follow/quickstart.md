# Quickstart: Batch Follow

Prerequisites: `uv sync`. All checks run against fakes; nothing touches a real account.

```bash
uv run pytest tests/contract/test_engagement_tools.py tests/safety
uv run pre-commit run --all-files
uv run pytest
```

Expected:

1. A 25-account call returns 25 results in order; a repeat of the same call returns all
   `already_following` and writes nothing (SC-001, SC-002).
2. A mixed batch (new, already followed, unknown, own account, repeated) gets the right status for
   each entry (SC-003, FR-006, FR-007).
3. A `failed` account does not stop the rest (SC-004).
4. 0 or 26 accounts is refused and writes nothing (SC-005).
5. A 429 midway stops the loop: later accounts are `not_attempted`, no further requests are made
   (SC-006).
6. A call with `actor` instead of `actors` is rejected.
7. `tests/safety` still passes with no change to the operation allowlist or tool names (SC-007).

Manual check against a real account: follow two accounts with `follow {"actors": [...]}`, repeat the
call, confirm the second reports `already_following`, then `unfollow` them.
