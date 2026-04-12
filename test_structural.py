"""Structural smoke test."""

from __future__ import annotations

from ev_charging_grid_env.envs import MultiAgentEVChargingGridEnv


def main() -> int:
    env = MultiAgentEVChargingGridEnv()
    observation, info = env.reset(seed=42)
    assert "station_features" in observation
    assert "queue_lengths" in observation
    result = env.step(
        {
            "coordinator_action": {
                "price_deltas": [0] * env.num_stations,
                "emergency_target_station": 0,
            },
            "station_actions": [1] * env.num_stations,
        }
    )
    assert len(result) == 5
    print("structural: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

