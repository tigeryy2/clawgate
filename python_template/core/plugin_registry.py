from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from python_template.core.exceptions import NotFoundError
from python_template.core.manifests import PluginActionManifest, PluginManifest
from python_template.core.models import (
    InternalActionResult,
    InternalReadResult,
    PluginSummary,
    ReadQuery,
)


@dataclass(frozen=True)
class ActionContext:
    plugin_id: str
    phase: str
    action: PluginActionManifest
    resource: str | None = None
    resource_id: str | None = None


class PluginProtocol(Protocol):
    manifest: PluginManifest

    def list_resource(self, resource: str, query: ReadQuery) -> InternalReadResult: ...

    def get_resource(
        self,
        resource: str,
        resource_id: str,
        view: str | None,
        query: ReadQuery,
    ) -> InternalReadResult: ...

    def run_action(
        self, context: ActionContext, args: dict
    ) -> InternalActionResult: ...


class PluginRegistry:
    def __init__(self, plugins: list[PluginProtocol]):
        self._plugins: dict[str, PluginProtocol] = {}
        for plugin in plugins:
            plugin_id = plugin.manifest.id
            if plugin_id in self._plugins:
                msg = f"duplicate plugin id '{plugin_id}'"
                raise ValueError(msg)
            self._plugins[plugin_id] = plugin

    def list_plugins(self) -> list[PluginSummary]:
        return [
            PluginSummary(
                id=plugin.manifest.id,
                name=plugin.manifest.name,
                version=plugin.manifest.version,
                runtime_mode=plugin.manifest.runtime_mode,
            )
            for plugin in self._plugins.values()
        ]

    def get_plugin(self, plugin_id: str) -> PluginProtocol:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise NotFoundError(f"plugin '{plugin_id}' not found")
        return plugin

    def get_manifest(self, plugin_id: str) -> PluginManifest:
        return self.get_plugin(plugin_id).manifest

    def list_capabilities(self, plugin_id: str) -> list[dict[str, str]]:
        manifest = self.get_manifest(plugin_id)
        return [
            {
                "action": action.name,
                "capability_id": action.capability_id,
                "resource_type": action.resource_type,
                "risk_tier": action.risk_tier.value,
                "route_pattern": action.route_pattern,
            }
            for action in manifest.actions
        ]

    def resolve_action(
        self,
        plugin_id: str,
        action_name: str,
        resource: str | None,
    ) -> PluginActionManifest:
        manifest = self.get_manifest(plugin_id)
        for action in manifest.actions:
            if action.name != action_name:
                continue
            if action.resource != resource:
                continue
            return action
        if resource:
            msg = f"action '{action_name}' for resource '{resource}' not found in '{plugin_id}'"
            raise NotFoundError(msg)
        msg = f"action '{action_name}' not found in '{plugin_id}'"
        raise NotFoundError(msg)
