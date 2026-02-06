# Documentation Home

## V1 HTTP Contract

- Canonical base path: `/v1`
- Optional alias path: `/api` (disabled unless `ENABLE_API_ALIAS=true`)
- AuthN/AuthZ: bearer token + `X-Tailscale-Identity`, enforced by capability IDs.
- Read endpoints are REST resource routes.
- Mutating or side-effect actions use `POST ...:{action}/propose|execute`.
- Core approval APIs live under `/v1/approvals/*`.
- Sidecar runtime: configure third-party plugins with `SIDECAR_PLUGINS_JSON`.

## Auth Config

- `AGENT_TOKENS_JSON` accepts a JSON list:
  - `token`, `agent_id`, `tailscale_identity`, `capabilities[]`
- Example capability IDs:
  - `system.plugins.read`
  - `system.approvals.manage`
  - `{plugin}.{resource}.read`
  - manifest action capability IDs

## Sidecar Config

- `SIDECAR_PLUGINS_JSON` accepts a JSON list:
  - `id`, `base_url`, optional `shared_secret`, optional `timeout_seconds`
