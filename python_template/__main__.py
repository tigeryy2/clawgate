from __future__ import annotations

import uvicorn

from python_template.core.config import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "python_template.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
    )


if __name__ == "__main__":
    main()
