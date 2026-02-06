from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RiskTier(StrEnum):
    read_only = "read_only"
    routine = "routine"
    transactional = "transactional"
    dangerous = "dangerous"


class RuntimeMode(StrEnum):
    in_process = "in_process"
    sidecar = "sidecar"


class ActionPhase(StrEnum):
    propose = "propose"
    execute = "execute"


class ActionStatus(StrEnum):
    success = "success"
    blocked = "blocked"


class ReadQuery(BaseModel):
    limit: int
    cursor: str | None = None
    sort: str | None = None
    q: str | None = None
    filters: dict[str, str] = Field(default_factory=dict)
    max_chars: int | None = None


class CollectionResponse(BaseModel):
    items: list[Any]
    next_cursor: str | None = None


class ActionRequest(BaseModel):
    idempotency_key: str | None = None
    reason: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)


class ActionSuccessResponse(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None


class ActionNeedsApprovalResponse(BaseModel):
    approval_ticket_id: str
    summary: str
    proposed_effect: dict[str, Any] = Field(default_factory=dict)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PolicyItem(BaseModel):
    data_ref: str
    attrs: dict[str, Any] = Field(default_factory=dict)


class InternalReadResult(BaseModel):
    data: Any
    policy_items: list[PolicyItem] = Field(default_factory=list)


class InternalActionResult(BaseModel):
    status: ActionStatus = ActionStatus.success
    result: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    proposed_effect: dict[str, Any] = Field(default_factory=dict)
    policy_items: list[PolicyItem] = Field(default_factory=list)


class PluginSummary(BaseModel):
    id: str
    name: str
    version: str
    runtime_mode: RuntimeMode


class ApprovalTicket(BaseModel):
    id: str
    status: str
    summary: str
    proposed_effect: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str
    capability_id: str
