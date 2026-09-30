"""Serveur API avec demande locale d'arrêt coopératif, gérée par le propriétaire."""

import asyncio
import os
from pathlib import Path

import uvicorn


async def serve() -> None:
    from services.api.settings import Settings

    settings = Settings.load()
    marker = Path(os.environ["RAG_SHUTDOWN_MARKER"])
    config = uvicorn.Config("services.api.main:app", host="127.0.0.1",
                            port=settings.value("app", "port", 8785), workers=1,
                            access_log=False, timeout_graceful_shutdown=120,
                            log_level="info")
    server = uvicorn.Server(config)

    async def watch():
        while not marker.exists():
            await asyncio.sleep(0.25)
        server.should_exit = True

    task = asyncio.create_task(watch())
    try:
        await server.serve()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(serve())
