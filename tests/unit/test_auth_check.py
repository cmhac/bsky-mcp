"""Allowlisted GitHub user check (T011)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastmcp import Client
from fastmcp.exceptions import AuthorizationError
from fastmcp.server.auth import AccessToken
from fastmcp.server.middleware import AuthMiddleware
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from bsky_mcp.auth import github_user_id, is_allowed_user, make_user_check
from bsky_mcp.server import create_server
from tests.conftest import FakeBluesky

OWNER_ID = 49451910


def token(sub: str | None, login: str = "cmhac") -> AccessToken:
    claims = {"login": login} | ({"sub": sub} if sub is not None else {})
    return AccessToken(token="t", client_id="c", scopes=["user"], subject=sub, claims=claims)


def test_user_id_from_sub() -> None:
    assert github_user_id(token(str(OWNER_ID))) == OWNER_ID
    assert github_user_id(token(None)) is None
    assert github_user_id(None) is None


def test_allowed_user() -> None:
    assert is_allowed_user(token(str(OWNER_ID)), (OWNER_ID,))
    assert not is_allowed_user(token("12345"), (OWNER_ID,))
    assert not is_allowed_user(None, (OWNER_ID,))


def test_login_match_with_different_id_is_denied() -> None:
    # Someone who renamed into the owner's old username must not get in.
    assert not is_allowed_user(token("999", login="cmhac"), (OWNER_ID,))


def test_check_raises_for_denied_user() -> None:
    check = make_user_check((OWNER_ID,))

    class Ctx:
        token = None

    with pytest.raises(AuthorizationError):
        check(Ctx())  # type: ignore[arg-type]


async def _client_as(sub: str | None) -> AsyncIterator[Client]:
    mcp = create_server(
        lambda: FakeBluesky(), middleware=[AuthMiddleware(auth=make_user_check((OWNER_ID,)))]
    )
    user = AuthenticatedUser(token(sub)) if sub is not None else None
    reset = auth_context_var.set(user)
    try:
        async with Client(mcp) as c:
            yield c
    finally:
        auth_context_var.reset(reset)


@pytest.fixture
async def allowed() -> AsyncIterator[Client]:
    async for c in _client_as(str(OWNER_ID)):
        yield c


@pytest.fixture
async def denied() -> AsyncIterator[Client]:
    async for c in _client_as("12345"):
        yield c


@pytest.fixture
async def anonymous() -> AsyncIterator[Client]:
    async for c in _client_as(None):
        yield c


async def test_allowed_user_sees_tools(allowed: Client) -> None:
    tools = await allowed.list_tools()
    assert "get_timeline" in {t.name for t in tools}
    result = await allowed.call_tool("get_my_profile", {})
    assert not result.is_error


async def _assert_sees_nothing(c: Client) -> None:
    assert await c.list_tools() == []
    with pytest.raises(Exception, match=r"(?i)not allowed|unknown tool|not found|authoriz"):
        await c.call_tool("get_my_profile", {})


async def test_unlisted_user_sees_nothing(denied: Client) -> None:
    await _assert_sees_nothing(denied)


async def test_anonymous_sees_nothing(anonymous: Client) -> None:
    await _assert_sees_nothing(anonymous)
