"""Separate-origin HTTP shell for the deterministic M4 runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from opintel_demo.contracts import CapabilityExchangeRequest, RuntimeEventRequest
from opintel_demo.domain import DemoError
from opintel_demo.policy import CSP
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.base import RequestResponseEndpoint

STATIC = Path(__file__).with_name("static")


class RuntimeGateway(Protocol):
    def exchange(self, command: CapabilityExchangeRequest) -> dict[str, object]: ...
    def event(self, command: RuntimeEventRequest) -> dict[str, object]: ...


class RuntimeUnavailableGateway:
    def exchange(self, command: CapabilityExchangeRequest) -> dict[str, object]:
        del command
        raise RuntimeError("runtime gateway is not configured")

    def event(self, command: RuntimeEventRequest) -> dict[str, object]:
        del command
        raise RuntimeError("runtime gateway is not configured")


class RuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    mode: str
    live_ai: bool = False
    public_access: bool = False
    external_actions: bool = False
    credential_classes: list[str] = Field(default_factory=list)


def create_runtime_app(gateway: RuntimeGateway | None = None) -> FastAPI:
    active_gateway = gateway or RuntimeUnavailableGateway()
    app = FastAPI(
        title="Opportunity Intelligence M4 Demo Runtime",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DemoError)
    def demo_error(request: Request, error: DemoError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=400,
            content={"detail": error.safe_message, "code": error.code},
        )

    @app.exception_handler(RuntimeError)
    def runtime_unavailable(request: Request, error: RuntimeError) -> JSONResponse:
        del request, error
        return JSONResponse(status_code=503, content={"detail": "runtime gateway unavailable"})

    @app.get("/healthz", response_model=RuntimeStatus)
    def health() -> RuntimeStatus:
        return RuntimeStatus(
            status="ok",
            mode="m4-separate-origin",
            credential_classes=[],
        )

    @app.get("/robots.txt", include_in_schema=False)
    def robots() -> Response:
        return Response("User-agent: *\nDisallow: /\n", media_type="text/plain")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", media_type="text/html")

    @app.get("/runtime.js", include_in_schema=False)
    def runtime_javascript() -> FileResponse:
        return FileResponse(STATIC / "runtime.js", media_type="text/javascript")

    @app.get("/runtime.css", include_in_schema=False)
    def runtime_styles() -> FileResponse:
        return FileResponse(STATIC / "runtime.css", media_type="text/css")

    @app.post("/runtime/v1/capabilities/exchange")
    def exchange(command: CapabilityExchangeRequest) -> dict[str, object]:
        return active_gateway.exchange(command)

    @app.post("/runtime/v1/events")
    def event(command: RuntimeEventRequest) -> dict[str, object]:
        return active_gateway.event(command)

    return app
