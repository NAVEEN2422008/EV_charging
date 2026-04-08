"""Dashboard policy adapter behavior tests."""

from __future__ import annotations

from pathlib import Path

from ev_charging_grid_env.dashboard.policies import build_policy_bundle


def test_checkpoint_note_is_truthful_without_inference() -> None:
    fake = Path("nonexistent.ckpt")
    bundle_missing = build_policy_bundle("PPO", 10, checkpoint_path=str(fake))
    assert "fallback" in bundle_missing.note.lower()


def test_existing_checkpoint_still_reports_fallback(tmp_path: Path) -> None:
    ckpt = tmp_path / "model.pt"
    ckpt.write_text("placeholder", encoding="utf-8")
    bundle = build_policy_bundle("MAPPO", 10, checkpoint_path=str(ckpt))
    assert "fallback" in bundle.note.lower()
