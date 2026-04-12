"""Station-level baseline policy."""

from __future__ import annotations

from typing import Any


class StationAgent:
    """Converts station-local signals into one of four actions."""

    def act(self, station_snapshot: dict[str, Any]) -> int:
        queue_length = int(station_snapshot["queue_length"])
        emergency_queue = int(station_snapshot["emergency_queue"])
        free_chargers = int(station_snapshot["free_chargers"])

        if emergency_queue > 0:
            return 2
        if queue_length > max(6, free_chargers + 4):
            return 3
        if free_chargers > 0 and queue_length > 0:
            return 1
        return 0

