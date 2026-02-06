from __future__ import annotations

from pathlib import Path

import pytest

from python_template.core.config import load_settings


def test_load_settings_defaults_include_unique_api_port(monkeypatch):
    monkeypatch.delenv("CLAWGATE_API_HOST", raising=False)
    monkeypatch.delenv("CLAWGATE_API_PORT", raising=False)
    monkeypatch.delenv("ACTION_APPROVAL_DEFAULTS_JSON", raising=False)
    monkeypatch.delenv("ACTION_APPROVAL_OVERRIDES_JSON", raising=False)

    settings = load_settings()

    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8117
    assert settings.action_approval_defaults_json is None
    assert settings.action_approval_overrides_json is None


def test_load_settings_reads_api_bind_from_env(monkeypatch):
    monkeypatch.setenv("CLAWGATE_API_HOST", "0.0.0.0")
    monkeypatch.setenv("CLAWGATE_API_PORT", "9011")

    settings = load_settings()

    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 9011


def test_load_settings_rejects_invalid_api_port(monkeypatch):
    monkeypatch.setenv("CLAWGATE_API_PORT", "bad-port")

    with pytest.raises(ValueError, match="CLAWGATE_API_PORT must be an integer"):
        load_settings()


def test_load_settings_auto_loads_env_file(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CLAWGATE_API_HOST=127.0.0.1\n"
        "CLAWGATE_API_PORT=9222\n"
        'AGENT_TOKENS_JSON=[{"token":"token-from-dotenv","agent_id":"bot","tailscale_identity":"*","capabilities":["*"]}]\n',
        encoding="utf-8",
    )

    monkeypatch.delenv("CLAWGATE_API_HOST", raising=False)
    monkeypatch.delenv("CLAWGATE_API_PORT", raising=False)
    monkeypatch.delenv("AGENT_TOKENS_JSON", raising=False)
    monkeypatch.setattr("python_template.core.config.DOTENV_FILE", env_file)

    settings = load_settings()

    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 9222
    assert settings.agent_tokens_json is not None
    assert "token-from-dotenv" in settings.agent_tokens_json


def test_load_settings_reads_action_approval_env_json(monkeypatch):
    monkeypatch.setenv(
        "ACTION_APPROVAL_DEFAULTS_JSON",
        '{"read_only": false, "routine": false, "transactional": true, "dangerous": true}',
    )
    monkeypatch.setenv(
        "ACTION_APPROVAL_OVERRIDES_JSON",
        '{"global":{"allow":["apple_music.playback.*"]},"plugins":{"apple_music":{"require":["playlist.delete"]}}}',
    )

    settings = load_settings()

    assert settings.action_approval_defaults_json is not None
    assert '"routine": false' in settings.action_approval_defaults_json
    assert settings.action_approval_overrides_json is not None
    assert '"plugins"' in settings.action_approval_overrides_json
