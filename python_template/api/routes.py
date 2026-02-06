from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from python_template.api.actions import handle_action
from python_template.api.runtime import Runtime
from python_template.core.exceptions import APIError
from python_template.core.models import (
    ActionNeedsApprovalResponse,
    ActionRequest,
    ActionSuccessResponse,
    CollectionResponse,
    ErrorResponse,
    ReadQuery,
)


def build_contract_router(runtime: Runtime, prefix: str) -> APIRouter:
    router = APIRouter(prefix=prefix)

    @router.get(
        "/plugins",
        response_model=list[dict[str, Any]],
        responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    )
    def list_plugins(request: Request) -> list[dict[str, Any]]:
        _authorize_static(runtime, request, capability_id="system.plugins.read")
        return [plugin.model_dump() for plugin in runtime.registry.list_plugins()]

    @router.get(
        "/plugins/{plugin_id}",
        response_model=dict[str, Any],
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def get_plugin(request: Request, plugin_id: str) -> dict[str, Any]:
        _authorize_static(runtime, request, capability_id="system.plugins.read")
        return runtime.registry.get_manifest(plugin_id).model_dump()

    @router.get(
        "/plugins/{plugin_id}/capabilities",
        response_model=list[dict[str, str]],
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def list_capabilities(request: Request, plugin_id: str) -> list[dict[str, str]]:
        _authorize_static(runtime, request, capability_id="system.plugins.read")
        return runtime.registry.list_capabilities(plugin_id)

    @router.post(
        "/approvals/{ticket_id}:approve",
        response_model=dict[str, Any],
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def approve_ticket(request: Request, ticket_id: str) -> dict[str, Any]:
        _authorize_static(runtime, request, capability_id="system.approvals.manage")
        ticket = runtime.approvals.set_status(ticket_id=ticket_id, status="approved")
        return ticket.model_dump()

    @router.post(
        "/approvals/{ticket_id}:deny",
        response_model=dict[str, Any],
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def deny_ticket(request: Request, ticket_id: str) -> dict[str, Any]:
        _authorize_static(runtime, request, capability_id="system.approvals.manage")
        ticket = runtime.approvals.set_status(ticket_id=ticket_id, status="denied")
        return ticket.model_dump()

    @router.get(
        "/approvals/{ticket_id}",
        response_model=dict[str, Any],
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def get_ticket(request: Request, ticket_id: str) -> dict[str, Any]:
        _authorize_static(runtime, request, capability_id="system.approvals.manage")
        return runtime.approvals.get(ticket_id).model_dump()

    @router.post(
        "/{plugin_id}:{action}/propose",
        response_model=ActionSuccessResponse,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def propose_global_action(
        request: Request,
        plugin_id: str,
        action: str,
        payload: ActionRequest,
    ) -> ActionSuccessResponse | JSONResponse:
        return handle_action(
            runtime=runtime,
            request=request,
            plugin_id=plugin_id,
            resource=None,
            resource_id=None,
            action_name=action,
            phase="propose",
            payload=payload,
        )

    @router.post(
        "/{plugin_id}:{action}/execute",
        response_model=ActionSuccessResponse,
        responses={
            202: {"model": ActionNeedsApprovalResponse},
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def execute_global_action(
        request: Request,
        plugin_id: str,
        action: str,
        payload: ActionRequest,
    ) -> JSONResponse | ActionSuccessResponse:
        return handle_action(
            runtime=runtime,
            request=request,
            plugin_id=plugin_id,
            resource=None,
            resource_id=None,
            action_name=action,
            phase="execute",
            payload=payload,
        )

    @router.post(
        "/{plugin_id}/{resource}/{resource_id}:{action}/propose",
        response_model=ActionSuccessResponse,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def propose_resource_action(
        request: Request,
        plugin_id: str,
        resource: str,
        resource_id: str,
        action: str,
        payload: ActionRequest,
    ) -> ActionSuccessResponse | JSONResponse:
        return handle_action(
            runtime=runtime,
            request=request,
            plugin_id=plugin_id,
            resource=resource,
            resource_id=resource_id,
            action_name=action,
            phase="propose",
            payload=payload,
        )

    @router.post(
        "/{plugin_id}/{resource}/{resource_id}:{action}/execute",
        response_model=ActionSuccessResponse,
        responses={
            202: {"model": ActionNeedsApprovalResponse},
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def execute_resource_action(
        request: Request,
        plugin_id: str,
        resource: str,
        resource_id: str,
        action: str,
        payload: ActionRequest,
    ) -> ActionSuccessResponse | JSONResponse:
        return handle_action(
            runtime=runtime,
            request=request,
            plugin_id=plugin_id,
            resource=resource,
            resource_id=resource_id,
            action_name=action,
            phase="execute",
            payload=payload,
        )

    @router.get(
        "/{plugin_id}/{resource}",
        response_model=CollectionResponse,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
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
        principal = runtime.auth.authenticate(request)
        resource_manifest = runtime.registry.resolve_resource(plugin_id, resource)
        runtime.auth.require_capability(principal, resource_manifest.capability_id)

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

    @router.get(
        "/{plugin_id}/{resource}/{resource_id}",
        response_model=dict[str, Any],
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def get_resource(
        request: Request,
        plugin_id: str,
        resource: str,
        resource_id: str,
    ) -> dict[str, Any]:
        principal = runtime.auth.authenticate(request)
        resource_manifest = runtime.registry.resolve_resource(plugin_id, resource)
        runtime.auth.require_capability(principal, resource_manifest.capability_id)

        query = ReadQuery(limit=runtime.settings.default_limit)
        plugin = runtime.registry.get_plugin(plugin_id)
        result = plugin.get_resource(
            resource=resource,
            resource_id=resource_id,
            view=None,
            query=query,
        )
        return runtime.policy.apply_single_item_policy(result)

    @router.get(
        "/{plugin_id}/{resource}/{resource_id}/{view}",
        response_model=dict[str, Any],
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
        },
    )
    def get_resource_view(
        request: Request,
        plugin_id: str,
        resource: str,
        resource_id: str,
        view: str,
        max_chars: int | None = Query(default=None, ge=1),
    ) -> dict[str, Any]:
        principal = runtime.auth.authenticate(request)
        resource_manifest = runtime.registry.resolve_resource(plugin_id, resource)
        runtime.auth.require_capability(principal, resource_manifest.capability_id)

        runtime.policy.enforce_view_policy(view=view)
        if view not in {"headers", "body", "raw"}:
            raise APIError(404, "NOT_FOUND", f"view '{view}' not found")
        if view not in resource_manifest.allowed_views:
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
                max_chars=query.max_chars or runtime.settings.default_body_max_chars,
            )
        return payload

    return router


def _authorize_static(runtime: Runtime, request: Request, capability_id: str) -> None:
    principal = runtime.auth.authenticate(request)
    runtime.auth.require_capability(principal, capability_id)
