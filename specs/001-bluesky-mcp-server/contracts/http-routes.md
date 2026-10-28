# Contract: HTTP Routes and Access Rules

Base URL: the production domain, set as `BASE_URL`. Route names come from FastMCP's OAuth proxy
([docs](https://gofastmcp.com/servers/auth/oauth-proxy.md)); implementation must confirm the exact
consent-page path in the installed FastMCP version and record it here.

| Route | Called by | IP allowlist | OAuth | User-ID check |
| --- | --- | --- | --- | --- |
| `POST /mcp` (and GET/DELETE per Streamable HTTP) | Claude (Anthropic cloud) | **Enforced** | Required | Required |
| `GET /.well-known/oauth-protected-resource[/mcp]` | Claude | **Enforced** | No | No |
| `GET /.well-known/oauth-authorization-server` | Claude | **Enforced** | No | No |
| `POST /register` | Claude | **Enforced** | No | No |
| `POST /token` | Claude | **Enforced** | No | No |
| `GET /authorize` | Owner's browser | **Exempt** | Starts flow | — |
| Consent page (FastMCP-defined path) | Owner's browser | **Exempt** | Part of flow | — |
| `GET /auth/callback` | Owner's browser (redirect from GitHub) | **Exempt** | Completes flow | Checked when the token is used |
| Anything else | — | Enforced | — | 404 |

## IP check

- Client IP source on Vercel: `x-vercel-forwarded-for` (set by Vercel; Vercel overwrites
  `X-Forwarded-For` to prevent spoofing per its
  [request headers docs](https://vercel.com/docs/headers/request-headers)). Off Vercel: the ASGI
  connection's peer address. Client-supplied forwarding headers are never trusted off Vercel.
- Requests outside `ALLOWED_IP_RANGES` on enforced routes get `403` with a generic body. The
  denial is logged with path and IP only.
- Exempt routes come from `IP_ALLOWLIST_EXEMPT_PATHS` (default: the three browser routes above).
  Exemption is exact-path matching, not prefix matching.

## User-ID check

The GitHub user's numeric ID is read from the verified token (`sub`). If not in
`ALLOWED_GITHUB_USER_IDS`, every tool call and tool listing is denied, so a non-allowlisted
account sees no tools.

## Redirect URIs

`allowed_client_redirect_uris` is set from `ALLOWED_CLIENT_REDIRECT_URIS` (default: Claude's
connector callback). Any other redirect URI is rejected at registration and authorization.
