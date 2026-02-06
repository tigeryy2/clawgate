# clawgate
Trusted-box API runtime with plugin-scoped REST reads and `:{action}` RPC endpoints.

## Setup

1. Create or update the environment: `uv sync --locked`
2. Activate it (optional): `source .venv/bin/activate`
3. Run tests: `uv run pytest`

`uv sync` installs the project itself into `.venv` by default, so a separate `pip install -e .` step is not needed.

## API Contract Highlights

- Canonical prefix: `/v1` (`/api` alias is optional and disabled by default).
- Auth: bearer token + `X-Tailscale-Identity` on every contract route.
  - Default dev token: `Authorization: Bearer dev-local-token`
  - Default identity header: `X-Tailscale-Identity: tailnet://local/dev-local`
- Discovery:
  - `GET /v1/plugins`
  - `GET /v1/plugins/{plugin_id}`
  - `GET /v1/plugins/{plugin_id}/capabilities`
- Reads:
  - `GET /v1/{plugin_id}/{resource}`
  - `GET /v1/{plugin_id}/{resource}/{resource_id}`
  - `GET /v1/{plugin_id}/{resource}/{resource_id}/headers|body|raw`
- Actions:
  - `POST /v1/{plugin_id}:{action}/propose|execute`
  - `POST /v1/{plugin_id}/{resource}/{resource_id}:{action}/propose|execute`
- Approvals:
  - `GET /v1/approvals/{ticket_id}`
  - `POST /v1/approvals/{ticket_id}:approve`
  - `POST /v1/approvals/{ticket_id}:deny`
- Runtime modes:
  - First-party plugins: in-process
  - Third-party plugins: sidecar via `SIDECAR_PLUGINS_JSON`

## Initial Plugins

- `gmail` (demo reference plugin)
- `imessage` (BlueBubbles-backed)
- `apple_music` (`osascript`-backed)
- `find_my` (`FindMy.py`-backed)

## Daily Commands

- Run API (default bind `0.0.0.0:8117`): `uv run python-template`
- Run API on a different port: `CLAWGATE_API_PORT=8121 uv run python-template`
- Run API tests: `uv run pytest`
- Lint and auto-fix: `uv run ruff check --fix .`
- Format: `uv run ruff format .`

## Environment Variables

`python-dotenv` is used for loading `.env` values.
Start from [`.env.example`](.env.example) when creating local environment files.
`uv run python-template` auto-loads `.env` from the repository root.

- API bind host: `CLAWGATE_API_HOST` (default `0.0.0.0`)
- API bind port: `CLAWGATE_API_PORT` (default `8117`)
