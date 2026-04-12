"""Compatibility entrypoint for Docker and Hugging Face Spaces."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ev_charging_grid_env.api.server import app, main

__all__ = ["app", "main"]


if __name__ == "__main__":
    main()
