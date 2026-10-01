"""Configuration du serveur API tirée du profil (C6) : app.asgi_workers est lu et borné à un seul processus."""

import pytest

from services.runtime.api_entry import server_config


class Settings:
    def __init__(self, **app):
        self.profile = {"app": app}

    def value(self, section, key, default=None):
        return self.profile.get(section, {}).get(key, default)


class DevelopmentPolicy:
    production = False


def test_delivered_single_worker_is_read_from_the_profile():
    config = server_config(Settings(port=8799, asgi_workers=1), DevelopmentPolicy())
    assert (config.workers, config.port, config.host) == (1, 8799, "127.0.0.1")
    assert config.ssl_certfile is None


@pytest.mark.parametrize("workers", [0, 2, 4])
def test_other_worker_counts_are_refused(workers):
    with pytest.raises(ValueError, match="app.asgi_workers doit valoir 1"):
        server_config(Settings(port=8799, asgi_workers=workers), DevelopmentPolicy())
