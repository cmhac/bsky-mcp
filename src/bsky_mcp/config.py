"""Typed settings loaded from the environment.

Validation fails closed: a missing or malformed required value stops startup. Error messages name
the variable but never include its value.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
from functools import lru_cache
from typing import Annotated, Any

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ANTHROPIC_OUTBOUND_RANGE = "160.79.104.0/21"
CLAUDE_CALLBACK_URI = "https://claude.ai/api/mcp/auth_callback"
GITHUB_CALLBACK_PATH = "/auth/callback"
# Routes a person's browser loads during sign-in. Everything else is IP-restricted.
DEFAULT_EXEMPT_PATHS = ("/authorize", "/consent", GITHUB_CALLBACK_PATH)
MIN_SIGNING_KEY_BYTES = 32

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

# Settings whose values must never be logged or returned.
SECRET_FIELDS = (
    "bluesky_app_password",
    "github_client_secret",
    "jwt_signing_key",
    "storage_encryption_key",
    "redis_url",
)


def _split_csv(value: Any) -> Any:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def _empty_to_none(value: Any) -> Any:
    """An empty variable means "use the default"."""
    return None if value in ([], (), "") else value


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    bluesky_handle: str | None = None
    bluesky_app_password: SecretStr | None = None
    bluesky_service: str = "https://bsky.social"

    github_client_id: str | None = None
    github_client_secret: SecretStr | None = None
    allowed_github_user_ids: Annotated[tuple[int, ...], NoDecode] = ()

    base_url: str | None = None
    jwt_signing_key: SecretStr | None = None
    storage_encryption_key: SecretStr | None = None
    redis_url: SecretStr | None = None

    allowed_ip_ranges: Annotated[tuple[IPNetwork, ...], NoDecode] = (
        ipaddress.ip_network(ANTHROPIC_OUTBOUND_RANGE),
    )
    ip_allowlist_exempt_paths: Annotated[tuple[str, ...], NoDecode] = DEFAULT_EXEMPT_PATHS
    allowed_client_redirect_uris: Annotated[tuple[str, ...], NoDecode] = (CLAUDE_CALLBACK_URI,)

    unsafe_disable_oauth: bool = False
    unsafe_disable_ip_allowlist: bool = False
    log_level: str = "INFO"

    vercel_env: str | None = Field(default=None)
    vercel: str | None = Field(default=None)

    @field_validator("allowed_ip_ranges", mode="before")
    @classmethod
    def _parse_networks(cls, value: Any) -> Any:
        value = _empty_to_none(_split_csv(value))
        if value is None:
            return (ipaddress.ip_network(ANTHROPIC_OUTBOUND_RANGE),)
        networks = []
        for item in value:
            try:
                networks.append(ipaddress.ip_network(item, strict=True))
            except ValueError as exc:
                raise ValueError("ALLOWED_IP_RANGES contains an invalid CIDR range") from exc
        return tuple(networks)

    @field_validator("ip_allowlist_exempt_paths", mode="before")
    @classmethod
    def _default_exempt(cls, value: Any) -> Any:
        value = _empty_to_none(_split_csv(value))
        if value is None:
            return DEFAULT_EXEMPT_PATHS
        for path in value:
            if not path.startswith("/"):
                raise ValueError("IP_ALLOWLIST_EXEMPT_PATHS entries must start with '/'")
        return tuple(value)

    @field_validator("allowed_client_redirect_uris", mode="before")
    @classmethod
    def _default_redirects(cls, value: Any) -> Any:
        value = _empty_to_none(_split_csv(value))
        return (CLAUDE_CALLBACK_URI,) if value is None else tuple(value)

    @field_validator("allowed_github_user_ids", mode="before")
    @classmethod
    def _parse_user_ids(cls, value: Any) -> Any:
        value = _empty_to_none(_split_csv(value))
        if value is None:
            return ()
        try:
            return tuple(int(item) for item in value)
        except (TypeError, ValueError) as exc:
            raise ValueError("ALLOWED_GITHUB_USER_IDS must be numeric GitHub user IDs") from exc

    @field_validator("base_url")
    @classmethod
    def _strip_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value

    @property
    def is_production(self) -> bool:
        return self.vercel_env == "production"

    @property
    def on_vercel(self) -> bool:
        return self.vercel == "1" or self.vercel_env is not None

    @property
    def bluesky_configured(self) -> bool:
        return bool(self.bluesky_handle and self.bluesky_app_password)

    @model_validator(mode="after")
    def _validate_required(self) -> Settings:
        missing: list[str] = []
        if self.is_production and not self.bluesky_configured:
            missing += [
                name
                for name, val in (
                    ("BLUESKY_HANDLE", self.bluesky_handle),
                    ("BLUESKY_APP_PASSWORD", self.bluesky_app_password),
                )
                if not val
            ]
        if not self.unsafe_disable_oauth:
            required = {
                "GITHUB_CLIENT_ID": self.github_client_id,
                "GITHUB_CLIENT_SECRET": self.github_client_secret,
                "ALLOWED_GITHUB_USER_IDS": self.allowed_github_user_ids,
                "BASE_URL": self.base_url,
                "JWT_SIGNING_KEY": self.jwt_signing_key,
                "STORAGE_ENCRYPTION_KEY": self.storage_encryption_key,
                "REDIS_URL": self.redis_url,
            }
            missing += [name for name, val in required.items() if not val]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

        if self.base_url and self.is_production and not self.base_url.startswith("https://"):
            raise ValueError("BASE_URL must use https in production")
        if self.jwt_signing_key is not None:
            _validate_signing_key(self.jwt_signing_key.get_secret_value())
        if self.storage_encryption_key is not None:
            _validate_fernet_key(self.storage_encryption_key.get_secret_value())
        return self


def _validate_signing_key(value: str) -> None:
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("JWT_SIGNING_KEY must be base64") from exc
    if len(raw) < MIN_SIGNING_KEY_BYTES:
        raise ValueError(f"JWT_SIGNING_KEY must decode to at least {MIN_SIGNING_KEY_BYTES} bytes")


def _validate_fernet_key(value: str) -> None:
    try:
        Fernet(value.encode())
    except (ValueError, TypeError) as exc:
        raise ValueError("STORAGE_ENCRYPTION_KEY must be a valid Fernet key") from exc


def signing_key_bytes(settings: Settings) -> bytes:
    if settings.jwt_signing_key is None:
        raise ConfigError("JWT_SIGNING_KEY is not set")
    return base64.b64decode(settings.jwt_signing_key.get_secret_value())


def load_settings() -> Settings:
    """Load settings, converting validation failures into a value-free ConfigError."""
    from pydantic import ValidationError

    try:
        return Settings()
    except ValidationError as exc:
        messages = "; ".join(err["msg"].removeprefix("Value error, ") for err in exc.errors())
        raise ConfigError(messages) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
