"""Enable ``python -m keel ...`` (and ``pythonw -m keel app`` for a no-console
desktop launch on Windows)."""

from __future__ import annotations

import sys

from keel.cli import main

if __name__ == "__main__":
    sys.exit(main())
