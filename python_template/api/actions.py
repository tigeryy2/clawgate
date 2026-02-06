from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from python_template.api.runtime import Runtime
from python_template.core import ActionContext
from python_template.core.exceptions import APIError, PolicyBlockedError
from python_template.core.manifests import PluginActionManifest
from python_template.core.models import (
    ActionNeedsApprovalResponse,
    ActionRequest,
    ActionSuccessResponse,
    InternalActionResult,
)


def handle_action(
    runtime: Runtime,
    request: Request,
    plugin_id: str,
    resource: str | None,
    resource_id: str | None,
    action_name: str,
    phase: str,
    payload: ActionRequest,
) -> JSONResponse | ActionSuccessResponse:
    principal = runtime.auth.authenticate(request)
    action = runtime.registry.resolve_action(
        plugin_id=plugin_id,
        action_name=action_name,
        resource=resource,
    )
    runtime.auth.require_capability(principal, action.capability_id)

    if phase == "propose" and not action.supports_propose:
        raise APIError(
            400,
            "ACTION_NOT_PROPOSABLE",
            "this action does not support propose",
        )

    runtime.policy.validate_action_request(
        action=action,
        phase=phase,
        idempotency_key=payload.idempotency_key,
        args=payload.args,
    )

    request_hash = _hash_payload(
        {
            "plugin_id": plugin_id,
            "resource": resource,
            "resource_id": resource_id,
            "action": action_name,
            "phase": phase,
            "args": payload.args,
        }
    )
    idempotency_scope = f"{plugin_id}:{resource or '_'}:{action_name}"

    if phase == "execute" and payload.idempotency_key and action.mutating:
        existing = runtime.idempotency.fetch_or_validate(
            scope=idempotency_scope,
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
        )
        if existing is not None:
            return JSONResponse(
                status_code=existing.status_code, content=existing.payload
            )

    plugin = runtime.registry.get_plugin(plugin_id)
    context = ActionContext(
        plugin_id=plugin_id,
        phase=phase,
        action=action,
        resource=resource,
        resource_id=resource_id,
    )

    if runtime.policy.requires_approval(action=action, phase=phase):
        fingerprint = _approval_fingerprint(
            capability_id=action.capability_id,
            resource_id=resource_id,
            args=payload.args,
        )
        approved = runtime.approvals.find_for_fingerprint(
            capability_id=action.capability_id,
            fingerprint=fingerprint,
            statuses={"approved"},
        )
        if approved is None:
            pending = runtime.approvals.find_for_fingerprint(
                capability_id=action.capability_id,
                fingerprint=fingerprint,
                statuses={"pending"},
            )
            preview_result = _run_preview(
                plugin=plugin,
                action=action,
                context=context,
                args=payload.args,
            )
            summary = preview_result.summary or f"{action.name} requires approval"
            proposed_effect = preview_result.proposed_effect or preview_result.result
            ticket = pending or runtime.approvals.create_ticket(
                summary=summary,
                proposed_effect=proposed_effect,
                capability_id=action.capability_id,
                fingerprint=fingerprint,
            )
            approval_response = ActionNeedsApprovalResponse(
                approval_ticket_id=ticket.id,
                summary=ticket.summary,
                proposed_effect=ticket.proposed_effect,
            ).model_dump()
            return JSONResponse(status_code=202, content=approval_response)

    result = plugin.run_action(context=context, args=payload.args)
    _enforce_action_policy(runtime=runtime, result=result)

    if result.status.value == "blocked":
        raise PolicyBlockedError(result.summary or "blocked by policy")

    response = ActionSuccessResponse(
        result=result.result,
        summary=result.summary,
    )

    if phase == "execute" and payload.idempotency_key and action.mutating:
        runtime.idempotency.save(
            scope=idempotency_scope,
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
            status_code=200,
            payload=response.model_dump(),
        )

    return response


def _run_preview(
    plugin: Any,
    action: PluginActionManifest,
    context: ActionContext,
    args: dict,
) -> InternalActionResult:
    if not action.supports_propose:
        return plugin.run_action(context=context, args=args)
    preview_context = ActionContext(
        plugin_id=context.plugin_id,
        phase="propose",
        action=context.action,
        resource=context.resource,
        resource_id=context.resource_id,
    )
    return plugin.run_action(context=preview_context, args=args)


def _enforce_action_policy(runtime: Runtime, result: InternalActionResult) -> None:
    for item in result.policy_items:
        domain = item.attrs.get("counterparty_domain")
        if isinstance(domain, str) and domain in runtime.policy.blocked_domains:
            raise PolicyBlockedError()


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _approval_fingerprint(
    capability_id: str,
    resource_id: str | None,
    args: dict[str, Any],
) -> str:
    return _hash_payload(
        {
            "capability_id": capability_id,
            "resource_id": resource_id,
            "args": args,
        }
    )
