from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from python_template.core.models import RiskTier, RuntimeMode

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


class PluginResourceManifest(BaseModel):
    name: str
    capability_id: str
    allowed_views: list[str] = Field(default_factory=lambda: ["headers", "body", "raw"])

    @field_validator("name")
    @classmethod
    def validate_resource_name(cls, value: str) -> str:
        if not SNAKE_CASE.match(value):
            msg = f"resource name '{value}' must be snake_case"
            raise ValueError(msg)
        return value


class PluginActionManifest(BaseModel):
    name: str
    capability_id: str
    resource_type: str
    risk_tier: RiskTier
    route_pattern: str
    supports_propose: bool
    requires_idempotency: bool
    emits_attributes: list[str]
    resource: str | None = None
    mutating: bool = True

    @field_validator("name")
    @classmethod
    def validate_action_name(cls, value: str) -> str:
        if not SNAKE_CASE.match(value):
            msg = f"action name '{value}' must be snake_case"
            raise ValueError(msg)
        return value

    @field_validator("resource")
    @classmethod
    def validate_resource_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not SNAKE_CASE.match(value):
            msg = f"resource name '{value}' must be snake_case"
            raise ValueError(msg)
        return value

    @field_validator("emits_attributes")
    @classmethod
    def validate_attributes(cls, value: list[str]) -> list[str]:
        if not value:
            msg = "emits_attributes must include at least one attribute"
            raise ValueError(msg)
        return value


class PluginManifest(BaseModel):
    schema_version: str = "1.0"
    id: str
    name: str
    version: str
    runtime_mode: RuntimeMode
    resources: list[PluginResourceManifest] = Field(default_factory=list)
    actions: list[PluginActionManifest]
    required_secrets: list[str] = Field(default_factory=list)
    required_scopes: list[str] = Field(default_factory=list)
    default_policy: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_plugin_id(cls, value: str) -> str:
        if not SNAKE_CASE.match(value):
            msg = f"plugin id '{value}' must be lowercase snake_case"
            raise ValueError(msg)
        return value

    @field_validator("resources")
    @classmethod
    def validate_resources(
        cls, value: list[PluginResourceManifest]
    ) -> list[PluginResourceManifest]:
        names = [resource.name for resource in value]
        if len(names) != len(set(names)):
            raise ValueError("resource names must be unique within plugin")
        return value

    @field_validator("actions")
    @classmethod
    def validate_actions(
        cls, value: list[PluginActionManifest]
    ) -> list[PluginActionManifest]:
        if not value:
            msg = "manifest must declare at least one action"
            raise ValueError(msg)
        action_keys = {(action.name, action.resource) for action in value}
        if len(action_keys) != len(value):
            msg = "action names must be unique per resource within plugin"
            raise ValueError(msg)
        return value
