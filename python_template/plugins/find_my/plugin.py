from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from python_template.core.exceptions import NotFoundError, ValidationError
from python_template.core.manifests import (
    PluginActionManifest,
    PluginManifest,
    PluginResourceManifest,
)
from python_template.core.models import (
    ActionStatus,
    InternalActionResult,
    InternalReadResult,
    PolicyItem,
    ReadQuery,
    RiskTier,
    RuntimeMode,
)
from python_template.core.plugin_registry import ActionContext

try:
    from findmy import AppleAccount, FindMyAccessory
except ImportError:  # pragma: no cover - exercised with dependency installed
    AppleAccount = None
    FindMyAccessory = None


@dataclass(frozen=True)
class TrackedDevice:
    id: str
    label: str
    path: Path


class FindMyPlugin:
    manifest = PluginManifest(
        id="find_my",
        name="Find My",
        version="0.1.0",
        runtime_mode=RuntimeMode.in_process,
        resources=[
            PluginResourceManifest(
                name="friends",
                capability_id="find_my.friends.read",
                allowed_views=["headers", "body"],
            )
        ],
        required_secrets=["apple_account_session"],
        required_scopes=["findmy.location.read"],
        default_policy={"max_limit": 50},
        actions=[
            PluginActionManifest(
                name="refresh",
                capability_id="find_my.friends.refresh",
                resource_type="friend",
                risk_tier=RiskTier.read_only,
                route_pattern="/:refresh/{phase}",
                supports_propose=True,
                requires_idempotency=False,
                emits_attributes=["principal", "origin", "resource_type", "time"],
                resource=None,
                mutating=False,
            )
        ],
    )

    def __init__(self):
        self._account_json = Path(
            os.getenv("FINDMY_ACCOUNT_JSON", "findmy_account.json")
        )
        self._anisette_libs = Path(
            os.getenv("FINDMY_ANISETTE_LIBS_PATH", "ani_libs.bin")
        )
        self._tracked_devices = self._load_tracked_devices()
        self._account = None

    def list_resource(self, resource: str, query: ReadQuery) -> InternalReadResult:
        if resource != "friends":
            raise NotFoundError(f"resource '{resource}' not found")

        items = self._fetch_locations()
        if query.q:
            needle = query.q.lower()
            items = [item for item in items if needle in item["label"].lower()]

        offset = int(query.cursor or "0")
        page = items[offset : offset + query.limit]
        next_offset = offset + query.limit
        next_cursor = str(next_offset) if next_offset < len(items) else None

        return InternalReadResult(
            data={"items": page, "next_cursor": next_cursor},
            policy_items=[
                PolicyItem(
                    data_ref=f"items[{idx}]",
                    attrs={
                        "principal": item.get("label"),
                        "origin": "find_my",
                        "resource_type": "friend",
                        "time": item.get("timestamp"),
                    },
                )
                for idx, item in enumerate(page)
            ],
        )

    def get_resource(
        self,
        resource: str,
        resource_id: str,
        view: str | None,
        query: ReadQuery,
    ) -> InternalReadResult:
        _ = view
        _ = query
        if resource != "friends":
            raise NotFoundError(f"resource '{resource}' not found")

        items = self._fetch_locations()
        for item in items:
            if item["id"] == resource_id:
                return InternalReadResult(
                    data=item,
                    policy_items=[
                        PolicyItem(
                            data_ref="self",
                            attrs={
                                "principal": item.get("label"),
                                "origin": "find_my",
                                "resource_type": "friend",
                                "time": item.get("timestamp"),
                            },
                        )
                    ],
                )
        raise NotFoundError(f"friend '{resource_id}' not found")

    def run_action(self, context: ActionContext, args: dict) -> InternalActionResult:
        _ = args
        if context.action.name != "refresh":
            raise NotFoundError(f"action '{context.action.name}' not implemented")
        if context.phase == "propose":
            return InternalActionResult(
                status=ActionStatus.success,
                summary="Refresh Find My locations",
                result={"count": 0},
                proposed_effect={"count": 0},
                policy_items=[
                    PolicyItem(
                        data_ref="result",
                        attrs={
                            "origin": "find_my",
                            "resource_type": "friend",
                        },
                    )
                ],
            )
        locations = self._fetch_locations()
        result = {"count": len(locations), "items": locations}
        return InternalActionResult(
            status=ActionStatus.success,
            summary=f"Refreshed {len(locations)} Find My locations",
            result=result,
            proposed_effect={"count": len(locations)},
            policy_items=[
                PolicyItem(
                    data_ref="result",
                    attrs={
                        "origin": "find_my",
                        "resource_type": "friend",
                    },
                )
            ],
        )

    def _load_tracked_devices(self) -> list[TrackedDevice]:
        raw_paths = os.getenv("FINDMY_DEVICE_FILES", "")
        if not raw_paths.strip():
            return []
        devices = []
        for raw_path in raw_paths.split(","):
            path = Path(raw_path.strip())
            if not path:
                continue
            label = path.stem
            devices.append(TrackedDevice(id=label, label=label, path=path))
        return devices

    def _fetch_locations(self) -> list[dict[str, Any]]:
        if AppleAccount is None or FindMyAccessory is None:
            raise ValidationError("FindMy.py dependency is not installed")

        if not self._account_json.exists():
            raise ValidationError(
                f"Find My account session file not found: {self._account_json}",
                code="FINDMY_SESSION_MISSING",
            )

        if not self._tracked_devices:
            raise ValidationError(
                "no FINDMY_DEVICE_FILES configured",
                code="FINDMY_DEVICES_MISSING",
            )

        account = self._get_account()
        payload: list[dict[str, Any]] = []
        for device in self._tracked_devices:
            if not device.path.exists():
                continue
            accessory = FindMyAccessory.from_json(str(device.path))
            report = account.fetch_location(accessory)
            if report is None:
                continue
            payload.append(
                {
                    "id": device.id,
                    "label": device.label,
                    "latitude": getattr(report, "latitude", None),
                    "longitude": getattr(report, "longitude", None),
                    "accuracy": getattr(report, "horizontal_accuracy", None),
                    "timestamp": str(getattr(report, "timestamp", "")),
                }
            )

        return payload

    def _get_account(self):
        if self._account is not None:
            return self._account

        anisette_path = str(self._anisette_libs)
        if not self._anisette_libs.exists():
            anisette_path = "ani_libs.bin"
        self._account = AppleAccount.from_json(
            str(self._account_json),
            anisette_libs_path=anisette_path,
        )
        return self._account
