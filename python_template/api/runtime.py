from __future__ import annotations

from dataclasses import dataclass

from python_template.core import (
    ApprovalStore,
    AuthService,
    IdempotencyStore,
    PluginRegistry,
    PolicyEngine,
    Settings,
    load_settings,
    load_sidecar_plugins,
)
from python_template.plugins import (
    AppleMusicPlugin,
    FindMyPlugin,
    GmailDemoPlugin,
    IMessageBlueBubblesPlugin,
)


@dataclass
class Runtime:
    settings: Settings
    registry: PluginRegistry
    policy: PolicyEngine
    approvals: ApprovalStore
    idempotency: IdempotencyStore
    auth: AuthService


def create_runtime(settings: Settings | None = None) -> Runtime:
    settings = settings or load_settings()
    first_party_plugins = [
        GmailDemoPlugin(),
        IMessageBlueBubblesPlugin(),
        AppleMusicPlugin(),
        FindMyPlugin(),
    ]
    sidecar_plugins = load_sidecar_plugins(settings)
    registry = PluginRegistry(plugins=[*first_party_plugins, *sidecar_plugins])
    return Runtime(
        settings=settings,
        registry=registry,
        policy=PolicyEngine(settings=settings),
        approvals=ApprovalStore(),
        idempotency=IdempotencyStore(),
        auth=AuthService(settings=settings),
    )
