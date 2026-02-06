from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from python_template import DOTENV_FILE


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str | None, default: int, key: str) -> int:
    if value is None:
        return default
    stripped = value.strip()
    if not stripped:
        return default
    try:
        return int(stripped)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    api_prefix: str = "/v1"
    api_host: str = "0.0.0.0"
    api_port: int = 8117
    enable_api_alias: bool = False
    default_limit: int = 20
    max_limit: int = 100
    default_body_max_chars: int = 1200
    raw_read_enabled: bool = False
    require_auth: bool = True
    agent_tokens_json: str | None = None
    sidecar_plugins_json: str | None = None


def load_settings() -> Settings:
    load_dotenv(DOTENV_FILE)
    return Settings(
        api_host=os.getenv("CLAWGATE_API_HOST", "0.0.0.0").strip() or "0.0.0.0",
        api_port=_to_int(
            os.getenv("CLAWGATE_API_PORT"),
            default=8117,
            key="CLAWGATE_API_PORT",
        ),
        enable_api_alias=_to_bool(os.getenv("ENABLE_API_ALIAS"), default=False),
        raw_read_enabled=_to_bool(os.getenv("ENABLE_RAW_READ"), default=False),
        require_auth=_to_bool(os.getenv("REQUIRE_AUTH"), default=True),
        agent_tokens_json=os.getenv("AGENT_TOKENS_JSON"),
        sidecar_plugins_json=os.getenv("SIDECAR_PLUGINS_JSON"),
    )
