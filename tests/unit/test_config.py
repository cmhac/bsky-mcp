"""Settings validation (T008)."""

from __future__ import annotations

import ipaddress

import pytest

from bsky_mcp.config import ConfigError, load_settings


def test_valid_settings_load(env: pytest.MonkeyPatch) -> None:
    s = load_settings()
    assert s.allowed_github_user_ids == (49451910,)
    assert s.allowed_ip_ranges == (ipaddress.ip_network("160.79.104.0/21"),)
    assert s.ip_allowlist_exempt_paths == ("/authorize", "/consent", "/auth/callback")
    assert s.allowed_client_redirect_uris == ("https://claude.ai/api/mcp/auth_callback",)
    assert s.unsafe_disable_oauth is False
    assert s.unsafe_disable_ip_allowlist is False


@pytest.mark.parametrize(
    "missing",
    [
        "GITHUB_CLIENT_ID",
        "GITHUB_CLIENT_SECRET",
        "ALLOWED_GITHUB_USER_IDS",
        "BASE_URL",
        "JWT_SIGNING_KEY",
        "STORAGE_ENCRYPTION_KEY",
        "REDIS_URL",
    ],
)
def test_missing_required_fails(env: pytest.MonkeyPatch, missing: str) -> None:
    env.delenv(missing)
    with pytest.raises(ConfigError, match=missing):
        load_settings()


def test_invalid_cidr_fails(env: pytest.MonkeyPatch) -> None:
    env.setenv("ALLOWED_IP_RANGES", "160.79.104.0/33")
    with pytest.raises(ConfigError, match="ALLOWED_IP_RANGES"):
        load_settings()


def test_multiple_ranges_parse(env: pytest.MonkeyPatch) -> None:
    env.setenv("ALLOWED_IP_RANGES", "10.0.0.0/8, 2001:db8::/32")
    assert len(load_settings().allowed_ip_ranges) == 2


def test_short_signing_key_fails(env: pytest.MonkeyPatch) -> None:
    import base64

    env.setenv("JWT_SIGNING_KEY", base64.b64encode(b"x" * 31).decode())
    with pytest.raises(ConfigError, match="JWT_SIGNING_KEY"):
        load_settings()


def test_bad_fernet_key_fails(env: pytest.MonkeyPatch) -> None:
    env.setenv("STORAGE_ENCRYPTION_KEY", "not-a-fernet-key")
    with pytest.raises(ConfigError, match="STORAGE_ENCRYPTION_KEY"):
        load_settings()


def test_non_numeric_user_ids_fail(env: pytest.MonkeyPatch) -> None:
    env.setenv("ALLOWED_GITHUB_USER_IDS", "cmhac")
    with pytest.raises(ConfigError, match="ALLOWED_GITHUB_USER_IDS"):
        load_settings()


def test_production_requires_https_and_bluesky(env: pytest.MonkeyPatch) -> None:
    env.setenv("VERCEL_ENV", "production")
    with pytest.raises(ConfigError, match="BLUESKY_HANDLE"):
        load_settings()
    env.setenv("BLUESKY_HANDLE", "me.bsky.social")
    env.setenv("BLUESKY_APP_PASSWORD", "abcd-efgh-ijkl-mnop")
    env.setenv("BASE_URL", "http://insecure.example.test")
    with pytest.raises(ConfigError, match="https"):
        load_settings()


def test_bluesky_optional_outside_production(env: pytest.MonkeyPatch) -> None:
    env.setenv("VERCEL_ENV", "preview")
    assert load_settings().bluesky_configured is False


def test_error_messages_never_include_values(env: pytest.MonkeyPatch) -> None:
    env.setenv("STORAGE_ENCRYPTION_KEY", "super-secret-but-invalid")
    with pytest.raises(ConfigError) as info:
        load_settings()
    assert "super-secret-but-invalid" not in str(info.value)


def test_disabling_oauth_relaxes_auth_requirements(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("UNSAFE_DISABLE_OAUTH", "true")
    assert load_settings().unsafe_disable_oauth is True
