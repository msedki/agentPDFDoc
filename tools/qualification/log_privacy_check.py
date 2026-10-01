"""Journaux sans texte privé, originaux et modèles hors de Git (critère D08.7), en lecture seule.

Échantillonne dans la base SQLite de l'instance (ouverte en lecture seule) des extraits du texte réellement extrait des
documents, des questions et des réponses, puis les cherche, en clair et sous forme échappée JSON, dans tous les
journaux de l'instance : `logs/**` (API, Ollama, Qdrant, ressources, audit de sécurité), journal de démarrage du
superviseur et journaux du worker d'extraction. Les checkpoints d'extraction sont des données, pas des journaux, et ne
sont pas examinés. Le rapport ne contient que des comptes et des noms de fichiers, jamais le texte cherché.

Contrôle Git : les chemins des originaux, du corpus `PDF/`, des modèles et des journaux sont ignorés ; aucun fichier
suivi sous `PDF/` ou `.runtime/`, aucun poids de modèle suivi, et les seuls PDF suivis sont des fixtures synthétiques.

    .venv\\Scripts\\python.exe tools/qualification/log_privacy_check.py [--profile config/local16.yaml] --report <rapport.json>
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.runtime.supervisor import data_path, load_profile  # noqa: E402

MODEL_SUFFIXES = (".onnx", ".gguf", ".safetensors", ".pt", ".bin", ".traineddata")
SYNTHETIC_PDF_ROOTS = ("fixtures/", "evals/", "apps/web/tests/")


def window(text: str, size: int) -> str | None:
    """Extrait central de `size` caractères, sans retour à la ligne, assez long pour ne pas être un mot courant."""
    flat = " ".join(text.split())
    if len(flat) < size + 8:
        return None
    start = (len(flat) - size) // 2
    return flat[start:start + size]


def samples(database: Path, limit: int) -> dict[str, list[str]]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        blocks = [row[0] for row in connection.execute("SELECT DISTINCT text FROM blocks WHERE length(text) >= 48")]
        questions = [row[0] for row in connection.execute("SELECT question FROM query_runs WHERE length(question) >= 32")]
        answers = [row[0] for row in connection.execute("SELECT answer FROM query_runs WHERE answer IS NOT NULL AND length(answer) >= 48")]
    finally:
        connection.close()
    generator = random.Random(20261001)
    picked = {"document_text": generator.sample(blocks, min(limit, len(blocks))), "questions": questions, "answers": answers}
    return {kind: [part for part in (window(text, 32 if kind != "questions" else 24) for text in texts) if part] for kind, texts in picked.items()}


def log_files(data: Path) -> list[Path]:
    files = [path for pattern in ("logs/**/*.log", "logs/**/*.jsonl", "control/*.log", "extractions/**/worker-*.log", "extractions/**/worker-*.jsonl")
             for path in data.glob(pattern)]
    return sorted(set(files))


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", type=Path, default=ROOT / "config/local16.yaml")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3000)
    args = parser.parse_args()
    data = data_path(load_profile(args.profile))
    wanted = samples(data / "app.sqlite3", args.samples)
    files = log_files(data)
    hits: Counter[str] = Counter()
    files_with_hits: dict[str, list[str]] = {}
    scanned_bytes = 0
    for path in files:
        content = path.read_text(encoding="utf-8", errors="replace")
        scanned_bytes += path.stat().st_size
        for kind, parts in wanted.items():
            found = sum(1 for part in parts if part in content or json.dumps(part)[1:-1] in content)
            if found:
                hits[kind] += found
                files_with_hits.setdefault(path.relative_to(data).as_posix(), []).append(kind)
    # Témoin positif : les checkpoints d'extraction contiennent le texte des documents ; le détecteur doit l'y retrouver.
    controls = sorted(data.glob("extractions/**/window-*.json"))[:20]
    control_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in controls)
    control_hits = sum(1 for part in wanted["document_text"] if part in control_text or json.dumps(part)[1:-1] in control_text)
    ignored = {path: subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT, check=False).returncode == 0
               for path in ("PDF/exemple.pdf", ".runtime/data/originals/exemple.pdf", ".runtime/models/e5/model.onnx", ".runtime/data/logs/x/api.log", ".runtime/data/app.sqlite3")}
    tracked = git("ls-files").splitlines()
    tracked_private = [path for path in tracked if path.startswith(("PDF/", ".runtime/"))]
    tracked_models = [path for path in tracked if path.lower().endswith(MODEL_SUFFIXES)]
    tracked_pdfs = [path for path in tracked if path.lower().endswith(".pdf")]
    pdf_outside_fixtures = [path for path in tracked_pdfs if not path.startswith(SYNTHETIC_PDF_ROOTS)]
    checks = {"samples_available": all(wanted[kind] for kind in ("document_text",)), "logs_examined": bool(files), "detector_finds_text_in_checkpoints": control_hits > 0,
              "no_document_text_in_logs": hits["document_text"] == 0, "no_question_in_logs": hits["questions"] == 0, "no_answer_in_logs": hits["answers"] == 0,
              "private_paths_ignored": all(ignored.values()), "nothing_tracked_under_pdf_or_runtime": not tracked_private,
              "no_model_weights_tracked": not tracked_models, "tracked_pdfs_are_fixtures": not pdf_outside_fixtures}
    report = {"utc": datetime.now(UTC).isoformat(), "criterion": "D08.7", "profile": args.profile.name,
              "samples": {kind: len(parts) for kind, parts in wanted.items()}, "log_files": len(files), "log_bytes": scanned_bytes,
              "log_kinds": dict(Counter(path.name if path.parent.name != "control" else "control/" + path.name for path in files)),
              "hits": dict(hits), "files_with_hits": files_with_hits, "detector_control": {"checkpoint_files": len(controls), "samples_found": control_hits},
              "ignored_paths": ignored,
              "tracked": {"private": tracked_private, "model_weights": tracked_models, "pdfs": len(tracked_pdfs), "pdfs_outside_fixtures": pdf_outside_fixtures},
              "method": "Extraits centraux de 32 caractères (24 pour les questions) cherchés en clair et échappés JSON ; blocs distincts d'au moins 48 caractères (tirage à graine fixe au-delà de --samples), toutes les questions et réponses enregistrées",
              "limit": "Un texte reformulé, tronqué autrement ou plus court que les seuils ne serait pas détecté",
              "checks": checks, "result": "PASS" if all(checks.values()) else "FAIL"}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "samples": report["samples"], "log_files": len(files), "hits": dict(hits), "checks": checks}, ensure_ascii=False))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
