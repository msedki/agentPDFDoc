"""True, generated Office containers and source-level oracles; no running RAG."""

import hashlib
import json
import runpy
from dataclasses import replace
from pathlib import Path

import pytest

from services.ingestion.errors import IngestionError
from services.ingestion.office.models import OfficeLimits
from services.ingestion.office.opc import OfficePackage
from services.ingestion.office.xlsx import address_coordinates, parse_xlsx, range_coordinates

CASES = runpy.run_path(str(Path(__file__).parents[1] / "fixtures" / "office" / "xlsx_cases.py"))


def extract(tmp_path, *, strict=False, date1904=False, parts=None, limits=None, checkpoint=None):
    source = CASES["write_workbook"](tmp_path / "source.xlsx", strict=strict, date1904=date1904, parts=parts)
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    with OfficePackage(source, expected_format="xlsx", limits=limits) as package:
        result = parse_xlsx(package, checkpoint=checkpoint)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    return result


def cells(result, sheet=0):
    return {cell["address"]: cell for cell in result["units"][sheet]["cells"]}


@pytest.mark.parametrize("strict", [False, True])
def test_source_order_structures_comments_relationships_and_metadata(tmp_path, strict):
    result = extract(tmp_path, strict=strict)
    assert result["status"] == "ready" and result["parser_complete"]
    assert result["coverage"]["cells"] == 27
    assert [unit["title"] for unit in result["units"]] == ["Budget été", "Historique"]
    first, second = result["units"]
    assert first["metadata"]["visibility"] == "visible"
    assert second["metadata"]["visibility"] == "veryHidden"
    assert second["metadata"]["source_sheet_id"] == "7"
    assert first["metadata"]["merged_ranges"] == ["A10:C10"]
    assert first["metadata"]["column_properties"][0]["hidden"] == "1"
    assert first["metadata"]["row_properties"][0]["hidden"] == "1"
    assert first["metadata"]["bounds"] == {"row_start": 1, "column_start": 1,
                                            "row_end": 1048576, "column_end": 16384}
    assert first["metadata"]["declared_dimension"] == "A1"
    assert result["tables"][0]["name"] == "BudgetTable"
    assert result["tables"][0]["cell_range"] == "A1:C4"
    assert result["tables"][0]["columns"][2]["children"][0]["text"] == "B2*2"
    assert result["metadata"]["defined_names"][0]["text"] == "'Budget été'!$A$1:$C$4"
    assert result["metadata"]["defined_names"][1]["text"] == "'[other.xlsx]Data'!$B$2"
    assert result["metadata"]["properties"]["core-properties"]["children"][0]["text"] == "Budget fixture"
    assert cells(result)["B2"]["comment"]["text"] == "Vérifier le budget."
    assert first["metadata"]["orphan_comments"][0]["address"] == "D20"
    assert first["metadata"]["hyperlinks"][0]["relation"]["external"] is True
    assert cells(result, 1)["C1"]["formula"]["external_reference_present"] is True
    assert cells(result, 1)["B1"]["formula"]["references"] == ["'Budget été'!B2"]


def test_exact_numbers_types_empty_cells_and_rich_text(tmp_path):
    result = extract(tmp_path)
    native = cells(result)
    assert native["B2"]["raw_value"] == "9007199254740993"
    assert native["B2"]["value"] == {"kind": "number", "value": "9007199254740993"}
    assert native["B3"]["display_text"] == "0"
    assert native["B4"]["data_type"] == "error" and native["B4"]["value"]["value"] == "#DIV/0!"
    assert native["A5"]["value"] == {"kind": "boolean", "value": False}
    assert native["A5"]["display_text"] == "false"
    assert native["A3"]["value"]["kind"] == "string" and native["A3"]["value"]["value"] == ""
    assert native["A9"]["value_element_present"] and native["A9"]["raw_value"] is None
    assert "D3" not in native
    assert native["A2"]["value"]["value"] == "Projet alpha"
    assert len(native["A2"]["value"]["rich_text"]) == 2
    assert "not-visible-phonetics" not in json.dumps(result)


def test_formula_and_cache_presence_staleness_never_recalculate(tmp_path):
    result = extract(tmp_path)
    native = cells(result)
    assert native["C2"]["formula"]["raw_text"] == "B2*2"
    assert native["C2"]["value"] is None
    assert native["C2"]["cached_value"]["value"] == "18014398509481986"
    assert native["C2"]["cached_present"] and native["C2"]["cache_freshness"] == "unknown"
    assert native["C3"]["cache"]["element_present"] is True
    assert native["C3"]["cached_value"] is None and not native["C3"]["cached_present"]
    assert native["C3"]["cache_freshness"] == "absent"
    assert native["C4"]["cached_value"]["value"] == "1"  # Known deliberately stale cache stays stale.
    assert native["C4"]["cache_freshness"] == "unknown"
    assert result["metadata"]["calculation"]["fullCalcOnLoad"] == "1"
    assert result["metadata"]["formula_evaluation"] == "never"
    assert all(not native[address]["cache"]["evaluated"] for address in ["C2", "C3", "C4"])


def test_shared_array_dynamic_source_metadata_are_distinct(tmp_path):
    result = extract(tmp_path)
    native = cells(result)
    master = native["A6"]["formula"]
    follower = native["A7"]["formula"]
    assert master["attributes"] == {"t": "shared", "si": "2", "ref": "A6:A7"}
    assert follower["raw_text"] is None
    assert follower["effective_text"] == "B7+$B$2"
    assert follower["shared_source_address"] == "A6"
    assert follower["resolution"] == "translated_shared_source"
    assert native["B6"]["formula"]["type"] == "array"
    assert native["B6"]["formula"]["attributes"]["ref"] == "B6:B7"
    assert native["B7"]["formula"] is None  # The dependent value is not an invented formula.
    assert native["C6"]["attributes"]["cm"] == "1"
    assert native["C6"]["cell_metadata"]["index"] == 1
    assert native["C6"]["formula"]["dynamic_array_metadata"]["evaluated"] is False
    assert "dynamicArrayProperties" in json.dumps(result["metadata"]["cell_metadata"])
    assert native["C6"]["formula"]["raw_text"].startswith("_xlfn._xlws.FILTER")


@pytest.mark.parametrize("date1904", [False, True])
def test_dates_keep_original_epoch_serial_and_leap_day(tmp_path, date1904):
    result = extract(tmp_path, date1904=date1904)
    native = cells(result)
    assert result["metadata"]["date_system"] == ("1904" if date1904 else "1900")
    assert native["B5"]["raw_value"] == "60" and native["B5"]["number_format"] == "mm-dd-yy"
    if date1904:
        assert native["B5"]["value"]["value"] == "1904-03-01T00:00:00"
    else:
        assert native["B5"]["value"]["excel_1900_leap_day"] is True
        assert native["B5"]["value"]["value"] is None
    assert native["C5"]["value"]["value"] == "2026-10-09T12:30:00+00:00"
    assert native["B8"]["value"] == {"kind": "duration", "value": "216000.0", "unit": "seconds", "serial": "2.5"}
    assert native["B5"]["style"]["properties"]["alignment"]["horizontal"] == "right"


def test_sparse_dimensions_never_materialize_the_rectangle(tmp_path, monkeypatch):
    import openpyxl

    monkeypatch.setattr(openpyxl, "load_workbook", lambda *_args, **_kwargs: pytest.fail("No full workbook copy"))
    source = CASES["sparse_workbook"](tmp_path / "source.xlsx", present_cells=10_000)
    with OfficePackage(source) as package:
        result = parse_xlsx(package)
    assert len(result["units"][0]["cells"]) == 10_000
    assert result["units"][0]["metadata"]["bounds"]["column_end"] == 1
    assert len(result["units"][0]["blocks"]) == 10_000
    assert result["units"][0]["metadata"]["declared_dimension"] == "A1:XFD1048576"


def test_derived_blocks_preserve_unicode_offsets_and_bounded_wide_cells(tmp_path):
    parts = CASES["workbook_parts"]()
    value = "é🙂 budget " * 25
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace("Projet ", value)
    # Use a long inline string, not a shared-string mutation that changes the oracle's part.
    parts["xl/sharedStrings.xml"] = parts["xl/sharedStrings.xml"].replace("Projet ", value)
    result = extract(tmp_path, parts=parts, limits=replace(OfficeLimits(), max_block_chars=80))
    for unit in result["units"]:
        native = cells(result, unit["order_index"])
        for block in unit["blocks"]:
            assert len(block["text"]) <= 80
            assert "page" not in block["locator"] and block["locator"]["kind"] == "xlsx_cells"
            for binding in block["bindings"]:
                source = native[binding["address"]]
                field = binding["field"]
                text = source["display_text"] if field == "value" else (
                    "=" + source["formula"]["effective_text"] if field == "formula" else (
                        source["comment"]["text"] if field == "comment" else (
                            "cache de formule : fraîcheur inconnue" if source["cached_present"] else "cache de formule absent")))
                assert block["text"][binding["start"]:binding["end"]] == text[binding["source_start"]:binding["source_end"]]
    bindings = [binding for block in result["units"][0]["blocks"] for binding in block["bindings"]
                if binding["address"] == "A2" and binding["field"] == "value"]
    assert len(bindings) > 1
    assert sum(binding["end"] - binding["start"] for binding in bindings) == len(value + "alpha")


@pytest.mark.parametrize("limit,value", [("max_cells", 10), ("max_shared_strings", 1),
    ("max_cell_chars", 2), ("max_blocks", 2), ("max_units", 1), ("max_text_chars", 30)])
def test_declared_quotas_fail_without_successful_partial_result(tmp_path, limit, value):
    parts = CASES["workbook_parts"]()
    if limit == "max_shared_strings":
        parts["xl/sharedStrings.xml"] = parts["xl/sharedStrings.xml"].replace("</sst>", "<si><t>extra</t></si></sst>")
    with pytest.raises(IngestionError) as caught:
        extract(tmp_path, parts=parts, limits=replace(OfficeLimits(), **{limit: value}))
    assert caught.value.code == "OFFICE_LIMIT_EXCEEDED"


@pytest.mark.parametrize("before,after", [
    ('r="B2"><v>9007199254740993', 'r="A2"><v>9007199254740993'),
    ('r="2"><c r="A2"', 'r="1"><c r="A2"'),
    ('r="XFD1048576"', 'r="XFE1048576"'),
    ('<v>9007199254740993</v>', '<v>NaN</v>'),
    ('r="A2" t="s"><v>0', 'r="A2" t="s"><v>99'),
    ('r="B5" s="1"', 'r="B5" s="99"'),
])
def test_semantically_corrupt_cells_refused(tmp_path, before, after):
    parts = CASES["workbook_parts"]()
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace(before, after)
    with pytest.raises(IngestionError):
        extract(tmp_path, parts=parts)


def test_unresolved_shared_formula_is_partial_and_visible(tmp_path):
    parts = CASES["workbook_parts"]()
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace('<f t="shared" si="2"/>', '<f t="shared" si="99"/>')
    result = extract(tmp_path, parts=parts)
    assert result["status"] == "ready_partial" and not result["parser_complete"]
    assert cells(result)["A7"]["formula"]["raw_text"] is None
    assert cells(result)["A7"]["formula"]["effective_text"] is None
    assert cells(result)["A7"]["formula"]["resolution"] == "unresolved_shared"
    assert result["warnings"][0]["code"] == "XLSX_FORMULA_UNRESOLVED"


def test_checkpoint_pause_propagates_without_claiming_completion(tmp_path):
    seen = []

    def checkpoint(key):
        seen.append(key)
        if key.endswith(":row:3"):
            raise IngestionError("CHECKPOINT_REQUESTED", "Pause fixture")

    with pytest.raises(IngestionError) as caught:
        extract(tmp_path, checkpoint=checkpoint)
    assert caught.value.code == "CHECKPOINT_REQUESTED"
    assert [key.rsplit(":", 1)[-1] for key in seen] == ["1", "2", "3"]


def test_deterministic_ids_and_json_serialization(tmp_path):
    first = extract(tmp_path)
    second = extract(tmp_path)
    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(second, sort_keys=True, ensure_ascii=False)
    assert first["units"][0]["id"] == "xlsx:xl/worksheets/sheet1.xml"
    assert first["units"][0]["blocks"][0]["id"].endswith(":row:1:part:0")


def test_native_table_headers_are_structural_metadata_not_injected_cell_text(tmp_path):
    result = extract(tmp_path)
    block = result["units"][0]["blocks"][1]
    assert block["structure"]["headers_included"] is False
    context = block["structure"]["table_contexts"][0]
    assert context["name"] == "BudgetTable"
    assert context["headers"][1] == {"column": 2, "label": "Amount", "provenance": "table_column_metadata",
                                       "part": "xl/tables/table1.xml", "header_source_row": 1}
    assert all(binding["row"] == 2 for binding in block["bindings"])


def test_optional_source_row_and_cell_addresses_follow_source_positions(tmp_path):
    parts = CASES["workbook_parts"]()
    ns = CASES["TRANSITIONAL"]
    parts["xl/worksheets/sheet1.xml"] = f'<worksheet xmlns="{ns}"><sheetData><row>'
    parts["xl/worksheets/sheet1.xml"] += '<c t="inlineStr"><is><t>implicit A1</t></is></c><c><v>2</v></c></row>'
    parts["xl/worksheets/sheet1.xml"] += '<row><c><v>3</v></c></row></sheetData></worksheet>'
    result = extract(tmp_path, parts=parts)
    native = cells(result)
    assert list(native) == ["A1", "B1", "A2"]
    assert all(cell["source_address_kind"] == "implicit_position" for cell in native.values())
    assert all("r" not in cell["attributes"] for cell in native.values())


def test_complete_sheet_cache_reuses_no_sheet_xml_and_preserves_partial_warnings(tmp_path, monkeypatch):
    parts = CASES["workbook_parts"]()
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace('<f t="shared" si="2"/>', '<f t="shared" si="99"/>')
    source = CASES["write_workbook"](tmp_path / "source.xlsx", parts=parts)
    emitted = []
    with OfficePackage(source) as package:
        first = parse_xlsx(package, unit_sink=emitted.append)
    assert len(emitted) == 2
    with OfficePackage(source) as package:
        real_iterator = package.iter_xml

        def iterator(part, events=("end",)):
            if part.startswith("xl/worksheets/"):
                pytest.fail("A fully validated cached sheet should not be parsed again")
            return real_iterator(part, events=events)

        monkeypatch.setattr(package, "iter_xml", iterator)
        reused = parse_xlsx(package, cached_units={unit["id"]: unit for unit in emitted})
    assert json.dumps(reused, sort_keys=True) == json.dumps(first, sort_keys=True)
    assert reused["status"] == "ready_partial"


def test_pause_after_complete_sheet_emits_exactly_one_reusable_unit(tmp_path):
    source = CASES["write_workbook"](tmp_path / "source.xlsx")
    emitted = []

    def pause(key):
        if key == "xlsx:xl/worksheets/sheet1.xml":
            raise IngestionError("CHECKPOINT_REQUESTED", "Pause fixture")

    with OfficePackage(source) as package, pytest.raises(IngestionError):
        parse_xlsx(package, checkpoint=pause, unit_sink=emitted.append)
    assert len(emitted) == 1 and len(emitted[0]["cells"]) == 24
    with OfficePackage(source) as package:
        resumed = parse_xlsx(package, cached_units={emitted[0]["id"]: emitted[0]})
        fresh = parse_xlsx(package)
    assert resumed == fresh


def test_complete_cache_enforces_global_limits_and_wrong_sheet_identity(tmp_path):
    source = CASES["write_workbook"](tmp_path / "source.xlsx")
    with OfficePackage(source) as package:
        first = parse_xlsx(package)
    cached = {unit["id"]: unit for unit in first["units"]}
    with OfficePackage(source, limits=replace(OfficeLimits(), max_cells=25)) as package, pytest.raises(IngestionError) as caught:
        parse_xlsx(package, cached_units=cached)
    assert caught.value.code == "OFFICE_LIMIT_EXCEEDED"
    cached[first["units"][0]["id"]] = dict(first["units"][0], title="Wrong workbook")
    with OfficePackage(source) as package, pytest.raises(IngestionError) as caught:
        parse_xlsx(package, cached_units=cached)
    assert caught.value.code == "OFFICE_INVALID_CHECKPOINT"


def test_unsupported_drawing_is_source_relation_and_visible_partial_coverage(tmp_path):
    parts = CASES["workbook_parts"]()
    rels = "xl/worksheets/_rels/sheet1.xml.rels"
    parts[rels] = parts[rels].replace('</Relationships>', '<Relationship Id="rDrawing" '
        f'Type="{CASES["TRANSITIONAL_REL"]}/drawing" Target="../drawings/drawing1.xml"/></Relationships>')
    parts["xl/drawings/drawing1.xml"] = '<drawing xmlns="urn:fixture"/>'
    result = extract(tmp_path, parts=parts)
    assert result["status"] == "ready_partial" and result["coverage"]["unsupported"] == 1
    warning = next(item for item in result["warnings"] if item["code"] == "XLSX_UNSUPPORTED_OBJECT")
    assert warning["part"] == "xl/drawings/drawing1.xml"
    assert len(cells(result)) == 24  # Source values are still extracted.


@pytest.mark.parametrize("modification", ["dtd", "malformed", "external_read"])
def test_unsafe_xml_rejected_before_adapter_and_never_follows_links(tmp_path, monkeypatch, modification):
    import socket

    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: pytest.fail("No network call permitted"))
    parts = CASES["workbook_parts"]()
    if modification == "dtd":
        parts["xl/sharedStrings.xml"] = '<!DOCTYPE sst [<!ENTITY x "expanded">]>' + parts["xl/sharedStrings.xml"]
    elif modification == "external_read":
        parts["xl/sharedStrings.xml"] = '<!DOCTYPE sst [<!ENTITY x SYSTEM "file:///etc/passwd">]>' + parts["xl/sharedStrings.xml"]
    else:
        parts["xl/sharedStrings.xml"] = '<sst><si>broken'
    with pytest.raises(IngestionError):
        extract(tmp_path, parts=parts)


@pytest.mark.parametrize("address", ["A0", "XFE1", "A1048577", "a1", "$A$1", "A1:B2", "A01"])
def test_invalid_cell_addresses(address):
    with pytest.raises(IngestionError):
        address_coordinates(address)


def test_ranges_do_not_expand_or_accept_reverse_order():
    assert range_coordinates("$A$1:$XFD$1048576") == (1, 1, 1048576, 16384)
    with pytest.raises(IngestionError):
        range_coordinates("B2:A1")


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("cell_type,value_xml,present", [
    ("str", "<v/>", True), ("str", "", False), ("n", "<v/>", False),
])
def test_formula_empty_string_cache_distinct_from_missing_cache(tmp_path, strict, cell_type, value_xml, present):
    parts = CASES["workbook_parts"](strict=strict)
    source_cell = '<c r="A9" t="str"><v></v></c>'
    formula_cell = f'<c r="A9" t="{cell_type}"><f>IF(1=1,&quot;&quot;,&quot;x&quot;)</f>{value_xml}</c>'
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace(source_cell, formula_cell)
    source = CASES["write_workbook"](tmp_path / "source.xlsx", parts=parts)
    with OfficePackage(source) as package:
        result = parse_xlsx(package)
        resumed = parse_xlsx(package, cached_units={unit["id"]: unit for unit in result["units"]})
    assert resumed == result
    cell = cells(result)["A9"]
    assert cell["cached_present"] is present
    assert cell["cached_value"] == ({"kind": "string", "value": ""} if present else None)
    assert cell["data_type"] == ("string" if present else "empty")
    assert cell["cache_freshness"] == ("unknown" if present else "absent")
    assert cell["raw_value"] is None and cell["value"] is None
    assert cell["value_element_present"] is bool(value_xml)
    block = next(block for block in result["units"][0]["blocks"] if block["locator"]["row_start"] == 9)
    expected = "cache de formule : fraîcheur inconnue" if present else "cache de formule absent"
    assert expected in block["text"]
    assert cell["cache"]["evaluated"] is False


@pytest.mark.parametrize("part,closing_tag", [
    ("xl/worksheets/sheet1.xml", "worksheet"), ("xl/workbook.xml", "workbook"),
    ("xl/tables/table1.xml", "table"), ("xl/metadata.xml", "metadata"),
])
def test_unknown_extension_is_preserved_and_explicit_partial_coverage(tmp_path, part, closing_tag):
    parts = CASES["workbook_parts"]()
    extension = '<extLst><ext uri="urn:unknown-version"><q:future xmlns:q="urn:unknown-payload">'
    extension += 'Important semantic extension</q:future></ext></extLst>'
    parts[part] = parts[part].replace(f"</{closing_tag}>", extension + f"</{closing_tag}>")
    source = CASES["write_workbook"](tmp_path / "source.xlsx", parts=parts)
    with OfficePackage(source) as package:
        result = parse_xlsx(package)
        resumed = parse_xlsx(package, cached_units={unit["id"]: unit for unit in result["units"]})
    assert resumed == result
    assert result["status"] == "ready_partial" and not result["parser_complete"]
    assert result["coverage"]["unsupported"] == 1
    warnings = [item for item in result["warnings"] if item["code"] == "XLSX_UNSUPPORTED_EXTENSION"]
    assert len(warnings) == 1 and warnings[0]["part"] == part
    assert warnings[0]["uri"] == "urn:unknown-version"
    assert "Important semantic extension" in json.dumps(result, ensure_ascii=False)
    assert len(cells(result)) == 24


@pytest.mark.parametrize("payload", [
    '<q:dynamicArrayProperties xmlns:q="urn:unknown-payload" fDynamic="1" fCollapsed="0"/>',
    '<da:dynamicArrayProperties fDynamic="1" fCollapsed="0" futureAttribute="1"/>',
    '<da:dynamicArrayProperties fDynamic="1" fCollapsed="0"><da:future/></da:dynamicArrayProperties>',
    '<da:dynamicArrayProperties fDynamic="invalid" fCollapsed="0"/>',
])
def test_dynamic_array_extension_requires_exact_supported_payload(tmp_path, payload):
    parts = CASES["workbook_parts"]()
    parts["xl/metadata.xml"] = parts["xl/metadata.xml"].replace(
        '<da:dynamicArrayProperties fDynamic="1" fCollapsed="0"/>', payload)
    result = extract(tmp_path, parts=parts)
    assert result["status"] == "ready_partial" and result["coverage"]["unsupported"] == 1
    warning = next(item for item in result["warnings"] if item["code"] == "XLSX_UNSUPPORTED_EXTENSION")
    assert warning["part"] == "xl/metadata.xml"


@pytest.mark.parametrize("strict", [False, True])
def test_xstring_decoded_once_shared_inline_cache_comments_and_unicode_bindings(tmp_path, strict):
    parts = CASES["workbook_parts"](strict=strict)
    encoded = "Ligne_x000D_suivante _x005F_x0041_ _xD83D__xDE42_"
    expected = "Ligne\rsuivante _x0041_ 🙂"
    parts["xl/sharedStrings.xml"] = parts["xl/sharedStrings.xml"].replace("Projet ", encoded)
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace("<t>Item</t>", f"<t>{encoded}</t>")
    source_formula = '<c r="C2"><f>B2*2</f><v>18014398509481986</v></c>'
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace(source_formula,
        f'<c r="C2" t="str"><f>&quot;_x0041_&quot;</f><v>{encoded}</v></c>')
    parts["xl/comments1.xml"] = parts["xl/comments1.xml"].replace("Vérifier le budget.", encoded)
    source = CASES["write_workbook"](tmp_path / "source.xlsx", parts=parts)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with OfficePackage(source) as package:
        result = parse_xlsx(package)
        resumed = parse_xlsx(package, cached_units={unit["id"]: unit for unit in result["units"]})
    assert result == resumed
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    native = cells(result)
    assert native["A2"]["value"]["value"] == expected + "alpha"
    assert native["A2"]["value"]["rich_text"][0]["raw_text"] == encoded
    assert native["A1"]["value"]["value"] == expected
    assert native["A1"]["value"]["raw_text"] == encoded
    assert native["C2"]["cached_value"] == {"kind": "string", "value": expected}
    assert native["C2"]["raw_value"] == encoded
    assert native["C2"]["formula"]["raw_text"] == '"_x0041_"'
    assert native["B2"]["comment"]["text"] == expected
    assert native["B2"]["comment"]["raw_text"] == encoded
    for block in result["units"][0]["blocks"]:
        for binding in block["bindings"]:
            cell = native[binding["address"]]
            if binding["field"] in {"value", "comment"}:
                value = cell["display_text"] if binding["field"] == "value" else cell["comment"]["text"]
                assert block["text"][binding["start"]:binding["end"]] == value[binding["source_start"]:binding["source_end"]]
    json.dumps(result, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize("escape", ["_xD800_", "_xDC00_", "_xD83D__x0041_"])
def test_xstring_invalid_surrogate_sequence_refused_without_partial_unicode(tmp_path, escape):
    parts = CASES["workbook_parts"]()
    parts["xl/sharedStrings.xml"] = parts["xl/sharedStrings.xml"].replace("Projet ", escape)
    with pytest.raises(IngestionError) as caught:
        extract(tmp_path, parts=parts)
    assert caught.value.code == "OFFICE_INVALID_XSTRING"


def test_xstring_native_labels_and_number_formats_keep_raw_attributes(tmp_path):
    parts = CASES["workbook_parts"]()
    sheet_name = "Budget_x000D_été"
    label = "Amount_x0009__x005F_x0041_"
    parts["xl/workbook.xml"] = parts["xl/workbook.xml"].replace('name="Budget été"', f'name="{sheet_name}"')
    parts["xl/tables/table1.xml"] = parts["xl/tables/table1.xml"].replace('name="Amount"', f'name="{label}"')
    parts["xl/styles.xml"] = parts["xl/styles.xml"].replace('formatCode="[hh]:mm:ss"', 'formatCode="[hh]:mm:ss_x000D_"')
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace(
        'ref="A2" r:id="rExternal"', 'ref="A2" display="Lien_x0009_budget" tooltip="Voir_x000D_budget" r:id="rExternal"')
    result = extract(tmp_path, parts=parts)
    assert result["units"][0]["title"] == "Budget\rété"
    assert result["units"][0]["metadata"]["raw_sheet_name"] == sheet_name
    column = result["tables"][0]["columns"][1]
    assert column["label"] == "Amount\t_x0041_"
    assert column["attributes"]["name"] == label
    header = result["units"][0]["blocks"][1]["structure"]["table_contexts"][0]["headers"][1]
    assert header["label"] == column["label"]
    assert cells(result)["B8"]["number_format"] == "[hh]:mm:ss\r"
    assert cells(result)["B8"]["style"]["raw_number_format"] == "[hh]:mm:ss_x000D_"
    hyperlink = result["units"][0]["metadata"]["hyperlinks"][0]
    assert hyperlink["display"] == "Lien\tbudget" and hyperlink["tooltip"] == "Voir\rbudget"
    assert hyperlink["raw_attributes"]["display"] == "Lien_x0009_budget"
