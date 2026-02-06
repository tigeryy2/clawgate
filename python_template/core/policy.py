from __future__ import annotations

import re
from typing import Any

from python_template.core.config import Settings
from python_template.core.exceptions import PolicyBlockedError, ValidationError
from python_template.core.manifests import PluginActionManifest
from python_template.core.models import InternalReadResult

_URL_PATTERN = re.compile(r"https?://\S+")
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@([^@\s]+)$")


class PolicyEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.blocked_domains = {"blocked.example"}

    def normalize_limit(self, limit: int) -> int:
        if limit < 1:
            raise ValidationError("limit must be >= 1")
        return min(limit, self.settings.max_limit)

    def normalize_max_chars(self, max_chars: int | None) -> int:
        if max_chars is None:
            return self.settings.default_body_max_chars
        if max_chars < 1:
            raise ValidationError("max_chars must be >= 1")
        return min(max_chars, self.settings.default_body_max_chars)

    def validate_action_request(
        self,
        action: PluginActionManifest,
        phase: str,
        idempotency_key: str | None,
        args: dict[str, Any],
    ) -> None:
        if phase == "execute" and action.requires_idempotency and not idempotency_key:
            raise ValidationError(
                "idempotency_key is required for this action",
                code="IDEMPOTENCY_KEY_REQUIRED",
            )
        domains = self._extract_domains_from_args(args)
        if any(domain in self.blocked_domains for domain in domains):
            raise PolicyBlockedError()

    def requires_approval(self, action: PluginActionManifest, phase: str) -> bool:
        if phase != "execute":
            return False
        return action.risk_tier.value != "read_only"

    def enforce_view_policy(self, view: str | None) -> None:
        if view == "raw" and not self.settings.raw_read_enabled:
            raise PolicyBlockedError(
                "blocked by policy: raw content reads are disabled"
            )

    def apply_collection_policy(self, result: InternalReadResult) -> dict[str, Any]:
        data = result.data
        if not isinstance(data, dict):
            return {"items": [], "next_cursor": None}
        items = data.get("items")
        if not isinstance(items, list):
            return {"items": [], "next_cursor": data.get("next_cursor")}

        keep = [True] * len(items)
        for policy_item in result.policy_items:
            idx = self._parse_item_index(policy_item.data_ref)
            if idx is None or idx >= len(items):
                continue
            domain = policy_item.attrs.get("counterparty_domain")
            if isinstance(domain, str) and domain in self.blocked_domains:
                keep[idx] = False

        filtered_items = [item for idx, item in enumerate(items) if keep[idx]]
        return {
            "items": filtered_items,
            "next_cursor": data.get("next_cursor"),
        }

    def apply_single_item_policy(self, result: InternalReadResult) -> dict[str, Any]:
        for policy_item in result.policy_items:
            domain = policy_item.attrs.get("counterparty_domain")
            if isinstance(domain, str) and domain in self.blocked_domains:
                raise PolicyBlockedError()
        if isinstance(result.data, dict):
            return result.data
        return {"value": result.data}

    def sanitize_body_payload(
        self, payload: dict[str, Any], max_chars: int
    ) -> dict[str, Any]:
        sanitized = dict(payload)
        body = sanitized.get("body")
        if isinstance(body, str):
            sanitized["body"] = self._sanitize_text(body, max_chars=max_chars)
        snippet = sanitized.get("snippet")
        if isinstance(snippet, str):
            sanitized["snippet"] = self._sanitize_text(snippet, max_chars=max_chars)
        return sanitized

    @staticmethod
    def _parse_item_index(data_ref: str) -> int | None:
        if data_ref.startswith("items[") and data_ref.endswith("]"):
            maybe_idx = data_ref[6:-1]
            if maybe_idx.isdigit():
                return int(maybe_idx)
        return None

    def _extract_domains_from_args(self, args: dict[str, Any]) -> set[str]:
        domains: set[str] = set()
        for key in ("to", "cc", "bcc", "principal", "counterparty"):
            raw = args.get(key)
            if raw is None:
                continue
            values = raw if isinstance(raw, list) else [raw]
            for value in values:
                if not isinstance(value, str):
                    continue
                domain = self._domain_for(value)
                if domain:
                    domains.add(domain)
        return domains

    @staticmethod
    def _domain_for(value: str) -> str | None:
        match = _EMAIL_PATTERN.match(value.strip())
        if not match:
            return None
        return match.group(1).lower()

    def _sanitize_text(self, value: str, max_chars: int) -> str:
        no_links = _URL_PATTERN.sub("", value)
        no_html = _HTML_TAG_PATTERN.sub(" ", no_links)
        compact = _WHITESPACE_PATTERN.sub(" ", no_html).strip()
        return compact[:max_chars]
