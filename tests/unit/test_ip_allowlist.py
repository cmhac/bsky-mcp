"""IP allowlist middleware (T010)."""

from __future__ import annotations

import ipaddress
import logging

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from bsky_mcp.config import DEFAULT_EXEMPT_PATHS
from bsky_mcp.ip_allowlist import IPAllowlistMiddleware, client_ip, ip_allowed

ANTHROPIC = (ipaddress.ip_network("160.79.104.0/21"),)
INSIDE = "160.79.104.10"
OUTSIDE = "203.0.113.5"


async def ok(_request):
    return PlainTextResponse("ok")


def make_app(trust_vercel: bool, disabled: bool = False) -> IPAllowlistMiddleware:
    inner = Starlette(
        routes=[Route(p, ok) for p in ["/mcp", "/token", "/authorize/x", *DEFAULT_EXEMPT_PATHS]]
    )
    return IPAllowlistMiddleware(
        inner,
        networks=ANTHROPIC,
        exempt_paths=DEFAULT_EXEMPT_PATHS,
        trust_vercel_header=trust_vercel,
        disabled=disabled,
    )


async def get(app, path: str, peer: str, headers: dict[str, str] | None = None) -> int:
    transport = httpx.ASGITransport(app=app, client=(peer, 1234))
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as http:
        return (await http.get(path, headers=headers or {})).status_code


def test_ip_allowed() -> None:
    assert ip_allowed(INSIDE, ANTHROPIC)
    assert not ip_allowed(OUTSIDE, ANTHROPIC)
    assert not ip_allowed(None, ANTHROPIC)
    assert not ip_allowed("not-an-ip", ANTHROPIC)


def test_vercel_header_used_on_vercel() -> None:
    scope = {"headers": [(b"x-vercel-forwarded-for", f"{INSIDE}, 10.0.0.1".encode())]}
    assert client_ip(scope, trust_vercel_header=True) == INSIDE


def test_missing_vercel_header_means_no_ip() -> None:
    assert client_ip({"headers": [], "client": (INSIDE, 1)}, trust_vercel_header=True) is None


async def test_enforced_routes_block_outside_ips() -> None:
    app = make_app(trust_vercel=False)
    assert await get(app, "/mcp", OUTSIDE) == 403
    assert await get(app, "/token", OUTSIDE) == 403
    assert await get(app, "/mcp", INSIDE) == 200


async def test_spoofed_headers_ignored_off_vercel() -> None:
    app = make_app(trust_vercel=False)
    spoof = {"x-forwarded-for": INSIDE, "x-real-ip": INSIDE, "x-vercel-forwarded-for": INSIDE}
    assert await get(app, "/mcp", OUTSIDE, spoof) == 403


async def test_on_vercel_uses_vercel_header() -> None:
    app = make_app(trust_vercel=True)
    assert await get(app, "/mcp", OUTSIDE, {"x-vercel-forwarded-for": INSIDE}) == 200
    assert await get(app, "/mcp", INSIDE, {"x-vercel-forwarded-for": OUTSIDE}) == 403


@pytest.mark.parametrize("path", DEFAULT_EXEMPT_PATHS)
async def test_browser_signin_routes_exempt(path: str) -> None:
    assert await get(make_app(trust_vercel=False), path, OUTSIDE) == 200


async def test_exemption_is_exact_path_only() -> None:
    assert await get(make_app(trust_vercel=False), "/authorize/x", OUTSIDE) == 403


async def test_disabled_allows_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        app = make_app(trust_vercel=False, disabled=True)
    assert "UNSAFE_DISABLE_IP_ALLOWLIST" in caplog.text
    assert await get(app, "/mcp", OUTSIDE) == 200
