#!/usr/bin/env python3

import asyncio
import os

import uvicorn

from krkn_retriever.api import app as compat_app
from krkn_retriever.debug_api import app as debug_app


async def _serve(app, host: str, port: int, log_level: str) -> None:
    config = uvicorn.Config(app, host=host, port=port, log_level=log_level)
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    compat_port = int(os.environ.get("PORT", "8080"))
    debug_port = int(os.environ.get("DEBUG_PORT", "18080"))
    log_level = os.environ.get("LOG_LEVEL", "info")

    async def _main() -> None:
        await asyncio.gather(
            _serve(compat_app, host=host, port=compat_port, log_level=log_level),
            _serve(debug_app, host=host, port=debug_port, log_level=log_level),
        )

    asyncio.run(_main())


if __name__ == "__main__":
    main()
