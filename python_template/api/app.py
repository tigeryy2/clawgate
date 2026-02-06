from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from python_template.api.routes import build_contract_router
from python_template.api.runtime import Runtime, create_runtime
from python_template.core.exceptions import APIError
from python_template.core.models import ErrorResponse


def create_app(runtime: Runtime | None = None) -> FastAPI:
    runtime = runtime or create_runtime()
    app = FastAPI(title="Clawgate API", version="0.2.0")
    app.state.runtime = runtime

    @app.exception_handler(APIError)
    def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error={
                    "code": exc.payload.code,
                    "message": exc.payload.message,
                }
            ).model_dump(),
        )

    app.include_router(
        build_contract_router(runtime=runtime, prefix=runtime.settings.api_prefix)
    )
    if runtime.settings.enable_api_alias:
        app.include_router(build_contract_router(runtime=runtime, prefix="/api"))

    return app


app = create_app()
