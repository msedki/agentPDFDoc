"""Shared, bounded Office extraction contract. Source locators never imply pages."""

from dataclasses import asdict, dataclass, fields
from typing import Literal

from services.ingestion.errors import IngestionError

OfficeFormat = Literal["docx", "xlsx"]
OFFICE_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@dataclass(frozen=True)
class OfficeLimits:
    max_members: int = 10_000
    max_total_bytes: int = 268_435_456
    max_part_bytes: int = 67_108_864
    max_compression_ratio: int = 1_000
    max_xml_depth: int = 128
    max_elements: int = 2_000_000
    max_blocks: int = 100_000
    max_cells: int = 100_000
    max_shared_strings: int = 100_000
    max_units: int = 10_000
    max_text_chars: int = 20_000_000
    max_cell_chars: int = 100_000
    max_block_chars: int = 8_000

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            raise IngestionError("OFFICE_INVALID_LIMITS", "Les limites Office doivent être des entiers positifs.")
        if self.max_part_bytes > self.max_total_bytes:
            raise IngestionError("OFFICE_INVALID_LIMITS", "Une partie Office ne peut dépasser le budget total.")

    @classmethod
    def from_mapping(cls, config=None):
        config = config or {}
        value = config.get("office", {})
        if not isinstance(value, dict) or set(value) - {field.name for field in fields(cls)}:
            raise IngestionError("OFFICE_INVALID_LIMITS", "Configuration Office inconnue ou invalide.")
        return cls(**value)


def limit_error():
    return IngestionError("OFFICE_LIMIT_EXCEEDED", "Le document dépasse une limite d'ingestion Office.")
