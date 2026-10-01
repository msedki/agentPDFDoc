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
