"""API route tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ev_charging_grid_env.api.server import app


def test_reset_step_state_routes() -> None:
    client = TestClient(app)

    reset_response = client.post("/reset", json={"seed": 42, "task_id": "medium"})
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert "observation" in reset_payload

    step_response = client.post(
        "/step",
        json={
            "action": {
                "coordinator_action": {
                    "price_deltas": [0] * 10,
                    "emergency_target_station": 0,
                },
                "station_actions": [1] * 10,
            }
        },
    )
    assert step_response.status_code == 200
    step_payload = step_response.json()
    assert "reward" in step_payload

    state_response = client.get("/state")
    assert state_response.status_code == 200
    assert "observation" in state_response.json()

