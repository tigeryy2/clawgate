from __future__ import annotations

import pytest

from python_template.core.config import load_settings


def test_load_settings_defaults_include_unique_api_port(monkeypatch):
    monkeypatch.delenv("CLAWGATE_API_HOST", raising=False)
    monkeypatch.delenv("CLAWGATE_API_PORT", raising=False)

    settings = load_settings()

    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8117


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
