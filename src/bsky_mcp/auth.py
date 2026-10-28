"""GitHub OAuth (via FastMCP's OAuth proxy) and the allowlisted-user check."""

from __future__ import annotations

from cryptography.fernet import Fernet
from fastmcp.exceptions import AuthorizationError
from fastmcp.server.auth import AccessToken, AuthContext
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.middleware import AuthMiddleware
from key_value.aio.stores.redis import RedisStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

from bsky_mcp.config import GITHUB_CALLBACK_PATH, ConfigError, Settings, signing_key_bytes
from bsky_mcp.logging import get_logger

_logger = get_logger("auth")


def github_user_id(token: AccessToken | None) -> int | None:
    """The numeric GitHub user ID from a verified token, or None.

    The ID (not the login) is used because GitHub usernames can be renamed and later reclaimed by
    someone else.
    """
    if token is None:
        return None
    raw = (token.claims or {}).get("sub") or token.subject
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def is_allowed_user(token: AccessToken | None, allowed_ids: tuple[int, ...]) -> bool:
    user_id = github_user_id(token)
    return user_id is not None and user_id in allowed_ids


def make_user_check(allowed_ids: tuple[int, ...]):
    """An AuthMiddleware check that admits only allowlisted GitHub user IDs."""

    def check(ctx: AuthContext) -> bool:
        if is_allowed_user(ctx.token, allowed_ids):
            return True
        login = (ctx.token.claims or {}).get("login") if ctx.token else None
        _logger.info("Denied unlisted GitHub account: login=%s", login)
        raise AuthorizationError("This GitHub account is not allowed to use this server.")

    return check


def build_storage(settings: Settings) -> FernetEncryptionWrapper:
    if settings.redis_url is None or settings.storage_encryption_key is None:
        raise ConfigError("REDIS_URL and STORAGE_ENCRYPTION_KEY are required for OAuth storage")
    store = RedisStore(url=settings.redis_url.get_secret_value())
    fernet = Fernet(settings.storage_encryption_key.get_secret_value().encode())
    return FernetEncryptionWrapper(key_value=store, fernet=fernet)


def build_auth(settings: Settings) -> tuple[GitHubProvider | None, list[AuthMiddleware]]:
    """Return the OAuth provider and the user-check middleware, or nothing if OAuth is disabled."""
    if settings.unsafe_disable_oauth:
        _logger.warning("UNSAFE_DISABLE_OAUTH is set: OAuth and the user allowlist are OFF.")
        return None, []
    if not (settings.github_client_id and settings.github_client_secret and settings.base_url):
        raise ConfigError("GitHub OAuth settings are incomplete")
    provider = GitHubProvider(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret.get_secret_value(),
        base_url=settings.base_url,
        redirect_path=GITHUB_CALLBACK_PATH,
        jwt_signing_key=signing_key_bytes(settings),
        client_storage=build_storage(settings),
        require_authorization_consent=True,
        allowed_client_redirect_uris=list(settings.allowed_client_redirect_uris),
    )
    return provider, [AuthMiddleware(auth=make_user_check(settings.allowed_github_user_ids))]
