import copy

import pytest
import yaml

from services.runtime.artifacts import ROOT
from services.runtime.supervisor import load_profile


@pytest.mark.parametrize("service,key,value", [
    ("llm", "base_url", "http://192.168.1.10:11434"),
    ("qdrant", "url", "http://0.0.0.0:6333"),
    ("llm", "base_url", "https://127.0.0.1:11434"),
    ("llm", "base_url", "http://user:password@127.0.0.1:11434"),
    ("qdrant", "url", "http://127.0.0.1:6333?token=test"),
    ("qdrant", "url", "http://127.0.0.1:6333/other"),
    ("llm", "base_url", "http://127.0.0.1"),
])
def test_native_profile_rejects_service_urls_before_launch(tmp_path, service, key, value):
    baseline = load_profile(ROOT / "config/local16.yaml")
    changed = copy.deepcopy(baseline)
    changed[service][key] = value
    target = tmp_path / "invalid.yaml"
    target.write_text(yaml.safe_dump(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="URL HTTP loopback"):
        load_profile(target)
    assert not (tmp_path / "control").exists()


def test_native_profile_accepts_separate_restore_ports(tmp_path):
    restored = load_profile(ROOT / "config/local16.yaml")
    restored["qdrant"]["url"] = "http://127.0.0.1:6343"
    restored["llm"]["base_url"] = "http://127.0.0.1:11445"
    restored["app"]["port"] = 8795
    target = tmp_path / "Profil restauré.yaml"
    target.write_text(yaml.safe_dump(restored), encoding="utf-8")
    assert load_profile(target) == restored


# --- Accélération GPU (W024, W025) : clé llm.accelerator et forme antérieure llm.num_gpu ------------------------------

def _profile_with_llm(tmp_path, **changes):
    """Profil livré, section llm sans num_gpu ni accelerator, puis les clés données (None retire la clé)."""
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    for key in ("num_gpu", "accelerator"):
        profile["llm"].pop(key, None)
    profile["llm"].update({key: value for key, value in changes.items() if value is not None})
    target = tmp_path / "profil.yaml"
    target.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    return target


@pytest.mark.parametrize("path", [ROOT / "config/local16.yaml", ROOT / "RAG_Local_Agents/config/local16.yaml"])
def test_the_shipped_profile_and_its_documentary_copy_are_admitted(path):
    assert load_profile(path)["schema_version"] == 2


@pytest.mark.parametrize("llm", [{"accelerator": "auto"}, {"accelerator": "cpu"}, {"accelerator": "gpu"},
                                 {"num_gpu": 0}, {}])
def test_each_accelerator_form_is_admitted(tmp_path, llm):
    assert load_profile(_profile_with_llm(tmp_path, **llm))["llm"].get("accelerator") == llm.get("accelerator")


@pytest.mark.parametrize(("llm", "message"), [
    ({"accelerator": "cuda"}, "llm.accelerator accepte auto (GPU utilisé s'il est détecté sur un poste qualifié, CPU "
                              "sinon), cpu (calcul CPU imposé) ou gpu (essai du GPU sur un poste non qualifié)."),
    ({"num_gpu": 1}, "llm.num_gpu n'accepte que 0 (profil antérieur à l'accélération GPU) ; pour utiliser le GPU, remplacez-le par "
                     "llm.accelerator: auto, ou gpu pour l'essayer sur un poste non qualifié."),
    ({"num_gpu": -1}, "llm.num_gpu n'accepte que 0 (profil antérieur à l'accélération GPU) ; pour utiliser le GPU, remplacez-le par "
                      "llm.accelerator: auto, ou gpu pour l'essayer sur un poste non qualifié."),
    ({"num_gpu": 0, "accelerator": "auto"}, "llm.num_gpu est remplacé par llm.accelerator : retirez llm.num_gpu du profil."),
])
def test_invalid_accelerator_forms_are_refused_with_the_messages_of_the_api(tmp_path, llm, message):
    # Messages exacts, communs au superviseur et à Settings.load (services/runtime/accelerator.py).
    with pytest.raises(ValueError) as refused:
        load_profile(_profile_with_llm(tmp_path, **llm))
    assert str(refused.value) == message


def test_the_host_check_keeps_its_own_message(tmp_path):
    # Avant W024, l'hôte et le CPU partageaient un message (« Le runtime exige loopback et CPU ») ; l'hôte garde le sien.
    profile = yaml.safe_load((ROOT / "config/local16.yaml").read_text(encoding="utf-8"))
    profile["app"]["host"] = "0.0.0.0"
    target = tmp_path / "profil.yaml"
    target.write_text(yaml.safe_dump(profile, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError) as refused:
        load_profile(target)
    assert str(refused.value) == "Le runtime exige loopback"
