"""Server and ASGI app construction."""

from __future__ import annotations

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware

from bsky_mcp import instructions
from bsky_mcp.auth import build_auth
from bsky_mcp.bluesky.client import BlueskyAPI, SafeBlueskyClient
from bsky_mcp.config import Settings
from bsky_mcp.ip_allowlist import IPAllowlistMiddleware
from bsky_mcp.logging import configure_logging
from bsky_mcp.tools import ApiProvider, delete, discovery, drafts, engagement, lists, read

MCP_PATH = "/mcp"
SERVER_NAME = "bsky-mcp"


def create_server(api: ApiProvider, auth=None, middleware: list | None = None) -> FastMCP:
    """Build the FastMCP server with every tool registered against ``api``."""
    mcp = FastMCP(
        name=SERVER_NAME,
        instructions=instructions.SERVER_INSTRUCTIONS,
        auth=auth,
        middleware=middleware or [],
        mask_error_details=True,
    )
    for module in (read, drafts, engagement, delete, discovery, lists):
        module.register(mcp, api)
    return mcp


def create_app(settings: Settings, api: BlueskyAPI | None = None) -> Starlette:
    """Build the production ASGI app: IP allowlist -> OAuth -> user check -> tools."""
    configure_logging(settings)
    if api is None:
        api = SafeBlueskyClient(
            handle=settings.bluesky_handle,
            app_password=(
                settings.bluesky_app_password.get_secret_value()
                if settings.bluesky_app_password
                else None
            ),
            service=settings.bluesky_service,
        )
    bound_api = api
    provider, auth_middleware = build_auth(settings)
    mcp = create_server(lambda: bound_api, auth=provider, middleware=auth_middleware)
    return mcp.http_app(
        path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        middleware=[
            Middleware(
                IPAllowlistMiddleware,
                networks=settings.allowed_ip_ranges,
                exempt_paths=settings.ip_allowlist_exempt_paths,
                trust_vercel_header=settings.on_vercel,
                disabled=settings.unsafe_disable_ip_allowlist,
            )
        ],
    )
