from __future__ import annotations

from pathlib import Path

from python_template.plugins.find_my import plugin as find_my_module


def test_get_account_uses_findmy_supported_from_json_signature(tmp_path, monkeypatch):
    calls: list[tuple[str, dict[str, str]]] = []
    expected_account = object()

    class StubAppleAccount:
        @staticmethod
        def from_json(path: str, **kwargs):
            calls.append((path, kwargs))
            return expected_account

    monkeypatch.setattr(find_my_module, "AppleAccount", StubAppleAccount)

    plugin = find_my_module.FindMyPlugin()
    plugin._account_json = Path(tmp_path / "findmy_account.json")
    plugin._anisette_libs = Path(tmp_path / "ani_libs.bin")
    plugin._anisette_libs.write_text("stub-libs", encoding="utf-8")

    loaded = plugin._get_account()
    cached = plugin._get_account()

    assert loaded is expected_account
    assert cached is expected_account
    assert calls == [
        (
            str(plugin._account_json),
            {"anisette_libs_path": str(plugin._anisette_libs)},
        )
    ]
