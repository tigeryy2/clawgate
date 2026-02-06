# API
FastAPI app and HTTP routing for the V1 contract.

## Contents
- `app.py`: App factory and exception handling.
- `runtime.py`: Runtime wiring for settings, auth, policy, plugins, and sidecars.
- `routes.py`: HTTP route handlers for discovery, reads, actions, and approvals.
- `actions.py`: Shared action execution pipeline (authz, approvals, idempotency, policy).
