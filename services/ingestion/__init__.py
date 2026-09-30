"""PDF ingestion boundary; importing this package does not load Docling."""

from .errors import IngestionError


def preflight_pdf(path, config=None):
    from .preflight import preflight_pdf as implementation

    return implementation(path, config)


def extraction_fingerprint(config=None):
    """Extraction identity without importing parser/model runtimes."""
    from .config import IngestionConfig

    return IngestionConfig.from_mapping(config).fingerprint()


def extract_window(path, version_id, page_start, page_end, config, output_dir, cancel_event=None):
    from .pipeline import extract_window as implementation

    return implementation(path, version_id, page_start, page_end, config, output_dir, cancel_event)


def extract_pdf(path, output_dir, config, version_id, cancel_path=None):
    from .pipeline import extract_pdf as implementation

    return implementation(path, output_dir, config, version_id, cancel_path)


__all__ = ["IngestionError", "preflight_pdf", "extraction_fingerprint", "extract_window", "extract_pdf"]
