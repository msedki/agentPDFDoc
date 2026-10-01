"""Tâches de fond de l'API (file d'ingestion, nettoyage vectoriel) : reprise bornée après erreur et fin journalisée."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable


def retry_delay(failures: int, base_seconds: float, max_seconds: float) -> float:
    """Attente avant un nouvel essai après `failures` échecs consécutifs : doublée à chaque échec, plafonnée."""
    return min(max_seconds, base_seconds * 2 ** max(0, failures - 1))


class FailureLog:
    """Échecs consécutifs d'une boucle de fond : attente croissante et plafonnée, pile complète au premier échec
    ou quand l'erreur change, une seule ligne tant qu'elle se répète (le journal de l'API reste lisible)."""

    def __init__(self, logger: logging.Logger, base_seconds: float, max_seconds: float):
        self.logger, self.base_seconds, self.max_seconds = logger, base_seconds, max_seconds
        self.failures = 0
        self._last: tuple[str, str] | None = None

    def success(self) -> None:
        self.failures, self._last = 0, None

    def failure(self, what: str, error: BaseException) -> float:
        """Journalise l'échec et rend l'attente avant le prochain essai."""
        self.failures += 1
        delay = retry_delay(self.failures, self.base_seconds, self.max_seconds)
        signature = (type(error).__name__, str(error))
        self.logger.error("%s (échec consécutif n° %d) ; nouvel essai dans %.1f s.", what, self.failures, delay,
                          exc_info=error if signature != self._last else None)
        self._last = signature
        return delay


def log_unexpected_end(task: asyncio.Task, name: str, closing: Callable[[], bool], logger: logging.Logger) -> None:
    """Journalise la fin d'une boucle de fond survenue sans demande d'arrêt de l'API.

    Les boucles interceptent leurs propres erreurs ; ce rappel couvre le reste (annulation extérieure, défaut
    du code de reprise) pour qu'un arrêt ne passe jamais inaperçu jusqu'au redémarrage.
    """
    def finished(done: asyncio.Task) -> None:
        if done.cancelled():
            if not closing():
                logger.error("Boucle %s annulée sans arrêt de l'API ; elle reste arrêtée jusqu'au redémarrage de l'API.", name)
            return
        error = done.exception()
        if error is not None:
            # Journalisée même pendant l'arrêt : `finish` ne relève pas cette erreur.
            logger.error("Boucle %s arrêtée par une erreur inattendue ; elle reste arrêtée jusqu'au redémarrage de l'API.",
                         name, exc_info=error)
        elif not closing():
            logger.error("Boucle %s terminée sans arrêt de l'API ; elle reste arrêtée jusqu'au redémarrage de l'API.", name)

    task.add_done_callback(finished)


async def finish(task: asyncio.Task | None) -> None:
    """Attend la fin d'une boucle sans relever son erreur, déjà journalisée par `log_unexpected_end`."""
    if task is not None:
        await asyncio.gather(task, return_exceptions=True)
