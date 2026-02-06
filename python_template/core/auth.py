from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import Request

from python_template.core.config import Settings
from python_template.core.exceptions import APIError, UnauthorizedError


@dataclass(frozen=True)
class AgentPrincipal:
    agent_id: str
    tailscale_identity: str
    capabilities: tuple[str, ...]

    def can(self, capability_id: str) -> bool:
        if "*" in self.capabilities:
            return True
        if capability_id in self.capabilities:
            return True
        for capability in self.capabilities:
            if capability.endswith(".*") and capability_id.startswith(capability[:-1]):
                return True
        return False


@dataclass(frozen=True)
class TokenRecord:
    token: str
    agent_id: str
    tailscale_identity: str
    capabilities: tuple[str, ...]


class AuthService:
    def __init__(self, settings: Settings):
        self._require_auth = settings.require_auth
        self._tokens = self._parse_tokens(settings.agent_tokens_json)

    def authenticate(self, request: Request) -> AgentPrincipal:
        if not self._require_auth:
            return AgentPrincipal(
                agent_id="anonymous",
                tailscale_identity="*",
                capabilities=("*",),
            )

        token = self._extract_bearer_token(request)
        tailscale_identity = request.headers.get("X-Tailscale-Identity")
        if not tailscale_identity:
            raise UnauthorizedError("missing X-Tailscale-Identity header")

        record = self._tokens.get(token)
        if record is None:
            raise UnauthorizedError("invalid bearer token")

        if record.tailscale_identity not in {"*", tailscale_identity}:
            raise UnauthorizedError("tailscale identity mismatch")

        return AgentPrincipal(
            agent_id=record.agent_id,
            tailscale_identity=tailscale_identity,
            capabilities=record.capabilities,
        )

    def require_capability(self, principal: AgentPrincipal, capability_id: str) -> None:
        if principal.can(capability_id):
            return
        raise APIError(
            status_code=403,
            code="CAPABILITY_DENIED",
            message=f"agent '{principal.agent_id}' is not allowed to call '{capability_id}'",
        )

    @staticmethod
    def _extract_bearer_token(request: Request) -> str:
        authorization = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            raise UnauthorizedError("missing bearer token")
        token = authorization[len(prefix) :].strip()
        if not token:
            raise UnauthorizedError("missing bearer token")
        return token

    def _parse_tokens(self, raw_json: str | None) -> dict[str, TokenRecord]:
        if not raw_json:
            return {
                "dev-local-token": TokenRecord(
                    token="dev-local-token",
                    agent_id="dev_local",
                    tailscale_identity="*",
                    capabilities=("*",),
                )
            }

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            msg = "AGENT_TOKENS_JSON must be valid JSON"
            raise ValueError(msg) from exc

        if not isinstance(payload, list):
            raise ValueError("AGENT_TOKENS_JSON must be a list of token records")

        records: dict[str, TokenRecord] = {}
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("each token record must be an object")
            token = str(item.get("token", "")).strip()
            agent_id = str(item.get("agent_id", "")).strip()
            tailscale_identity = str(item.get("tailscale_identity", "")).strip()
            raw_capabilities = item.get("capabilities", [])

            if (
                not token
                or not agent_id
                or not tailscale_identity
                or not isinstance(raw_capabilities, list)
            ):
                raise ValueError(
                    "token records require token, agent_id, tailscale_identity, capabilities[]"
                )

            capabilities = tuple(
                str(value).strip() for value in raw_capabilities if str(value).strip()
            )
            if not capabilities:
                raise ValueError("token records must include at least one capability")

            records[token] = TokenRecord(
                token=token,
                agent_id=agent_id,
                tailscale_identity=tailscale_identity,
                capabilities=capabilities,
            )

        if not records:
            raise ValueError("AGENT_TOKENS_JSON contains no valid token records")
        return records
