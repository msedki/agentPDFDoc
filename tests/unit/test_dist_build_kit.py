"""Kit hors ligne (DIST-04) : liste blanche, exclusions, chemins du poste de fabrication et intégrité, sur une arborescence factice."""
import json
import sys

import pytest

from tools.dist.build_kit import build_kit, selected_files, verify_kit


def write(root, relative, content="x"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "depot"
    for relative in ("services/api/main.py", "config/local16.yaml", "apps/web/out/index.html", "rag.ps1", "pyproject.toml", "uv.lock", "tools/dist/install.ps1",
                     ".runtime/models/e5-small-int8/model.onnx", ".runtime/bin/ollama-0.35.0/lib/ollama/cuda_v12/cublas.dll",
                     ".runtime/bin/ollama-0.35.0/ollama.exe"):
        write(root, relative)
    for relative in ("services/api/__pycache__/main.cpython-312.pyc", ".runtime/models/granite-97m-int8/model.onnx", ".runtime/data/app.sqlite3",
                     "PDF/manuel.pdf", "tests/unit/test_x.py", "RAG_Local_Agents/PLAN.md", ".runtime/evals/jeu.json"):
        write(root, relative)
    write(root, "config/artifacts.lock.json", json.dumps({"groups": {"qdrant": [{"version": "1.19.1", "publisher": "Qdrant", "license": "Apache-2.0", "url": "https://github.com/qdrant/qdrant/releases", "extract_to": ".runtime/bin/qdrant-1.19.1"}]}}))
    write(root, ".runtime/bin/qdrant-1.19.1/LICENSE", "Apache")
    write(root, ".runtime/manifests/tesseract-installed-copy.json", json.dumps({"source": str(root / "Tesseract-OCR"), "files": []}))
    return root


def test_whitelist_keeps_the_runtime_and_never_the_user_or_project_files(repository):
    files = selected_files(repository)
    assert "services/api/main.py" in files and ".runtime/models/e5-small-int8/model.onnx" in files
    assert not [name for name in files if "__pycache__" in name or "granite" in name or name.startswith(("PDF/", ".runtime/data/", "tests/", "RAG_Local_Agents/", ".runtime/evals/"))]
    assert ".runtime/bin/ollama-0.35.0/lib/ollama/cuda_v12/cublas.dll" in files
    assert ".runtime/bin/ollama-0.35.0/lib/ollama/cuda_v12/cublas.dll" not in selected_files(repository, without_gpu=True)


def test_kit_neutralizes_the_tesseract_source_checks_integrity_and_detects_tampering(repository, tmp_path):
    kit = tmp_path / "kit"
    manifest = build_kit(kit, root=repository, version="0.1.0", commit="abc")
    assert manifest["files"] == len(selected_files(repository)) and manifest["version"] == "0.1.0"
    copied = json.loads((kit / ".runtime/manifests/tesseract-installed-copy.json").read_text(encoding="utf-8"))
    assert copied["source"] == "<poste de fabrication>/Tesseract-OCR"
    assert verify_kit(kit)["status"] == "verified"
    assert b"-ExecutionPolicy Bypass" in (kit / "Installer l'atelier.cmd").read_bytes() and (kit / "tools/dist/install.ps1").is_file()
    (kit / "services/api/main.py").write_text("modifié", encoding="utf-8")
    (kit / "en-trop.txt").write_text("y", encoding="utf-8")
    report = verify_kit(kit)
    assert report["status"] == "failed" and report["altered_or_missing"] == ["services/api/main.py"] and report["unexpected"] == ["en-trop.txt"]


def test_kit_refuses_a_build_host_path_and_an_output_inside_the_repository(repository, tmp_path):
    with pytest.raises(ValueError, match="dossier neuf hors du dépôt"):
        build_kit(repository / "kit", root=repository, version="0.1.0")
    write(repository, "config/notes.yaml", f"donnees: {repository}\\.runtime\\data")
    with pytest.raises(ValueError, match="Chemin du poste de fabrication"):
        build_kit(tmp_path / "kit2", root=repository, version="0.1.0")
    assert not (tmp_path / "kit2").exists()


def test_program_inventory_reports_added_removed_and_changed_files(tmp_path):
    from tools.dist.program_inventory import compare, snapshot

    write(tmp_path, "programme/a.py", "a")
    write(tmp_path, "programme/b.py", "b")
    before = snapshot(tmp_path / "programme")
    assert compare(before, snapshot(tmp_path / "programme"))["status"] == "unchanged"
    write(tmp_path, "programme/a.py", "modifié")
    (tmp_path / "programme/b.py").unlink()
    write(tmp_path, "programme/__pycache__/c.pyc", "c")
    report = compare(before, snapshot(tmp_path / "programme"))
    assert (report["status"], report["changed"], report["removed"], report["added"]) == ("changed", ["a.py"], ["b.py"], ["__pycache__/c.pyc"])


def test_install_copy_hashes_while_copying_and_removes_a_partial_copy(repository, tmp_path):
    from tools.dist.build_kit import install_copy

    kit = tmp_path / "kit"
    build_kit(kit, root=repository, version="0.1.0")
    result = install_copy(kit, tmp_path / "programme")
    assert result["status"] == "copied" and (tmp_path / "programme/services/api/main.py").is_file()
    assert (tmp_path / "programme/SHA256SUMS").is_file() and verify_kit(tmp_path / "programme")["status"] == "verified"
    with pytest.raises(ValueError, match="jamais remplacée"):
        install_copy(kit, tmp_path / "programme")
    (kit / "rag.ps1").write_text("altéré", encoding="utf-8")
    with pytest.raises(ValueError, match="altéré : rag.ps1"):
        install_copy(kit, tmp_path / "autre")
    assert not (tmp_path / "autre").exists()


def test_kit_carries_third_party_notices_from_the_artifact_lock(repository, tmp_path):
    kit = tmp_path / "kit"
    build_kit(kit, root=repository, version="0.1.0")
    notices = (kit / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "| qdrant | 1.19.1 | Qdrant | Apache-2.0 |" in notices and "`.runtime/bin/qdrant-1.19.1/LICENSE`" in notices
    assert "section 4 b" in notices and "## Manques connus" in notices
    assert verify_kit(kit)["status"] == "verified"


def test_notices_state_internal_use_and_preserve_known_gaps(repository):
    from tools.dist.notices import third_party_notices

    notices = third_party_notices(repository, [], "0.1.0")
    assert "usage interne" in notices and "W030" in notices
    assert "Une redistribution hors de l'organisation" in notices
    assert "rouvrirait" in notices and "pas un avis juridique" in notices
    assert "attendent la décision P7" not in notices
    assert "## Manques connus" in notices
    assert "Qdrant et à Ollama" in notices and "licences des DLL tierces" in notices


@pytest.mark.parametrize("platform", ["windows-x86_64", "linux-aarch64", "linux-x86_64"])
def test_notices_disclose_missing_office_license_texts_on_both_platforms(repository, platform):
    from tools.dist.notices import third_party_notices

    notices = third_party_notices(repository, [], "0.1.0", platform)
    assert "openpyxl 3.1.5" in notices and "et-xmlfile 2.0.0" in notices
    assert "la déclaration de licence des métadonnées ne remplace pas ces textes" in notices
    assert "absence" in notices and "W030" in notices


def test_notices_cover_every_locked_artifact_of_the_repository():
    from tools.dist.build_kit import ROOT
    from tools.dist.notices import third_party_notices

    lock = json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    notices = third_party_notices(ROOT, selected_files(ROOT), "0.1.0")
    for group, entries in lock["groups"].items():
        for entry in entries:
            # Le kit est celui de Windows : chaque artefact Windows ou commun figure, aucun artefact propre à Linux.
            if entry.get("platform", "windows-x86_64") == "windows-x86_64":
                assert f"| {entry.get('model_id') or group} |" in notices
            else:
                assert entry["url"] not in notices


def test_kit_lists_only_windows_and_common_artifacts(repository, tmp_path):
    lock = {"groups": {"qdrant": [
        {"version": "1.19.1", "platform": "windows-x86_64", "publisher": "Qdrant", "license": "Apache-2.0",
         "url": "https://example.invalid/qdrant-x86_64-pc-windows-msvc.zip", "extract_to": ".runtime/bin/qdrant-1.19.1"},
        {"version": "1.19.1", "platform": "linux-aarch64", "publisher": "Qdrant", "license": "Apache-2.0",
         "url": "https://example.invalid/qdrant-aarch64-unknown-linux-musl.tar.gz", "extract_to": ".runtime/bin/qdrant-1.19.1"}],
        "tesseract-source": [{"version": "5.4.0", "platform": ["linux-aarch64", "linux-x86_64"], "publisher": "tesseract-ocr", "license": "Apache-2.0",
                              "url": "https://example.invalid/tesseract-5.4.0.tar.gz", "target": ".runtime/cache/downloads/t.tar.gz"}]}}
    write(repository, "config/artifacts.lock.json", json.dumps(lock))
    build_kit(tmp_path / "kit", root=repository, version="0.1.0")
    notices = (tmp_path / "kit/THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "qdrant-x86_64-pc-windows-msvc.zip" in notices
    assert "linux-musl" not in notices and "tesseract-source" not in notices


@pytest.mark.parametrize(("platform", "expected"), [
    ("windows-x86_64", {("qdrant", "qdrant-x86_64-pc-windows-msvc.zip"), ("e5", "model.onnx")}),
    ("linux-x86_64", {("qdrant", "qdrant-x86_64-unknown-linux-musl.tar.gz"), ("tesseract-source", "tesseract-5.4.0.tar.gz"),
                      ("e5", "model.onnx")}),
    ("linux-aarch64", {("tesseract-source", "tesseract-5.4.0.tar.gz"), ("e5", "model.onnx")}),
])
def test_notice_rows_apply_the_platform_rule_of_the_lock_including_platform_lists(platform, expected):
    # Même règle que le provisionnement (platforms.entries_for_platform) : sans champ, partout ; un nom, cette
    # plateforme ; une liste, chacune des plateformes listées (sources Tesseract des deux architectures Linux).
    from tools.dist.notices import artifact_rows

    def entry(name, platform=None, **fields):
        return {"version": "1", "publisher": "p", "license": "l", "url": f"https://example.invalid/{name}",
                **({"platform": platform} if platform else {}), **fields}

    lock = {"groups": {
        "qdrant": [entry("qdrant-x86_64-pc-windows-msvc.zip", "windows-x86_64"),
                   entry("qdrant-x86_64-unknown-linux-musl.tar.gz", "linux-x86_64")],
        "tesseract-source": [entry("tesseract-5.4.0.tar.gz", ["linux-aarch64", "linux-x86_64"])],
        "e5": [entry("model.onnx")]}}
    rows = artifact_rows(lock, [], platform)
    assert {(row["component"], row["source"].rsplit("/", 1)[-1]) for row in rows} == expected


@pytest.mark.skipif(sys.platform == "win32", reason="refus propre aux postes non Windows")
def test_kit_build_is_refused_outside_windows(tmp_path, monkeypatch, capsys):
    from tools.dist import build_kit as module

    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--output", str(tmp_path / "kit")])
    assert module.main() == 1
    assert "windows-x86_64" in capsys.readouterr().out and not (tmp_path / "kit").exists()


@pytest.mark.parametrize("residue", [".runtime/bin/ollama-0.35.0/bin/.runtime/qa/instance-1/home/.ollama/id_ed25519",
                                     ".runtime/bin/ollama-0.35.0/bin/.runtime/data/home/.ollama/id_ed25519",
                                     ".runtime/models/ollama/.runtime/evals/jeu.json"])
def test_a_nested_runtime_residue_is_refused_wherever_it_lies(repository, residue):
    # Revue J11 (B5) : un dossier de données relatif, résolu depuis bin/ d'Ollama, a laissé .runtime/qa/… (clés
    # id_ed25519 comprises) sous .runtime/bin ; le préfixe seul ne l'attrapait pas.
    write(repository, residue, "cle")
    with pytest.raises(ValueError, match="Entrée interdite dans le kit"):
        selected_files(repository)


def test_the_gpu_discovery_of_the_build_host_is_not_shipped(repository):
    # La découverte consignée par provision décrit le matériel du poste de fabrication, pas celui du poste installé.
    write(repository, ".runtime/manifests/ollama-discovery.json", json.dumps({"platform": "windows-x86_64", "status": "gpu"}))
    files = selected_files(repository)
    assert ".runtime/manifests/ollama-discovery.json" not in files
    assert ".runtime/manifests/tesseract-installed-copy.json" in files


def test_the_windows_kit_lists_no_gpu_complement_of_ollama():
    # Les compléments JetPack du verrou ne valent que pour Linux aarch64 : le kit Windows n'en porte aucun.
    from tools.dist.build_kit import KIT_PLATFORM, ROOT
    from tools.dist.notices import artifact_rows

    lock = json.loads((ROOT / "config/artifacts.lock.json").read_text(encoding="utf-8"))
    assert lock["groups"]["ollama-gpu"]
    rows = artifact_rows(lock, [], KIT_PLATFORM)
    assert {row["component"] for row in rows} >= {"ollama", "qdrant"}
    assert not [row for row in rows if row["component"] == "ollama-gpu" or "jetpack" in row["source"]]


# --- Kit sans bibliothèques GPU et proposition de la rubrique « calcul » (revue J11 runtime-4, runtime-6) ---------------

def test_the_without_gpu_option_says_what_an_nvidia_host_gets(monkeypatch, capsys):
    from tools.dist import build_kit as module

    assert module.WITHOUT_GPU_HELP == (
        "retirer cuda_v12, cuda_v13 et vulkan d'Ollama, pour des postes sans GPU NVIDIA : calcul sur CPU, sans "
        "proposition GPU ; sur un poste NVIDIA, doctor signale que l'installation ne contient pas les bibliothèques CUDA")
    monkeypatch.setattr(sys, "argv", ["build_kit", "build", "--help"])
    with pytest.raises(SystemExit):
        module.main()
    assert " ".join(module.WITHOUT_GPU_HELP.split()) in " ".join(capsys.readouterr().out.split())


@pytest.mark.parametrize(("script", "line"), [
    ("tools/dist/raccourci.ps1", "if ($item.proposal) { Write-Output ('        Proposition : {0}' -f $item.proposal) }"),
    ("tools/dist/install.ps1", 'if ($item.proposal) { Write-Output ("      Proposition : {0}" -f $item.proposal) }'),
    ("tools/dist/install.ps1", "foreach ($item in @($doctor.verdict.rubrics | Where-Object { $_.proposal })) { "
                               'Write-Output ("  Proposition, rubrique {0} : {1}" -f $item.rubric, $item.proposal) }'),
])
def test_windows_outputs_print_the_proposal_the_summary_points_to(script, line):
    # Sans PowerShell sur le poste, au moins la ligne d'affichage ; son rendu réel est dans test_powershell_syntax.py.
    from tools.dist.build_kit import ROOT

    assert line in [item.strip() for item in (ROOT / script).read_text(encoding="utf-8-sig").splitlines()]
