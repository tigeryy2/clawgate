from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from python_template.core.config import Settings
from python_template.core.exceptions import APIError, NotFoundError
from python_template.core.manifests import PluginManifest
from python_template.core.models import (
    InternalActionResult,
    InternalReadResult,
    ReadQuery,
)
from python_template.core.plugin_registry import ActionContext


@dataclass(frozen=True)
class SidecarPluginConfig:
    id: str
    base_url: str
    shared_secret: str | None = None
    timeout_seconds: float = 5.0


class SidecarPlugin:
    def __init__(self, config: SidecarPluginConfig):
        self._config = config
        manifest_payload = _request_json(
            method="GET",
            url=f"{self._config.base_url.rstrip('/')}/plugin/manifest",
            payload=None,
            headers=self._headers(),
            timeout_seconds=self._config.timeout_seconds,
        )
        self.manifest = PluginManifest.model_validate(manifest_payload)
        if self.manifest.id != self._config.id:
            msg = (
                f"sidecar plugin id mismatch: expected '{self._config.id}', "
                f"got '{self.manifest.id}'"
            )
            raise ValueError(msg)

    def list_resource(self, resource: str, query: ReadQuery) -> InternalReadResult:
        payload = _request_json(
            method="POST",
            url=f"{self._config.base_url.rstrip('/')}/plugin/resources/{resource}/list",
            payload=query.model_dump(),
            headers=self._headers(),
            timeout_seconds=self._config.timeout_seconds,
        )
        return InternalReadResult.model_validate(payload)

    def get_resource(
        self,
        resource: str,
        resource_id: str,
        view: str | None,
        query: ReadQuery,
    ) -> InternalReadResult:
        payload = _request_json(
            method="POST",
            url=(
                f"{self._config.base_url.rstrip('/')}/plugin/resources/{resource}/{resource_id}/get"
            ),
            payload={
                "view": view,
                "query": query.model_dump(),
            },
            headers=self._headers(),
            timeout_seconds=self._config.timeout_seconds,
        )
        return InternalReadResult.model_validate(payload)

    def run_action(self, context: ActionContext, args: dict) -> InternalActionResult:
        payload = _request_json(
            method="POST",
            url=(
                f"{self._config.base_url.rstrip('/')}/plugin/actions/"
                f"{context.action.name}/{context.phase}"
            ),
            payload={
                "resource": context.resource,
                "resource_id": context.resource_id,
                "args": args,
            },
            headers=self._headers(),
            timeout_seconds=self._config.timeout_seconds,
        )
        return InternalActionResult.model_validate(payload)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.shared_secret:
            headers["X-Clawgate-Sidecar-Secret"] = self._config.shared_secret
        return headers


def load_sidecar_plugins(settings: Settings) -> list[SidecarPlugin]:
    if not settings.sidecar_plugins_json:
        return []

    try:
        raw_payload = json.loads(settings.sidecar_plugins_json)
    except json.JSONDecodeError as exc:
        raise ValueError("SIDECAR_PLUGINS_JSON must be valid JSON") from exc

    if not isinstance(raw_payload, list):
        raise ValueError("SIDECAR_PLUGINS_JSON must be a list")

    plugins: list[SidecarPlugin] = []
    for item in raw_payload:
        if not isinstance(item, dict):
            raise ValueError("sidecar plugin entries must be objects")
        plugin_id = str(item.get("id", "")).strip()
        base_url = str(item.get("base_url", "")).strip()
        shared_secret = item.get("shared_secret")
        timeout_seconds = float(item.get("timeout_seconds", 5.0))

        if not plugin_id or not base_url:
            raise ValueError("sidecar plugin entries require id and base_url")

        config = SidecarPluginConfig(
            id=plugin_id,
            base_url=base_url,
            shared_secret=str(shared_secret).strip()
            if shared_secret is not None
            else None,
            timeout_seconds=timeout_seconds,
        )
        plugins.append(SidecarPlugin(config=config))

    return plugins


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
            if not raw_body:
                return {}
            body = json.loads(raw_body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        if exc.code == 404:
            raise NotFoundError(detail or "sidecar route not found") from exc
        raise APIError(
            500, "SIDECAR_HTTP_ERROR", detail or "sidecar request failed"
        ) from exc
    except urllib.error.URLError as exc:
        raise APIError(500, "SIDECAR_UNREACHABLE", str(exc.reason)) from exc

    if isinstance(body, dict):
        return body
    raise APIError(
        500, "SIDECAR_BAD_RESPONSE", "sidecar response must be a JSON object"
    )
