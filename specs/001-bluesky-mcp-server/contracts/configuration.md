# Contract: Configuration (Environment Variables)

"Secret" means it MUST be stored as a Vercel
[Secret environment variable](https://vercel.com/docs/projects/environment-variables/sensitive-environment-variables)
(write-only after saving). `.env.example` lists every name with no values.

| Variable | Secret | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `BLUESKY_HANDLE` | No | Production only | — | Owner's Bluesky handle |
| `BLUESKY_APP_PASSWORD` | **Yes** | Production only | — | Bluesky app password (never the main password) |
| `BLUESKY_SERVICE` | No | No | `https://bsky.social` | PDS/entryway URL |
| `GITHUB_CLIENT_ID` | No | Yes | — | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | **Yes** | Yes | — | GitHub OAuth app client secret |
| `ALLOWED_GITHUB_USER_IDS` | No | Yes | — | Comma-separated numeric GitHub user IDs |
| `BASE_URL` | No | Yes | — | Public HTTPS URL of the production deployment |
| `JWT_SIGNING_KEY` | **Yes** | Yes | — | ≥32 random bytes, base64; signs FastMCP-issued tokens |
| `STORAGE_ENCRYPTION_KEY` | **Yes** | Yes | — | Fernet key encrypting OAuth state |
| `REDIS_URL` | **Yes** | Yes | — | `rediss://` URL of the OAuth state store |
| `ALLOWED_IP_RANGES` | No | No | `160.79.104.0/21` | Comma-separated CIDRs allowed to reach enforced routes |
| `IP_ALLOWLIST_EXEMPT_PATHS` | No | No | `/authorize,<consent path>,/auth/callback` | Exact paths exempt from the IP check |
| `ALLOWED_CLIENT_REDIRECT_URIS` | No | No | Claude's connector callback | OAuth client redirect URIs allowed |
| `UNSAFE_DISABLE_OAUTH` | No | No | `false` | Turns off OAuth. Reduces security; warns every cold start |
| `UNSAFE_DISABLE_IP_ALLOWLIST` | No | No | `false` | Turns off the IP check. Reduces security; warns every cold start |
| `LOG_LEVEL` | No | No | `INFO` | Logging level |

Rules:

- Startup fails if any required variable is missing or invalid (bad CIDR, non-HTTPS `BASE_URL` in
  production, short signing key, malformed Fernet key).
- "Production only" means required when `VERCEL_ENV=production`. Elsewhere (previews, local dev)
  the server starts without Bluesky credentials and tools return `not_configured` (spec edge case).
  Auth and storage variables are required everywhere the server is reachable.
- No variable value is ever logged. Logs show only whether a variable is set.
