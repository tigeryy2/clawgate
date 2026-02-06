from __future__ import annotations

import json
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
_DEFAULT_APPROVAL_BY_RISK = {
    "read_only": False,
    "routine": False,
    "transactional": True,
    "dangerous": True,
}


class PolicyEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.blocked_domains = {"blocked.example"}
        self._approval_defaults = self._load_approval_defaults(
            settings.action_approval_defaults_json
        )
        (
            self._global_allow_patterns,
            self._global_require_patterns,
            self._plugin_allow_patterns,
            self._plugin_require_patterns,
        ) = self._load_approval_overrides(settings.action_approval_overrides_json)

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
        capability_id = action.capability_id
        plugin_id = self._plugin_id_for(capability_id)

        plugin_require = self._plugin_require_patterns.get(plugin_id, ())
        plugin_allow = self._plugin_allow_patterns.get(plugin_id, ())
        if self._matches_any(capability_id, plugin_require):
            return True
        if self._matches_any(capability_id, plugin_allow):
            return False

        if self._matches_any(capability_id, self._global_require_patterns):
            return True
        if self._matches_any(capability_id, self._global_allow_patterns):
            return False

        return self._approval_defaults.get(action.risk_tier.value, True)

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

    @staticmethod
    def _plugin_id_for(capability_id: str) -> str:
        if "." not in capability_id:
            return capability_id
        return capability_id.split(".", maxsplit=1)[0]

    @staticmethod
    def _matches_any(capability_id: str, patterns: tuple[str, ...]) -> bool:
        return any(
            PolicyEngine._matches_pattern(capability_id, pattern)
            for pattern in patterns
        )

    @staticmethod
    def _matches_pattern(capability_id: str, pattern: str) -> bool:
        if pattern.endswith("*"):
            return capability_id.startswith(pattern[:-1])
        return capability_id == pattern

    def _load_approval_defaults(self, raw_json: str | None) -> dict[str, bool]:
        defaults = dict(_DEFAULT_APPROVAL_BY_RISK)
        if not raw_json:
            return defaults
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "ACTION_APPROVAL_DEFAULTS_JSON must be valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError("ACTION_APPROVAL_DEFAULTS_JSON must be a JSON object")

        for risk_tier, requires_approval in payload.items():
            if risk_tier not in defaults:
                raise ValueError(
                    f"ACTION_APPROVAL_DEFAULTS_JSON has unknown risk tier '{risk_tier}'"
                )
            if not isinstance(requires_approval, bool):
                raise ValueError(
                    f"ACTION_APPROVAL_DEFAULTS_JSON value for '{risk_tier}' must be boolean"
                )
            defaults[risk_tier] = requires_approval
        return defaults

    def _load_approval_overrides(
        self,
        raw_json: str | None,
    ) -> tuple[
        tuple[str, ...],
        tuple[str, ...],
        dict[str, tuple[str, ...]],
        dict[str, tuple[str, ...]],
    ]:
        if not raw_json:
            return tuple(), tuple(), {}, {}
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "ACTION_APPROVAL_OVERRIDES_JSON must be valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError("ACTION_APPROVAL_OVERRIDES_JSON must be a JSON object")

        global_config = payload.get("global", {})
        global_allow, global_require = self._parse_override_block(
            block=global_config,
            source="ACTION_APPROVAL_OVERRIDES_JSON.global",
            plugin_id=None,
        )

        plugin_allow: dict[str, tuple[str, ...]] = {}
        plugin_require: dict[str, tuple[str, ...]] = {}
        plugins_config = payload.get("plugins", {})
        if plugins_config is not None and not isinstance(plugins_config, dict):
            raise ValueError(
                "ACTION_APPROVAL_OVERRIDES_JSON.plugins must be an object of plugin ids"
            )
        for plugin_id, block in plugins_config.items():
            if not isinstance(plugin_id, str) or not plugin_id.strip():
                raise ValueError(
                    "ACTION_APPROVAL_OVERRIDES_JSON.plugins keys must be non-empty plugin ids"
                )
            allow_patterns, require_patterns = self._parse_override_block(
                block=block,
                source=f"ACTION_APPROVAL_OVERRIDES_JSON.plugins.{plugin_id}",
                plugin_id=plugin_id.strip(),
            )
            plugin_allow[plugin_id.strip()] = allow_patterns
            plugin_require[plugin_id.strip()] = require_patterns

        return global_allow, global_require, plugin_allow, plugin_require

    def _parse_override_block(
        self,
        block: Any,
        source: str,
        plugin_id: str | None,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if block is None:
            return tuple(), tuple()
        if not isinstance(block, dict):
            raise ValueError(f"{source} must be an object")

        allow_patterns = self._normalize_patterns(
            raw_patterns=block.get("allow"),
            source=f"{source}.allow",
            plugin_id=plugin_id,
        )
        require_patterns = self._normalize_patterns(
            raw_patterns=block.get("require"),
            source=f"{source}.require",
            plugin_id=plugin_id,
        )
        return allow_patterns, require_patterns

    def _normalize_patterns(
        self,
        raw_patterns: Any,
        source: str,
        plugin_id: str | None,
    ) -> tuple[str, ...]:
        if raw_patterns is None:
            return tuple()
        if not isinstance(raw_patterns, list):
            raise ValueError(f"{source} must be a list")

        normalized: list[str] = []
        for raw_pattern in raw_patterns:
            if not isinstance(raw_pattern, str) or not raw_pattern.strip():
                raise ValueError(f"{source} entries must be non-empty strings")
            pattern = raw_pattern.strip()
            if pattern.count("*") > 1 or ("*" in pattern and not pattern.endswith("*")):
                raise ValueError(
                    f"{source} pattern '{pattern}' only supports trailing *"
                )
            if plugin_id:
                pattern = self._normalize_plugin_pattern(
                    plugin_id=plugin_id,
                    pattern=pattern,
                )
            normalized.append(pattern)
        return tuple(normalized)

    @staticmethod
    def _normalize_plugin_pattern(plugin_id: str, pattern: str) -> str:
        if pattern == "*":
            return f"{plugin_id}.*"
        if pattern.startswith(f"{plugin_id}."):
            return pattern
        return f"{plugin_id}.{pattern.lstrip('.')}"

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
