"""Pièces du contrôle réel (DIST-05) : PDF synthétique, profil de l'instance de contrôle, racine temporaire courte."""

import pypdfium2 as pdfium
import yaml

from services.runtime.artifacts import ROOT, runtime_location
from services.runtime.selftest import control_profile, short_root, synthetic_pdf
from services.runtime.supervisor import data_path, load_profile, qdrant_data_path

BASE = ROOT / "config/local16.yaml"


def test_synthetic_pdf_carries_the_control_code_in_its_native_text_layer():
    document = pdfium.PdfDocument(synthetic_pdf("AUTOTEST-ABC123"))
    try:
        assert len(document) == 1
        text = document[0].get_textpage().get_text_range()
    finally:
        document.close()
    assert "Contrôle de l'atelier documentaire." in text
    assert "La pression nominale du banc AUTOTEST-ABC123 est de 3,1 bar." in text


def test_control_profile_isolates_data_and_ports_but_shares_the_host_heavy_lock(tmp_path):
    root = short_root()
    try:
        path = control_profile(BASE, root)
        profile = load_profile(path)
        base = load_profile(BASE)
        assert data_path(profile) == (root / "data").resolve() and qdrant_data_path(profile, data_path(profile)) == (root / "q").resolve()
        assert len(str(root / "q" / "storage")) <= 57
        assert runtime_location(profile, "host_lock_path") == runtime_location(base, "host_lock_path")
        assert runtime_location(profile, "backups_dir") == root / "backups"
        ports = {profile["app"]["port"], yaml.safe_load(path.read_text(encoding="utf-8"))["qdrant"]["url"].rsplit(":", 1)[1], profile["llm"]["base_url"].rsplit(":", 1)[1]}
        assert len(ports) == 3 and base["app"]["port"] not in ports
    finally:
        for item in sorted(root.rglob("*"), reverse=True):
            item.unlink() if item.is_file() else item.rmdir()
        root.rmdir()


# --- Matériel de la génération (W024, W025 P7) -------------------------------------------------------------------------

def test_the_start_step_names_the_generation_hardware_of_the_control_instance(monkeypatch):
    from services.runtime import selftest as module
    from tests.unit.test_runtime_accelerator import ORIN

    accelerator = {"requested": "auto", "requested_source": "profile", "mode": "gpu", "reason": "gpu_discovered",
                   "device": ORIN, "variant": "cuda_jetpack5", "qualified": True}
    monkeypatch.setattr(module, "start", lambda path: {"status": "running", "instance_id": "controle",
                                                       "accelerator": accelerator})
    report = module.selftest(BASE, generation=False)
    launch = next(item for item in report["steps"] if item["step"] == "démarrage")
    assert launch["status"] == "PASS"
    assert launch["detail"] == ("instance controle démarrée, génération sur GPU, Orin (CUDA, GPU intégré, bibliothèques "
                                "cuda_jetpack5)")
    assert report["generation_mode"] == {"requested": "auto", "mode": "gpu", "reason": "gpu_discovered",
                                         "variant": "cuda_jetpack5"}
    assert report["root_removed"] is True


def test_the_answer_step_reads_the_processor_of_the_control_ollama(monkeypatch):
    import httpx

    from services.runtime.selftest import execution_text, model_processor

    profile = load_profile(BASE)
    routes = {"/api/ps": {"models": [{"name": profile["llm"]["model"], "size": 100, "size_vram": 52}]}}

    def answer(request):
        return httpx.Response(200, json=routes[request.url.path])

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(answer)))
    assert model_processor(profile) == "48%/52% CPU/GPU"
    routes["/api/ps"] = {"models": []}
    assert model_processor(profile) is None
    assert execution_text({"llm_execution": {"mode": "gpu", "fallback": False}}, "100% GPU") == "modèle chargé : 100% GPU"
    assert execution_text({"llm_execution": {"mode": "cpu", "fallback": True}}, "100% CPU") == (
        "modèle chargé : 100% CPU ; repli sur CPU après un échec du chargement sur le GPU")
    assert execution_text({}, None) == "occupation du modèle non lue"
    # Colonne « Unknown » d'Ollama (size_vram supérieur à size) : rien n'est lu comme une répartition (revue J11 web-4).
    assert execution_text({}, "Unknown") == "répartition du modèle entre GPU et CPU non déterminée par Ollama"


def test_the_start_step_of_a_cpu_instance_names_its_reason_without_nested_parentheses(monkeypatch):
    from services.runtime import selftest as module

    accelerator = {"requested": "cpu", "requested_source": "profile", "mode": "cpu", "reason": "imposed_by_profile",
                   "device": None, "variant": None, "qualified": False}
    monkeypatch.setattr(module, "start", lambda path: {"status": "running", "instance_id": "controle",
                                                       "accelerator": accelerator})
    report = module.selftest(BASE, generation=False)
    launch = next(item for item in report["steps"] if item["step"] == "démarrage")
    assert launch["detail"] == "instance controle démarrée, génération sur CPU, imposée par le profil (llm.accelerator: cpu)"


def test_model_processor_without_ollama_is_none(monkeypatch):
    import httpx

    from services.runtime.selftest import model_processor

    def refused(request):
        raise httpx.ConnectError("refusé", request=request)

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(refused)))
    assert model_processor(load_profile(BASE)) is None
