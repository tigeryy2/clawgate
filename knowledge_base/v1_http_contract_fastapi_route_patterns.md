---
last_read: 2026-02-06T00:00:00Z
usefulness: 1
read_win_tags:
  - fastapi
  - routing
  - plugins
---
# V1 HTTP contract implementation notes

## Decisions
- Canonical prefix `/v1`; optional `/api` alias behind `ENABLE_API_ALIAS` (default false).
- Resource reads stay RESTful.
- Side-effect operations use colon action paths: `...:{action}/propose|execute`.
- Approval flow uses `202` + ticket; approvals managed by core endpoints.

## Gotchas
- Colon-action routes can conflict with generic resource routes if route registration order is wrong.
- Register action routes before generic `/{resource}/{resource_id}/{view}` routes.
- Keep path params explicit and stable for OpenAPI contracts:
  - `/v1/{plugin_id}:{action}/propose`
  - `/v1/{plugin_id}/{resource}/{resource_id}:{action}/execute`

## Validation checklist
- `limit` normalized to default/hard cap (`20`/`100`).
- `idempotency_key` enforced for mutating execute actions.
- `raw` tier read blocked by policy default.
- Body tier sanitized and truncated centrally.
- Route -> capability mapping verified via approval ticket metadata.

## Testing pattern used
- Use `fastapi.testclient.TestClient` with fresh runtime per test.
- Seed plugin in test when validating limit cap behavior.
- Assert OpenAPI path keys directly for contract drift detection.
