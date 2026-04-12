"""Compatibility shim for older validators."""

from ev_charging_grid_env.api.server import app, main

__all__ = ["app", "main"]


if __name__ == "__main__":
    main()
