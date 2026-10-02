import asyncio
import hashlib
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from services.runtime.accelerator import processor_label

from .errors import ApiError

logger = logging.getLogger("rag.llm")

# Repli CPU (W025) : Ollama 0.35.0 ne se replie pas seul quand le chargement sur GPU échoue ; il répond 500 avant le flux
# (`server/sched.go`, `handleScheduleError` de `server/routes.go`). 503 (file pleine), 499 (annulation) et les 4xx ne
# disent rien du GPU : ils sont rapportés comme avant, sans repli.
FALLBACK_STATUS = 500
# Message d'Ollama consigné par le repli, tronqué ; le corps d'une erreur ne contient pas l'invite.
FALLBACK_ERROR_CHARS = 300
FALLBACK_BODY_LIMIT = 64 * 1024
# Relecture de /api/ps après une réponse en mode GPU : courte, elle ne doit pas retenir la session HTTP partagée.
PLACEMENT_READ_SECONDS = 5


class OllamaGateway:
    def __init__(self, settings):
        self.settings = settings
        self.base_url = settings.value("llm", "base_url", "http://127.0.0.1:11434")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(settings.value("llm", "idle_read_timeout_seconds", 300),
                                                                                    connect=settings.value("llm", "connect_timeout_seconds", 5)), trust_env=False)
        accelerator = getattr(settings, "llm_accelerator", None) or {}
        # Mode fixé pour la vie de l'instance (une requête sans num_gpu réutilise le runner chargé, `needsReload`) ;
        # seul un repli le passe en CPU, jusqu'au redémarrage.
        self.execution: dict[str, Any] = {
            "requested": accelerator.get("requested"), "requested_source": accelerator.get("requested_source"),
            "mode": "gpu" if accelerator.get("mode") == "gpu" else "cpu", "reason": accelerator.get("reason"), "fallback": None}
        # Nouvelle admission à froid avant la relance sur CPU (H1), posée par l'application quand un gouverneur existe.
        self.before_cpu_fallback: Callable[[], Awaitable[Any]] | None = None
        # Dernière occupation du modèle relue dans /api/ps (colonne PROCESSOR d'`ollama ps`), publiée par GET /jobs pour
        # l'atelier : relue avant chaque question et, en mode GPU, après chaque réponse ; None avant la première lecture
        # du modèle chargé et après un repli, qui le décharge.
        self.placement: str | None = None
        # Relectures de l'occupation lancées après une réponse ; la fin du flux ne les attend pas.
        self.placement_reads: set[asyncio.Task] = set()

    async def close(self):
        for task in list(self.placement_reads):
            task.cancel()
        await asyncio.gather(*self.placement_reads, return_exceptions=True)
        await self.client.aclose()

    def expected_identity(self):
        path = self.settings.path(self.settings.value("llm", "model_manifest", ".runtime/manifests/ollama-model.json"))
        try:
            data = path.read_bytes()
            record = json.loads(data)["model"]
            if not isinstance(record, dict):
                raise ValueError("Invalid provisioned model manifest")
            model = self.settings.value("llm", "model", "qwen3.5:4b")
            digest = record.get("digest")
            if (record.get("name", record.get("model")) != model or not isinstance(digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    or record.get("details", {}).get("quantization_level") != self.settings.value("llm", "required_quantization", "Q4_K_M")):
                raise ValueError("Invalid provisioned model identity")
            return {"model": model, "digest": digest, "manifest_sha256": hashlib.sha256(data).hexdigest()}
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ApiError("llm_identity_unverified", "Manifest local Qwen absent ou incompatible ; génération refusée.", 503) from error

    @staticmethod
    def verify_digest(record, identity):
        if record.get("digest") != identity["digest"]:
            raise ApiError("llm_identity_mismatch", "Digest Qwen différent ou inconnu ; génération refusée avant envoi du contexte.", 503)

    async def verify_model_identity(self):
        state = await self.loaded_state()
        if state["resident"]:
            return {"digest": state["digest"], "source": "/api/ps", "manifest_sha256": state["manifest_sha256"]}
        identity = self.expected_identity()
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            record = next((item for item in response.json().get("models", []) if item.get("name", item.get("model")) == identity["model"]), None)
            if record is None:
                raise ApiError("llm_identity_unverified", "Modèle Qwen provisionné absent des tags locaux.", 503)
            self.verify_digest(record, identity)
            return {"digest": identity["digest"], "source": "/api/tags", "manifest_sha256": identity["manifest_sha256"]}
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise ApiError("ollama_unavailable", "Impossible de vérifier le digest Qwen local à froid.", 503) from error

    def describe(self):
        """État de l'accélération pour `GET /diagnostics` (`llm_accelerator`) ; `reason` est celle du démarrage."""
        fallback = self.execution["fallback"]
        return {key: self.execution[key] for key in ("requested", "requested_source", "mode", "reason")} | {
            "fallback": dict(fallback) if fallback else None}

    def chat_options(self, output_tokens=None, *, cpu=True):
        """Options de /api/chat. `num_gpu: 0` en CPU seulement, à sa place d'avant W024 (corps inchangé octet pour octet) ;
        absent en GPU, llama-server place lui-même les couches."""
        physical_cores = os.cpu_count() or 1
        try:
            import psutil
            physical_cores = psutil.cpu_count(logical=False) or physical_cores
        except ImportError:
            pass
        options = {"num_ctx": self.settings.value("llm", "num_ctx", 8192),
                   "num_predict": output_tokens or self.settings.value("llm", "num_predict", 768),
                   "temperature": self.settings.value("llm", "temperature", 0.2),
                   "top_p": self.settings.value("llm", "top_p", 0.9)}
        if cpu:
            options["num_gpu"] = 0
        options["num_thread"] = min(max(1, int(self.settings.value("llm", "threads_max", 4))), max(1, physical_cores - 1))
        return options

    async def loaded_state(self):
        """Read-only warm admission evidence; unknown/incompatible state stays cold.

        En CPU, un modèle en partie sur le GPU (`size_vram` non nul) serait rechargé par la requête (`num_gpu: 0`) :
        il compte comme froid. En GPU, la requête sans `num_gpu` réutilise le runner chargé, quel qu'il soit (M5).
        """
        model = self.settings.value("llm", "model", "qwen3.5:4b")
        identity = self.expected_identity()
        try:
            response = await self.client.get("/api/ps")
            response.raise_for_status()
            running = next((item for item in response.json().get("models", []) if item.get("name", item.get("model")) == model), None)
            if running is None:
                return {"loaded": False, "resident": False, "model": model, "additional_peak_mib": 0}
            self.verify_digest(running, identity)
            expected_context = self.settings.value("llm", "num_ctx", 8192)
            quantization = running.get("details", {}).get("quantization_level")
            reasons = []
            if running.get("context_length") != expected_context:
                reasons.append("context_mismatch_or_unknown")
            mode = self.execution["mode"]
            if mode == "cpu" and running.get("size_vram") != 0:
                reasons.append("cpu_residency_not_verified")
            if quantization != self.settings.value("llm", "required_quantization", "Q4_K_M"):
                reasons.append("quantization_mismatch_or_unknown")
            size, size_vram = running.get("size"), running.get("size_vram")
            measured = all(isinstance(value, int) and not isinstance(value, bool) for value in (size, size_vram))
            self.placement = processor_label(size, size_vram) if measured else "Unknown"
            return {"loaded": not reasons, "resident": True, "model": model, "digest": running.get("digest"),
                    "identity_verified": True, "manifest_sha256": identity["manifest_sha256"],
                    "context_length": running.get("context_length"), "size_vram": running.get("size_vram"),
                    "resident_size_mib": running.get("size", 0) / (1024 * 1024), "quantization": quantization,
                    "processor": self.placement, "execution_mode": mode,
                    "additional_peak_mib": self.settings.value("resources", "warm_llm_additional_peak_estimate_mib", 512),
                    "estimate_basis": "provisional_incremental_warm_estimate_not_qualified", "cold_reasons": reasons}
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise ApiError("ollama_unavailable", "Impossible de vérifier la résidence CPU/context du modèle.", 503) from error

    async def unload(self):
        """Control call with no documentary prompt; confirm the model leaves /api/ps."""
        model = self.settings.value("llm", "model", "qwen3.5:4b")
        try:
            loaded = await self.client.get("/api/ps")
            loaded.raise_for_status()
            if not any(item.get("name", item.get("model")) == model for item in loaded.json().get("models", [])):
                return {"state": "already_unloaded"}
            response = await self.client.post("/api/generate", json={"model": model, "prompt": "", "stream": False, "think": False, "keep_alive": 0})
            response.raise_for_status()
            result = response.json()
            if result.get("done") is not True or result.get("done_reason") != "unload":
                raise ApiError("ollama_unload_failed", "Le runtime n'a pas confirmé le déchargement du modèle.", 503)
            for _ in range(50):
                status = await self.client.get("/api/ps")
                status.raise_for_status()
                if not any(item.get("name", item.get("model")) == model for item in status.json().get("models", [])):
                    return {"state": "unloaded"}
                await asyncio.sleep(0.1)
            raise ApiError("ollama_unload_failed", "Le modèle demeure résident après déchargement.", 503)
        except (httpx.HTTPError, ValueError) as error:
            raise ApiError("ollama_unavailable", "Impossible de contrôler le runtime local avant ingestion.", 503) from error

    @staticmethod
    async def failure_text(response):
        """Message d'erreur d'Ollama (`{"error": …}`), tronqué ; corps illisible : texte vide."""
        raw = bytearray()
        try:
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw) >= FALLBACK_BODY_LIMIT:
                    break
        except httpx.HTTPError:
            pass
        text = raw.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("error"), str):
            text = parsed["error"]
        return " ".join(text.split())[:FALLBACK_ERROR_CHARS]

    async def fall_back_to_cpu(self, http_status, error, cancel_event):
        """Repli W025 après un échec du chargement sur GPU, avant tout événement : instance en CPU jusqu'au redémarrage.

        Le modèle est déchargé ; un déchargement non confirmé est consigné dans le journal de l'API sans empêcher le
        repli (B4), la requête avec `num_gpu: 0` imposant de toute façon un rechargement (`needsReload`). L'admission du
        bail a pu être « chaude » (modèle résident sur le GPU) : la relance attend une nouvelle admission à froid (H1).
        """
        self.execution["fallback"] = {"utc": datetime.now(UTC).isoformat(), "http_status": http_status, "error": error}
        self.execution["mode"] = "cpu"
        logger.warning("Génération sur GPU refusée par Ollama (HTTP %s : %s) ; repli sur CPU jusqu'au redémarrage.", http_status, error)
        try:
            await self.unload()
        except ApiError as failure:
            logger.warning("Repli sur CPU : déchargement du modèle non confirmé (%s : %s) ; relance maintenue.", failure.code, failure.message)
        self.placement = None
        if cancel_event.is_set():
            raise asyncio.CancelledError
        if self.before_cpu_fallback is not None:
            await self.before_cpu_fallback()
        if cancel_event.is_set():
            raise asyncio.CancelledError

    async def stream(self, messages, cancel_event, output_tokens=None):
        if cancel_event.is_set():
            raise asyncio.CancelledError
        model_identity = await self.verify_model_identity()
        received_done = False
        fallback = False
        try:
            while True:
                cpu = self.execution["mode"] != "gpu"
                body = {"model": self.settings.value("llm", "model", "qwen3.5:4b"), "messages": messages,
                        "stream": True, "think": False, "keep_alive": self.settings.value("llm", "keep_alive", "10m"),
                        "options": self.chat_options(output_tokens, cpu=cpu)}
                failure = None
                async with self.client.stream("POST", "/api/chat", json=body) as response:
                    if not cpu and response.status_code == FALLBACK_STATUS:
                        failure = await self.failure_text(response)
                    else:
                        response.raise_for_status()
                        lines = response.aiter_lines().__aiter__()
                        while True:
                            line_task = asyncio.ensure_future(anext(lines))
                            cancel_task = asyncio.create_task(cancel_event.wait())
                            try:
                                done, pending = await asyncio.wait({line_task, cancel_task}, return_when=asyncio.FIRST_COMPLETED)
                            except asyncio.CancelledError:
                                line_task.cancel()
                                cancel_task.cancel()
                                await asyncio.gather(line_task, cancel_task, return_exceptions=True)
                                raise
                            if cancel_task in done:
                                line_task.cancel()
                                await asyncio.gather(line_task, return_exceptions=True)
                                await response.aclose()
                                raise asyncio.CancelledError
                            cancel_task.cancel()
                            await asyncio.gather(cancel_task, return_exceptions=True)
                            try:
                                line = line_task.result()
                            except StopAsyncIteration:
                                break
                            if not line:
                                continue
                            event = json.loads(line)
                            if event.get("error"):
                                raise ApiError("ollama_failure", "Le runtime local a refusé la génération.", 503)
                            message = event.get("message", {})
                            if message.get("tool_calls") or message.get("thinking"):
                                raise ApiError("unexpected_llm_behavior", "Le modèle a produit un mode non autorisé.", 503)
                            if message.get("content"):
                                yield {"type": "delta", "text": message["content"]}
                            if event.get("done"):
                                received_done = True
                                yield {"type": "done", "finish_reason": event.get("done_reason", "stop"),
                                       "metrics": {**{key: event.get(key, "unknown") for key in ("prompt_eval_count", "prompt_eval_cached_count", "eval_count", "total_duration", "load_duration", "prompt_eval_duration", "eval_duration")},
                                                   "verified_model_identity": model_identity,
                                                   "llm_execution": {"mode": "cpu" if cpu else "gpu", "fallback": fallback}}}
                                break
                if failure is None:
                    break
                # Une seule relance : le mode vaut désormais cpu, un nouvel échec est rapporté sans repli.
                await self.fall_back_to_cpu(FALLBACK_STATUS, failure, cancel_event)
                fallback = True
                # Nouvelle admission obtenue : l'appelant peut annoncer que la génération reprend, sur CPU.
                yield {"type": "cpu_fallback"}
            if not received_done:
                raise ApiError("incomplete_generation", "Flux Ollama terminé sans marqueur final.", 503)
        except (httpx.HTTPError, ValueError) as error:
            raise ApiError("ollama_unavailable", "Runtime Ollama local indisponible.", 503) from error
        if self.execution["mode"] == "gpu":
            # Hors du flux : l'événement done, son enregistrement et la durée de la réponse n'attendent pas /api/ps.
            task = asyncio.create_task(self.observe_placement())
            self.placement_reads.add(task)
            task.add_done_callback(self.placement_reads.discard)

    async def observe_placement(self):
        """Occupation du modèle relue après une réponse en mode GPU (P7) : llama-server a pu le charger en partie, ou en
        totalité, sur le CPU. Lancée en tâche de fond après la réponse, bornée à PLACEMENT_READ_SECONDS ; une lecture en
        échec garde la précédente."""
        try:
            await asyncio.wait_for(self.loaded_state(), PLACEMENT_READ_SECONDS)
        except ApiError as failure:
            logger.info("Occupation du modèle non relue après la réponse (%s : %s).", failure.code, failure.message)
        except TimeoutError:
            logger.info("Occupation du modèle non relue après la réponse : /api/ps sans réponse en %s s.", PLACEMENT_READ_SECONDS)
