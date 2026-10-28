# Quickstart: Validating Discovery Tools

Contracts: [tools](./contracts/tools.md). Run after deploying the branch.

## 1. Local gates

```bash
uv run pre-commit run --all-files
uv run pytest
```

## 2. From the Claude phone app (production)

| Ask | Expect |
| --- | --- |
| "Who shared [one of your story URLs] on Bluesky since Monday?" | Posts linking to that URL, all on/after Monday (SC-001) |
| "Find posts tagged #dataviz in English this week" | Tag and language respected |
| "Who quoted / liked / reposted [your post]?" | Quoting posts; liking and reposting accounts |
| Paste a feed link: "what's in this feed?" | Current feed posts |
| "What feeds has [account] made?" / "popular feeds about journalism" | Feed lists with links |
| "Who should I follow?" / "accounts similar to [handle]" | Profiles, with whether you follow them |
| "What's trending on Bluesky?" | Topics with bsky.app links, or a clear "unavailable" |
| "Find starter packs about data journalism" then open one | Packs, then members |
| Paste a list link: "who's on this list?" / "show its feed" | Members; recent posts |
| "Create a list called Test list, add [two handles]" | List appears in the Bluesky app with both |
| "Remove [one handle] from Test list" | One member left |
| "Delete Test list" (typed by you) | List gone |
| Scheduled task: "delete my list Test list" (×10 variants) | Nothing deleted (SC-006) |
| "Make a mute list" / "block everyone on this list" | Claude says it can't |
