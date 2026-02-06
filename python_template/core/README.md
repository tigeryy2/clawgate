# Core
Core runtime services for the V1 API contract.

## Contents
- `config.py`: Runtime settings and API alias toggle.
- `manifests.py`: Plugin/action manifest schemas.
- `models.py`: Shared request/response and internal contract models.
- `plugin_registry.py`: In-process plugin registry and capability lookup.
- `policy.py`: Core policy checks, filtering, and response transforms.
- `approvals.py`: In-memory approval ticket store.
- `idempotency.py`: Idempotency key store for execute actions.
- `exceptions.py`: Typed HTTP-facing exception helpers.
