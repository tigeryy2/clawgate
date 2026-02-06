from __future__ import annotations

import subprocess
from typing import Any

from python_template.core.exceptions import APIError, NotFoundError, ValidationError
from python_template.core.manifests import (
    PluginActionManifest,
    PluginManifest,
    PluginResourceManifest,
)
from python_template.core.models import (
    ActionStatus,
    InternalActionResult,
    InternalReadResult,
    PolicyItem,
    ReadQuery,
    RiskTier,
    RuntimeMode,
)
from python_template.core.plugin_registry import ActionContext


class OsaScriptRunner:
    def run(self, script: str) -> str:
        command = ["osascript", "-e", script]
        process = subprocess.run(command, check=False, capture_output=True, text=True)
        if process.returncode != 0:
            raise APIError(
                status_code=500,
                code="OSASCRIPT_ERROR",
                message=process.stderr.strip() or "osascript failed",
            )
        return process.stdout.strip()


class AppleMusicPlugin:
    manifest = PluginManifest(
        id="apple_music",
        name="Apple Music",
        version="0.1.0",
        runtime_mode=RuntimeMode.in_process,
        resources=[
            PluginResourceManifest(
                name="playlists",
                capability_id="apple_music.playlists.read",
                allowed_views=["headers", "body"],
            ),
            PluginResourceManifest(
                name="playback",
                capability_id="apple_music.playback.read",
                allowed_views=["headers", "body"],
            ),
        ],
        required_secrets=[],
        required_scopes=["music.playback"],
        default_policy={"max_limit": 50},
        actions=[
            PluginActionManifest(
                name="play",
                capability_id="apple_music.playback.play",
                resource_type="playback",
                risk_tier=RiskTier.transactional,
                route_pattern="/:play/{phase}",
                supports_propose=True,
                requires_idempotency=False,
                emits_attributes=["origin", "resource_type"],
                resource=None,
                mutating=True,
            ),
            PluginActionManifest(
                name="pause",
                capability_id="apple_music.playback.pause",
                resource_type="playback",
                risk_tier=RiskTier.transactional,
                route_pattern="/:pause/{phase}",
                supports_propose=True,
                requires_idempotency=False,
                emits_attributes=["origin", "resource_type"],
                resource=None,
                mutating=True,
            ),
            PluginActionManifest(
                name="next_track",
                capability_id="apple_music.playback.next_track",
                resource_type="playback",
                risk_tier=RiskTier.transactional,
                route_pattern="/:next_track/{phase}",
                supports_propose=True,
                requires_idempotency=False,
                emits_attributes=["origin", "resource_type"],
                resource=None,
                mutating=True,
            ),
            PluginActionManifest(
                name="play",
                capability_id="apple_music.playlist.play",
                resource_type="playlist",
                risk_tier=RiskTier.transactional,
                route_pattern="/playlists/{resource_id}:play/{phase}",
                supports_propose=True,
                requires_idempotency=False,
                emits_attributes=["origin", "resource_type", "container"],
                resource="playlists",
                mutating=True,
            ),
        ],
    )

    def __init__(self, runner: OsaScriptRunner | None = None):
        self._runner = runner or OsaScriptRunner()

    def list_resource(self, resource: str, query: ReadQuery) -> InternalReadResult:
        if resource == "playlists":
            items = self._list_playlists(query=query)
            return InternalReadResult(
                data={"items": items, "next_cursor": None},
                policy_items=[
                    PolicyItem(
                        data_ref=f"items[{idx}]",
                        attrs={
                            "resource_type": "playlist",
                            "origin": "apple_music",
                            "container": item.get("name"),
                        },
                    )
                    for idx, item in enumerate(items)
                ],
            )

        if resource == "playback":
            playback = self._current_playback()
            return InternalReadResult(
                data={"items": [playback], "next_cursor": None},
                policy_items=[
                    PolicyItem(
                        data_ref="items[0]",
                        attrs={
                            "resource_type": "playback",
                            "origin": "apple_music",
                        },
                    )
                ],
            )

        raise NotFoundError(f"resource '{resource}' not found")

    def get_resource(
        self,
        resource: str,
        resource_id: str,
        view: str | None,
        query: ReadQuery,
    ) -> InternalReadResult:
        _ = view
        _ = query
        if resource == "playlists":
            playlists = self._list_playlists(query=ReadQuery(limit=100))
            for playlist in playlists:
                if playlist.get("id") == resource_id:
                    return InternalReadResult(
                        data=playlist,
                        policy_items=[
                            PolicyItem(
                                data_ref="self",
                                attrs={
                                    "resource_type": "playlist",
                                    "origin": "apple_music",
                                    "container": playlist.get("name"),
                                },
                            )
                        ],
                    )
            raise NotFoundError(f"playlist '{resource_id}' not found")

        if resource == "playback":
            playback = self._current_playback()
            return InternalReadResult(
                data=playback,
                policy_items=[
                    PolicyItem(
                        data_ref="self",
                        attrs={
                            "resource_type": "playback",
                            "origin": "apple_music",
                        },
                    )
                ],
            )

        raise NotFoundError(f"resource '{resource}' not found")

    def run_action(self, context: ActionContext, args: dict) -> InternalActionResult:
        if context.action.name == "play" and context.resource == "playlists":
            playlist_name = str(
                args.get("playlist_name") or context.resource_id or ""
            ).strip()
            if not playlist_name:
                raise ValidationError("playlist action requires playlist_name")
            return self._run_music_action(
                phase=context.phase,
                script=(f'tell application "Music" to play playlist "{playlist_name}"'),
                summary=f"Play playlist '{playlist_name}'",
                result={"playlist_name": playlist_name},
            )

        if context.action.name == "play":
            return self._run_music_action(
                phase=context.phase,
                script='tell application "Music" to play',
                summary="Play Apple Music",
                result={"state": "playing"},
            )

        if context.action.name == "pause":
            return self._run_music_action(
                phase=context.phase,
                script='tell application "Music" to pause',
                summary="Pause Apple Music",
                result={"state": "paused"},
            )

        if context.action.name == "next_track":
            return self._run_music_action(
                phase=context.phase,
                script='tell application "Music" to next track',
                summary="Skip to next track",
                result={"state": "advanced"},
            )

        raise NotFoundError(f"action '{context.action.name}' not implemented")

    def _run_music_action(
        self,
        phase: str,
        script: str,
        summary: str,
        result: dict[str, Any],
    ) -> InternalActionResult:
        if phase == "execute":
            output = self._runner.run(script)
            if output:
                result = dict(result)
                result["output"] = output

        return InternalActionResult(
            status=ActionStatus.success,
            summary=summary,
            result=result,
            proposed_effect=result,
            policy_items=[
                PolicyItem(
                    data_ref="result",
                    attrs={
                        "resource_type": "playback",
                        "origin": "apple_music",
                    },
                )
            ],
        )

    def _list_playlists(self, query: ReadQuery) -> list[dict[str, Any]]:
        output = self._runner.run(
            'tell application "Music" to get name of every playlist'
        )
        names = [value.strip() for value in output.split(",") if value.strip()]
        if query.q:
            needle = query.q.lower()
            names = [name for name in names if needle in name.lower()]
        names = names[: query.limit]
        return [{"id": name, "name": name} for name in names]

    def _current_playback(self) -> dict[str, Any]:
        script = """
        tell application "Music"
            set player_state to (get player state) as text
            if player_state is "stopped" then
                return "stopped|||"
            end if
            set track_name to ""
            set artist_name to ""
            if exists current track then
                set track_name to (name of current track)
                set artist_name to (artist of current track)
            end if
            return player_state & "|" & track_name & "|" & artist_name
        end tell
        """
        output = self._runner.run(script)
        parts = output.split("|")
        while len(parts) < 3:
            parts.append("")
        state, track_name, artist_name = parts[:3]
        return {
            "state": state,
            "track": track_name,
            "artist": artist_name,
        }
