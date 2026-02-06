# Core
Core runtime services for the V1 API contract.

## Contents
- `config.py`: Runtime settings, auth toggles, and sidecar config strings.
- `auth.py`: Tailscale identity + bearer token authentication and capability checks.
- `manifests.py`: Plugin/resource/action manifest schemas.
- `models.py`: Shared request/response and internal contract models.
- `plugin_registry.py`: In-process plugin registry and capability lookup.
- `policy.py`: Core policy checks, filtering, and response transforms.
- `approvals.py`: In-memory approval ticket store.
- `idempotency.py`: Idempotency key store for execute actions.
- `sidecar.py`: Sidecar plugin protocol client and loader.
- `exceptions.py`: Typed HTTP-facing exception helpers.
