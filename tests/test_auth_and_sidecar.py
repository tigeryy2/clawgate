from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from python_template.api.app import create_app
from python_template.api.runtime import create_runtime
from python_template.core.config import Settings

DEFAULT_HEADERS = {
    "Authorization": "Bearer dev-local-token",
    "X-Tailscale-Identity": "tailnet://local/dev-local",
}


def make_client(settings: Settings, headers: dict[str, str]) -> TestClient:
    runtime = create_runtime(settings=settings)
    app = create_app(runtime=runtime)
    client = TestClient(app)
    client.headers.update(headers)
    return client


def test_missing_auth_header_returns_401():
    settings = Settings()
    client = make_client(settings=settings, headers={})

    response = client.get("/v1/plugins")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_capability_denied_returns_403():
    limited_tokens = json.dumps(
        [
            {
                "token": "limited-token",
                "agent_id": "limited",
                "tailscale_identity": "tailnet://local/limited",
                "capabilities": ["system.plugins.read"],
            }
        ]
    )
    settings = Settings(agent_tokens_json=limited_tokens)
    headers = {
        "Authorization": "Bearer limited-token",
        "X-Tailscale-Identity": "tailnet://local/limited",
    }
    client = make_client(settings=settings, headers=headers)

    allowed = client.get("/v1/plugins")
    assert allowed.status_code == 200

    denied = client.get("/v1/gmail/messages")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "CAPABILITY_DENIED"


def test_sidecar_plugin_registration_and_routing(monkeypatch):
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_request_json(
        method: str,
        url: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        _ = headers
        _ = timeout_seconds
        calls.append((method, url, payload))

        if url.endswith("/plugin/manifest"):
            return {
                "schema_version": "1.0",
                "id": "notes_sidecar",
                "name": "Notes Sidecar",
                "version": "0.1.0",
                "runtime_mode": "sidecar",
                "resources": [
                    {
                        "name": "notes",
                        "capability_id": "notes_sidecar.notes.read",
                        "allowed_views": ["headers", "body"],
                    }
                ],
                "actions": [
                    {
                        "name": "sync",
                        "capability_id": "notes_sidecar.notes.sync",
                        "resource_type": "note",
                        "risk_tier": "read_only",
                        "route_pattern": "/:sync/{phase}",
                        "supports_propose": True,
                        "requires_idempotency": False,
                        "emits_attributes": ["principal", "resource_type"],
                        "resource": None,
                        "mutating": False,
                    }
                ],
                "required_secrets": [],
                "required_scopes": [],
                "default_policy": {},
            }

        if url.endswith("/plugin/resources/notes/list"):
            return {
                "data": {
                    "items": [{"id": "note_1", "title": "Hello"}],
                    "next_cursor": None,
                },
                "policy_items": [
                    {
                        "data_ref": "items[0]",
                        "attrs": {
                            "principal": "alice@corp.com",
                            "counterparty_domain": "corp.com",
                            "resource_type": "note",
                        },
                    }
                ],
            }

        if url.endswith("/plugin/actions/sync/execute"):
            return {
                "status": "success",
                "result": {"synced": 1},
                "summary": "Synced notes",
                "proposed_effect": {"synced": 1},
                "policy_items": [
                    {
                        "data_ref": "result",
                        "attrs": {
                            "principal": "alice@corp.com",
                            "counterparty_domain": "corp.com",
                        },
                    }
                ],
            }

        raise AssertionError(f"unexpected sidecar URL: {url}")

    monkeypatch.setattr("python_template.core.sidecar._request_json", fake_request_json)

    settings = Settings(
        sidecar_plugins_json=json.dumps(
            [
                {
                    "id": "notes_sidecar",
                    "base_url": "http://127.0.0.1:8900",
                    "shared_secret": "local-secret",
                }
            ]
        )
    )
    client = make_client(settings=settings, headers=DEFAULT_HEADERS)

    plugins = client.get("/v1/plugins")
    assert plugins.status_code == 200
    assert any(plugin["id"] == "notes_sidecar" for plugin in plugins.json())

    notes = client.get("/v1/notes_sidecar/notes")
    assert notes.status_code == 200
    assert notes.json()["items"][0]["id"] == "note_1"

    sync = client.post("/v1/notes_sidecar:sync/execute", json={"args": {}})
    assert sync.status_code == 200
    assert sync.json()["result"]["synced"] == 1

    assert any(url.endswith("/plugin/manifest") for _, url, _ in calls)
    assert any(url.endswith("/plugin/resources/notes/list") for _, url, _ in calls)
    assert any(url.endswith("/plugin/actions/sync/execute") for _, url, _ in calls)
