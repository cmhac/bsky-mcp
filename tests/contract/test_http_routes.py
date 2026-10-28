"""HTTP route access rules on the real ASGI app (T033, User Story 5)."""

from __future__ import annotations

import importlib
import sys

import httpx
import pytest

from bsky_mcp.config import ConfigError, get_settings, load_settings
from bsky_mcp.server import create_app
from tests.conftest import FakeBluesky

INSIDE = "160.79.104.10"
OUTSIDE = "203.0.113.5"

ENFORCED = [
    ("POST", "/mcp"),
    ("GET", "/.well-known/oauth-protected-resource/mcp"),
    ("GET", "/.well-known/oauth-authorization-server"),
    ("POST", "/register"),
    ("POST", "/token"),
    ("GET", "/nonexistent"),
]
EXEMPT = [("GET", "/authorize"), ("GET", "/consent"), ("GET", "/auth/callback")]


@pytest.fixture
def app(env: pytest.MonkeyPatch):
    return create_app(load_settings(), api=FakeBluesky())


async def request(app, method: str, path: str, peer: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, client=(peer, 4321))
    async with httpx.AsyncClient(
        transport=transport, base_url="https://bsky-mcp.example.test"
    ) as c:
        return await c.request(method, path)


@pytest.mark.parametrize(("method", "path"), ENFORCED)
async def test_enforced_routes_reject_outside_ips(app, method: str, path: str) -> None:
    assert (await request(app, method, path, OUTSIDE)).status_code == 403


@pytest.mark.parametrize(("method", "path"), EXEMPT)
async def test_browser_routes_reachable_from_any_ip(app, method: str, path: str) -> None:
    assert (await request(app, method, path, OUTSIDE)).status_code != 403


async def test_mcp_requires_token_from_allowed_ip(app) -> None:
    response = await request(app, "POST", "/mcp", INSIDE)
    assert response.status_code == 401
    assert "resource_metadata" in response.headers.get("www-authenticate", "")


async def test_discovery_reachable_from_allowed_ip(app) -> None:
    response = await request(app, "GET", "/.well-known/oauth-authorization-server", INSIDE)
    assert response.status_code == 200
    body = response.json()
    assert body["issuer"].startswith("https://bsky-mcp.example.test")
    assert "S256" in body.get("code_challenge_methods_supported", [])


async def test_unknown_path_404_from_allowed_ip(app) -> None:
    assert (await request(app, "GET", "/nonexistent", INSIDE)).status_code == 404


def test_app_module_fails_closed_without_config(clean_env: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    sys.modules.pop("bsky_mcp.app", None)
    with pytest.raises(ConfigError, match="Missing required configuration"):
        importlib.import_module("bsky_mcp.app")
    get_settings.cache_clear()
