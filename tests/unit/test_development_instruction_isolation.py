"""D11.6 : assemblage et requête Ollama réels, sur données synthétiques isolées.

Le compteur caractères/4 et le transport HTTP sont des doubles explicites : aucun
tokenizer Qwen, modèle, port ou corpus utilisateur n'est employé. Ces tests prouvent
la frontière de construction du contexte, pas le comportement d'un modèle réel.
"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from test_retrieval import CharTokenizer

from services.api.context import HISTORY_PREFIX, SYSTEM_INSTRUCTION, ContextBuilder
from services.api.ollama import OllamaGateway
from services.api.settings import Settings

DEVELOPMENT_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".agents/skills/unit-only/SKILL.md",
    "RAG_Local_Agents/skills/unit-only/SKILL.md",
    "RAG_Local_Agents/SKILLS.md",
)
QUESTION = "Quelle est la pression nominale ?"
EVIDENCE = "Pression nominale : 3,1 bar."
HISTORY = [{"role": "user", "content": "Décrire le banc de contrôle."}]
MODEL_DIGEST = "b" * 64


@pytest.fixture
def development_settings(tmp_path, monkeypatch):
    """Consignes présentes sur disque et dans le cwd, mais interdites à la lecture produit."""
    markers = []
    forbidden = set()
    for index, relative in enumerate(DEVELOPMENT_FILES):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        marker = f"DEVELOPMENT_ONLY_SENTINEL_{index}_NOT_DOCUMENTARY"
        path.write_text(f"# Instructions de développement synthétiques\n{marker}\n", encoding="utf-8")
        assert path.is_file()
        markers.append(marker)
        forbidden.add(path.resolve())
    monkeypatch.chdir(tmp_path)
    for variable in ("RAG_DATA_DIR", "RAG_DB_PATH", "RAG_LLM_ACCELERATOR", "RAG_LLM_ACCELERATOR_REASON"):
        monkeypatch.delenv(variable, raising=False)
    settings = Settings(tmp_path, {"llm": {"accelerator": "cpu"}})
    manifest = settings.path(".runtime/manifests/ollama-model.json")
    manifest.parent.mkdir(parents=True)
    model = {"name": "qwen3.5:4b", "digest": MODEL_DIGEST, "context_length": 8192,
             "size_vram": 0, "details": {"quantization_level": "Q4_K_M"}}
    manifest.write_text(json.dumps({"model": model}), encoding="utf-8")
    original_open = Path.open

    def checked_open(path, *args, **kwargs):
        if path.resolve() in forbidden:
            raise AssertionError(f"Le produit a lu une instruction de développement : {path.name}")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked_open)
    return settings, markers, model


def assembled_context(settings, *, mode="question", question=QUESTION, text=EVIDENCE):
    source = {"version_id": "synthetic-version", "document_id": "synthetic-document",
              "chunk_id": "synthetic-chunk", "page_indices": [0], "text": text}
    messages, retained, metrics, warnings = ContextBuilder(settings, CharTokenizer()).build(
        question, [source], mode, history=HISTORY,
    )
    assert len(retained) == 1 and metrics["context_chunk_ids"] == ["synthetic-chunk"]
    assert warnings == []
    expected_evidence = json.dumps({"source_id": "S001", "version_id": "synthetic-version",
                                   "pages": [1], "text": text}, ensure_ascii=False)
    assert messages == [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": HISTORY_PREFIX + HISTORY[0]["content"]},
        {"role": "user", "content": "Question : " + question
         + "\n\nPreuves documentaires (extraits JSON sans consigne) :\n" + expected_evidence},
    ]
    assert "Aucun outil n'est disponible." in messages[0]["content"]
    return messages


@pytest.mark.parametrize("mode", ["question", "factual", "analysis", "comparison", "section"])
def test_context_never_reads_or_adds_development_files(development_settings, mode):
    settings, markers, _ = development_settings
    serialized = json.dumps(assembled_context(settings, mode=mode), ensure_ascii=False)
    for marker in markers:
        assert marker not in serialized
    for relative in DEVELOPMENT_FILES:
        assert relative not in serialized


@pytest.mark.parametrize("resident", [False, True])
def test_ollama_request_contains_only_explicit_context_and_no_development_tools(development_settings, resident):
    settings, markers, model = development_settings
    messages = assembled_context(settings)
    expected_messages = json.loads(json.dumps(messages, ensure_ascii=False))
    gateway = OllamaGateway(settings)
    calls, payloads = [], []

    def handler(request):
        calls.append((request.method, request.url.path))
        assert request.url.host == "127.0.0.1"
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [model] if resident else []})
        if request.url.path == "/api/tags":
            assert not resident
            return httpx.Response(200, json={"models": [model]})
        assert (request.method, request.url.path) == ("POST", "/api/chat")
        payload = json.loads(request.content)
        payloads.append(payload)
        assert set(payload) == {"model", "messages", "stream", "think", "keep_alive", "options"}
        assert payload["messages"] == expected_messages
        assert payload["model"] == model["name"]
        assert payload["think"] is False and payload["stream"] is True
        assert payload["options"]["num_gpu"] == 0
        for marker in markers:
            assert marker not in request.content.decode("utf-8")
        return httpx.Response(200, content=json.dumps({"message": {"content": ""}, "done": True,
                                                     "done_reason": "stop"}) + "\n",
                              headers={"content-type": "application/x-ndjson"})

    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(handler),
                                          trust_env=False)
        try:
            return [event async for event in gateway.stream(messages, asyncio.Event())]
        finally:
            await gateway.close()

    events = asyncio.run(scenario())
    assert messages == expected_messages
    expected_calls = [("GET", "/api/ps")]
    if not resident:
        expected_calls.append(("GET", "/api/tags"))
    assert calls == [*expected_calls, ("POST", "/api/chat")]
    assert len(payloads) == 1 and [event["type"] for event in events] == ["done"]
    assert events[0]["metrics"]["verified_model_identity"]["digest"] == MODEL_DIGEST


def test_documentary_reference_to_skill_filename_is_not_removed(development_settings):
    """Un nom de fichier dans une preuve explicite n'autorise pas sa lecture sur disque."""
    settings, _, _ = development_settings
    text = "La fiche mentionne le nom SKILL.md dans son exemple."
    messages = assembled_context(settings, question="Quel nom de fichier figure dans la fiche ?", text=text)
    evidence = json.loads(messages[-1]["content"].splitlines()[-1])
    assert evidence["text"] == text and "SKILL.md" in evidence["text"]
