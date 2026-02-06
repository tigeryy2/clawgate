from __future__ import annotations

from fastapi.testclient import TestClient

from python_template.api.app import create_app, create_runtime
from python_template.core.config import Settings


def make_client(enable_api_alias: bool = False) -> TestClient:
    settings = Settings(enable_api_alias=enable_api_alias)
    runtime = create_runtime(settings=settings)
    app = create_app(runtime=runtime)
    return TestClient(app)


def test_discovery_endpoints_and_alias_default_off():
    client = make_client(enable_api_alias=False)

    plugins_response = client.get("/v1/plugins")
    assert plugins_response.status_code == 200
    assert plugins_response.json()[0]["id"] == "gmail"

    plugin_response = client.get("/v1/plugins/gmail")
    assert plugin_response.status_code == 200
    manifest = plugin_response.json()
    assert manifest["id"] == "gmail"
    assert manifest["runtime_mode"] == "in_process"

    capabilities_response = client.get("/v1/plugins/gmail/capabilities")
    assert capabilities_response.status_code == 200
    assert any(
        capability["capability_id"] == "gmail.message.reply"
        for capability in capabilities_response.json()
    )

    alias_response = client.get("/api/plugins")
    assert alias_response.status_code == 404


def test_route_to_capability_resolution_for_resource_action_execute():
    client = make_client()

    execute_response = client.post(
        "/v1/gmail/messages/msg_allowed:reply/execute",
        json={
            "idempotency_key": "idem-reply-1",
            "args": {"body": "Tuesday works"},
        },
    )

    assert execute_response.status_code == 202
    ticket_id = execute_response.json()["approval_ticket_id"]

    ticket_response = client.get(f"/v1/approvals/{ticket_id}")
    assert ticket_response.status_code == 200
    assert ticket_response.json()["capability_id"] == "gmail.message.reply"


def test_query_normalization_limit_cap():
    client = make_client()
    runtime = client.app.state.runtime
    plugin = runtime.registry.get_plugin("gmail")

    plugin._messages = {
        f"msg_{idx}": {
            "id": f"msg_{idx}",
            "thread_id": f"thr_{idx}",
            "from": f"user{idx}@corp.com",
            "subject": f"Subject {idx}",
            "labels": ["Inbox", "OpenClaw"],
            "snippet": "safe snippet",
            "body": "<p>safe body</p>",
            "raw": f"RAW_{idx}",
        }
        for idx in range(150)
    }

    response = client.get("/v1/gmail/messages", params={"limit": 1000})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 100
    assert payload["next_cursor"] == "100"


def test_approval_lifecycle_execute_requires_then_succeeds_after_approval():
    client = make_client()

    execute_response = client.post(
        "/v1/gmail/messages/msg_allowed:reply/execute",
        json={
            "idempotency_key": "idem-reply-2",
            "args": {"body": "On it"},
        },
    )
    assert execute_response.status_code == 202
    ticket_id = execute_response.json()["approval_ticket_id"]

    approve_response = client.post(f"/v1/approvals/{ticket_id}:approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    execute_after_approval = client.post(
        "/v1/gmail/messages/msg_allowed:reply/execute",
        json={
            "idempotency_key": "idem-reply-2",
            "args": {"body": "On it"},
        },
    )
    assert execute_after_approval.status_code == 200
    assert (
        execute_after_approval.json()["result"]["sent_message_id"] == "sent_reply_001"
    )


def test_policy_blocked_for_disallowed_domain_returns_403_with_stable_code():
    client = make_client()

    blocked_response = client.post(
        "/v1/gmail:send/execute",
        json={
            "idempotency_key": "idem-send-1",
            "args": {
                "to": ["mallory@blocked.example"],
                "body": "test",
            },
        },
    )

    assert blocked_response.status_code == 403
    assert blocked_response.json()["error"]["code"] == "POLICY_BLOCKED"


def test_idempotency_replays_success_response():
    client = make_client()

    first_execute = client.post(
        "/v1/gmail/messages/msg_allowed:archive/execute",
        json={
            "idempotency_key": "idem-archive-1",
            "args": {},
        },
    )
    assert first_execute.status_code == 202
    ticket_id = first_execute.json()["approval_ticket_id"]

    approve_response = client.post(f"/v1/approvals/{ticket_id}:approve")
    assert approve_response.status_code == 200

    second_execute = client.post(
        "/v1/gmail/messages/msg_allowed:archive/execute",
        json={
            "idempotency_key": "idem-archive-1",
            "args": {},
        },
    )
    assert second_execute.status_code == 200

    replay_execute = client.post(
        "/v1/gmail/messages/msg_allowed:archive/execute",
        json={
            "idempotency_key": "idem-archive-1",
            "args": {},
        },
    )
    assert replay_execute.status_code == 200
    assert replay_execute.json() == second_execute.json()


def test_tiered_reads_raw_gated_and_body_sanitized_truncated():
    client = make_client()

    body_response = client.get(
        "/v1/gmail/messages/msg_allowed/body",
        params={"max_chars": 20},
    )
    assert body_response.status_code == 200
    body = body_response.json()["body"]
    assert "<" not in body
    assert "http" not in body.lower()
    assert len(body) <= 20

    raw_response = client.get("/v1/gmail/messages/msg_allowed/raw")
    assert raw_response.status_code == 403
    assert raw_response.json()["error"]["code"] == "POLICY_BLOCKED"


def test_openapi_contains_v1_contract_paths_and_shared_schemas():
    client = make_client()

    response = client.get("/openapi.json")
    assert response.status_code == 200

    spec = response.json()
    paths = spec["paths"]
    assert "/v1/{plugin_id}:{action}/propose" in paths
    assert "/v1/{plugin_id}/{resource}/{resource_id}:{action}/execute" in paths
    assert "/v1/plugins/{plugin_id}/capabilities" in paths

    schemas = spec["components"]["schemas"]
    assert "ActionRequest" in schemas
    assert "ActionSuccessResponse" in schemas
