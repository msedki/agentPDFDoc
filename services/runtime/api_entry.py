"""Serveur API avec demande locale d'arrêt coopératif, gérée par le propriétaire."""

import asyncio
import os
from pathlib import Path

import uvicorn


def server_config(settings, policy) -> uvicorn.Config:
    """Configuration uvicorn tirée du profil ; un seul processus API, qui porte le gouverneur et la file des travaux."""
    workers = settings.value("app", "asgi_workers", 1)
    if workers != 1:
        raise ValueError("app.asgi_workers doit valoir 1 : un seul processus API détient le gouverneur de ressources "
                         "et la file des travaux")
    # Production (W011) : HTTPS loopback avec le certificat et la clé du profil ; développement en HTTP.
    return uvicorn.Config("services.api.main:app", host="127.0.0.1",
                          port=settings.value("app", "port", 8785), workers=workers,
                          access_log=False, timeout_graceful_shutdown=120, log_level="info",
                          ssl_certfile=str(policy.tls_cert_file) if policy.production else None,
                          ssl_keyfile=str(policy.tls_key_file) if policy.production else None)


async def serve() -> None:
    from services.api.security import SecurityPolicy
    from services.api.settings import Settings

    settings = Settings.load()
    policy = SecurityPolicy.from_settings(settings)
    marker = Path(os.environ["RAG_SHUTDOWN_MARKER"])
    server = uvicorn.Server(server_config(settings, policy))

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
