"""CLI entry point for the M0 API."""

import uvicorn
from opintel_m0_local.settings import get_local_settings

from opintel_api.app import create_app


def run() -> None:
    settings = get_local_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    run()
