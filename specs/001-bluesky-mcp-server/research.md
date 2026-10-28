# Phase 0 Research: Personal Bluesky MCP Server

**Date**: 2026-10-28 | **Plan**: [plan.md](./plan.md)

Versions below were checked by installing the packages on 2026-10-28: FastMCP 4.1.4, mcp 2.3.0,
atproto 0.0.73, py-key-value-aio 0.4.6, Spec Kit 1.2.4, PMD 7.28.0.

## R1. Runtime and hosting

- **Decision**: Python 3.13 FastMCP app exposed as an ASGI app via `mcp.http_app(stateless_http=True)`,
  deployed on Vercel's Python runtime with the entrypoint set by `tool.vercel.entrypoint` in
  `pyproject.toml`. Dependencies managed with uv.
- **Rationale**: Vercel [runs ASGI apps natively](https://vercel.com/docs/functions/runtimes/python),
  loads them from `tool.vercel.entrypoint`, reads `pyproject.toml` with or without `uv.lock`, and
  supports Python 3.12–3.14. FastMCP's [HTTP deployment docs](https://gofastmcp.com/deployment/http.md)
  say stateless mode gives each request a fresh transport context, so no session affinity is needed,
  which suits serverless instances.
- **Alternatives**: TypeScript with Vercel's `mcp-handler` (rejected: owner chose FastMCP); a
  long-running host such as Fly or ECS (rejected: owner chose Vercel).

## R2. GitHub OAuth and the user allowlist

- **Decision**: `GitHubProvider` (FastMCP's OAuth proxy for GitHub) plus a server-wide
  `AuthMiddleware` check that admits only tokens whose GitHub user ID is in `ALLOWED_GITHUB_USER_IDS`
  (see the rename risk below).
  Consent screen stays on (`require_authorization_consent=True`). `allowed_client_redirect_uris` is
  pinned to Claude's callback.
- **Rationale**:
  - GitHub has no dynamic client registration, so FastMCP bridges it with an
    [OAuth proxy](https://gofastmcp.com/integrations/github.md).
  - FastMCP does **not** restrict which GitHub users can sign in. Its
    [authorization docs](https://gofastmcp.com/servers/authorization.md) show `AuthMiddleware` with a
    callable that rejects every request unless a claim matches. Inspecting FastMCP 4.1.4's source
    confirmed `GitHubProvider` puts the GitHub `login` in the token claims.
  - The [OAuth proxy docs](https://gofastmcp.com/servers/auth/oauth-proxy.md) recommend keeping the
    consent page on and list `https://claude.ai/api/mcp/auth_callback` as an example allowed redirect
    URI. Implementation must confirm the callback Claude actually uses.
  - The allowlist check is on GitHub login. Note the risk: a GitHub username can be renamed and later
    reclaimed by someone else. **Decision**: allowlist by numeric GitHub user ID (`sub` claim, also
    present in the token) with the login shown in logs, so a rename cannot grant access.
- **Alternatives**: a static bearer token (rejected: owner wants OAuth); OAuth without a user check
  (rejected: any GitHub user could connect).

## R3. Persistent, encrypted OAuth storage

- **Decision**: A Redis-compatible store from the Vercel Marketplace (Upstash by default), reached
  over TLS through `REDIS_URL`, wrapped in `FernetEncryptionWrapper` keyed by `STORAGE_ENCRYPTION_KEY`.
  Explicit `JWT_SIGNING_KEY`.
- **Rationale**: FastMCP's [storage docs](https://gofastmcp.com/servers/storage-backends.md) say
  in-memory storage is unsuitable for multi-process deployments, production needs persistent storage
  and an explicit signing key, and custom storage should be wrapped in `FernetEncryptionWrapper` or
  tokens are stored in plaintext. Upstash [accepts standard Redis clients over TLS](https://upstash.com/docs/redis/howto/connectclient)
  and offers a [Vercel integration](https://upstash.com/docs/redis/howto/vercelintegration.md).
  `RedisStore` in py-key-value-aio 0.4.6 accepts a `url`.
- **Alternatives**: DynamoDB (more setup); FastMCP's file store (does not survive serverless instances).

## R4. IP allowlisting on Vercel

- **Decision**: ASGI middleware in the app that reads the client IP from `x-vercel-forwarded-for`
  (falling back to `x-real-ip` only when running on Vercel) and checks it against `ALLOWED_IP_RANGES`
  (default `160.79.104.0/21`). Browser-facing OAuth routes are exempt (see R5). Outside Vercel
  (local dev, tests), the IP comes from the ASGI connection, never from headers.
- **Rationale**:
  - Vercel [overwrites `X-Forwarded-For` and does not forward external IPs](https://vercel.com/docs/headers/request-headers)
    to prevent spoofing; `x-real-ip` and `x-vercel-forwarded-for` carry the same value, and the latter
    is the one that survives an extra proxy in front of Vercel.
  - Anthropic publishes `160.79.104.0/21` as its [outbound range for MCP tool calls](https://platform.claude.com/docs/en/api/ip-addresses),
    stable and not changed without notice.
  - Vercel's own IP-based protection, [Trusted IPs](https://vercel.com/docs/deployment-protection),
    is Enterprise-only, so the check lives in the app.
- **Alternatives**: Vercel Firewall custom rules (possible later as an extra layer; not required).

## R5. Routes exempt from the IP allowlist

- **Decision**: Exempt only routes a human browser loads during sign-in: `/authorize`, the consent
  page route, and `/auth/callback`. Discovery (`/.well-known/*`), `/register`, `/token`, and `/mcp`
  stay IP-restricted.
- **Rationale**: Per the [OAuth proxy docs](https://gofastmcp.com/servers/auth/oauth-proxy.md),
  `/authorize` shows the consent page and GitHub redirects the browser to `/auth/callback`; those
  requests come from the owner's browser, not Anthropic. Claude's backend performs discovery,
  registration, and token exchange, and Anthropic says connectors are reached
  [from Anthropic's cloud](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).
- **Risk**: If any server-to-server step turns out to come from outside the published range, setup
  fails closed. **Mitigation**: denied requests are logged with path and IP (no secrets), and
  `IP_ALLOWLIST_EXEMPT_PATHS` lets the owner adjust exemptions without code changes. The quickstart
  verifies the real flow.

## R6. Bluesky drafts

- **Decision**: Use the `app.bsky.draft` endpoints (`createDraft`, `getDrafts`, `updateDraft`).
  `deleteDraft` is never wrapped. Each draft is created with `device_name = "Claude (bsky-mcp)"`.
- **Findings** (from atproto 0.0.73's generated models):
  - Drafts live in the account's private storage ("stash"), and `updateDraft` silently ignores
    unknown IDs. The server therefore re-reads the draft after updating and reports an error if it
    is missing.
  - A draft holds 1–100 posts, so threads are representable. Each draft post supports text (up to
    10,000 characters), one external link card, one quoted record, and media.
  - **There is no reply-target field in the draft schema.** A Bluesky draft cannot record which post
    it replies to. This conflicted with the original spec User Story 2; resolved below.
  - Bluesky [added drafts in February 2026](https://techcrunch.com/2026/02/09/bluesky-finally-adds-drafts).
    Whether an **app password** may call the draft endpoints is not documented anywhere I could find;
    the first implementation task is a smoke test against the real account.
- **Length rule**: Draft posts may hold 10,000 characters, but a published post is limited to
  [300 graphemes](https://raw.githubusercontent.com/bluesky-social/atproto/main/lexicons/app/bsky/feed/post.json).
  The server validates each draft post at 300 graphemes so drafts are publishable as-is (spec FR-007).

### Decision: reply drafts

Bluesky's draft format has no field for "this is a reply to post X." Options:

| Option | What happens | Trade-off |
| --- | --- | --- |
| A | Reply drafts go to Bluesky Drafts as plain text, with the parent post's link kept in the tool response and in a first line the owner deletes before posting | Visible in the app, but the owner must open the parent post and paste the reply manually |
| B | Reply drafts are kept on the server (encrypted, in the same store) and listed by `list_drafts`; Claude shows the text and the parent link | Keeps the reply target, but not visible in the Bluesky app |
| C | No stored reply drafts: Claude writes the reply in chat with a link to the parent post | Simplest; nothing to clean up |

**Resolved 2026-10-28: the owner chose C.** Revisit if Bluesky adds reply targets to drafts.

## R7. Allowed operations wrapper

- **Decision**: A `SafeBlueskyClient` class exposes only named methods mapped to an explicit
  allowlist of XRPC operations (reads; `createDraft`, `getDrafts`, `updateDraft`; follow, like,
  repost create; and delete of `app.bsky.graph.follow`, `app.bsky.feed.like`, `app.bsky.feed.repost`,
  and `app.bsky.feed.post` records owned by the session DID). The underlying atproto client is held
  privately and never returned. A test enumerates the wrapper's public surface and the allowlist and
  fails if `createRecord` for `app.bsky.feed.post`, `deleteDraft`, block, or any unlisted operation is
  reachable.
- **Rationale**: Constitution Principles II and III require rejection in code, not just omission.

## R8. Guarded post deletion

- **Decision**: `delete_post(post_uri, confirm: Literal["delete"])`. The tool checks the post's
  author DID equals the session DID, requires `confirm == "delete"`, and its description states the
  owner-message-only rule. Server instructions repeat it.
- **Rationale**: Spec FR-009–FR-011. A server cannot verify instruction provenance, so the
  confirmation input plus description is the strongest available guard; README says so (FR-025).

## R9. Pre-commit and CI

- **Decision**:
  - Ruff via [`astral-sh/ruff-pre-commit`](https://pydevtools.com/handbook/how-to/how-to-set-up-pre-commit-hooks-for-a-python-project.md)
    (`ruff-check --fix`, `ruff-format`); ty via the official `astral-sh/ty-pre-commit` hook.
  - CPD as a local hook running `scripts/cpd.sh`, which downloads a pinned PMD (7.28.0) release
    into a cache directory, verifies its SHA-256, and runs
    `pmd cpd --minimum-tokens 50 --language python --dir src --dir tests`. CPD
    [exits 4 when duplicates are found](https://docs.pmd-code.org/latest/pmd_userdocs_cpd.html), which
    fails the hook. I ran PMD 7.28.0's CPD with `--language python` on duplicated files and it
    reported the duplicate.
  - GitHub Actions workflow on `pull_request` runs `pre-commit run --all-files` with the same config,
    plus `pytest`. Java comes from `actions/setup-java`.
- **Branch protection caveat**: GitHub supports protected branches on private repositories only on
  [Pro, Team, and Enterprise plans](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
  If the owner's account is on GitHub Free, "failures block merging" (FR-021) needs either GitHub
  Pro or a public repository. The README documents this.

## R10. Vercel CI/CD and deploy button

- **Decision**: Vercel's GitHub integration builds a preview for every PR and deploys `main` to
  production. Deployment Protection stays at Standard Protection, which
  [protects every deployment except production domains](https://vercel.com/docs/deployment-protection),
  so previews are not publicly reachable; production relies on OAuth + IP allowlist.
- The README button uses `https://vercel.com/new/clone?repository-url=…&env=…&envDescription=…&envLink=…`
  per Vercel's [Deploy Button docs](https://vercel.com/docs/deploy-button/source). Because the repo
  is private, the button works for the owner's own account.
- Secrets are entered as [Secret environment variables](https://vercel.com/docs/projects/environment-variables/sensitive-environment-variables),
  which are write-only after saving.

## R11. Testing

- **Decision**: pytest with FastMCP's in-memory client against the server object, and a fake
  `SafeBlueskyClient` backend. Contract tests per tool, unit tests for IP and user allowlists, and
  the forbidden-operation tests from R7. A manual quickstart covers the live Bluesky, GitHub, and
  Claude steps.
- **Rationale**: FastMCP documents [testing by passing the server object directly to a `Client`](https://gofastmcp.com/servers/testing.md), with no network.
