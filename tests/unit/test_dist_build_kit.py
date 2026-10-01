"""Kit hors ligne (DIST-04) : liste blanche, exclusions, chemins du poste de fabrication et intégrité, sur une arborescence factice."""
import json

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
