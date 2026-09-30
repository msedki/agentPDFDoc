import asyncio
import hashlib
import json
import os
import re

import httpx

from .errors import ApiError


class OllamaGateway:
    def __init__(self, settings):
        self.settings = settings
        self.base_url = settings.value("llm", "base_url", "http://127.0.0.1:11434")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(settings.value("llm", "idle_read_timeout_seconds", 300), connect=5), trust_env=False)

    async def close(self):
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

    async def loaded_state(self):
        """Read-only warm admission evidence; unknown/incompatible state stays cold."""
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
            if running.get("size_vram") != 0:
                reasons.append("cpu_residency_not_verified")
            if quantization != self.settings.value("llm", "required_quantization", "Q4_K_M"):
                reasons.append("quantization_mismatch_or_unknown")
            return {"loaded": not reasons, "resident": True, "model": model, "digest": running.get("digest"),
                    "identity_verified": True, "manifest_sha256": identity["manifest_sha256"],
                    "context_length": running.get("context_length"), "size_vram": running.get("size_vram"),
                    "resident_size_mib": running.get("size", 0) / (1024 * 1024), "quantization": quantization,
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

    async def stream(self, messages, cancel_event, output_tokens=None):
        if cancel_event.is_set():
            raise asyncio.CancelledError
        model_identity = await self.verify_model_identity()
        physical_cores = os.cpu_count() or 1
        try:
            import psutil
            physical_cores = psutil.cpu_count(logical=False) or physical_cores
        except ImportError:
            pass
        body = {"model": self.settings.value("llm", "model", "qwen3.5:4b"), "messages": messages,
                "stream": True, "think": False, "keep_alive": self.settings.value("llm", "keep_alive", "10m"),
                "options": {"num_ctx": self.settings.value("llm", "num_ctx", 8192),
                            "num_predict": output_tokens or self.settings.value("llm", "num_predict", 768),
                            "temperature": self.settings.value("llm", "temperature", 0.2),
                            "top_p": self.settings.value("llm", "top_p", 0.9), "num_gpu": 0,
                            "num_thread": min(max(1, int(self.settings.value("llm", "threads_max", 4))), max(1, physical_cores - 1))}}
        received_done = False
        try:
            async with self.client.stream("POST", "/api/chat", json=body) as response:
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
                                           "verified_model_identity": model_identity}}
                        break
            if not received_done:
                raise ApiError("incomplete_generation", "Flux Ollama terminé sans marqueur final.", 503)
        except (httpx.HTTPError, ValueError) as error:
            raise ApiError("ollama_unavailable", "Runtime Ollama local indisponible.", 503) from error
