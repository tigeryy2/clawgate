from __future__ import annotations

import pytest

from python_template.core.exceptions import NotFoundError, ValidationError
from python_template.core.models import ReadQuery
from python_template.core.plugin_registry import ActionContext
from python_template.plugins.apple_music import AppleMusicPlugin


class StubRunner:
    def __init__(self):
        self.calls: list[str] = []

    def run(self, script: str) -> str:
        self.calls.append(script)

        if "get name of every playlist" in script:
            return "Chill, Recently Played"

        if 'repeat with item_track in tracks of playlist "Recently Played"' in script:
            return (
                "Yellow\x1fColdplay\x1fParachutes"
                "\x1e"
                "Viva La Vida\x1fColdplay\x1fViva La Vida"
            )

        if 'repeat with item_track in tracks of playlist "Chill"' in script:
            return (
                "Nude\x1fRadiohead\x1fIn Rainbows"
                "\x1e"
                "Teardrop\x1fMassive Attack\x1fMezzanine"
            )

        if 'repeat with item_track in tracks of playlist "Library"' in script:
            if 'contains "Yellow"' in script:
                return "Yellow\x1fColdplay\x1fParachutes"
            return "__TRACK_NOT_FOUND__"

        if 'play (first track of playlist "Library"' in script:
            return ""

        return "__PLAYLIST_NOT_FOUND__"


def _action(plugin: AppleMusicPlugin, name: str, resource: str | None):
    for action in plugin.manifest.actions:
        if action.name == name and action.resource == resource:
            return action
    raise AssertionError(f"missing action {name} for resource {resource}")


def test_history_resource_exposes_playback_history():
    plugin = AppleMusicPlugin(runner=StubRunner())

    result = plugin.list_resource("history", ReadQuery(limit=10, q="viva"))

    assert result.data["next_cursor"] is None
    assert len(result.data["items"]) == 1
    assert result.data["items"][0]["track"] == "Viva La Vida"
    assert result.data["items"][0]["artist"] == "Coldplay"


def test_playlist_tracks_requires_playlist_query_param():
    plugin = AppleMusicPlugin(runner=StubRunner())

    with pytest.raises(ValidationError, match="playlist_tracks requires playlist"):
        plugin.list_resource("playlist_tracks", ReadQuery(limit=10))


def test_playlist_tracks_list_and_get():
    plugin = AppleMusicPlugin(runner=StubRunner())

    list_result = plugin.list_resource(
        "playlist_tracks",
        ReadQuery(limit=10, filters={"playlist": "Chill"}),
    )
    assert [item["track"] for item in list_result.data["items"]] == ["Nude", "Teardrop"]

    get_result = plugin.get_resource(
        "playlist_tracks",
        "Chill",
        view=None,
        query=ReadQuery(limit=10),
    )
    assert get_result.data["name"] == "Chill"
    assert len(get_result.data["items"]) == 2


def test_track_search_requires_q():
    plugin = AppleMusicPlugin(runner=StubRunner())

    with pytest.raises(ValidationError, match="tracks resource requires q parameter"):
        plugin.list_resource("tracks", ReadQuery(limit=10))


def test_track_search_and_play_song_execute():
    runner = StubRunner()
    plugin = AppleMusicPlugin(runner=runner)

    search_result = plugin.list_resource(
        "tracks",
        ReadQuery(limit=5, q="Yellow", filters={"artist": "Coldplay"}),
    )
    assert search_result.data["items"][0]["track"] == "Yellow"

    play_song = _action(plugin, name="play_song", resource=None)
    context = ActionContext(
        plugin_id="apple_music",
        phase="execute",
        action=play_song,
        resource=None,
        resource_id=None,
    )

    action_result = plugin.run_action(
        context=context,
        args={"song": "Yellow", "artist": "Coldplay"},
    )
    assert action_result.result["track"] == "Yellow"
    assert action_result.result["artist"] == "Coldplay"
    assert "Play song 'Yellow'" in (action_result.summary or "")
    assert any(
        'play (first track of playlist "Library"' in call for call in runner.calls
    )


def test_play_song_missing_track_raises_not_found():
    plugin = AppleMusicPlugin(runner=StubRunner())
    play_song = _action(plugin, name="play_song", resource=None)
    context = ActionContext(
        plugin_id="apple_music",
        phase="propose",
        action=play_song,
        resource=None,
        resource_id=None,
    )

    with pytest.raises(NotFoundError, match="song 'Missing Song' not found in library"):
        plugin.run_action(context=context, args={"song": "Missing Song"})
