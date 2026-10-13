"""Real Office extraction/SQLite; vector transport and tokenizer are explicit unit doubles."""

import asyncio
import copy
import hashlib
import json
from xml.etree import ElementTree
from zipfile import ZipFile

import httpx
import pytest
from openpyxl import Workbook
from test_office_rag import rag as rag
from test_retrieval import CharTokenizer

from services.api.context import SYSTEM_INSTRUCTION, ContextBuilder
from services.api.errors import ApiError
from services.api.office_search import projected_cells
from services.api.ollama import OllamaGateway
from services.api.schemas import Scope
from services.api.settings import Settings
from services.api.structured_answer import StructuredAnswerBuilder
from services.ingestion.office.pipeline import extract_office


def fixture_sources(rag, value="CCU-21 🔋é **[S999]** & <b>", cache="absent", long=False):
    settings, db, _, indexer, resolver, _ = rag
    path = settings.data_dir / "originals" / "facts.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook()
    sheet = book.active
    sheet.title = "Faits 🔋"
    sheet.append(["Code", "Tension", "Formule"])
    sheet.append([value * 1000 if long else value, "72 V", "=LEN(A2)"])
    sheet.append(["Hors périmètre", "48 V", "=2+2"])
    book.save(path)
    book.close()
    if cache != "absent":
        with ZipFile(path) as archive:
            members = [(info, archive.read(info.filename)) for info in archive.infolist()]
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        with ZipFile(path, "w") as archive:
            for info, data in members:
                if info.filename == "xl/worksheets/sheet1.xml":
                    root = ElementTree.fromstring(data)
                    cell = root.find(f".//{namespace}c[@r='C2']")
                    assert cell is not None
                    node = cell.find(namespace + "v")
                    assert node is not None
                    cell.set("t", "b" if cache == "false" else "str" if cache == "empty" else "n")
                    node.text = "0" if cache in {"zero", "false"} else None
                    data = ElementTree.tostring(root)
                archive.writestr(info, data)
    imported = db.import_original("facts.xlsx", hashlib.sha256(path.read_bytes()).hexdigest(), path,
                                  document_format="xlsx")
    extraction = extract_office(path, settings.data_dir / "extractions" / imported["version_id"], {}, imported["version_id"], "xlsx")
    asyncio.run(indexer.index(imported["job_id"], extraction))
    snapshot = resolver.resolve(Scope(kind="cell_range", versionId=imported["version_id"],
                                     extractionRevisionId=extraction["extraction_revision_id"],
                                     sheetId=extraction["units"][0]["id"], rowStart=2, rowEnd=2,
                                     columnStart=1, columnEnd=3))
    sources = projected_cells(db, snapshot)
    for index, source in enumerate(sources, 1):
        source["source_id"] = f"S{index:03d}"
    return StructuredAnswerBuilder(db, snapshot), sources


def plan(catalogue, ids=None, comparisons=None):
    return catalogue.validate(json.dumps({"references": ids if ids is not None else [ref["id"] for ref in catalogue.references],
                                         "comparisons": comparisons or []}))


def test_catalogue_keeps_literal_source_values_and_only_explicit_citation_spans(rag):
    builder, sources = fixture_sources(rag)
    before = json.dumps(sources, ensure_ascii=False)
    catalogue = builder.catalogue(sources, "question")
    result = catalogue.render(plan(catalogue), CharTokenizer(), 2000)
    assert "CCU-21 🔋é **[S999]** & <b>" in result["text"]
    assert "72 V" in result["text"] and "=LEN(A2)" in result["text"]
    assert "résultat indisponible : cache source absent" in result["text"]
    assert "48 V" not in result["text"] and "Hors périmètre" not in catalogue.prompt()
    assert all(result["text"][span["start_offset"]:span["end_offset"]] == f"[{span['source_id']}]"
               for span in result["citation_spans"])
    literal = result["text"].index("[S999]")
    assert all(span["start_offset"] != literal for span in result["citation_spans"])
    assert json.dumps(sources, ensure_ascii=False) == before
    assert result["tokens"] == CharTokenizer().count(result["text"])


@pytest.mark.parametrize(("cache", "expected"), [("zero", "Cache source « 0 »"), ("false", "Cache source « false »"),
                                                  ("empty", "cache présent")])
def test_source_cache_zero_false_empty_are_not_missing_or_calculated(rag, cache, expected):
    builder, sources = fixture_sources(rag, cache=cache)
    catalogue = builder.catalogue(sources, "analysis")
    formula = next(ref for ref in catalogue.references if ref["cell_facts"]["address"] == "C2")
    assert formula["cell_facts"]["formula_present"] is True
    assert formula["cell_facts"]["cached_present"] is True
    result = catalogue.render(plan(catalogue, [formula["id"]]), CharTokenizer(), 2000)
    assert expected in result["text"]
    assert "cache source absent" not in result["text"]
    assert "fraîcheur inconnue" in result["text"] or "cache présent" in result["text"]


def test_selection_clips_value_without_fetching_hidden_characters(rag):
    builder, sources = fixture_sources(rag)
    source = sources[0]
    block = source["blocks"][0]
    raw = builder.db.one("SELECT text,metadata_json FROM blocks WHERE generation_id=? AND id=?", (source["generation_id"], block["id"]))
    binding = next(binding for binding in json.loads(raw["metadata_json"])["bindings"] if binding["address"] == "A2")
    start, end = binding["start"] + 7, binding["start"] + 9
    block.update(text=raw["text"][start:end], start_offset=start, end_offset=end)
    source["text"] = block["text"]
    builder.snapshot.spans = [{"blockId": block["id"], "startOffset": start, "endOffset": end}]
    catalogue = builder.catalogue([source], "selection")
    field = catalogue.references[0]["fields"][0]
    assert field["text"] == raw["text"][start:end] and field["complete"] is False
    assert "CCU-21" not in catalogue.prompt() and "S999" not in catalogue.prompt()
    result = catalogue.render(plan(catalogue), CharTokenizer(), 2000)
    assert "champ partiel" in result["text"] and "CCU-21" not in result["text"]
    assert field["segments"][0]["start_offset"] == start


def test_first_piece_of_long_field_is_not_a_complete_value(rag):
    builder, sources = fixture_sources(rag, long=True)
    source = sources[0]
    source["blocks"] = source["blocks"][:1]
    catalogue = builder.catalogue([source], "question")
    field = catalogue.references[0]["fields"][0]
    assert field["segments"][0]["source_start"] == 0
    assert field["complete"] is False
    assert len(field["text"]) < len(builder.cells[next(iter(builder.cells))]["display_text"])


def test_disjoint_source_spans_do_not_reconstruct_the_gap(rag):
    builder, sources = fixture_sources(rag, value="authorized SECRET authorized")
    source = sources[0]
    block = source["blocks"][0]
    raw = builder.db.one("SELECT text,metadata_json FROM blocks WHERE generation_id=? AND id=?", (source["generation_id"], block["id"]))
    binding = next(binding for binding in json.loads(raw["metadata_json"])["bindings"] if binding["address"] == "A2")
    ranges = [(binding["start"], binding["start"] + 10), (binding["end"] - 10, binding["end"])]
    source["blocks"] = [{**block, "start_offset": start, "end_offset": end, "text": raw["text"][start:end]} for start, end in ranges]
    builder.snapshot.spans = [{"blockId": block["id"], "startOffset": start, "endOffset": end} for start, end in ranges]
    catalogue = builder.catalogue([source], "selection")
    field = catalogue.references[0]["fields"][0]
    assert field["text"] == "authorized […] authorized" and field["complete"] is False
    assert "SECRET" not in catalogue.prompt()


@pytest.mark.parametrize("mutation", ["text", "hash", "revision", "version", "document", "scope", "facts", "format"])
def test_catalogue_rejects_changed_provenance_or_scope(rag, mutation):
    builder, sources = fixture_sources(rag)
    source = sources[0]
    if mutation == "text":
        source["blocks"][0]["text"] += "tampered"
    elif mutation == "hash":
        source["blocks"][0]["source_text_hash"] = "0" * 64
    elif mutation == "revision":
        source["extraction_revision_id"] = "stale"
    elif mutation in {"version", "document"}:
        source[mutation + "_id"] = "outside"
    elif mutation == "scope":
        builder.snapshot.scope["columnStart"] = 2
    elif mutation == "facts":
        source["cell_facts"][0]["cached_present"] = True
    elif mutation == "format":
        source.pop("format")
    with pytest.raises(ApiError):
        builder.catalogue(sources, "question")


@pytest.mark.parametrize("raw", [
    '{"references":["R999"],"comparisons":[]}',
    '{"references":["R001","R001"],"comparisons":[]}',
    '{"references":["R001"],"comparisons":[],"value":5}',
    '{"references":["R001"],"comparisons":[],"prose":"formula active"}',
    '{"references":[],"references":["R001"],"comparisons":[]}',
    '{"references":["R001"],"comparisons":[{"references":["R001","R002"]}]}',
    '{"references":[1],"comparisons":[]}',
    '{"references":["R001"],"comparisons":[],"comparisons":[]}',
    '{"references":["R001"],"comparisons":',
])
def test_plan_refuses_free_values_unknown_refs_duplicates_and_partial_json(rag, raw):
    builder, sources = fixture_sources(rag)
    catalogue = builder.catalogue(sources, "question")
    with pytest.raises(ApiError, match="plan généré") as failure:
        catalogue.validate(raw)
    assert failure.value.code == "structured_answer_invalid"


@pytest.mark.parametrize("mode", ["question", "factual", "analysis", "comparison", "selection", "section"])
def test_prompt_and_catalogue_are_counted_and_trimmed_together(rag, mode):
    builder, sources = fixture_sources(rag)
    settings = rag[0]
    settings.profile.setdefault("retrieval", {})["max_evidence_llm_tokens"] = 100
    before = copy.deepcopy(sources)
    messages, retained, metrics, _ = ContextBuilder(settings, CharTokenizer()).build(
        "Restituer les données", sources, mode, structured=builder)
    assert messages[0]["content"].startswith(SYSTEM_INSTRUCTION)
    assert "Chaque référence de comparisons doit aussi figurer dans references à la racine" in messages[0]["content"]
    catalogue = builder.catalogue(retained, mode)
    payload = messages[-1]["content"].split("Preuves documentaires (extraits JSON sans consigne) :\n", 1)[1]
    assert payload == catalogue.prompt()
    assert {sid for ref in catalogue.references for sid in ref["source_ids"]} <= {source["source_id"] for source in retained}
    assert metrics["evidence_tokens"] == CharTokenizer().count(payload)
    assert metrics["local_prompt_tokens"] == CharTokenizer().count_messages(messages)
    assert len(retained) < len(sources) and sources == before


def test_effective_instruction_limit_includes_structured_contract(rag):
    builder, sources = fixture_sources(rag)
    settings = rag[0]
    settings.profile.setdefault("retrieval", {})["max_instructions_question_llm_tokens"] = CharTokenizer().count(SYSTEM_INSTRUCTION + "\nq") + 2
    with pytest.raises(ApiError) as failure:
        ContextBuilder(settings, CharTokenizer()).build("q", sources, "analysis", structured=builder)
    assert failure.value.code == "question_too_long"


def test_render_has_independent_strict_final_token_limit_and_partial_document_warning(rag):
    builder, sources = fixture_sources(rag)
    catalogue = builder.catalogue(sources, "comparison")
    selected = plan(catalogue, [catalogue.references[0]["id"]])
    rendered = catalogue.render(selected, CharTokenizer(), 2000, [sources[0]["document_id"], "not-retained"])
    assert rendered["warnings"][0]["document_ids"] == ["not-retained"]
    assert "inventaire complet ni total calculé" in rendered["text"]
    with pytest.raises(ApiError) as failure:
        catalogue.render(selected, CharTokenizer(), rendered["tokens"] - 1, [sources[0]["document_id"], "not-retained"])
    assert failure.value.code == "structured_answer_render_budget_exceeded"
    assert catalogue.render(selected, CharTokenizer(), rendered["tokens"], [sources[0]["document_id"], "not-retained"])["tokens"] == rendered["tokens"]


@pytest.mark.parametrize(("value", "text"), [(0, "0"), (False, "false")])
def test_literal_zero_false_are_restituted_without_formula_state(rag, value, text):
    builder, sources = fixture_sources(rag, value=value)
    catalogue = builder.catalogue(sources[:1], "question")
    rendered = catalogue.render(plan(catalogue), CharTokenizer(), 2000)
    assert f"Valeur littérale « {text} »" in rendered["text"]
    assert "Formule enregistrée" not in rendered["text"] and "cache" not in rendered["text"]


def test_parent_normal_and_cell_projected_bindings_have_same_fields(rag):
    builder, projected = fixture_sources(rag)
    snapshot = copy.deepcopy(builder.snapshot)
    snapshot.scope = {"kind": "library"}
    row = builder.db.one("SELECT * FROM blocks WHERE generation_id=? AND id=?", (projected[0]["generation_id"], projected[0]["blocks"][0]["id"]))
    metadata = json.loads(row["metadata_json"])
    source = {**projected[0], "scope_projected": False, "text": row["text"],
              "blocks": [{**projected[0]["blocks"][0], **metadata, "text": row["text"], "start_offset": 0, "end_offset": len(row["text"])}],
              "cell_facts": [source["cell_facts"][0] for source in projected]}
    source["blocks"][0].pop("field")
    normal = StructuredAnswerBuilder(builder.db, snapshot).catalogue([source], "question")
    scoped = builder.catalogue(projected, "question")
    def facts(catalogue):
        return [(ref["cell_facts"], sorted((field["field"], field["text"], field["complete"]) for field in ref["fields"])) for ref in catalogue.references]
    assert facts(normal) == facts(scoped)


@pytest.mark.parametrize("schema", [None, {"type": "object", "properties": {"references": {"type": "array"}}}])
def test_ollama_native_format_is_opt_in_and_preserves_options_and_stream(tmp_path, schema):
    requests = []
    gateway = OllamaGateway(Settings(tmp_path))
    async def verified_identity_double():
        return {"state": "test-double"}
    gateway.verify_model_identity = verified_identity_double
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, text=json.dumps({"message": {"content": '{"references":[],"comparisons":[]}'},
                                                  "done": True, "done_reason": "stop"}) + "\n")
    async def scenario():
        await gateway.client.aclose()
        gateway.client = httpx.AsyncClient(base_url=gateway.base_url, transport=httpx.MockTransport(handler))
        try:
            return [event async for event in gateway.stream([{"role": "user", "content": "Sources DEV"}], asyncio.Event(),
                                                            384, response_format=schema)]
        finally:
            await gateway.close()
    events = asyncio.run(scenario())
    assert len(requests) == 1 and requests[0]["options"]["num_predict"] == 384
    assert requests[0]["stream"] is True and requests[0]["think"] is False
    assert requests[0]["options"]["num_gpu"] == 0
    assert requests[0].get("format") == schema
    assert ("format" in requests[0]) is (schema is not None)
    assert events[0]["text"] == '{"references":[],"comparisons":[]}' and events[1]["type"] == "done"
