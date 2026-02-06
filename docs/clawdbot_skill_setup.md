# ClawDBot Skill Setup for clawgate

Use this to create a ClawDBot skill that can read and control plugins exposed by this API.

## API Target

- Base URL: `http://0.0.0.0:8117/v1`
- Auth header: `Authorization: Bearer dev-local-token`
- Identity header: `X-Tailscale-Identity: tailnet://local/dev-local`
- Port source of truth: `CLAWGATE_API_PORT` default `8117` in `python_template/core/config.py`
- Local server start command: `uv run python-template`

## Skill Scope

Give the skill these responsibilities:

1. Discover plugins and capabilities.
2. Read plugin resources.
3. Propose actions before execute.
4. Handle approval tickets for execute flows.

## Approval Model (Current)

- Actions declare risk tiers in plugin manifests: `read_only`, `routine`, `transactional`, `dangerous`.
- Default approval behavior:
  - `read_only`: no approval
  - `routine`: no approval
  - `transactional`: approval required
  - `dangerous`: approval required
- User overrides:
  - `ACTION_APPROVAL_DEFAULTS_JSON` to change per-tier defaults.
  - `ACTION_APPROVAL_OVERRIDES_JSON` for capability pattern overrides (global + per plugin).
- Override precedence:
  - plugin `require` > plugin `allow` > global `require` > global `allow` > tier default.

## Minimal Endpoint Set

Use these routes in the skill integration:

- `GET /plugins`
- `GET /plugins/{plugin_id}`
- `GET /plugins/{plugin_id}/capabilities`
- `GET /{plugin_id}/{resource}`
- `GET /{plugin_id}/{resource}/{resource_id}`
- `POST /{plugin_id}:{action}/propose`
- `POST /{plugin_id}:{action}/execute`
- `POST /{plugin_id}/{resource}/{resource_id}:{action}/propose`
- `POST /{plugin_id}/{resource}/{resource_id}:{action}/execute`
- `GET /approvals/{ticket_id}`
- `POST /approvals/{ticket_id}:approve`
- `POST /approvals/{ticket_id}:deny`

## Skill Behavior Rules

1. Always send both auth headers.
2. Prefer `propose` for previews.
3. If `execute` returns `202` with `approval_ticket_id`, pause and surface ticket details.
4. Resume only after approval status is `approved`.
5. For writes, set stable `idempotency_key` values.

## Apple Music Quick Path

- Read playback: `GET /apple_music/playback`
- Read playlists: `GET /apple_music/playlists`
- Read playback history: `GET /apple_music/history`
- Read tracks in playlist: `GET /apple_music/playlist_tracks?playlist={playlist_name}`
- Read tracks in playlist (by id route): `GET /apple_music/playlist_tracks/{playlist_name}`
- Search tracks: `GET /apple_music/tracks?q={song_query}&artist={optional_artist}`
- Propose play: `POST /apple_music:play/propose`
- Execute play: `POST /apple_music:play/execute`
- Propose play specific song: `POST /apple_music:play_song/propose`
- Execute play specific song: `POST /apple_music:play_song/execute`
- Playlist play action: `POST /apple_music/playlists/{resource_id}:play/execute`

Apple Music playback actions are `routine` by default (typically execute without approval), but can require approval if overrides are configured.

## Validation Checklist

1. `GET /plugins` includes `apple_music`.
2. `POST /apple_music:play/propose` returns `200`.
3. `POST /apple_music:play/execute` returns `200` by default (or `202` if overrides require approval).
4. `GET /apple_music/playback` returns a single playback item.
5. `GET /apple_music/history` returns recently played track items (when available).
6. `GET /apple_music/playlist_tracks?playlist=...` returns track list for that playlist.
7. `GET /apple_music/tracks?q=...` returns track search matches.
8. `POST /apple_music:play_song/propose` returns `200` with resolved track metadata.
