"""CLI for the separate credential-free local M4 runtime origin."""

import uvicorn

from opintel_demo_runtime.app import create_runtime_app
from opintel_demo_runtime.gateway import CoreHttpRuntimeGateway


def run() -> None:
    uvicorn.run(
        create_runtime_app(CoreHttpRuntimeGateway()),
        host="127.0.0.1",
        port=8100,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    run()
