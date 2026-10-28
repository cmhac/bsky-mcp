# bsky-mcp

Personal Bluesky MCP server (FastMCP on Vercel). Read the constitution first:
`.specify/memory/constitution.md`. Principles II (least privilege) and III (draft-only, no
publishing) are non-negotiable.

## Workflow

All changes go through Spec Kit: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
`/speckit-implement`. Specs live in `specs/`.

## Commands

```bash
uv sync                              # install
uv run pre-commit run --all-files    # Ruff lint/format, ty, PMD CPD (50 tokens; needs Java 17+)
uv run pytest                        # all tests; tests/safety guards Principles II and III
```

## Rules for code changes

- Every Bluesky request goes through `src/bsky_mcp/bluesky/operations.py`. Never add an operation,
  collection, or tool without a spec, and never add a publishing, blocking, or draft-deleting path.
- `tests/safety/test_no_publishing.py` pins the exact tool set; update it only with a spec change.
- Never log, return, or commit secrets. Settings in `SECRET_FIELDS` are redacted from all logs.
- Safety wording lives in `src/bsky_mcp/instructions.py` and is asserted by tests.
