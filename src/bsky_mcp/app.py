"""ASGI entrypoint loaded by Vercel (``tool.vercel.entrypoint = "bsky_mcp.app:app"``).

Startup fails closed: invalid or missing required configuration raises before any request is
served.
"""

from bsky_mcp.config import get_settings
from bsky_mcp.server import create_app

app = create_app(get_settings())
