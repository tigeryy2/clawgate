# python_template
Application package for clawgate runtime and utilities.

## Contents
- `api/`: FastAPI app and V1 HTTP route contract.
- `core/`: Policy, approvals, idempotency, manifest, and plugin registry logic.
- `plugins/`: First-party plugin implementations.
- `utils/`: Generic utility and logging helpers.
- `__main__.py`: Package entrypoint.

## Notes
- HTTP routes require bearer token + `X-Tailscale-Identity` unless auth is disabled in settings.
- Third-party plugin sidecars can be loaded with `SIDECAR_PLUGINS_JSON`.
