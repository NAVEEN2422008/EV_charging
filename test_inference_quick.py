"""Quick inference smoke test."""

from __future__ import annotations

from inference import call_llm_analyze, run_simulation


def main() -> int:
    result = run_simulation(steps=10, seed=42, emit_logs=False)
    assert result["status"] == "success"
    assert "simulation" in result
    assert "metrics" in result
    summary = call_llm_analyze({"total_reward": result["simulation"]["total_reward"]})
    assert isinstance(summary, str)
    print("inference: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

