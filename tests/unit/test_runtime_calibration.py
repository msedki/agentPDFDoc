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


class FakeOllamaProcess:
    """Double nommé du processus Ollama possédé : sa mémoire (USS) est lue dans l'état partagé du pilote simulé."""

    def __init__(self, memory: dict):
        self.pid = os.getpid()
        self.memory = memory


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    """calibrate() avec doubles ; renvoie (rapport, corps envoyés) pour un journal de service et une résidence donnés.

    Mémoire simulée : `memory["available"]` (MemAvailable) et `memory["uss"]` (USS du seul processus Ollama double),
    fixées par la k-ième requête /api/chat d'après `lows`/`uss` ; elles restent à ce niveau jusqu'à la requête suivante,
    comme un modèle qui reste résident après un essai.
    """
    import psutil

    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    manifest = tmp_path / "ollama-model-text.json"
    manifest.write_text("{}", encoding="utf-8")
    profile["llm"]["model_manifest"] = str(manifest)
    profile_path = tmp_path / "profil.yaml"
    profile_path.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr("services.api.settings.Settings.load", classmethod(lambda cls, path=None: SimpleNamespace()))
    monkeypatch.setattr("services.api.context.LlmTokenizer", Tokenizer)
    memory = {"available": 8192.0, "uss": 0.0}
    monkeypatch.setattr(calibration, "process_tree", lambda pid: [FakeOllamaProcess(memory)])
    monkeypatch.setattr(calibration, "linux_memory_mib", lambda process: {
        "rss_mib": process.memory["uss"], "uss_mib": process.memory["uss"], "pss_mib": None})

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
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=memory["available"] * 1048576))
    swap = iter([2048, 2048, 1900, 1900, 1950] + [2000] * 1000)
    monkeypatch.setattr(psutil, "swap_memory", lambda: SimpleNamespace(free=next(swap) * 1048576))
    monkeypatch.setattr(calibration, "host_signals", lambda: JETSON)
    # Mémoire totale lue par la décision : celle du poste de l'essai réel du 02/10 (62 800 Mio).
    meminfo = tmp_path / "meminfo"
    meminfo.write_bytes(b"MemTotal:       64307708 kB\n")
    monkeypatch.setattr("services.runtime.accelerator.MEMINFO", meminfo)
    monkeypatch.setattr(calibration, "gpu_libraries", lambda signals: _verified("cuda_jetpack5"))

    # Client httpx réel capturé une fois : un second passage dans le même test ne doit pas envelopper le double.
    real_client = httpx.Client

    def run(accelerator: str, log: str, size_vram: int, *, lows: list[float] | None = None, uss: list[float] | None = None,
            eval_counts: list[int] | None = None, **options):
        sent: list[bytes] = []
        memory.update(available=8192.0, uss=0.0)

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
                index = len(sent)
                sent.append(request.content)
                if lows is not None:
                    memory["available"] = lows[index]
                if uss is not None:
                    memory["uss"] = uss[index]
                count = eval_counts[index] if eval_counts is not None else 12
                # Durée de génération Ollama en nanosecondes : 50 tokens par seconde.
                events = [{"message": {"content": "Réponse synthétique."}},
                          {"done": True, "done_reason": "stop", "eval_count": count, "eval_duration": count * 20_000_000}]
                return httpx.Response(200, content="".join(json.dumps(item) + "\n" for item in events).encode())
            if request.url.path == "/api/ps":
                return httpx.Response(200, json={"models": [{"name": profile["llm"]["model"], "size": 3107811491,
                                                             "size_vram": size_vram}]})
            raise AssertionError(f"route inattendue : {request.url.path}")

        monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(answer)))
        output = tmp_path / f"pilote-{accelerator}-{len(list(tmp_path.glob('pilote-*.json')))}.json"
        try:
            report = calibration.calibrate(profile_path, output, input_target=40, accelerator=accelerator, **options)
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


SERIES_LABELS = ["cold", "warm_same_prefix", "warm_new_content", "warm_series_1", "warm_series_2", "warm_series_3"]


def test_new_options_leave_the_three_existing_cpu_requests_byte_for_byte_unchanged(pilot):
    _, run = pilot
    _, plain, error = run("cpu", JETSON_BASE_ONLY, 0)
    assert error is None and len(plain) == 3
    report, extended, error = run("cpu", JETSON_BASE_ONLY, 0, warm_series=3, long_output=768)
    assert error is None and report["status"] == "PASS_PILOT_ONLY"
    assert extended[:3] == plain
    assert [trial["label"] for trial in report["trials"]] == [*SERIES_LABELS, "long_output"]
    assert list(report["serialized_tokens_by_trial"]) == [*SERIES_LABELS, "long_output"]


def test_warm_series_sends_new_distinct_contents_with_the_same_options(pilot):
    _, run = pilot
    _, sent, error = run("cpu", JETSON_BASE_ONLY, 0, warm_series=3)
    bodies = [json.loads(content) for content in sent]
    assert error is None and len(bodies) == 6
    users = [body["messages"][1]["content"] for body in bodies]
    assert users[0] == users[1]
    # Contenu neuf existant puis trois contenus de série : quatre textes distincts, aucun égal au texte froid.
    assert len(set(users[2:])) == 4 and users[0] not in users[2:]
    assert all(body["messages"][0] == bodies[0]["messages"][0] for body in bodies)
    assert all(body["options"] == bodies[0]["options"] for body in bodies)


def test_long_output_trial_asks_for_a_long_answer_under_its_own_limit(pilot):
    _, run = pilot
    report, sent, error = run("cpu", JETSON_BASE_ONLY, 0, long_output=768)
    bodies = [json.loads(content) for content in sent]
    assert error is None and len(bodies) == 4
    long_body = bodies[-1]
    assert long_body["options"]["num_predict"] == 768 and long_body["options"]["num_gpu"] == 0
    assert ({key: value for key, value in long_body["options"].items() if key != "num_predict"}
            == {key: value for key, value in bodies[0]["options"].items() if key != "num_predict"})
    text = long_body["messages"][1]["content"]
    assert text not in {body["messages"][1]["content"] for body in bodies[:-1]}
    assert "au moins 600 mots" in text
    assert report["trials"][-1]["output_limit"] == 768 and report["output_limit"] == 64
    assert report["long_output_limit"] == 768 and report["warm_series"] == 0


def test_each_trial_is_measured_just_before_its_submission_and_reports_its_own_drop(pilot):
    _, run = pilot
    lows = [5000.0, 4990.0, 4800.0, 4790.0]
    uss = [3000.0, 3005.0, 3150.0, 3160.0]
    report, _, error = run("cpu", JETSON_BASE_ONLY, 0, warm_series=1, lows=lows, uss=uss)
    assert error is None
    trials = report["trials"]
    # Mesure avant soumission : niveau laissé par l'essai précédent (le modèle reste résident), base initiale avant le froid.
    assert [trial["pre_trial_available_mib"] for trial in trials] == [8192.0, 5000.0, 4990.0, 4800.0]
    assert [trial["drop_from_pre_trial_mib"] for trial in trials] == [3192.0, 10.0, 190.0, 10.0]
    assert [trial["pre_trial_ollama_uss_mib"] for trial in trials] == [0.0, 3000.0, 3005.0, 3150.0]
    assert [trial["post_trial_ollama_uss_mib"] for trial in trials] == uss
    assert all(trial["pre_trial_swap_free_mib"] >= 0 for trial in trials)
    boundaries = [(sample["trial"], sample["phase"]) for sample in report["samples"] if sample["phase"] != "during_trial"]
    assert boundaries == [(label, phase) for label in SERIES_LABELS[:4] for phase in ("pre_trial", "post_trial")]
    assert report["max_available_drop_mib"] == 8192.0 - 4790.0


def test_400_token_flag_and_throughput_follow_eval_count(pilot):
    _, run = pilot
    report, _, error = run("cpu", JETSON_BASE_ONLY, 0, long_output=768, eval_counts=[64, 64, 64, 450])
    assert error is None
    trials = report["trials"]
    assert [trial["eval_count"] for trial in trials] == [64, 64, 64, 450]
    assert [trial["not_a_400_token_measurement"] for trial in trials] == [True, True, True, False]
    assert [trial["throughput_400_tokens_per_second"] for trial in trials] == [None, None, None, 50.0]
    assert report["admission_review"]["output_400_tokens"] == {"observed": True, "trials": ["long_output"]}


def test_a_long_output_that_stops_early_reports_no_400_token_throughput(pilot):
    _, run = pilot
    report, _, error = run("cpu", JETSON_BASE_ONLY, 0, long_output=768, eval_counts=[64, 64, 64, 399])
    assert error is None and report["trials"][-1]["not_a_400_token_measurement"] is True
    assert report["trials"][-1]["throughput_400_tokens_per_second"] is None
    assert report["admission_review"]["output_400_tokens"] == {"observed": False, "trials": []}


@pytest.mark.parametrize(("peak", "current", "candidate", "contradicted", "proposed"), [
    (3418.79296875, 3456, 3584, True, 3584),  # mesure du 6 octobre : 3456 Mio contredits, 3584 retenus
    (3418.79296875, 3584, 3584, False, 3584),
    (3500.0, 3584, 3712, True, 3712),
    (1000.0, 3584, 1152, False, 3584),  # une borne n'est jamais baissée
    (383.0, 512, 512, False, 512),  # 383 + 129 = 512 : couvert exactement
    (383.5, 512, 640, True, 640),
])
def test_bound_review_applies_the_frozen_rule_and_never_lowers(peak, current, candidate, contradicted, proposed):
    review = calibration.bound_review(peak, current)
    assert (review["candidate_mib"], review["contradicted"], review["proposed_mib"]) == (candidate, contradicted, proposed)
    assert (review["peak_mib"], review["current_mib"], review["margin_mib"], review["step_mib"]) == (peak, current, 129, 128)


@pytest.mark.parametrize(("last_uss", "delta", "stable"), [(3200.0, 30.0, True), (3202.0, 32.0, True), (3210.0, 40.0, False)])
def test_admission_review_compares_the_last_two_warm_contents_and_changes_no_threshold(pilot, last_uss, delta, stable):
    profile, run = pilot
    lows = [5000.0, 4990.0, 4800.0, 4790.0, 4785.0, 4780.0]
    uss = [3000.0, 3005.0, 3150.0, 3160.0, 3170.0, last_uss]
    report, _, error = run("cpu", JETSON_BASE_ONLY, 0, warm_series=3, lows=lows, uss=uss)
    assert error is None
    review = report["admission_review"]
    # Règle figée du 06/10 à 20:20 UTC : pic froid lu pendant l'essai froid seulement ; la baisse globale de la série
    # (minimum atteint plus tard, essais chauds compris) reste une information.
    assert review["cold"]["peak_mib"] == 8192.0 - 5000.0
    assert review["cold_peak_basis"] == {"from_baseline_mib": 8192.0 - 5000.0, "from_pre_trial_mib": 8192.0 - 5000.0}
    assert review["global_drop_information_mib"] == report["max_available_drop_mib"] == 8192.0 - 4780.0
    assert review["cold"]["current_mib"] == profile["resources"]["initial_llm_load_peak_estimate_mib"]
    assert (review["warm"]["peak_mib"], review["warm"]["current_mib"]) == (
        190.0, profile["resources"]["warm_llm_additional_peak_estimate_mib"])
    assert review["uss_plateau"] == {"basis": ["warm_series_2", "warm_series_3"], "delta_mib": delta, "limit_mib": 32,
                                     "stable": stable}
    assert review["d07_eligible"] is False and report["thresholds_modified"] is False


def test_without_two_series_contents_the_uss_plateau_is_not_measured(pilot):
    _, run = pilot
    report, _, error = run("cpu", JETSON_BASE_ONLY, 0, warm_series=1)
    assert error is None
    assert report["admission_review"]["uss_plateau"] == {"basis": ["warm_series_1"], "delta_mib": None, "limit_mib": 32,
                                                         "stable": None}


@pytest.mark.parametrize(("options", "message"), [
    ({"long_output": 399}, "400"), ({"warm_series": 10}, "0 à 9"), ({"warm_series": -1}, "0 à 9")])
def test_invalid_series_or_long_output_is_refused_before_anything_starts(tmp_path, options, message):
    with pytest.raises(ValueError, match=message):
        calibration.calibrate(PROFILE, tmp_path / "rapport.json", **options)
    assert not (tmp_path / "rapport.json").exists()


def test_a_long_output_beyond_the_context_is_refused_before_any_request(pilot, tmp_path):
    _, run = pilot
    with pytest.raises(ValueError, match="num_ctx"):
        run("cpu", JETSON_BASE_ONLY, 0, long_output=8190)
    assert list(tmp_path.glob("pilote-*.json")) == []


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


def test_admission_review_reproduces_the_exclusive_2b_pilot_with_the_frozen_rule():
    """Mesure réelle du rejeu exclusif R26-ADM-01 (2b-cpu-6300.json, SHA fa0b6539…, 06/10 20:22 UTC), recopiée : pic froid
    = max(base − minimum de l'essai froid, baisse depuis sa mesure préalable) = 3 723,50 Mio, borne 3 968 ; la baisse
    globale 3 954,06 Mio n'est pas retenue ; pic chaud = maximum des baisses chaudes = 263,64 Mio, borne 512."""
    uss = "post_trial_ollama_" + calibration.memory_key()
    rows = [("cold", 47937.9765625, 44263.5859375, 3674.390625, 3523.43, True),
            ("warm_same_prefix", 44493.00390625, 44295.6875, 197.31640625, 3525.66, True),
            ("warm_new_content", 44282.07421875, 44090.3984375, 191.67578125, 3659.68, True),
            ("warm_series_1", 44145.24609375, 44118.6953125, 26.55078125, 3660.83, True),
            ("warm_series_2", 44176.796875, 44095.01171875, 81.78515625, 3660.83, True),
            ("warm_series_3", 44176.984375, 44033.0234375, 143.9609375, 3659.31, True),
            ("long_output", 44303.51171875, 44039.875, 263.63671875, 3660.13, False)]
    trials = [{"label": label, "pre_trial_available_mib": pre, "min_available_mib": low, "drop_from_pre_trial_mib": drop, uss: memory,
               "not_a_400_token_measurement": short} for label, pre, low, drop, memory, short in rows]
    report = {"baseline_available_mib": 47987.08203125, "minimum_available_mib": 44033.0234375, "max_available_drop_mib": 3954.05859375,
              "trials": trials}
    review = calibration.admission_review(report, {"initial_llm_load_peak_estimate_mib": 3584, "warm_llm_additional_peak_estimate_mib": 512})
    assert review["cold"]["peak_mib"] == pytest.approx(3723.49609375)
    assert (review["cold"]["candidate_mib"], review["cold"]["contradicted"], review["cold"]["proposed_mib"]) == (3968, True, 3968)
    assert review["cold_peak_basis"] == {"from_baseline_mib": pytest.approx(3723.49609375), "from_pre_trial_mib": 3674.390625}
    assert review["global_drop_information_mib"] == 3954.05859375
    assert (review["warm"]["peak_mib"], review["warm"]["candidate_mib"], review["warm"]["proposed_mib"]) == (263.63671875, 512, 512)
    assert review["uss_plateau"]["stable"] is True and review["d07_eligible"] is False
    # Profil actuel (3 968 et 512 depuis W041) : bornes confirmées, aucune baisse proposée.
    current = calibration.admission_review(report, {"initial_llm_load_peak_estimate_mib": 3968, "warm_llm_additional_peak_estimate_mib": 512})
    assert (current["cold"]["contradicted"], current["cold"]["proposed_mib"], current["warm"]["proposed_mib"]) == (False, 3968, 512)
