"""Pilote de calibration (W024, W025) : `cpu` par défaut, requêtes d'avant W024 octet pour octet ; `auto` exige un GPU.

Le pilote est exercé sans Ollama réel : Job, exécutable, disponibilité, verrou lourd et tokenizer sont des doubles, et
les réponses d'Ollama passent par un transport httpx simulé. Aucune écriture sous `.runtime` ni sur le verrou lourd réel
du poste ; le port 11444 du service pilote n'est pas ouvert.
"""

import json
import os
from contextlib import nullcontext
from types import SimpleNamespace

import httpx
import pytest
import yaml

from services.runtime import calibration
from services.runtime.artifacts import ROOT
from tests.unit.test_runtime_accelerator import JETSON, JETSON_BASE_ONLY, JETSON_JETPACK5, ORIN, _verified

PROFILE = ROOT / "config/local16.yaml"
MESSAGES = [{"role": "system", "content": "Tu réponds en français."}, {"role": "user", "content": "Question ?"}]


def test_cpu_body_is_byte_for_byte_the_body_before_w024():
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    # Corps de la révision ba945af (calibration.py, l. 88-95), reconstruit tel quel.
    before = {"model": profile["llm"]["model"], "messages": MESSAGES, "think": False,
              "stream": True, "keep_alive": profile["llm"].get("keep_alive", "10m"), "options": {
                  "num_ctx": profile["llm"]["num_ctx"], "num_predict": 64, "num_gpu": 0,
                  "num_thread": 4, "temperature": profile["llm"]["temperature"],
                  "top_p": profile["llm"]["top_p"]}}
    for use_mmap in (None, False):
        expected = json.loads(json.dumps(before))
        if use_mmap is not None:
            expected["options"]["use_mmap"] = use_mmap
        body = calibration.chat_body(profile, MESSAGES, output_limit=64, threads=4, use_mmap=use_mmap, accelerator="cpu")
        assert json.dumps(body, ensure_ascii=False).encode() == json.dumps(expected, ensure_ascii=False).encode()


def test_auto_body_omits_num_gpu_and_keeps_every_other_option():
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    cpu = calibration.chat_body(profile, MESSAGES, output_limit=64, threads=4, use_mmap=None, accelerator="cpu")
    auto = calibration.chat_body(profile, MESSAGES, output_limit=64, threads=4, use_mmap=None, accelerator="auto")
    assert "num_gpu" not in auto["options"]
    assert auto["options"] == {key: value for key, value in cpu["options"].items() if key != "num_gpu"}
    assert {key: value for key, value in auto.items() if key != "options"} == {
        key: value for key, value in cpu.items() if key != "options"}


@pytest.mark.parametrize(("accelerator", "resident", "message"), [
    ("cpu", [{"size": 100, "size_vram": 1}], "Le modèle pilote a utilisé le GPU"),
    ("auto", [{"size": 100, "size_vram": 0}], "Le modèle pilote n'a pas été chargé sur le GPU"),
    ("auto", [], "Le modèle pilote n'a pas été chargé sur le GPU"),
])
def test_residency_is_refused_when_it_contradicts_the_requested_hardware(accelerator, resident, message):
    with pytest.raises(RuntimeError, match=message):
        calibration.check_residency(resident, accelerator)


@pytest.mark.parametrize(("accelerator", "resident"), [
    ("cpu", [{"size": 100, "size_vram": 0}]), ("auto", [{"size": 100, "size_vram": 100}]),
    ("auto", [{"size": 100, "size_vram": 52}])])
def test_residency_matching_the_requested_hardware_is_accepted(accelerator, resident):
    calibration.check_residency(resident, accelerator)


class Tokenizer:
    def __init__(self, settings):
        pass

    def count_messages(self, messages):
        return sum(len(message["content"]) for message in messages) // 4


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    """calibrate() avec doubles ; renvoie (rapport, corps envoyés) pour un journal de service et une résidence donnés."""
    import psutil

    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    manifest = tmp_path / "ollama-model-text.json"
    manifest.write_text("{}", encoding="utf-8")
    profile["llm"]["model_manifest"] = str(manifest)
    profile_path = tmp_path / "profil.yaml"
    profile_path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr("services.api.settings.Settings.load", classmethod(lambda cls, path=None: SimpleNamespace()))
    monkeypatch.setattr("services.api.context.LlmTokenizer", Tokenizer)

    class Socket:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def bind(self, address):
            assert address == ("127.0.0.1", 11444)

    # Sonde du port 11444 par port_probe (règle de check_ports), sans réseau.
    monkeypatch.setattr(calibration, "port_probe", Socket)
    monkeypatch.setattr(calibration, "acquire_host_heavy_lock", lambda *args: nullcontext())
    monkeypatch.setattr(calibration, "native_paths", lambda: {"ollama": tmp_path / "ollama"})
    monkeypatch.setattr(calibration, "wait_http", lambda *args, **kwargs: {"version": "0.35.0"})
    monkeypatch.setattr(calibration, "send_owned_console_interrupt", lambda *args: True)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=8192 * 1048576))
    swap = iter([2048, 2048, 1900, 1900, 1950] + [2000] * 1000)
    monkeypatch.setattr(psutil, "swap_memory", lambda: SimpleNamespace(free=next(swap) * 1048576))
    monkeypatch.setattr(calibration, "host_signals", lambda: JETSON)
    # Mémoire totale lue par la décision : celle du poste de l'essai réel du 02/10 (62 800 Mio).
    meminfo = tmp_path / "meminfo"
    meminfo.write_bytes(b"MemTotal:       64307708 kB\n")
    monkeypatch.setattr("services.runtime.accelerator.MEMINFO", meminfo)
    monkeypatch.setattr(calibration, "gpu_libraries", lambda signals: _verified("cuda_jetpack5"))

    def run(accelerator: str, log: str, size_vram: int):
        sent: list[bytes] = []

        class Child:
            pid = os.getpid()

            def wait(self, timeout=30):
                return 0

        class Job:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def launch(self, argv, *, cwd, env, log_path):
                log_path.write_text(log, encoding="utf-8")
                return Child()

            def close(self):
                pass

        monkeypatch.setattr(calibration, "ProcessJob", Job)

        def answer(request):
            if request.url.path == "/api/chat":
                sent.append(request.content)
                events = [{"message": {"content": "Réponse synthétique."}},
                          {"done": True, "done_reason": "stop", "eval_count": 12}]
                return httpx.Response(200, content="".join(json.dumps(item) + "\n" for item in events).encode())
            if request.url.path == "/api/ps":
                return httpx.Response(200, json={"models": [{"name": profile["llm"]["model"], "size": 3107811491,
                                                             "size_vram": size_vram}]})
            raise AssertionError(f"route inattendue : {request.url.path}")

        real_client = httpx.Client
        monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(answer)))
        output = tmp_path / f"pilote-{accelerator}-{len(list(tmp_path.glob('pilote-*.json')))}.json"
        try:
            report = calibration.calibrate(profile_path, output, input_target=40, accelerator=accelerator)
        except RuntimeError as error:
            return json.loads(output.read_text(encoding="utf-8")), sent, error
        return report, sent, None

    return profile, run


def test_cpu_pilot_sends_num_gpu_zero_and_records_swap(pilot):
    profile, run = pilot
    report, sent, error = run("cpu", JETSON_BASE_ONLY, 0)
    assert error is None and report["status"] == "PASS_PILOT_ONLY" and len(sent) == 3
    for content in sent:
        body = json.loads(content)
        assert body["options"]["num_gpu"] == 0 and list(body["options"]) == [
            "num_ctx", "num_predict", "num_gpu", "num_thread", "temperature", "top_p"]
    assert report["scope"] == "Early QCPU controlled pilot; not the final performance qualification"
    assert report["accelerator"] == {"requested": "cpu"}
    assert [trial["processor"] for trial in report["trials"]] == ["100% CPU"] * 3
    # SwapFree relevé avec MemAvailable (W025, revue M1).
    assert report["baseline_swap_free_mib"] == 2048 and all("swap_free_mib" in item for item in report["samples"])
    assert report["max_swap_free_drop_mib"] == 2048 - report["minimum_swap_free_mib"]


def test_cpu_pilot_refuses_a_model_loaded_on_the_gpu(pilot):
    _, run = pilot
    _, _, error = run("cpu", JETSON_JETPACK5, 3107811491)
    assert str(error) == "Le modèle pilote a utilisé le GPU"


def test_gpu_pilot_omits_num_gpu_and_records_the_discovery(pilot):
    profile, run = pilot
    report, sent, error = run("auto", JETSON_JETPACK5, 3107811491)
    assert error is None and report["status"] == "PASS_PILOT_ONLY"
    assert all("num_gpu" not in json.loads(content)["options"] for content in sent) and len(sent) == 3
    assert report["scope"] == "Early GPU pilot on this host; never a D07 measurement"
    accelerator = report["accelerator"]
    assert accelerator["requested"] == "auto" and accelerator["discovery"]["devices"] == [ORIN]
    assert (accelerator["decision"]["mode"], accelerator["decision"]["reason"]) == ("gpu", "gpu_discovered")
    assert [trial["processor"] for trial in report["trials"]] == ["100% GPU"] * 3


def test_gpu_pilot_is_refused_without_a_discovered_gpu_before_any_request(pilot):
    _, run = pilot
    report, sent, error = run("auto", JETSON_BASE_ONLY, 0)
    assert sent == [] and report["status"] == "REFUSED_NO_USABLE_GPU"
    assert str(error).startswith("Pilote GPU refusé : Ollama n'a découvert aucun GPU utilisable ; journal ")
    assert str(error).endswith(".service.log.")


def test_gpu_pilot_fails_when_the_model_stays_on_the_cpu(pilot):
    _, run = pilot
    _, _, error = run("auto", JETSON_JETPACK5, 0)
    assert str(error) == "Le modèle pilote n'a pas été chargé sur le GPU"


def test_an_unknown_accelerator_is_refused(tmp_path):
    with pytest.raises(ValueError, match="cpu ou auto"):
        calibration.calibrate(PROFILE, tmp_path / "rapport.json", accelerator="gpu")
    assert not (tmp_path / "rapport.json").exists()


def test_the_refusal_and_the_help_name_neither_an_internal_decision_nor_a_non_nvidia_gpu():
    # Revue J11 (web-5, runtime-7) : GPU NVIDIA écarté par CUDA, vu seulement par Vulkan ; aide de la ligne de commande.
    import subprocess
    import sys

    from services.runtime.accelerator import parse_discovery, resolve_mode
    from tests.unit.test_runtime_accelerator import DISCOVERING

    vulkan = ('time=x level=INFO source=types.go:32 msg="inference compute" id=0 filter_id="" library=Vulkan '
              'compute=0.0 name=Vulkan0 description="NVIDIA GeForce GTX 1060 6GB" libdirs=ollama,vulkan driver=0.0 '
              'pci_id=0000:01:00.0 type=discrete total="6.0 GiB" available="5.2 GiB"\n')
    decision = resolve_mode({"requested": "gpu", "requested_source": "calibration"},
                            parse_discovery(DISCOVERING + vulkan), _verified("vulkan"), "windows-x86_64")
    assert calibration.gpu_refusal({"decision": decision, "log": "pilote.service.log"}) == (
        "Pilote GPU refusé : GPU NVIDIA vu seulement par Vulkan, CUDA ne l'a pas retenu : pilote ou capacité de calcul ; "
        "journal pilote.service.log.")
    shown = subprocess.run([sys.executable, "-m", "services.runtime.calibration", "--help"], cwd=ROOT,
                           capture_output=True, text=True, timeout=120, check=True).stdout
    assert "W02" not in shown and "comme avant l'accélération GPU" in " ".join(shown.split())
