---
last_read: 2026-02-06T00:00:00Z
usefulness: 1
read_win_tags:
  - auth
  - sidecar
  - plugins
---
# V1 auth + sidecar + initial plugins notes

## Decisions
- Authentication: bearer token + `X-Tailscale-Identity` header required by default.
- Authorization: capability checks per endpoint type.
  - discovery: `system.plugins.read`
  - approvals: `system.approvals.manage`
  - resource reads: `manifest.resources[].capability_id`
  - actions: `manifest.actions[].capability_id`
- Default local dev token stays enabled when `AGENT_TOKENS_JSON` unset:
  - token `dev-local-token`, capabilities `*`, tailscale identity wildcard.

## Sidecar protocol implemented
- Manifest fetch: `GET /plugin/manifest`
- List resource: `POST /plugin/resources/{resource}/list`
- Get resource: `POST /plugin/resources/{resource}/{resource_id}/get`
- Action run: `POST /plugin/actions/{action}/{phase}`
- Shared-secret header: `X-Clawgate-Sidecar-Secret`

## Plugin metadata expansion
- Added manifest `resources[]` with `name`, `capability_id`, `allowed_views`.
- Capability listing now includes both resource and action entries.
- Action uniqueness check changed to `(name, resource)` instead of `name` only.

## Initial plugin set
- `imessage` via BlueBubbles HTTP API wrapper.
- `apple_music` via AppleScript (`osascript`).
- `find_my` via `FindMy.py` account session + accessory JSON files.

## Obstacles solved
- Large route module hit >500 lines: split action orchestration into `api/actions.py`.
- Plugin propose paths should avoid side effects:
  - iMessage/Apple Music proposes do not invoke external APIs.
  - Find My propose returns preview without loading account/device data.
