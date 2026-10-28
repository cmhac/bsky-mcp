"""ASGI middleware that rejects requests from outside the allowed IP ranges.

On Vercel the client IP comes from ``x-vercel-forwarded-for``, which Vercel sets itself and which
clients cannot spoof (Vercel overwrites forwarding headers). Off Vercel, forwarding headers are
ignored and the socket peer address is used. Only exact paths in the exemption list skip the check.
"""

from __future__ import annotations

import ipaddress
import json
from collections.abc import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

from bsky_mcp.logging import get_logger

VERCEL_IP_HEADER = b"x-vercel-forwarded-for"
_logger = get_logger("ip_allowlist")

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def client_ip(scope: Scope, trust_vercel_header: bool) -> str | None:
    if trust_vercel_header:
        for name, value in scope.get("headers") or []:
            if name.lower() == VERCEL_IP_HEADER:
                # The first entry is the original client.
                return value.decode("latin-1").split(",")[0].strip()
        return None
    peer = scope.get("client")
    return peer[0] if peer else None


def ip_allowed(ip: str | None, networks: Iterable[IPNetwork]) -> bool:
    if not ip:
        return False
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in network for network in networks)


class IPAllowlistMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        networks: Iterable[IPNetwork],
        exempt_paths: Iterable[str],
        trust_vercel_header: bool,
        disabled: bool = False,
    ) -> None:
        self.app = app
        self.networks = tuple(networks)
        self.exempt_paths = frozenset(exempt_paths)
        self.trust_vercel_header = trust_vercel_header
        self.disabled = disabled
        if disabled:
            _logger.warning("UNSAFE_DISABLE_IP_ALLOWLIST is set: the IP allowlist is OFF.")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.disabled:
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return
        ip = client_ip(scope, self.trust_vercel_header)
        if ip_allowed(ip, self.networks):
            await self.app(scope, receive, send)
            return
        _logger.info("Denied request by IP allowlist: path=%s ip=%s", path, ip)
        body = json.dumps({"error": "forbidden"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
