"""Inference contract tests."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import inference


def test_run_simulation_and_logs() -> None:
    logs, result = inference.capture_run_output(task_id="easy", steps=5, seed=42)
    assert "[START]" in logs
    assert "[STEP]" in logs and "reward=" in logs
    assert "[END]" in logs
    assert isinstance(result["total_reward"], float)
    assert isinstance(result["summary"], str)
    json.dumps(result)


@patch("inference.OpenAI")
def test_llm_client_uses_proxy_settings(mock_openai: MagicMock) -> None:
    os.environ["API_BASE_URL"] = "https://proxy.example.com/v1"
    os.environ["API_KEY"] = "test-key"
    try:
        inference.get_llm_client()
        kwargs = mock_openai.call_args.kwargs
        assert kwargs["base_url"] == "https://proxy.example.com/v1"
        assert kwargs["api_key"] == "test-key"
    finally:
        os.environ.pop("API_BASE_URL", None)
        os.environ.pop("API_KEY", None)


def test_setup_llm_client_requires_env_vars() -> None:
    old_base = os.environ.pop("API_BASE_URL", None)
    old_key = os.environ.pop("API_KEY", None)
    try:
        try:
            inference.setup_llm_client()
        except ValueError as exc:
            assert "API_BASE_URL" in str(exc)
        else:
            raise AssertionError("setup_llm_client() should require API_BASE_URL")
    finally:
        if old_base is not None:
            os.environ["API_BASE_URL"] = old_base
        if old_key is not None:
            os.environ["API_KEY"] = old_key

