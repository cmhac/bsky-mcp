"""Vercel loads ``app`` from the root ``main.py`` (default entrypoint location)."""

from __future__ import annotations

import importlib
import sys

import pytest
from starlette.applications import Starlette

from bsky_mcp.config import get_settings


def test_root_main_exposes_app(env: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    for name in ("main", "bsky_mcp.app"):
        sys.modules.pop(name, None)
    main = importlib.import_module("main")
    assert isinstance(main.app, Starlette)
    assert any(getattr(route, "path", None) == "/mcp" for route in main.app.routes)
    get_settings.cache_clear()
