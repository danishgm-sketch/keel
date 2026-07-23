"""Minimal .env loader (stdlib only — no python-dotenv dependency).

Loads KEY=VALUE lines from a .env file into os.environ without overwriting
variables already set in the real environment. Secrets stay in the process;
they are never logged or written anywhere by Keel.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(start: str | Path | None = None) -> Path | None:
    """Find the nearest .env walking up from `start` (default: cwd) and load it.
    Returns the path loaded, or None if no .env was found."""
    here = Path(start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        candidate = d / ".env"
        if candidate.is_file():
            _apply(candidate)
            return candidate
    return None


def _apply(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
