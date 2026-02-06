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


def load_settings() -> Settings:
    return Settings(
        enable_api_alias=_to_bool(os.getenv("ENABLE_API_ALIAS"), default=False),
    )
