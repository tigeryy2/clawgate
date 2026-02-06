from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from python_template.core import (
    ActionContext,
    ApprovalStore,
    IdempotencyStore,
    PluginRegistry,
    PolicyEngine,
    load_settings,
)
from python_template.core.config import Settings
from python_template.core.exceptions import APIError, PolicyBlockedError
from python_template.core.manifests import PluginActionManifest
from python_template.core.models import (
    ActionNeedsApprovalResponse,
    ActionRequest,
    ActionSuccessResponse,
    CollectionResponse,
    ErrorResponse,
    ReadQuery,
)
from python_template.plugins import GmailDemoPlugin


@dataclass
class Runtime:
    settings: Settings
    registry: PluginRegistry
    policy: PolicyEngine
    approvals: ApprovalStore
    idempotency: IdempotencyStore


def create_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or load_settings()
    registry = PluginRegistry(plugins=[GmailDemoPlugin()])
    return Runtime(
        settings=settings,
        registry=registry,
        policy=PolicyEngine(settings=settings),
        approvals=ApprovalStore(),
        idempotency=IdempotencyStore(),
    )


def create_app(runtime: Runtime | None = None) -> FastAPI:
    runtime = runtime or create_runtime()
    app = FastAPI(title="Clawgate API", version="0.1.0")
    app.state.runtime = runtime

    @app.exception_handler(APIError)
    def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error={
                    "code": exc.payload.code,
                    "message": exc.payload.message,
                }
            ).model_dump(),
        )

    def register_contract_routes(prefix: str) -> None:
        @app.get(
            f"{prefix}/plugins",
            response_model=list[dict[str, Any]],
        )
        def list_plugins() -> list[dict[str, Any]]:
            return [plugin.model_dump() for plugin in runtime.registry.list_plugins()]

        @app.get(
            f"{prefix}/plugins/{{plugin_id}}",
            response_model=dict[str, Any],
            responses={404: {"model": ErrorResponse}},
        )
        def get_plugin(plugin_id: str) -> dict[str, Any]:
            return runtime.registry.get_manifest(plugin_id).model_dump()

        @app.get(
            f"{prefix}/plugins/{{plugin_id}}/capabilities",
            response_model=list[dict[str, str]],
            responses={404: {"model": ErrorResponse}},
        )
        def list_capabilities(plugin_id: str) -> list[dict[str, str]]:
            return runtime.registry.list_capabilities(plugin_id)

        @app.post(
            f"{prefix}/approvals/{{ticket_id}}:approve",
            response_model=dict[str, Any],
            responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        )
        def approve_ticket(ticket_id: str) -> dict[str, Any]:
            ticket = runtime.approvals.set_status(
                ticket_id=ticket_id, status="approved"
            )
            return ticket.model_dump()

        @app.post(
            f"{prefix}/approvals/{{ticket_id}}:deny",
            response_model=dict[str, Any],
            responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        )
        def deny_ticket(ticket_id: str) -> dict[str, Any]:
            ticket = runtime.approvals.set_status(ticket_id=ticket_id, status="denied")
            return ticket.model_dump()

        @app.get(
            f"{prefix}/approvals/{{ticket_id}}",
            response_model=dict[str, Any],
            responses={404: {"model": ErrorResponse}},
        )
        def get_ticket(ticket_id: str) -> dict[str, Any]:
            return runtime.approvals.get(ticket_id).model_dump()

        @app.post(
            f"{prefix}/{{plugin_id}}:{{action}}/propose",
            response_model=ActionSuccessResponse,
            responses={
                400: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
                404: {"model": ErrorResponse},
            },
        )
        def propose_global_action(
            plugin_id: str,
            action: str,
            payload: ActionRequest,
        ) -> ActionSuccessResponse:
            return _handle_action(
                runtime=runtime,
                plugin_id=plugin_id,
                resource=None,
                resource_id=None,
                action_name=action,
                phase="propose",
                payload=payload,
            )

        @app.post(
            f"{prefix}/{{plugin_id}}:{{action}}/execute",
            response_model=ActionSuccessResponse,
            responses={
                202: {"model": ActionNeedsApprovalResponse},
                400: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
                404: {"model": ErrorResponse},
            },
        )
        def execute_global_action(
            plugin_id: str,
            action: str,
            payload: ActionRequest,
        ) -> JSONResponse | ActionSuccessResponse:
            return _handle_action(
                runtime=runtime,
                plugin_id=plugin_id,
                resource=None,
                resource_id=None,
                action_name=action,
                phase="execute",
                payload=payload,
            )

        @app.post(
            f"{prefix}/{{plugin_id}}/{{resource}}/{{resource_id}}:{{action}}/propose",
            response_model=ActionSuccessResponse,
            responses={
                400: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
                404: {"model": ErrorResponse},
            },
        )
        def propose_resource_action(
            plugin_id: str,
            resource: str,
            resource_id: str,
            action: str,
            payload: ActionRequest,
        ) -> ActionSuccessResponse:
            return _handle_action(
                runtime=runtime,
                plugin_id=plugin_id,
                resource=resource,
                resource_id=resource_id,
                action_name=action,
                phase="propose",
                payload=payload,
            )

        @app.post(
            f"{prefix}/{{plugin_id}}/{{resource}}/{{resource_id}}:{{action}}/execute",
            response_model=ActionSuccessResponse,
            responses={
                202: {"model": ActionNeedsApprovalResponse},
                400: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
                404: {"model": ErrorResponse},
            },
        )
        def execute_resource_action(
            plugin_id: str,
            resource: str,
            resource_id: str,
            action: str,
            payload: ActionRequest,
        ) -> JSONResponse | ActionSuccessResponse:
            return _handle_action(
                runtime=runtime,
                plugin_id=plugin_id,
                resource=resource,
                resource_id=resource_id,
                action_name=action,
                phase="execute",
                payload=payload,
            )

        @app.get(
            f"{prefix}/{{plugin_id}}/{{resource}}",
            response_model=CollectionResponse,
            responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        )
        def list_resource(
            request: Request,
            plugin_id: str,
            resource: str,
            limit: int = Query(default=20, ge=1),
            cursor: str | None = Query(default=None),
            sort: str | None = Query(default=None),
            q: str | None = Query(default=None),
        ) -> CollectionResponse:
            extra_filters = {
                key: value
                for key, value in request.query_params.items()
                if key not in {"limit", "cursor", "sort", "q"}
            }
            query = ReadQuery(
                limit=runtime.policy.normalize_limit(limit),
                cursor=cursor,
                sort=sort,
                q=q,
                filters=extra_filters,
            )
            plugin = runtime.registry.get_plugin(plugin_id)
            result = plugin.list_resource(resource=resource, query=query)
            filtered = runtime.policy.apply_collection_policy(result)
            return CollectionResponse(**filtered)

        @app.get(
            f"{prefix}/{{plugin_id}}/{{resource}}/{{resource_id}}",
            response_model=dict[str, Any],
            responses={
                400: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
                404: {"model": ErrorResponse},
            },
        )
        def get_resource(
            plugin_id: str,
            resource: str,
            resource_id: str,
        ) -> dict[str, Any]:
            query = ReadQuery(
                limit=runtime.settings.default_limit,
            )
            plugin = runtime.registry.get_plugin(plugin_id)
            result = plugin.get_resource(
                resource=resource,
                resource_id=resource_id,
                view=None,
                query=query,
            )
            return runtime.policy.apply_single_item_policy(result)

        @app.get(
            f"{prefix}/{{plugin_id}}/{{resource}}/{{resource_id}}/{{view}}",
            response_model=dict[str, Any],
            responses={
                400: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
                404: {"model": ErrorResponse},
            },
        )
        def get_resource_view(
            plugin_id: str,
            resource: str,
            resource_id: str,
            view: str,
            max_chars: int | None = Query(default=None, ge=1),
        ) -> dict[str, Any]:
            runtime.policy.enforce_view_policy(view=view)
            if view not in {"headers", "body", "raw"}:
                raise APIError(404, "NOT_FOUND", f"view '{view}' not found")
            query = ReadQuery(
                limit=runtime.settings.default_limit,
                max_chars=runtime.policy.normalize_max_chars(max_chars),
            )
            plugin = runtime.registry.get_plugin(plugin_id)
            result = plugin.get_resource(
                resource=resource,
                resource_id=resource_id,
                view=view,
                query=query,
            )
            payload = runtime.policy.apply_single_item_policy(result)
            if view == "body":
                payload = runtime.policy.sanitize_body_payload(
                    payload,
                    max_chars=query.max_chars
                    or runtime.settings.default_body_max_chars,
                )
            return payload

    register_contract_routes(prefix=runtime.settings.api_prefix)
    if runtime.settings.enable_api_alias:
        register_contract_routes(prefix="/api")

    return app


def _handle_action(
    runtime: Runtime,
    plugin_id: str,
    resource: str | None,
    resource_id: str | None,
    action_name: str,
    phase: str,
    payload: ActionRequest,
) -> JSONResponse | ActionSuccessResponse:
    action = runtime.registry.resolve_action(
        plugin_id=plugin_id,
        action_name=action_name,
        resource=resource,
    )
    if phase == "propose" and not action.supports_propose:
        raise APIError(
            400, "ACTION_NOT_PROPOSABLE", "this action does not support propose"
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
    args: dict[str, Any],
):
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


def _enforce_action_policy(runtime: Runtime, result: Any) -> None:
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


app = create_app()
