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

_TRACK_FIELD_DELIM = "\x1f"
_TRACK_ROW_DELIM = "\x1e"
_PLAYLIST_NOT_FOUND = "__PLAYLIST_NOT_FOUND__"
_HISTORY_PLAYLIST_NAME = "Recently Played"
_TRACK_NOT_FOUND = "__TRACK_NOT_FOUND__"


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
            PluginResourceManifest(
                name="history",
                capability_id="apple_music.history.read",
                allowed_views=["headers", "body"],
            ),
            PluginResourceManifest(
                name="playlist_tracks",
                capability_id="apple_music.playlist_tracks.read",
                allowed_views=["headers", "body"],
            ),
            PluginResourceManifest(
                name="tracks",
                capability_id="apple_music.tracks.read",
                allowed_views=["headers", "body"],
            ),
        ],
        required_secrets=[],
        required_scopes=["music.playback", "music.library.read"],
        default_policy={"max_limit": 50},
        actions=[
            PluginActionManifest(
                name="play",
                capability_id="apple_music.playback.play",
                resource_type="playback",
                risk_tier=RiskTier.routine,
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
                risk_tier=RiskTier.routine,
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
                risk_tier=RiskTier.routine,
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
                risk_tier=RiskTier.routine,
                route_pattern="/playlists/{resource_id}:play/{phase}",
                supports_propose=True,
                requires_idempotency=False,
                emits_attributes=["origin", "resource_type", "container"],
                resource="playlists",
                mutating=True,
            ),
            PluginActionManifest(
                name="play_song",
                capability_id="apple_music.track.play",
                resource_type="playback",
                risk_tier=RiskTier.routine,
                route_pattern="/:play_song/{phase}",
                supports_propose=True,
                requires_idempotency=False,
                emits_attributes=["origin", "resource_type"],
                resource=None,
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

        if resource == "history":
            items = self._playback_history(query=query)
            return InternalReadResult(
                data={"items": items, "next_cursor": None},
                policy_items=[
                    PolicyItem(
                        data_ref=f"items[{idx}]",
                        attrs={
                            "resource_type": "playback_history",
                            "origin": "apple_music",
                            "container": _HISTORY_PLAYLIST_NAME,
                        },
                    )
                    for idx, _ in enumerate(items)
                ],
            )

        if resource == "playlist_tracks":
            playlist_name = str(query.filters.get("playlist", "")).strip()
            if not playlist_name:
                raise ValidationError(
                    "playlist_tracks requires playlist query parameter"
                )
            items = self._list_playlist_tracks(
                playlist_name=playlist_name,
                query=query,
                raise_if_missing=True,
            )
            return InternalReadResult(
                data={"items": items, "next_cursor": None},
                policy_items=[
                    PolicyItem(
                        data_ref=f"items[{idx}]",
                        attrs={
                            "resource_type": "track",
                            "origin": "apple_music",
                            "container": playlist_name,
                        },
                    )
                    for idx, _ in enumerate(items)
                ],
            )

        if resource == "tracks":
            query_text = str(query.q or "").strip()
            if not query_text:
                raise ValidationError("tracks resource requires q parameter")
            artist_name = str(query.filters.get("artist", "")).strip() or None
            items = self._search_tracks(
                query_text=query_text,
                artist_name=artist_name,
                limit=query.limit,
            )
            return InternalReadResult(
                data={"items": items, "next_cursor": None},
                policy_items=[
                    PolicyItem(
                        data_ref=f"items[{idx}]",
                        attrs={
                            "resource_type": "track",
                            "origin": "apple_music",
                            "container": "Library",
                        },
                    )
                    for idx, _ in enumerate(items)
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

        if resource == "history":
            items = self._playback_history(query=ReadQuery(limit=250))
            for item in items:
                if item.get("id") == resource_id:
                    return InternalReadResult(
                        data=item,
                        policy_items=[
                            PolicyItem(
                                data_ref="self",
                                attrs={
                                    "resource_type": "playback_history",
                                    "origin": "apple_music",
                                    "container": _HISTORY_PLAYLIST_NAME,
                                },
                            )
                        ],
                    )
            raise NotFoundError(f"history entry '{resource_id}' not found")

        if resource == "playlist_tracks":
            playlist_name = resource_id.strip()
            if not playlist_name:
                raise ValidationError("playlist id is required")
            tracks = self._list_playlist_tracks(
                playlist_name=playlist_name,
                query=ReadQuery(limit=1000),
                raise_if_missing=True,
            )
            return InternalReadResult(
                data={
                    "id": playlist_name,
                    "name": playlist_name,
                    "items": tracks,
                    "next_cursor": None,
                },
                policy_items=[
                    PolicyItem(
                        data_ref="self",
                        attrs={
                            "resource_type": "playlist",
                            "origin": "apple_music",
                            "container": playlist_name,
                        },
                    )
                ],
            )

        if resource == "tracks":
            query_text = resource_id.strip()
            if not query_text:
                raise ValidationError("track id is required")
            items = self._search_tracks(
                query_text=query_text,
                artist_name=None,
                limit=1,
            )
            if not items:
                raise NotFoundError(f"track '{resource_id}' not found")
            return InternalReadResult(
                data=items[0],
                policy_items=[
                    PolicyItem(
                        data_ref="self",
                        attrs={
                            "resource_type": "track",
                            "origin": "apple_music",
                            "container": "Library",
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

        if context.action.name == "play_song":
            song_name = str(
                args.get("song") or args.get("track") or args.get("title") or ""
            ).strip()
            if not song_name:
                raise ValidationError("play_song action requires song")
            artist_name = str(args.get("artist") or "").strip() or None
            return self._play_song(
                phase=context.phase,
                song_name=song_name,
                artist_name=artist_name,
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

    def _playback_history(self, query: ReadQuery) -> list[dict[str, Any]]:
        return self._list_playlist_tracks(
            playlist_name=_HISTORY_PLAYLIST_NAME,
            query=query,
            raise_if_missing=False,
        )

    def _play_song(
        self,
        phase: str,
        song_name: str,
        artist_name: str | None,
    ) -> InternalActionResult:
        matched_track = self._find_track(song_name=song_name, artist_name=artist_name)
        if matched_track is None:
            if artist_name:
                raise NotFoundError(
                    f"song '{song_name}' by '{artist_name}' not found in library"
                )
            raise NotFoundError(f"song '{song_name}' not found in library")

        track_name = str(matched_track.get("track") or "").strip() or song_name
        resolved_artist = str(matched_track.get("artist") or "").strip()
        script = self._play_track_script(
            track_name=track_name,
            artist_name=resolved_artist or artist_name,
        )
        summary = f"Play song '{track_name}'"
        if resolved_artist:
            summary = f"{summary} by '{resolved_artist}'"
        return self._run_music_action(
            phase=phase,
            script=script,
            summary=summary,
            result={
                "track": track_name,
                "artist": resolved_artist,
            },
        )

    def _list_playlist_tracks(
        self,
        playlist_name: str,
        query: ReadQuery,
        raise_if_missing: bool,
    ) -> list[dict[str, Any]]:
        output = self._runner.run(self._playlist_tracks_script(playlist_name))
        if output == _PLAYLIST_NOT_FOUND:
            if raise_if_missing:
                raise NotFoundError(f"playlist '{playlist_name}' not found")
            return []
        return self._parse_track_rows(output=output, query=query)

    def _search_tracks(
        self,
        query_text: str,
        artist_name: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        output = self._runner.run(
            self._search_tracks_script(
                query_text=query_text,
                artist_name=artist_name,
                limit=limit,
            )
        )
        if output == _TRACK_NOT_FOUND:
            return []
        return self._parse_track_rows(output=output, query=ReadQuery(limit=limit))

    def _find_track(
        self,
        song_name: str,
        artist_name: str | None,
    ) -> dict[str, Any] | None:
        items = self._search_tracks(
            query_text=song_name,
            artist_name=artist_name,
            limit=1,
        )
        if not items:
            return None
        return items[0]

    def _playlist_tracks_script(self, playlist_name: str) -> str:
        escaped = self._escape_applescript_text(playlist_name)
        return f"""
        set field_delim to ASCII character 31
        set row_delim to ASCII character 30
        tell application "Music"
            if not (exists playlist "{escaped}") then
                return "{_PLAYLIST_NOT_FOUND}"
            end if
            set rows to {{}}
            repeat with item_track in tracks of playlist "{escaped}"
                set track_name to ""
                set artist_name to ""
                set album_name to ""
                try
                    set track_name to (name of item_track) as text
                end try
                try
                    set artist_name to (artist of item_track) as text
                end try
                try
                    set album_name to (album of item_track) as text
                end try
                copy (track_name & field_delim & artist_name & field_delim & album_name) to end of rows
            end repeat
            set AppleScript's text item delimiters to row_delim
            set payload to rows as text
            set AppleScript's text item delimiters to ""
            return payload
        end tell
        """

    def _search_tracks_script(
        self,
        query_text: str,
        artist_name: str | None,
        limit: int,
    ) -> str:
        escaped_query = self._escape_applescript_text(query_text)
        escaped_artist = self._escape_applescript_text(artist_name or "")
        safe_limit = max(1, min(limit, 100))

        return f"""
        set field_delim to ASCII character 31
        set row_delim to ASCII character 30
        tell application "Music"
            set rows to {{}}
            set search_results to search playlist "Library" for "{escaped_query}"
            repeat with item_track in search_results
                set track_name to ""
                set artist_name to ""
                set album_name to ""
                try
                    set track_name to (name of item_track) as text
                end try
                try
                    set artist_name to (artist of item_track) as text
                end try
                try
                    set album_name to (album of item_track) as text
                end try
                set include_track to true
                ignoring case
                    if "{escaped_artist}" is not "" then
                        if artist_name does not contain "{escaped_artist}" then
                            set include_track to false
                        end if
                    end if
                end ignoring
                if include_track then
                    copy (track_name & field_delim & artist_name & field_delim & album_name) to end of rows
                end if
                if (count of rows) is greater than or equal to {safe_limit} then
                    exit repeat
                end if
            end repeat
            if (count of rows) is 0 then
                return "{_TRACK_NOT_FOUND}"
            end if
            set AppleScript's text item delimiters to row_delim
            set payload to rows as text
            set AppleScript's text item delimiters to ""
            return payload
        end tell
        """

    def _play_track_script(self, track_name: str, artist_name: str | None) -> str:
        escaped_track = self._escape_applescript_text(track_name)
        if artist_name:
            escaped_artist = self._escape_applescript_text(artist_name)
            return f"""
            tell application "Music"
                play (first track of playlist "Library" whose name is "{escaped_track}" and artist is "{escaped_artist}")
            end tell
            """
        return f"""
        tell application "Music"
            play (first track of playlist "Library" whose name is "{escaped_track}")
        end tell
        """

    def _parse_track_rows(self, output: str, query: ReadQuery) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        rows = [row for row in output.split(_TRACK_ROW_DELIM) if row] if output else []
        for idx, row in enumerate(rows):
            parts = row.split(_TRACK_FIELD_DELIM)
            while len(parts) < 3:
                parts.append("")
            track_name, artist_name, album_name = [value.strip() for value in parts[:3]]
            items.append(
                {
                    "id": str(idx + 1),
                    "position": idx + 1,
                    "track": track_name,
                    "artist": artist_name,
                    "album": album_name,
                }
            )

        if query.q:
            needle = query.q.lower()
            items = [
                item
                for item in items
                if needle in item["track"].lower()
                or needle in item["artist"].lower()
                or needle in item["album"].lower()
            ]

        return items[: query.limit]

    @staticmethod
    def _escape_applescript_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
