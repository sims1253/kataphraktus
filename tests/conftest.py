"""Pytest configuration to ensure the `src` package layout is importable.

This adds the `src/` directory to `sys.path` so tests can import the
`cataphract` package (e.g., `from cataphract.main import app`) without
requiring an editable install in CI.
"""

import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
