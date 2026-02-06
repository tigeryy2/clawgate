from __future__ import annotations

from python_template.__main__ import main


def test_main_uses_configured_api_bind(monkeypatch):
    monkeypatch.setenv("CLAWGATE_API_HOST", "0.0.0.0")
    monkeypatch.setenv("CLAWGATE_API_PORT", "9123")

    calls: list[tuple[str, str, int]] = []

    def fake_run(app: str, host: str, port: int) -> None:
        calls.append((app, host, port))

    monkeypatch.setattr("python_template.__main__.uvicorn.run", fake_run)

    main()

    assert calls == [("python_template.api.app:app", "0.0.0.0", 9123)]
