from __future__ import annotations

import os
from dataclasses import dataclass


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_prefix: str = "/v1"
    enable_api_alias: bool = False
    default_limit: int = 20
    max_limit: int = 100
    default_body_max_chars: int = 1200
    raw_read_enabled: bool = False
    require_auth: bool = True
    agent_tokens_json: str | None = None
    sidecar_plugins_json: str | None = None


def load_settings() -> Settings:
    return Settings(
        enable_api_alias=_to_bool(os.getenv("ENABLE_API_ALIAS"), default=False),
        raw_read_enabled=_to_bool(os.getenv("ENABLE_RAW_READ"), default=False),
        require_auth=_to_bool(os.getenv("REQUIRE_AUTH"), default=True),
        agent_tokens_json=os.getenv("AGENT_TOKENS_JSON"),
        sidecar_plugins_json=os.getenv("SIDECAR_PLUGINS_JSON"),
    )
