"""Check that a Bluesky app password can use the drafts endpoints (quickstart step 3).

Run on your own machine; never paste the app password into a chat:

    BLUESKY_HANDLE=you.bsky.social BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx \
        uv run python scripts/smoke_drafts.py

Creates a draft named "bsky-mcp smoke test", reads it back, and updates it. The server cannot
delete drafts, so delete it yourself in the Bluesky app afterwards.
"""

from __future__ import annotations

import asyncio
import os
import sys

from bsky_mcp.bluesky.client import BlueskyError, DraftPostInput, SafeBlueskyClient


async def main() -> int:
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        print("Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD.", file=sys.stderr)
        return 2
    client = SafeBlueskyClient(
        handle, password, os.environ.get("BLUESKY_SERVICE", "https://bsky.social")
    )
    try:
        created = await client.create_draft([DraftPostInput(text="bsky-mcp smoke test")], None)
        print(f"createDraft OK: {created.draft_id}")
        page = await client.list_drafts(25, None)
        print(f"getDrafts OK: {len(page.drafts)} draft(s) visible")
        updated = await client.update_draft(
            created.draft_id, [DraftPostInput(text="bsky-mcp smoke test (updated)")], None
        )
        print(f"updateDraft OK: {updated.posts[0].text!r}")
    except BlueskyError as exc:
        print(f"FAILED ({exc.code}): {exc.message}", file=sys.stderr)
        return 1
    print("All draft endpoints work with this app password. Delete the draft in the Bluesky app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
