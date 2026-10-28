"""Vercel entrypoint.

Vercel looks for an ``app`` object in ``main.py`` at the repository root. The package lives under
``src/``, so this file puts ``src`` on the import path first; that works whether or not Vercel
installs the project itself.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from bsky_mcp.app import app  # noqa: E402

__all__ = ["app"]
