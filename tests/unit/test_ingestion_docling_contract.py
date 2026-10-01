"""Contrat des membres privés de Docling sur lesquels repose `services/ingestion/regional_grid.py` (constat C13).

`regional_pipeline_class()` dérive `TesseractOcrCliModel` et `StandardPdfPipeline` et lit des attributs privés
de Docling 2.131.0 (version verrouillée, incluse dans l'empreinte d'extraction). Une montée de version qui
renomme, retire ou cesse d'appeler l'un d'eux casserait l'OCR régional sans erreur d'import : ces essais
échouent avant. Membres vérifiés, avec la ligne de `regional_grid.py` qui les emploie :

- `TesseractOcrCliModel.__init__(enabled, artifacts_path, options, accelerator_options)` : construction par mots-clés (l. 373) ;
- surcharges appelées par la classe de base : `get_ocr_rects(page)` (l. 178), `__call__(conv_res, page_batch)` (l. 215),
  `_perform_osd(ifilename)` (l. 224), `_run_tesseract(ifilename, osd)` (l. 286) ;
- méthodes privées appelées : `_parse_language` (l. 258), `_sanitize_lang` (l. 260), `_sanitize_filename` (l. 268) ;
- attributs privés lus : `_safe_tesseract_cmd` (l. 256), `_auto_script` (l. 257), `_native_codes` (l. 261),
  `_safe_tessdata_path` (l. 263), avec `scale` et `options.psm` ;
- fonction privée du module : `_parse_orientation` (l. 227, 245), dont la convention d'angle est enregistrée ;
- `Page._backend` et ses méthodes `get_visible_text_cells`, `get_text_cells`, `get_bitmap_rects` (l. 184-187) ;
- `StandardPdfPipeline._init_models()` et `_make_ocr_model(art_path)` (l. 363, 370), dont les attributs
  `ocr_model` et `table_model` alimentent les étapes de `_create_run_ctx` ;
- `tesseract_utils.tesseract_box_to_bounding_rectangle(bbox, *, original_offset, scale, orientation, im_size)` (l. 339-350).
"""

import importlib.metadata
import importlib.util
import inspect

import pytest

VERIFIED_DOCLING = "2.131.0"
DOCLING_MISSING = (f"Docling {VERIFIED_DOCLING}, dépendance verrouillée (pyproject.toml, uv.lock), est introuvable : "
                   "environnement incomplet, le contrat C13 n'est pas vérifié. Resynchroniser l'environnement "
                   "(`uv sync --locked`, ou le provisionnement du lanceur) puis relancer ces essais.")


def require_docling(find_spec=importlib.util.find_spec):
    """Échec explicite, jamais un essai ignoré : Docling fait partie de l'environnement verrouillé."""
    if find_spec("docling") is None:
        pytest.fail(DOCLING_MISSING, pytrace=False)


@pytest.fixture(autouse=True)
def docling_installed():
    require_docling()


def test_missing_docling_fails_instead_of_being_skipped():
    with pytest.raises(pytest.fail.Exception, match="dépendance verrouillée"):
        require_docling(lambda name: None)


def parameters(function):
    return list(inspect.signature(function).parameters)


def test_docling_version_is_the_one_whose_private_members_were_verified():
    assert importlib.metadata.version("docling") == VERIFIED_DOCLING, (
        "Montée de Docling : revérifier les membres privés listés dans ce module et regional_grid.py, "
        "puis mettre à jour VERIFIED_DOCLING")


def test_tesseract_cli_model_members_used_by_grid_aware_tesseract():
    from docling.models.stages.ocr.tesseract_ocr_cli_model import TesseractOcrCliModel

    assert parameters(TesseractOcrCliModel.__init__) == ["self", "enabled", "artifacts_path", "options", "accelerator_options"]
    assert parameters(TesseractOcrCliModel.get_ocr_rects) == ["self", "page"]
    assert parameters(TesseractOcrCliModel.__call__) == ["self", "conv_res", "page_batch"]
    assert parameters(TesseractOcrCliModel._perform_osd) == ["self", "ifilename"]
    assert parameters(TesseractOcrCliModel._run_tesseract) == ["self", "ifilename", "osd"]
    assert parameters(TesseractOcrCliModel._parse_language) == ["self", "df_osd"]
    for name in ("_sanitize_lang", "_sanitize_filename"):
        assert isinstance(inspect.getattr_static(TesseractOcrCliModel, name), staticmethod), name
    assert TesseractOcrCliModel._sanitize_lang("fra") == "fra"


def test_base_ocr_loop_still_dispatches_to_the_overridden_methods():
    from docling.models.stages.ocr.tesseract_ocr_cli_model import TesseractOcrCliModel

    source = inspect.getsource(TesseractOcrCliModel.__call__)
    for call in ("self.get_ocr_rects(page)", "self._perform_osd(", "self._run_tesseract(", "page._backend"):
        assert call in source, call


def test_private_attributes_exist_without_probing_a_tesseract_binary():
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import TesseractCliOcrOptions
    from docling.models.stages.ocr.tesseract_ocr_cli_model import TesseractOcrCliModel

    # enabled=False : le constructeur n'appelle pas `tesseract --version` ni `--list-langs`.
    model = TesseractOcrCliModel(enabled=False, artifacts_path=None, accelerator_options=AcceleratorOptions(),
                                 options=TesseractCliOcrOptions(lang=["fra", "eng"], tesseract_cmd="/opt/ocr/tesseract",
                                                                path="/opt/ocr/tessdata"))
    assert model._safe_tesseract_cmd == "/opt/ocr/tesseract"
    assert model._safe_tessdata_path is not None and model._safe_tessdata_path.endswith("tessdata")
    assert model._auto_script is False and model._native_codes == []
    assert model.scale == model.options.scale and hasattr(model.options, "psm")


def test_osd_orientation_convention_recorded_by_regional_grid():
    import pandas as pd
    from docling.models.stages.ocr.tesseract_ocr_cli_model import _parse_orientation

    observed = {angle: _parse_orientation(pd.DataFrame({"key": ["Orientation in degrees"], "value": [f" {angle}"]}))
                for angle in (0, 90, 180, 270)}
    assert observed == {0: 0, 90: 270, 180: 180, 270: 90}


@pytest.mark.parametrize("module,name", [("docling.backend.pypdfium2_backend", "PyPdfiumPageBackend"),
                                         ("docling.backend.docling_parse_backend", "ThreadedDoclingParsePageBackend")])
def test_page_backend_members_read_through_page_backend(module, name):
    import importlib

    from docling.datamodel.base_models import Page

    assert "_backend" in Page.__private_attributes__
    backend = getattr(importlib.import_module(module), name)
    assert parameters(backend.get_visible_text_cells) == ["self"]
    assert parameters(backend.get_text_cells) == ["self"]
    assert parameters(backend.get_bitmap_rects) == ["self", "scale"]
    assert parameters(backend.get_page_image) == ["self", "scale", "cropbox"]


def test_standard_pipeline_hooks_replaced_by_regional_pipeline():
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

    assert parameters(StandardPdfPipeline._init_models) == ["self"]
    assert parameters(StandardPdfPipeline._make_ocr_model) == ["self", "art_path"]
    initialisation = inspect.getsource(StandardPdfPipeline._init_models)
    assert "self.ocr_model = self._make_ocr_model(art_path)" in initialisation
    assert "self.table_model =" in initialisation
    # Les étapes sont construites après `_init_models` à partir des attributs, que la sous-classe remplace.
    stages = inspect.getsource(StandardPdfPipeline._create_run_ctx)
    assert "model=self.ocr_model" in stages and "model=self.table_model" in stages
    assert {"do_ocr", "ocr_options", "accelerator_options"} <= set(PdfPipelineOptions.model_fields)


def test_tesseract_box_conversion_signature():
    from docling.models.stages.ocr.tesseract_utils import tesseract_box_to_bounding_rectangle

    signature = inspect.signature(tesseract_box_to_bounding_rectangle)
    assert list(signature.parameters) == ["bbox", "original_offset", "scale", "orientation", "im_size"]
    assert all(signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
               for name in ("original_offset", "scale", "orientation", "im_size"))


def test_regional_pipeline_class_builds_against_installed_docling():
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

    from services.ingestion.regional_grid import regional_pipeline_class

    pipeline = regional_pipeline_class()
    assert issubclass(pipeline, StandardPdfPipeline)
    assert {"_init_models", "_make_ocr_model"} <= set(vars(pipeline))
