"""Size refusal uses an isolated small threshold, without opening a parser."""

import hashlib
from pathlib import Path

import pytest

from services.ingestion import IngestionError, preflight_pdf
from services.ingestion.config import IngestionConfig


@pytest.mark.parametrize("limit", [0, -1, float("nan"), float("inf")])
def test_nonpositive_or_nonfinite_size_limit_is_refused(limit):
    with pytest.raises(IngestionError) as caught:
        IngestionConfig.from_mapping({"max_file_mib": limit})
    assert caught.value.code == "INVALID_CONFIG"


def test_real_size_fixture_refused_at_isolated_64kib_threshold():
    source = Path(__file__).resolve().parents[2] / "fixtures/qualification-v2.1/errors/Limite de taille isolée.pdf"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assert source.stat().st_size > 65536
    isolated_profile = {"max_file_mib": 65536 / (1024 * 1024)}
    with pytest.raises(IngestionError) as caught:
        preflight_pdf(source, isolated_profile)
    assert caught.value.code == "PDF_TOO_LARGE"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    # This fixture exercises size refusal only. The production default remains
    # 200 MiB and no synthetic 200-MiB boundary is claimed by this test.
    assert IngestionConfig.from_mapping({}).max_file_mib == 200
