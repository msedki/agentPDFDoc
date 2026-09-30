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
