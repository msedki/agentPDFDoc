"""Règle de publication W012 : figures non interprétées et pages sans rien à lire ne rendent pas un document partiel."""
import pytest

from services.api.indexing import text_loss


def page(index, state="native", classification="native", regions=(), blocks=1, alnum=120):
    return {"page_index": index, "extraction_state": state, "classification": classification, "alphanumeric_count": alnum,
            "blocks": [{"id": f"b{index}"}] * blocks, "unresolved_regions": [{"reason": reason} for reason in regions]}


def extraction(pages, status="ready_partial", parser_complete=True, page_count=None):
    return {"status": status, "page_count": page_count or len(pages), "pages": pages, "parser_complete": parser_complete}


def test_graphics_and_pages_with_nothing_to_read_are_declared_limits_not_text_loss():
    pages = [page(0, regions=["GRAPHIC_INTERPRETATION_UNAVAILABLE"] * 2),
             page(1, state="error", classification="graphic_uncertain", blocks=0, alnum=0),
             page(2, state="blank", classification="blank", blocks=0, alnum=0)]
    assert text_loss(extraction(pages)) is False


@pytest.mark.parametrize("pages, options", [
    ([page(0, regions=["OCR_ORIENTATION_UNRESOLVED"])], {}),
    ([page(0, state="error", regions=["DOCLING_CONVERSION_FAILED"], blocks=0)], {}),
    ([page(0, state="error", classification="native", blocks=0, alnum=40)], {}),
    ([page(0, state="error", classification="graphic_uncertain", blocks=0, alnum=3)], {}),
    ([page(0, regions=["GRAPHIC_INTERPRETATION_UNAVAILABLE"])], {"parser_complete": None}),
    ([page(0, regions=["GRAPHIC_INTERPRETATION_UNAVAILABLE"])], {"parser_complete": False}),
    ([page(0)], {"page_count": 2}),
])
def test_any_real_or_unproven_text_loss_keeps_the_explicit_publication(pages, options):
    assert text_loss(extraction(pages, **options)) is True


def test_a_complete_extraction_is_never_partial():
    assert text_loss(extraction([page(0)], status="ready", parser_complete=None)) is False
