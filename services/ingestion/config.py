"""Resolved ingestion settings independent of backend settings classes."""

import hashlib
import importlib.metadata
import json
import math
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import IngestionError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OCR_RENDER_SCALE = 3.0
TABLE_RENDER_SCALE = 2.0


def project_path(value):
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class IngestionConfig:
    artifacts_path: str | None = None
    tesseract_cmd: str = "tesseract"
    tessdata_path: str | None = None
    ocr_languages: tuple[str, ...] = ("fra", "eng")
    threads_max: int = 2
    parser_threads: int = 2
    page_window_size: int = 4
    max_file_mib: float = 200
    max_document_pages: int = 2000
    suspect_text_min_alnum_chars: int = 40
    suspect_text_max_replacement_ratio: float = 0.02
    pipeline_route: str = "auto"
    pdf_backend: str = "docling_parse"
    ocr_intrinsic_aspect: bool = False
    # Recadrage borné sur l'encre des cellules de grille (profil : pdf.ocr_cell_ink_crop), nominal après E1.
    ocr_cell_border: bool = True
    # Mot ou cellule OCR sous ce seuil : région non résolue ; 0 désactive explicitement le contrôle.
    ocr_min_word_confidence: float = 0.8
    extraction_revision_id: str | None = None
    artifacts_lock_path: str | None = "config/artifacts.lock.json"
    max_page_render_pixels: int = 8_000_000
    # Allocation de rendu d'une région OCR (216 ppp, PDFium à 1,5 fois puis réduit) : une page A4, Lettre ou Legal
    # scannée en pleine page y tient (12,5 M pixels au plus) ; un format plus grand reste refusé et déclaré (W016).
    max_ocr_region_pixels: int = 13_000_000

    @property
    def resolved_tesseract_cmd(self):
        return str(project_path(self.tesseract_cmd).resolve()) if "/" in self.tesseract_cmd or "\\" in self.tesseract_cmd else self.tesseract_cmd

    @classmethod
    def from_mapping(cls, config: dict | None):
        supplied = config or {}
        pdf = supplied.get("pdf", supplied)
        values = {key: pdf[key] for key in cls.__dataclass_fields__ if key in pdf}
        for alias, canonical in {"tessdata_dir": "tessdata_path", "native_parser_threads": "parser_threads", "model_inference_threads": "threads_max", "checkpoint_window_pages_initial": "page_window_size", "ocr_cell_ink_crop": "ocr_cell_border"}.items():
            if alias in pdf:
                values[canonical] = pdf[alias]
        for key in ("artifacts_path", "tesseract_cmd", "tessdata_path", "extraction_revision_id"):
            if key in supplied:
                values[key] = supplied[key]
        if "ocr_languages" in values:
            values["ocr_languages"] = tuple(values["ocr_languages"])
        result = cls(**values)
        if result.page_window_size < 1 or result.page_window_size > 32:
            raise IngestionError("INVALID_CONFIG", "La fenêtre PDF doit contenir entre 1 et 32 pages.")
        if result.threads_max < 1 or result.parser_threads < 1:
            raise IngestionError("INVALID_CONFIG", "Le nombre de threads PDF doit être positif.")
        if not math.isfinite(result.max_file_mib) or result.max_file_mib <= 0 or result.max_document_pages < 1:
            raise IngestionError("INVALID_CONFIG", "Les limites PDF doivent être positives.")
        if result.max_page_render_pixels < 1 or result.max_ocr_region_pixels < 1:
            raise IngestionError("INVALID_CONFIG", "Les plafonds de rendu PDF doivent être positifs.")
        if result.pipeline_route not in {"auto", "native", "structured", "regional_ocr"}:
            raise IngestionError("INVALID_CONFIG", "La route PDF demandée est inconnue.")
        if result.pdf_backend not in {"docling_parse", "pypdfium2"}:
            raise IngestionError("INVALID_CONFIG", "Le backend PDF demandé est inconnu.")
        if not isinstance(result.ocr_intrinsic_aspect, bool) or not isinstance(result.ocr_cell_border, bool):
            raise IngestionError("INVALID_CONFIG", "Les options de dérivé OCR doivent être booléennes.")
        threshold = result.ocr_min_word_confidence
        if isinstance(threshold, bool) or not isinstance(threshold, int | float) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise IngestionError("INVALID_CONFIG", "Le seuil de confiance OCR doit être un nombre de [0,1].")
        if not result.ocr_languages or any(not isinstance(x, str) or not x for x in result.ocr_languages):
            raise IngestionError("INVALID_CONFIG", "Les langues OCR doivent être explicites.")
        return result

    def fingerprint(self):
        versions = {}
        for name in ("docling", "docling-core", "docling-parse", "docling-ibm-models", "pypdfium2", "Pillow", "torch", "transformers", "pandas", "numpy", "scipy"):
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = "missing"
        data = asdict(self)
        data.pop("extraction_revision_id")
        data["adapter_revision"] = "pdf-ingestion-v2.1-1"
        data["adapter_source_hashes"] = {source.name: sha256_file(source) for source in sorted(Path(__file__).parent.glob("*.py"))}
        data["versions"] = versions
        executable = shutil.which(self.resolved_tesseract_cmd)
        data["tesseract_executable_sha256"] = sha256_file(Path(executable)) if executable else "missing"
        data["model_artifacts"] = []
        if self.artifacts_lock_path and project_path(self.artifacts_lock_path).is_file():
            manifest = json.loads(project_path(self.artifacts_lock_path).read_text(encoding="utf-8-sig"))
            roots = [project_path(value).resolve() for value in (self.artifacts_path, self.tessdata_path) if value]
            for entries in manifest.get("groups", {}).values():
                for entry in entries:
                    target = project_path(entry.get("target", "")).resolve()
                    if target.suffix in {".json", ".safetensors", ".onnx", ".bin", ".traineddata"} and any(target.is_relative_to(root) for root in roots):
                        data["model_artifacts"].append({key: entry[key] for key in ("target", "revision", "sha256", "git_blob_sha1") if key in entry})
            data["model_artifacts"].sort(key=lambda item: item["target"])
        if self.tessdata_path:
            data["tessdata_hashes"] = {}
            for lang in (*self.ocr_languages, "osd"):
                candidate = project_path(self.tessdata_path) / f"{lang}.traineddata"
                if candidate.is_file():
                    data["tessdata_hashes"][lang] = sha256_file(candidate)
            tsv_config = project_path(self.tessdata_path) / "configs" / "tsv"
            if tsv_config.is_file():
                data["tessdata_hashes"]["configs/tsv"] = sha256_file(tsv_config)
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()
